"""Per-turn TalkBot workflow engine and conversion into the existing order domain."""

from __future__ import annotations

import hashlib
import logging
import re
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from datetime import timedelta
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone

from design.models import (
    HomeOrder,
    HomeReport,
    Lead,
    OrderDetail,
    Owner,
    Project,
)
from design.services import build_preview_schemes

from . import business_tools, empathy, llm, psychology, rag, slot_extraction, strategy
from .models import Conversation, CustomerProfile, Message, TalkStep, TalkWorkflow


logger = logging.getLogger(__name__)

RECOVERY_REPLY = (
    '您的消息已保存。刚才回复生成被中断，我已经恢复本次对话。'
    '请继续告诉我装修城市、面积、预算或风格中的任意一项，我会接着为您整理。'
)


BUILTIN_STEPS = (
    TalkStep.Kind.INTAKE,
    TalkStep.Kind.EMOTION,
    TalkStep.Kind.INTENT,
    TalkStep.Kind.PROFILE_UPDATE,
    TalkStep.Kind.STAGE_JUDGE,
    TalkStep.Kind.STRATEGY_PLAN,
    TalkStep.Kind.RAG_RETRIEVE,
    TalkStep.Kind.LLM_GENERATE,
    TalkStep.Kind.GUARD,
    TalkStep.Kind.OUTPUT,
    TalkStep.Kind.LOG,
)


QUESTION_COPY = {
    'city': '这套房在哪个城市？不同城市的施工与材料成本差异比较大。',
    'area': '房子的建筑面积大约是多少平方米？',
    'household': '以后主要有哪些家庭成员长期居住？',
    'style': '你目前更偏好哪种风格，比如现代简约、原木、奶油或新中式？',
    'budget_max': '你希望把整体装修预算控制在什么范围？给一个区间就可以。',
    'desired_timeline': '你希望大约什么时候完工或入住？',
    'pain_points': '这次装修你最担心什么：环保、增项、工期、施工质量，还是最后效果？',
    'name': '方便告诉我怎么称呼你吗？',
    'phone': '方便留一个联系电话吗？仅用于本次装修需求的方案与服务跟进。',
}


@dataclass
class TurnContext:
    conversation: Conversation
    profile: CustomerProfile
    text: str
    client_id: str = ''
    expected_field: str = ''
    analysis: dict | None = None
    updates: dict | None = None
    plan: dict | None = None
    knowledge: list[dict] | None = None
    reply: str = ''
    reply_source: str = 'rule'
    generation_status: str = 'not_run'
    generation_error: str = ''
    grounding_fallback: bool = False
    unsupported_facts: list[str] | None = None
    tool_results: list[dict] | None = None
    assistant_message: Message | None = None
    profile_update_completed: bool = False
    stage_update_completed: bool = False


def _initial_profile_values(user) -> dict:
    name = user.get_full_name().strip() or user.first_name or ''
    phone = ''
    try:
        name = user.profile.display_name or name
        phone = user.profile.phone or ''
    except Exception:  # noqa: BLE001 - profile is optional and created lazily elsewhere
        pass
    return {'name': name, 'phone': phone}


@transaction.atomic
def create_conversation(user) -> Conversation:
    conversation = Conversation.objects.create(user=user, title='我的装修顾问')
    profile = CustomerProfile.objects.create(
        conversation=conversation,
        **_initial_profile_values(user),
    )
    profile.missing_fields = strategy.missing_fields(profile)
    profile.save(update_fields=['missing_fields', 'updated_at'])
    Message.objects.create(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        content='你好，我是你的 AI 家装顾问。我会一次只问一个问题，帮你把需求、预算和落地风险理清楚。先告诉我，这套房在哪个城市？',
        question_asked='city',
        metadata={'action': 'ask', 'is_welcome': True},
    )
    return conversation


def _steps():
    workflow = TalkWorkflow.resolve()
    if workflow:
        return workflow, workflow.active_steps()
    return None, [
        SimpleNamespace(
            kind=kind,
            name='',
            params={},
            continue_on_error=True,
            get_kind_display=lambda value=kind: dict(TalkStep.Kind.choices).get(value, value),
        )
        for kind in BUILTIN_STEPS
    ]


def _merge_profile(profile: CustomerProfile, updates: dict, analysis: dict) -> None:
    """Apply one turn to an in-memory profile without persisting side effects."""
    effective_updates = dict(updates or {})
    try:
        bound_phone = profile.conversation.user.profile.phone or ''
    except Exception:  # noqa: BLE001 - legacy users may not have a profile yet
        bound_phone = ''
    if bound_phone:
        # Verified account binding is authoritative; chat text cannot replace it.
        effective_updates['phone'] = bound_phone
    for field, value in effective_updates.items():
        if field == 'recent_events':
            value = list(dict.fromkeys([*(profile.recent_events or []), *value]))
        setattr(profile, field, value)

    pains = list(dict.fromkeys([*(profile.pain_points or []), *(analysis.get('pain_points') or [])]))
    profile.pain_points = pains
    profile.emotion = analysis.get('emotion') or profile.emotion
    if analysis.get('persona_type'):
        profile.persona_type = analysis['persona_type']
    profile.trust_score = min(100, max(0, profile.trust_score + analysis.get('trust_delta', 0)))
    profile.intent_score = min(100, max(0, profile.intent_score + analysis.get('intent_delta', 0)))
    trace = list(profile.emotion_trace or [])[-29:]
    trace.append({'emotion': profile.emotion, 'intent': analysis.get('intent', 'chat')})
    profile.emotion_trace = trace
    profile.missing_fields = strategy.missing_fields(profile)


