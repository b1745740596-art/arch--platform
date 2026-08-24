"""Conservative emotion, intent, and concern classification for TalkBot."""

from __future__ import annotations

import re


PAIN_KEYWORDS = {
    '环保健康': ('甲醛', '环保', '孩子', '孕妇', '气味', '健康'),
    '预算失控': ('超预算', '增项', '预算', '太贵', '价格', '费用'),
    '工期拖延': ('工期', '拖延', '延期', '入住', '赶时间'),
    '施工质量': ('偷工减料', '质量', '返工', '施工', '验收'),
    '审美选择': ('装丑', '风格', '审美', '搭配', '选择困难'),
    '信任风险': ('被骗', '不靠谱', '不信', '怕坑', '套路'),
}

OPT_OUT_PATTERNS = (
    r'(?:不要|别|不可以|不能|不同意|不愿意|不想|拒绝)\s*(?:再)?(?:联系|留电话|回访|推销)',
    r'(?:不想|不要|不准备|暂时不|先不|不|取消)\s*(?:下单|预约|量房)',
    r'(?:^|[，。,.！!\s])停止(?:咨询|对话|聊天|联系|推销)?(?:[，。,.！!\s]|$)',
    r'不聊了',
)


def is_opt_out(text: str) -> bool:
    return any(re.search(pattern, text or '') for pattern in OPT_OUT_PATTERNS)


def analyze(text: str, previous_emotion: str = 'neutral') -> dict:
    normalized = (text or '').strip()
    emotion = 'neutral'
    if any(word in normalized for word in ('焦虑', '着急', '担心', '害怕', '头疼', '很累')):
        emotion = 'anxious'
    elif any(word in normalized for word in ('犹豫', '纠结', '再想想', '不确定', '考虑一下')):
        emotion = 'hesitant'
    elif any(word in normalized for word in ('不信', '套路', '骗', '忽悠', '不靠谱')):
        emotion = 'distrustful'
    elif any(word in normalized for word in ('别问', '不用推销', '不要联系', '不需要')):
        emotion = 'defensive'
    elif any(word in normalized for word in ('期待', '喜欢', '不错', '满意', '可以')):
        emotion = 'expectant' if '期待' in normalized else 'satisfied'
    elif previous_emotion and previous_emotion != 'neutral':
        emotion = previous_emotion

    pains = [label for label, words in PAIN_KEYWORDS.items() if any(word in normalized for word in words)]

    intent = 'chat'
    intent_delta = 0
    trust_delta = 1
    if is_opt_out(normalized):
        intent = 'opt_out'
        intent_delta = -20
        trust_delta = -8
    elif any(word in normalized for word in ('下单', '预约', '量房', '联系我', '怎么开始', '就这个')):
        intent = 'close'
        intent_delta = 25
        trust_delta = 8
    elif any(word in normalized for word in ('多少钱', '报价', '价格', '预算', '套餐')):
        intent = 'price'
        intent_delta = 8
    elif any(word in normalized for word in ('但是', '太贵', '担心', '怕', '不靠谱', '再想想')):
        intent = 'objection'
        intent_delta = 2
        trust_delta = -2 if emotion in ('distrustful', 'defensive') else 1
    elif any(word in normalized for word in ('想要', '需要', '准备装修', '设计', '改造', '新房')):
        intent = 'requirement'
        intent_delta = 6

    if any(word in normalized for word in ('谢谢', '明白了', '很专业', '有帮助')):
        trust_delta += 6
    if intent != 'opt_out' and any(word in normalized for word in ('不要联系', '不聊了')):
        trust_delta -= 12
        intent_delta -= 10

    persona = ''
    if any(word in normalized for word in ('数据', '对比', '明细', '依据', '怎么算')):
        persona = 'rational'
    elif any(word in normalized for word in ('感觉', '氛围', '温馨', '好看', '故事')):
        persona = 'emotional'
    elif any(word in normalized for word in ('马上', '现在就', '直接定', '就要')):
        persona = 'impulsive'
    elif any(word in normalized for word in ('再看看', '谨慎', '比较', '考虑')):
        persona = 'cautious'

    return {
        'emotion': emotion,
        'intent': intent,
        'pain_points': pains,
        'persona_type': persona,
        'trust_delta': trust_delta,
        'intent_delta': intent_delta,
    }
