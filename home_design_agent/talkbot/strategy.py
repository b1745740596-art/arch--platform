"""Sales-stage and next-best-action planning with explicit ethical constraints."""

from __future__ import annotations

from .models import Conversation


QUESTION_FIELDS = (
    'city', 'area', 'household', 'style', 'budget_max', 'desired_timeline', 'pain_points', 'name', 'phone',
)

FIELD_LABELS = {
    'city': '房屋所在城市',
    'area': '建筑面积',
    'household': '常住家庭成员',
    'style': '偏好的装修风格',
    'budget_max': '可接受的总预算范围',
    'desired_timeline': '希望完工或入住的时间',
    'pain_points': '最担心的问题',
    'name': '称呼',
    'phone': '联系电话',
    'verified_phone': '账号已验证手机号',
}


def missing_fields(profile) -> list[str]:
    missing = []
    for field in QUESTION_FIELDS:
        if field == 'pain_points':
            value = profile.pain_points
        else:
            value = getattr(profile, field, None)
        if value in (None, '', [], {}):
            missing.append(field)
    return missing


def conversion_missing(profile) -> list[str]:
    """Information needed to create an actionable project order."""
    required = ('city', 'area', 'style', 'budget_max', 'desired_timeline', 'name', 'phone')
    missing = [field for field in required if getattr(profile, field, None) in (None, '')]
    if profile.phone:
        try:
            bound_phone = profile.conversation.user.profile.phone or ''
        except Exception:  # noqa: BLE001 - legacy users may not have a profile yet
            bound_phone = ''
        if not bound_phone or bound_phone != profile.phone:
            missing.append('verified_phone')
    return missing


def judge_stage(conversation, profile, intent: str) -> str:
    if conversation.status == Conversation.Status.CONVERTED:
        return Conversation.Stage.ORDERED
    if intent == 'opt_out':
        return Conversation.Stage.FOLLOW_UP
    if intent == 'objection':
        return Conversation.Stage.OBJECTION
    missing = missing_fields(profile)
    if len(missing) >= 5:
        return Conversation.Stage.DISCOVERY
    if profile.intent_score >= 65 and len(conversion_missing(profile)) <= 2:
        return Conversation.Stage.CLOSING
    if len(missing) <= 4:
        return Conversation.Stage.MATCHING
    return Conversation.Stage.DISCOVERY


def plan(conversation, profile, intent: str) -> dict:
    missing = missing_fields(profile)
    question_field = missing[0] if missing else ''
    if intent == 'opt_out':
        action = 'stop'
        strategy = '尊重拒绝并停止推进'
        question_field = ''
    elif intent == 'objection':
        action = 'empathize'
        strategy = '先确认顾虑，再给可核验依据'
    elif intent == 'close' and not conversion_missing(profile):
        action = 'close'
        strategy = '确认用户授权并创建方案订单'
        question_field = ''
    elif question_field:
        action = 'ask'
        strategy = '先接住用户表达，再一次只补一个画像字段'
    else:
        action = 'value'
        strategy = '根据完整画像给出具体方案建议'

    pain = (profile.pain_points or ['装修方案'])[0]
    return {
        'action': action,
        'question_field': question_field,
        'question_label': FIELD_LABELS.get(question_field, ''),
        'rag_query': f'{pain} {intent} {conversation.stage}',
        'strategy': strategy,
        'reason': f'阶段={conversation.stage}，意向={profile.intent_score}，待补={len(missing)}',
    }