def _profile_summary(profile: CustomerProfile) -> str:
    facts = []
    for label, value in (
        ('城市', profile.city), ('面积', f'{profile.area}㎡' if profile.area else ''),
        ('风格', profile.style), ('预算', profile.budget_max), ('入住', profile.desired_timeline),
    ):
        if value:
            facts.append(f'{label}={value}')
    if profile.pain_points:
        facts.append('顾虑=' + '、'.join(profile.pain_points[:3]))
    return '；'.join(facts)


def _persist_recovery_reply(
    conversation_id: int,
    client_id: str,
    *,
    expected_lease_at=None,
    workflow_log: list[dict] | None = None,
    error_type: str = 'InterruptedTurn',
) -> Message | None:
    """Persist a minimal reply when normal finalization is interrupted.

    The fallback deliberately avoids mutating the customer profile or stage. This
    keeps retries safe even when the original transaction failed halfway through.
    """
    recovery_log = [*(workflow_log or []), {
        'order': 999,
        'kind': 'recovery',
        'name': '中断恢复',
        'status': 'recovered',
        'detail': error_type[:100],
        'elapsed_ms': 0,
    }]
    with transaction.atomic():
        conversation = Conversation.objects.select_for_update().get(pk=conversation_id)
        existing_reply = conversation.messages.filter(
            role=Message.Role.ASSISTANT,
            client_id=client_id,
        ).first()
        if existing_reply:
            if conversation.is_processing:
                conversation.is_processing = False
                conversation.processing_started_at = None
                conversation.save(update_fields=[
                    'is_processing', 'processing_started_at', 'updated_at',
                ])
            return existing_reply
        if (
            expected_lease_at is not None
            and conversation.processing_started_at != expected_lease_at
        ):
            return None
        user_message = conversation.messages.filter(
            role=Message.Role.USER,
            client_id=client_id,
        ).first()
        if user_message is None:
            return None
        reply = Message.objects.create(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            content=RECOVERY_REPLY,
            client_id=client_id,
            emotion=user_message.emotion,
            metadata={
                'reply_source': 'recovery',
                'generation_status': 'recovered',
                'generation_error': error_type[:100],
                'workflow_log': recovery_log,
            },
        )
        if not conversation.title:
            conversation.title = user_message.content[:40]
        conversation.workflow_log = recovery_log
        conversation.is_processing = False
        conversation.processing_started_at = None
        conversation.save(update_fields=[
            'title', 'workflow_log', 'is_processing', 'processing_started_at', 'updated_at',
        ])
        return reply


def _rule_reply(context: TurnContext) -> str:
    profile = context.profile
    plan = context.plan or {}
    prefix = empathy.empathy_prefix(
        profile.emotion,
        profile.pain_points or [],
        profile.recent_events or [],
    )
    if plan.get('action') == 'close':
        return f'{prefix} 你的关键信息已经齐了。确认后我可以立即生成三档预方案，并建立待确认项目订单；正式报价仍以现场量房为准。'
    if plan.get('action') == 'stop':
        return '好的，我会停止本次推进，也不会根据这次对话联系你。以后如果想继续，随时可以新建对话。'
    if plan.get('action') == 'empathize':
        evidence = (context.knowledge or [{}])[0].get('content', '')
        evidence = f' 可核对的信息是：{evidence}' if evidence else ''
        question = QUESTION_COPY.get(plan.get('question_field'), '你希望我先帮你核对哪一项风险？')
        return f'{prefix}{evidence} {question}'
    if plan.get('action') == 'ask':
        question = QUESTION_COPY.get(plan.get('question_field'), '接下来你最希望先解决哪个问题？')
        return f'{prefix} {question}'

    budget = f'，预算上限约 ¥{profile.budget_max:,}' if profile.budget_max else ''
    style = profile.style or '待确认风格'
    return (
        f'{prefix} 目前更适合先做一版“{style}”方向的空间规划{budget}，'
        '同时把环保、增项与工期写进核对清单。信息已基本完整，你可以让我生成方案订单。'
    )


