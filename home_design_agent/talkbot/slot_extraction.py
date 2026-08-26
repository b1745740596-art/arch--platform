"""LLM-based slot extraction for profile fields that rule-based extraction missed.

This module provides a single public function ``extract_slots`` which calls the
configured LLM to extract structured field values from free-form user text.  It
is designed as a *complement* to the regex/keyword rules in ``empathy.py``, not
a replacement:

1. Rules extract what they can (fast, zero-cost, reliable).
2. This module fills in what rules missed (understanding free-form text).
3. Deterministic validation rejects hallucinated or out-of-range values.

If the LLM is disabled, misconfigured, or returns invalid output, the function
returns an empty dict so the caller can proceed without disruption.
"""

from __future__ import annotations

import json
import logging
import re

from .llm import load_deepseek_config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Field descriptions for the LLM prompt
# ---------------------------------------------------------------------------

FIELD_DESCRIPTIONS: dict[str, str] = {
    'city': '所在城市（如"上海""北京"）',
    'area': '建筑面积，数字，单位平方米（如89）',
    'household': '家庭居住结构（如"与父母同住，养猫""夫妻两人""三代同堂"）',
    'style': '装修风格偏好（如"现代简约""原木""奶油""新中式"）',
    'budget_max': '装修预算上限，整数，单位元（如十五万=150000，20万=200000）',
    'desired_timeline': '期望入住时间（如"年底前""三个月后入住"）',
    'pain_points': '最担心的问题，字符串列表（如["环保","增项"]）',
    'name': '客户称呼',
    'phone': '联系电话',
}

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_PHONE_RE = re.compile(r'^1[3-9]\d{9}$')
_ID_RE = re.compile(r'\d{6,}')


def _validate_slots(slots: dict, missing_fields: list[str]) -> dict:
    """Drop any field that fails deterministic validation.

    Only fields present in *missing_fields* are accepted; everything else is
    discarded to prevent the LLM from overwriting already-populated fields.
    """
    allowed = set(missing_fields)
    validated: dict = {}
    for field, value in slots.items():
        if field not in allowed:
            continue
        try:
            if field == 'city':
                if isinstance(value, str) and len(value) <= 50 and not _ID_RE.search(value):
                    validated[field] = value
            elif field == 'area':
                area = float(value)
                if 10 <= area <= 1000:
                    from decimal import Decimal
                    validated[field] = Decimal(str(area)).quantize(Decimal('0.01'))
            elif field == 'household':
                if isinstance(value, str) and len(value) <= 120 and not _PHONE_RE.search(value):
                    validated[field] = value
            elif field == 'style':
                if isinstance(value, str) and len(value) <= 50:
                    validated[field] = value
            elif field == 'budget_max':
                budget = int(value)
                if 10_000 <= budget <= 5_000_000:
                    validated[field] = budget
            elif field == 'budget_min':
                budget = int(value)
                if 10_000 <= budget <= 5_000_000:
                    # budget_min must be less than budget_max if both present
                    budget_max = slots.get('budget_max') or validated.get('budget_max')
                    if budget_max is None or budget < int(budget_max):
                        validated[field] = budget
            elif field == 'desired_timeline':
                if isinstance(value, str) and len(value) <= 80:
                    validated[field] = value
            elif field == 'pain_points':
                if (
                    isinstance(value, list)
                    and all(isinstance(item, str) and len(item) <= 30 for item in value)
                ):
                    validated[field] = value
            elif field == 'name':
                if isinstance(value, str) and len(value) <= 50:
                    if not any(word in value for word in ('业主', '用户', '客户')):
                        validated[field] = value
            elif field == 'phone':
                if isinstance(value, str) and _PHONE_RE.search(value):
                    validated[field] = _PHONE_RE.search(value).group()
        except (TypeError, ValueError, OverflowError):
            continue
    return validated


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_prompt(text: str, missing_fields: list[str], current_profile: dict) -> str:
    field_lines = []
    for field in missing_fields:
        desc = FIELD_DESCRIPTIONS.get(field, field)
        field_lines.append(f'- {field}: {desc}')
    field_descriptions = '\n'.join(field_lines)

    profile_parts = []
    for f, v in current_profile.items():
        if v not in (None, '', [], {}):
            profile_parts.append(f'{f}={v}')
    profile_summary = '；'.join(profile_parts) if profile_parts else '空'

    return (
        '你是信息抽取引擎。从用户消息中提取指定字段的值。'
        '只提取用户明确说出的信息，不猜测。\n'
        f'字段说明：\n{field_descriptions}\n'
        f'用户消息：{text}\n'
        f'已有画像：{profile_summary}\n'
        '输出JSON，只包含能确定的字段。示例：{"household": "与父母同住，养猫"}'
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_slots(
    text: str,
    missing_fields: list[str],
    current_profile: dict,
) -> dict:
    """Use the LLM to extract values for profile fields that rules missed.

    Returns a validated dict of {field: value} pairs.  Returns {} if the LLM
    is disabled, misconfigured, returns invalid output, or extracts nothing.
    """
    if not missing_fields or not text:
        return {}

    config = load_deepseek_config()
    if not config.enabled or not config.configured:
        return {}

    prompt = _build_prompt(text, missing_fields, current_profile)

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=config.api_key,
            base_url=config.api_base,
            timeout=config.timeout,
            max_retries=config.max_retries,
        )
        response = client.chat.completions.create(
            model=config.model,
            messages=[
                {'role': 'system', 'content': '输出合法JSON，不要输出其他内容。'},
                {'role': 'user', 'content': prompt},
            ],
            temperature=0.0,
            max_tokens=200,
            stream=False,
            response_format={'type': 'json_object'},
        )
        content = (response.choices[0].message.content or '').strip()
    except Exception as exc:  # noqa: BLE001
        logger.debug('Slot extraction LLM call failed: %s', exc)
        return {}

    if not content:
        return {}

    try:
        raw_slots = json.loads(content)
    except json.JSONDecodeError:
        logger.debug('Slot extraction returned invalid JSON: %.100s', content)
        return {}

    if not isinstance(raw_slots, dict):
        return {}

    return _validate_slots(raw_slots, missing_fields)