def guard_reply(reply: str) -> str:
    """Remove unsafe absolutes and keep a hard output limit."""
    text = (reply or '').strip()
    replacements = {
        '一定无甲醛': '优先选用符合标准的材料，并在入住前检测',
        '绝对环保': '按可核验的环保等级选材',
        '保证零增项': '在合同中明确增项规则与审批方式',
        '保证按时完工': '通过节点计划和违约条款管理工期',
        '今天不下单就': '你可以按自己的节奏比较后再决定',
    }
    for unsafe, safe in replacements.items():
        text = text.replace(unsafe, safe)
    text = re.sub(
        r'(?:(?:100%|百分之百|绝对|完全|保证|确保)\s*)?(?:零|无)甲醛',
        '环保结果需以材料标准和入住前检测为准',
        text,
    )
    text = re.sub(
        r'(?:(?:保证|绝对|肯定|承诺)\s*)?(?:零增项|无增项|不会增项|绝不会增项)',
        '增项需通过合同规则和书面审批控制',
        text,
    )
    text = re.sub(
        r'(?:保证|确保|肯定|一定|绝对)\s*(?:按时|准时|如期)完工',
        '工期需按现场条件、节点计划和合同约定管理',
        text,
    )
    text = re.sub(
        r'(?:为了孩子[^，。,.]{0,12})?(?:必须|一定要)\s*(?:今天|马上|立即)\s*下单',
        '你可以在核对清楚后按自己的节奏决定',
        text,
    )
    return text[:700]


ARABIC_NUMBER = r'\d[\d,]*(?:\.\d+)?'
CHINESE_NUMBER = r'[零〇一二两三四五六七八九十百千万亿]+'
FACT_NUMBER = rf'(?:{ARABIC_NUMBER}|{CHINESE_NUMBER})'
RANGE_SEPARATOR = r'(?:到|至|[-~～—–])'
MONEY_UNIT = r'(?:万元|千元|元|万)'
DURATION_UNIT = r'(?:个?工作日|天|日|周|星期|个月|月|年)'
AREA_UNIT = r'(?:平方米|平米|㎡)'
RATIO_UNIT = r'(?:%|％|分|星)'
MONEY_RANGE_RE = re.compile(
    rf'(?P<first>{FACT_NUMBER})\s*{RANGE_SEPARATOR}\s*'
    rf'(?P<second>{FACT_NUMBER})\s*(?P<unit>{MONEY_UNIT})',
    re.IGNORECASE,
)
MONEY_RE = re.compile(
    rf'(?:[¥￥]\s*{FACT_NUMBER}(?:\s*元)?|{FACT_NUMBER}\s*{MONEY_UNIT})',
    re.IGNORECASE,
)
DURATION_RANGE_RE = re.compile(
    rf'(?P<first>{FACT_NUMBER})\s*{RANGE_SEPARATOR}\s*'
    rf'(?P<second>{FACT_NUMBER})\s*(?P<unit>{DURATION_UNIT})',
    re.IGNORECASE,
)
DURATION_RE = re.compile(rf'{FACT_NUMBER}\s*{DURATION_UNIT}', re.IGNORECASE)
AREA_RANGE_RE = re.compile(
    rf'(?P<first>{FACT_NUMBER})\s*{RANGE_SEPARATOR}\s*'
    rf'(?P<second>{FACT_NUMBER})\s*(?P<unit>{AREA_UNIT})',
    re.IGNORECASE,
)
RATIO_RANGE_RE = re.compile(
    rf'(?P<first>{FACT_NUMBER})\s*{RANGE_SEPARATOR}\s*'
    rf'(?P<second>{FACT_NUMBER})\s*(?P<unit>{RATIO_UNIT})',
    re.IGNORECASE,
)
GRADE_RE = re.compile(
    r'(?<![A-Za-z0-9])(?:E[0-2]|EN\s*\d+(?:\.\d+)?|GB(?:/T)?\s*\d+(?:\.\d+)?)(?:级)?(?![A-Za-z0-9])',
    re.IGNORECASE,
)
PERCENT_RE = re.compile(rf'{FACT_NUMBER}\s*{RATIO_UNIT}')
AREA_RE = re.compile(rf'{FACT_NUMBER}\s*{AREA_UNIT}')
PROMPT_LEAK_RE = re.compile(
    r'(?:system\s*prompt|developer\s*(?:message|instruction)|系统提示词|系统指令|开发者指令|'
    r'<\|(?:system|developer|assistant)\|>|BEGIN\s+(?:SYSTEM|PROMPT)|'
    r'你是\s*Arch\s*AI\s*的家装顾问\s*TalkBot|你的目标是帮助用户理清装修需求|'
    r'(?:当前阶段|客户画像|本轮策略|可引用资料)\s*[：:])',
    re.IGNORECASE,
)


CHINESE_DIGITS = {
    '零': 0, '〇': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
}
CHINESE_SMALL_UNITS = {'十': 10, '百': 100, '千': 1000}
CHINESE_LARGE_UNITS = {'万': 10000, '亿': 100000000}


def _parse_fact_number(raw: str) -> Decimal | None:
    compact = re.sub(r'[\s,]', '', raw)
    try:
        return Decimal(compact)
    except InvalidOperation:
        pass
    if not compact or any(
        char not in CHINESE_DIGITS | CHINESE_SMALL_UNITS | CHINESE_LARGE_UNITS
        for char in compact
    ):
        return None
    if all(char in CHINESE_DIGITS for char in compact):
        return Decimal(''.join(str(CHINESE_DIGITS[char]) for char in compact))
    total = 0
    section = 0
    number = 0
    for char in compact:
        if char in CHINESE_DIGITS:
            number = CHINESE_DIGITS[char]
        elif char in CHINESE_SMALL_UNITS:
            section += (number or 1) * CHINESE_SMALL_UNITS[char]
            number = 0
        else:
            total += (section + number) * CHINESE_LARGE_UNITS[char]
            section = 0
            number = 0
    return Decimal(total + section + number)


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), 'f')


def _canonical_money(raw: str) -> str:
    compact = re.sub(r'[\s,¥￥]', '', raw.lower())
    multiplier = Decimal(1)
    if compact.endswith('万元'):
        compact = compact[:-2]
        multiplier = Decimal(10000)
    elif compact.endswith('千元'):
        compact = compact[:-2]
        multiplier = Decimal(1000)
    elif compact.endswith('万'):
        compact = compact[:-1]
        multiplier = Decimal(10000)
    elif compact.endswith('元'):
        compact = compact[:-1]
    number = _parse_fact_number(compact)
    if number is None:
        return f'money:{raw}'
    return f'money:{_decimal_text(number * multiplier)}'


def _canonical_duration(raw: str) -> str:
    compact = re.sub(r'\s+', '', raw)
    units = ('个工作日', '工作日', '星期', '个月', '天', '日', '周', '月', '年')
    unit = next((candidate for candidate in units if compact.endswith(candidate)), '')
    number = _parse_fact_number(compact[:-len(unit)] if unit else compact)
    normalized_unit = {
        '个工作日': '工作日', '日': '天', '星期': '周', '个月': '月',
    }.get(unit, unit)
    if number is None or not normalized_unit:
        return f'duration:{compact}'
    return f'duration:{_decimal_text(number)}:{normalized_unit}'


def _canonical_area(raw: str) -> str:
    compact = re.sub(r'\s+', '', raw)
    unit = next((item for item in ('平方米', '平米', '㎡') if compact.endswith(item)), '')
    number = _parse_fact_number(compact[:-len(unit)] if unit else compact)
    return f'area:{_decimal_text(number)}:㎡' if number is not None else f'area:{compact}'


def _canonical_ratio(raw: str) -> str:
    compact = re.sub(r'\s+', '', raw).replace('％', '%')
    unit = next((item for item in ('%', '分', '星') if compact.endswith(item)), '')
    number = _parse_fact_number(compact[:-len(unit)] if unit else compact)
    return f'ratio:{_decimal_text(number)}:{unit}' if number is not None else f'ratio:{compact}'


def _numeric_facts(text: str) -> dict[str, str]:
    """Return canonical fact -> original token for facts that need grounding."""
    text = text or ''
    facts: dict[str, str] = {}
    for match in MONEY_RANGE_RE.finditer(text):
        for group in ('first', 'second'):
            raw = f'{match.group(group)}{match.group("unit")}'
            facts[_canonical_money(raw)] = raw
    for match in MONEY_RE.finditer(text):
        facts[_canonical_money(match.group())] = match.group()
    for match in DURATION_RANGE_RE.finditer(text):
        for group in ('first', 'second'):
            raw = f'{match.group(group)}{match.group("unit")}'
            facts[_canonical_duration(raw)] = raw
    for match in DURATION_RE.finditer(text):
        facts[_canonical_duration(match.group())] = match.group()
    for match in GRADE_RE.finditer(text):
        canonical = re.sub(r'\s+', '', match.group()).upper()
        facts[f'grade:{canonical}'] = match.group()
    for match in RATIO_RANGE_RE.finditer(text):
        for group in ('first', 'second'):
            raw = f'{match.group(group)}{match.group("unit")}'
            facts[_canonical_ratio(raw)] = raw
    for match in PERCENT_RE.finditer(text):
        facts[_canonical_ratio(match.group())] = match.group()
    for match in AREA_RANGE_RE.finditer(text):
        for group in ('first', 'second'):
            raw = f'{match.group(group)}{match.group("unit")}'
            facts[_canonical_area(raw)] = raw
    for match in AREA_RE.finditer(text):
        facts[_canonical_area(match.group())] = match.group()
    return facts


def _grounding_evidence(context: TurnContext) -> str:
    knowledge = '\n'.join(
        ' '.join(str(item.get(key, '')) for key in ('source', 'title', 'content'))
        for item in (context.knowledge or [])
    )
    profile = context.profile
    trusted = [
        str(profile.area or ''),
        f'{profile.area}㎡' if profile.area else '',
        profile.desired_timeline or '',
    ]
    for value in (profile.budget_min, profile.budget_max):
        if value:
            trusted.extend((f'¥{value}', f'{value}元', f'{value / 10000:g}万'))
    return f'{knowledge}\n{" ".join(trusted)}'


def _safe_reply(context: TurnContext) -> str:
    candidate = guard_reply(context.reply or _rule_reply(context))
    if context.reply_source != 'llm':
        return candidate

    evidence_facts = set(_numeric_facts(_grounding_evidence(context)))
    response_facts = _numeric_facts(candidate)
    unsupported = [raw for key, raw in response_facts.items() if key not in evidence_facts]
    prompt_leak = bool(PROMPT_LEAK_RE.search(candidate))
    if unsupported or prompt_leak:
        context.grounding_fallback = True
        context.unsupported_facts = unsupported
        context.generation_status = 'guard_fallback'
        return guard_reply(_rule_reply(context))
    return candidate


def _profile_fields_dict(profile: CustomerProfile) -> dict:
    """Snapshot of the structured fields consumed by the slot extractor."""
    return {
        'city': profile.city,
        'area': profile.area,
        'household': profile.household,
        'style': profile.style,
        'budget_max': profile.budget_max,
        'desired_timeline': profile.desired_timeline,
        'pain_points': profile.pain_points,
        'name': profile.name,
        'phone': profile.phone,
    }


def _augment_updates_with_slots(profile: CustomerProfile, updates: dict, text: str) -> dict:
    """Fill profile fields that rule extraction missed via one LLM slot pass.

    Rules stay the fast, deterministic first pass; the LLM only interprets the
    remaining free-form fields and never overwrites already-populated values.
    """
    merged = dict(updates or {})
    filled_by_rules = {
        field for field, value in merged.items()
        if value not in (None, '', [], {})
    }
    remaining = [
        field for field in strategy.missing_fields(profile)
        if field not in filled_by_rules
    ]
    if not remaining or not (text or '').strip():
        return merged
    slots = slot_extraction.extract_slots(text, remaining, _profile_fields_dict(profile))
    if slots:
        merged.update(slots)
    return merged


def _run_step(step, context: TurnContext) -> str:
    kind = step.kind
    if kind == TalkStep.Kind.INTAKE:
        return f'接收 {len(context.text)} 字'
    if kind == TalkStep.Kind.EMOTION:
        context.analysis = psychology.analyze(context.text, context.profile.emotion)
        return f'情绪={context.analysis["emotion"]}'
    if kind == TalkStep.Kind.INTENT:
        context.analysis = context.analysis or psychology.analyze(context.text, context.profile.emotion)
        return f'意图={context.analysis["intent"]}'
    if kind == TalkStep.Kind.PROFILE_UPDATE:
        context.analysis = context.analysis or psychology.analyze(context.text, context.profile.emotion)
        context.updates = empathy.extract_profile_updates(
            context.text,
            expected_field=context.expected_field,
        )
        context.updates = _augment_updates_with_slots(
            context.profile, context.updates, context.text,
        )
        _merge_profile(context.profile, context.updates, context.analysis)
        context.profile_update_completed = True
        return '更新=' + ('、'.join(context.updates) if context.updates else '无显式事实')
    if kind == TalkStep.Kind.STAGE_JUDGE:
        context.analysis = context.analysis or psychology.analyze(context.text, context.profile.emotion)
        context.conversation.stage = strategy.judge_stage(
            context.conversation, context.profile, context.analysis['intent'],
        )
        if context.analysis['intent'] == 'opt_out':
            context.conversation.status = Conversation.Status.CLOSED
        context.stage_update_completed = True
        return f'阶段={context.conversation.stage}'
    if kind == TalkStep.Kind.STRATEGY_PLAN:
        context.analysis = context.analysis or psychology.analyze(context.text, context.profile.emotion)
        context.plan = strategy.plan(context.conversation, context.profile, context.analysis['intent'])
        return f'动作={context.plan["action"]}，下一问={context.plan["question_field"] or "无"}'
    if kind == TalkStep.Kind.RAG_RETRIEVE:
        context.plan = context.plan or strategy.plan(
            context.conversation, context.profile, (context.analysis or {}).get('intent', 'chat'),
        )
        context.knowledge = rag.retrieve(
            f'{context.text} {context.plan.get("rag_query", "")}',
            context.profile,
            limit=int((step.params or {}).get('limit', 3)),
        )
        return f'召回={len(context.knowledge)}条'
    if kind == TalkStep.Kind.LLM_GENERATE:
        context.plan = context.plan or strategy.plan(
            context.conversation, context.profile, (context.analysis or {}).get('intent', 'chat'),
        )
        generation = llm.generate_reply(
            context.conversation, context.profile, context.plan, context.knowledge or [],
        )
        if isinstance(generation, str):
            # Compatibility with test doubles and older custom adapters.
            context.reply = generation
            context.reply_source = 'llm'
            context.generation_status = 'success'
        elif generation.content:
            context.reply = generation.content
            context.reply_source = 'llm'
            context.generation_status = generation.status
            context.generation_error = generation.error
        else:
            context.reply = _rule_reply(context)
            context.reply_source = 'rule'
            context.generation_status = generation.status
            context.generation_error = generation.error
        return f'{context.reply_source}回复（{context.generation_status}）'
    if kind == TalkStep.Kind.GUARD:
        context.reply = _safe_reply(context)
        return '合规过滤完成' + ('，已降级' if context.grounding_fallback else '')
    if kind == TalkStep.Kind.OUTPUT:
        # Safety is a hard boundary, not an optional workflow concern. Even if an
        # administrator disables or reorders the GUARD step, output is filtered.
        context.reply = _safe_reply(context)
        return '回复已准备，等待原子保存'
    if kind == TalkStep.Kind.LOG:
        return '轨迹已记录'
    return '未知步骤已跳过'


def process_message(conversation: Conversation, text: str, *, client_id: str = '') -> Message:
    text = (text or '').strip()
    if not text:
        raise ValueError('消息不能为空。')
    if len(text) > 1000:
        raise ValueError('单条消息不能超过 1000 个字符。')
    client_id = client_id or uuid.uuid4().hex
    content_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
    lease_started_at = None

    with transaction.atomic():
        conversation = Conversation.objects.select_for_update().select_related('user').get(pk=conversation.pk)
        existing_user_message = conversation.messages.filter(
            role=Message.Role.USER,
            client_id=client_id,
        ).first()
        existing_reply = conversation.messages.filter(
            role=Message.Role.ASSISTANT,
            client_id=client_id,
        ).first()
        if existing_reply:
            if (
                existing_user_message is None
                or existing_user_message.metadata.get('content_hash') != content_hash
            ):
                raise ValueError('同一客户端消息标识不能用于不同内容。')
            return existing_reply
        if conversation.status != Conversation.Status.ACTIVE:
            raise ValueError('当前会话已结束，请新建会话。')
        processing_is_fresh = (
            conversation.is_processing
            and conversation.processing_started_at
            and conversation.processing_started_at > timezone.now() - timedelta(minutes=5)
        )
        if processing_is_fresh:
            raise ValueError('上一条消息仍在处理中，请稍候。')
        conversation.is_processing = True
        lease_started_at = timezone.now()
        conversation.processing_started_at = lease_started_at
        conversation.save(update_fields=['is_processing', 'processing_started_at', 'updated_at'])

        profile, _ = CustomerProfile.objects.select_for_update().get_or_create(
            conversation=conversation,
            defaults=_initial_profile_values(conversation.user),
        )
        expected_field = (
            conversation.messages.filter(role=Message.Role.ASSISTANT)
            .order_by('-id')
            .values_list('question_asked', flat=True)
            .first()
            or ''
        )
        user_message = existing_user_message
        if user_message:
            if user_message.metadata.get('content_hash') != content_hash:
                raise ValueError('同一客户端消息标识不能用于不同内容。')
        else:
            user_message = Message.objects.create(
                conversation=conversation,
                role=Message.Role.USER,
                content=llm.redact_sensitive_text(text),
                client_id=client_id,
                metadata={'content_hash': content_hash},
            )
        if conversation.messages.filter(role=Message.Role.USER).count() == 1:
            conversation.title = llm.redact_sensitive_text(text)[:40]

    context = TurnContext(
        conversation=conversation,
        profile=profile,
        text=text,
        client_id=client_id,
        expected_field=expected_field,
    )
    logs = []
    try:
        # Workflow resolution is also covered by the lease cleanup below.
        workflow, steps = _steps()
        # Deliberately run the external LLM call outside a database transaction. The
        # processing lease above serializes turns without holding row locks for seconds.
        for index, step in enumerate(steps, start=1):
            started = time.monotonic()
            status = 'ok'
            detail = ''
            try:
                detail = _run_step(step, context)
            except Exception as exc:  # noqa: BLE001 - configured steps have per-step fallbacks
                status = 'failed'
                detail = str(exc)[:200]
                if (workflow and workflow.stop_on_error) or not step.continue_on_error:
                    logs.append({
                        'order': getattr(step, 'order', index * 10), 'kind': step.kind,
                        'name': step.name or step.get_kind_display(), 'status': status,
                        'detail': detail, 'elapsed_ms': int((time.monotonic() - started) * 1000),
                    })
                    break
            logs.append({
                'order': getattr(step, 'order', index * 10),
                'kind': step.kind,
                'name': step.name or step.get_kind_display(),
                'status': status,
                'detail': detail,
                'elapsed_ms': int((time.monotonic() - started) * 1000),
            })

        tool_started = time.monotonic()
        tool_status = 'ok'
        tool_detail = '未触发业务工具'
        try:
            if (context.analysis or {}).get('intent') != 'opt_out':
                context.tool_results = business_tools.collect_tool_results(
                    context.conversation,
                    context.profile,
                    context.text,
                )
            else:
                context.tool_results = []
            if context.tool_results:
                tool_detail = '调用=' + '、'.join(
                    item.get('kind', '') for item in context.tool_results
                )
        except Exception as exc:  # noqa: BLE001 - catalog failure must not break chat
            context.tool_results = []
            tool_status = 'failed'
            tool_detail = type(exc).__name__
        logs.append({
            'order': 850,
            'kind': 'business_tools',
            'name': '业务工具调用',
            'status': tool_status,
            'detail': tool_detail[:200],
            'elapsed_ms': int((time.monotonic() - tool_started) * 1000),
        })

        with transaction.atomic():
            conversation = Conversation.objects.select_for_update().get(pk=conversation.pk)
            existing_reply = conversation.messages.filter(
                role=Message.Role.ASSISTANT,
                client_id=client_id,
            ).first()
            if existing_reply:
                return existing_reply
            if conversation.processing_started_at != lease_started_at:
                raise ValueError('本轮处理租约已失效，请使用相同消息标识重试。')

            # PostgreSQL rejects SELECT FOR UPDATE when the query also locks the
            # nullable side of an outer join. The reverse user.profile relation is
            # optional, so load it lazily instead of joining it into the lock query.
            profile = CustomerProfile.objects.select_for_update().get(
                conversation=conversation,
            )
            if context.profile_update_completed:
                _merge_profile(profile, context.updates or {}, context.analysis or {})
                profile.save()
            context.profile = profile
            context.reply = _safe_reply(context)
            tool_intro = business_tools.tool_result_intro(context.tool_results or [])
            if tool_intro:
                context.reply = guard_reply(f'{tool_intro} {context.reply}')
            context.assistant_message = Message.objects.create(
                conversation=conversation,
                role=Message.Role.ASSISTANT,
                content=context.reply,
                client_id=client_id,
                intent=(context.analysis or {}).get('intent', ''),
                emotion=profile.emotion,
                question_asked=(context.plan or {}).get('question_field', ''),
                metadata={
                    'action': (context.plan or {}).get('action', ''),
                    'knowledge_sources': [
                        item.get('title') for item in (context.knowledge or [])
                    ],
                    'reply_source': context.reply_source,
                    'generation_status': context.generation_status,
                    'generation_error': context.generation_error,
                    'grounding_fallback': context.grounding_fallback,
                    'unsupported_facts': context.unsupported_facts or [],
                    'tool_results': context.tool_results or [],
                    'workflow_log': logs,
                },
            )

            user_message.intent = (context.analysis or {}).get('intent', '')
            user_message.emotion = profile.emotion
            user_message.metadata = {
                **(user_message.metadata or {}),
                'expected_field': context.expected_field,
                'profile_updates': list((context.updates or {}).keys()),
            }
            user_message.save(update_fields=['intent', 'emotion', 'metadata', 'updated_at'])
            conversation.title = context.conversation.title
            if context.stage_update_completed:
                conversation.stage = context.conversation.stage
                conversation.status = context.conversation.status
            conversation.last_action = (context.plan or {}).get('action', '')
            conversation.summary = _profile_summary(profile)
            conversation.workflow_log = logs
            conversation.is_processing = False
            conversation.processing_started_at = None
            conversation.save(update_fields=[
                'title', 'stage', 'status', 'last_action', 'summary', 'workflow_log',
                'is_processing', 'processing_started_at', 'updated_at',
            ])
        return context.assistant_message
    except Exception as exc:  # noqa: BLE001 - a saved user turn must receive a reply
        logger.exception(
            'TalkBot turn finalization failed: conversation_id=%s client_id=%s error=%s',
            conversation.pk,
            client_id,
            type(exc).__name__,
        )
        try:
            recovery_reply = _persist_recovery_reply(
                conversation.pk,
                client_id,
                expected_lease_at=lease_started_at,
                workflow_log=logs,
                error_type=type(exc).__name__,
            )
        except Exception as recovery_exc:  # noqa: BLE001 - preserve the original failure
            logger.exception(
                'TalkBot recovery reply failed: conversation_id=%s client_id=%s error=%s',
                conversation.pk,
                client_id,
                type(recovery_exc).__name__,
            )
            raise exc from recovery_exc
        if recovery_reply is not None:
            return recovery_reply
        raise
    finally:
        # Compare the lease timestamp so this cleanup can never clear a newer turn.
        if lease_started_at is not None:
            Conversation.objects.filter(
                pk=conversation.pk,
                is_processing=True,
                processing_started_at=lease_started_at,
            ).update(is_processing=False, processing_started_at=None)


@transaction.atomic
def convert_conversation(conversation: Conversation, *, consent: bool = False) -> HomeOrder:
    """Create a project, preview schemes, report, lead, and order exactly once."""
    conversation = Conversation.objects.select_for_update().select_related('user').get(pk=conversation.pk)
    if conversation.order_id:
        return HomeOrder.objects.get(pk=conversation.order_id)
    if conversation.status != Conversation.Status.ACTIVE:
        raise ValueError('当前会话已结束，请新建会话后再生成订单。')
    if conversation.is_processing:
        raise ValueError('机器人仍在整理上一条消息，请稍候再生成订单。')
    profile = CustomerProfile.objects.select_for_update().get(conversation=conversation)
    # Conversion is a fresh representational action. Require explicit consent on
    # this request; never rely on a possibly stale or misclassified chat message.
    if not consent:
        raise ValueError('请先确认同意平台根据本次需求联系你。')
    profile.consent_to_contact = True
    profile.save(update_fields=['consent_to_contact', 'updated_at'])
    missing = strategy.conversion_missing(profile)
    if missing:
        labels = [strategy.FIELD_LABELS.get(field, field) for field in missing]
        raise ValueError('创建订单前还需要：' + '、'.join(labels))
    owner = (
        Owner.objects.select_for_update()
        .filter(phone=profile.phone, projects__user=conversation.user)
        .order_by('id')
        .first()
    )
    owner_values = {
        'name': profile.name,
        'city': profile.city,
        'community': profile.community,
        'preference_tags': list(dict.fromkeys([
            value for value in (profile.room_type, profile.style, *profile.pain_points) if value
        ])),
    }
    if owner:
        for field, value in owner_values.items():
            setattr(owner, field, value)
        owner.save(update_fields=[*owner_values.keys(), 'updated_at'])
    else:
        owner = Owner.objects.create(phone=profile.phone, **owner_values)
    budget_min = profile.budget_min or int(profile.budget_max * 0.7)
    project = Project.objects.create(
        owner=owner,
        user=conversation.user,
        title=f'{profile.city}·{profile.style}装修方案',
        city=profile.city,
        community=profile.community,
        area=profile.area,
        budget_min=budget_min,
        budget_max=profile.budget_max,
        requirement_summary={
            'source': 'talkbot',
            'room_type': profile.room_type,
            'style': profile.style,
            'household': profile.household,
            'timeline': profile.desired_timeline,
            'pain_points': profile.pain_points,
            'conversation_summary': conversation.summary,
        },
        status=Project.Status.SCHEME,
    )
    schemes = build_preview_schemes(project)
    scheme_payload = [
        {
            'id': item.id,
            'name': item.name,
            'style': item.style,
            'budget_tier': item.budget_tier,
            'budget_min': item.budget_min,
            'budget_max': item.budget_max,
            'highlights': item.highlights,
            'risks': item.risks,
        }
        for item in schemes
    ]
    report_payload = {
        'source': 'talkbot',
        'profile': {
            'city': profile.city,
            'community': profile.community,
            'area': str(profile.area),
            'room_type': profile.room_type,
            'style': profile.style,
            'household': profile.household,
            'timeline': profile.desired_timeline,
            'pain_points': profile.pain_points,
        },
        'conversation_summary': conversation.summary,
        'schemes': scheme_payload,
        'budget_min': budget_min,
        'budget_max': profile.budget_max,
        'renovation_advice': '预方案用于确定方向；正式合同金额、材料、工期和环保指标需在量房及可施工校验后确认。',
    }
    report = HomeReport.objects.create(
        user=conversation.user,
        project=project,
        title=project.title,
        room_type=profile.room_type,
        style=profile.style,
        budget_tier='quality',
        report=report_payload,
        status=HomeReport.Status.ORDERED,
    )
    order = HomeOrder.objects.create(
        user=conversation.user,
        project=project,
        report=report,
        title=project.title,
        customer_name=profile.name,
        customer_phone=profile.phone,
        remark=f'TalkBot 转化；期望入住：{profile.desired_timeline}',
        amount_min=budget_min,
        amount_max=profile.budget_max,
        payload=report_payload,
    )
    OrderDetail.sync_from_order(order)
    Lead.objects.create(
        project=project,
        scheme=schemes[1] if len(schemes) > 1 else schemes[0],
        contact_name=profile.name,
        contact_phone=profile.phone,
        city=profile.city,
        community=profile.community,
        remark='TalkBot 高意向用户主动确认生成项目订单。',
    )
    project.status = Project.Status.SIGNED
    project.save(update_fields=['status', 'updated_at'])
    conversation.project = project
    conversation.order = order
    conversation.stage = Conversation.Stage.ORDERED
    conversation.status = Conversation.Status.CONVERTED
    conversation.last_action = 'close'
    conversation.save(update_fields=[
        'project', 'order', 'stage', 'status', 'last_action', 'updated_at',
    ])
    Message.objects.create(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        content=f'项目订单 {order.order_no} 已创建。我也为你准备了三档预方案，接下来可在“项目订单”中查看；正式报价以量房确认结果为准。',
        intent='converted',
        emotion=profile.emotion,
        metadata={
            'order_id': order.id,
            'project_id': project.id,
            'tool_results': [business_tools.completed_order_card(order)],
        },
    )
    return order
