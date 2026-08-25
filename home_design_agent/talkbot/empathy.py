"""Rule-based profile extraction and evidence-grounded empathy helpers."""

from __future__ import annotations

import re
from decimal import Decimal


ROOM_TYPES = ('客厅', '卧室', '主卧', '次卧', '厨房', '餐厅', '卫生间', '儿童房', '书房', '阳台', '全屋')
STYLES = ('现代简约', '现代', '原木', '奶油', '轻奢', '北欧', '新中式', '日式', '法式', '侘寂', '意式极简')
CITY_NAMES = (
    '北京', '上海', '广州', '深圳', '杭州', '成都', '重庆', '武汉', '南京', '苏州',
    '西安', '天津', '长沙', '青岛', '郑州', '宁波', '佛山', '东莞', '合肥', '厦门',
)
UNKNOWN_ANSWERS = ('不知道', '不清楚', '不确定', '没想好', '还没想好', '暂时不清楚')
CHINESE_MONTH = (
    r'(?:今年|明年|后年)?(?:1[0-2]|0?[1-9]|十[一二]?|[一二三四五六七八九])月份?'
)


def _money(value: str, unit: str) -> int:
    amount = float(value)
    if unit.lower() in ('万', 'w'):
        amount *= 10_000
    elif unit == '千':
        amount *= 1_000
    return max(0, int(amount))


def _extract_budget(text: str) -> tuple[int | None, int | None]:
    range_match = re.search(
        r'(?:(预算|费用|总价|装修款|控制在|准备花|大概花)\s*)?'
        r'(\d+(?:\.\d+)?)\s*(万|千|元|[wW])?\s*'
        r'(?:到|至|[-~—－])\s*(\d+(?:\.\d+)?)\s*(万|千|元|[wW])?',
        text,
    )
    if range_match:
        context = range_match.group(1)
        left_unit = range_match.group(3) or range_match.group(5) or ''
        right_unit = range_match.group(5) or range_match.group(3) or ''
        # A bare range such as “孩子3到5岁” or “工期3到5个月” is not a budget.
        if not context and not left_unit and not right_unit:
            return None, None
        if not left_unit and not right_unit:
            raw_low = float(range_match.group(2))
            raw_high = float(range_match.group(4))
            if min(raw_low, raw_high) < 10_000:
                return None, None
        low = _money(range_match.group(2), left_unit)
        high = _money(range_match.group(4), right_unit)
        return (min(low, high), max(low, high))

    single = re.search(
        r'(?:预算|费用|总价|装修款|控制在|大概|准备花|不超过|最多)\s*'
        r'(\d+(?:\.\d+)?)\s*(万|千|元|[wW])?',
        text,
    )
    if single:
        value = single.group(1)
        unit = single.group(2) or ''
        if not unit and float(value) < 10_000:
            return None, None
        maximum = _money(value, unit)
        return (int(maximum * 0.7), maximum)
    explicit_unit = re.search(
        r'(?<!\d)(\d+(?:\.\d+)?)\s*(万|千|元|[wW])(?![A-Za-z\d])',
        text,
    )
    if explicit_unit:
        maximum = _money(explicit_unit.group(1), explicit_unit.group(2))
        return (int(maximum * 0.7), maximum)
    return None, None


def _contextual_profile_update(text: str, expected_field: str) -> dict:
    """Interpret a terse answer only in the slot explicitly asked last turn."""
    compact = re.sub(r'\s+', '', (text or '').strip())
    if not compact or any(answer in compact for answer in UNKNOWN_ANSWERS):
        return {}

    if expected_field == 'area':
        match = re.fullmatch(
            r'(?:大概|约|差不多)?(\d+(?:\.\d+)?)(?:平米|平方米|㎡|平)?(?:左右)?',
            compact,
        )
        if match:
            area = Decimal(match.group(1))
            if Decimal('10') <= area <= Decimal('1000'):
                return {'area': area}

    if expected_field == 'budget_max':
        normalized = compact.lower().replace('w', '万')
        bare_range = re.fullmatch(
            r'(\d+(?:\.\d+)?)(?:到|至|[-~—－])(\d+(?:\.\d+)?)',
            normalized,
        )
        bare_single = re.fullmatch(r'(\d+(?:\.\d+)?)', normalized)
        if bare_range and max(float(bare_range.group(1)), float(bare_range.group(2))) <= 1000:
            normalized += '万'
        elif bare_single and float(bare_single.group(1)) <= 1000:
            normalized += '万'
        budget_min, budget_max = _extract_budget(f'预算{normalized}')
        if budget_min is not None:
            return {'budget_min': budget_min, 'budget_max': budget_max}

    if expected_field == 'desired_timeline' and re.fullmatch(
        rf'{CHINESE_MONTH}(?:左右|前|后)?',
        compact,
    ):
        return {'desired_timeline': compact}

    if expected_field == 'household':
        family_size = re.fullmatch(
            r'(?:一家|家里|我们|就(?:这个|这)?)?(?:一共|总共)?'
            r'([一二两三四五六七八九十\d]+)(?:口|个(?:人)?|人)'
            r'(?:住|居住|长期住|之家)?',
            compact,
        )
        if family_size:
            return {'household': f'{family_size.group(1)}口之家'}

    if expected_field == 'name' and re.fullmatch(
        r'[\u4e00-\u9fa5·]{1,6}|[A-Za-z][A-Za-z .-]{0,20}',
        compact,
    ):
        return {'name': compact}

    return {}


def extract_profile_updates(text: str, *, expected_field: str = '') -> dict:
    """Extract only facts explicitly present in the user's message."""
    text = (text or '').strip()
    updates: dict = {}

    phone_match = re.search(r'(?<!\d)(1[3-9]\d{9})(?!\d)', text)
    if phone_match:
        updates['phone'] = phone_match.group(1)

    name_match = re.search(
        r'(?:我叫|称呼我|叫我)\s*([\u4e00-\u9fa5·]{1,6}|[A-Za-z][A-Za-z .-]{0,20})(?=[，。,.\s]|$)',
        text,
    )
    if name_match and not any(word in name_match.group(1) for word in ('业主', '用户', '客户')):
        updates['name'] = name_match.group(1)

    area_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:平米|平方米|㎡|平)', text)
    if area_match:
        area = Decimal(area_match.group(1))
        if Decimal('10') <= area <= Decimal('1000'):
            updates['area'] = area

    budget_min, budget_max = _extract_budget(text)
    if budget_min is not None:
        updates['budget_min'] = budget_min
        updates['budget_max'] = budget_max

    city_candidates = []
    for city in CITY_NAMES:
        for match in re.finditer(re.escape(city), text):
            prefix = text[max(0, match.start() - 4):match.start()]
            if any(negative in prefix for negative in ('不在', '不是', '非', '不考虑')):
                continue
            city_candidates.append((match.start(), city))
    city_found = bool(city_candidates)
    if city_candidates:
        updates['city'] = max(city_candidates, key=lambda item: item[0])[1]
    city_match = re.search(r'(?:在|位于|坐标)(?:[\u4e00-\u9fa5]{2,8}省)?([\u4e00-\u9fa5]{2,10})市', text)
    if city_match and not city_found:
        updates['city'] = city_match.group(1)

    community_match = re.search(r'(?:小区|楼盘|社区)(?:是|叫|在)?\s*([\u4e00-\u9fa5A-Za-z0-9·-]{2,30})', text)
    if community_match:
        updates['community'] = community_match.group(1).rstrip('，。,. ')

    for room in ROOM_TYPES:
        if room in text:
            updates['room_type'] = room
            break
    style_candidates = []
    for style in STYLES:
        for match in re.finditer(re.escape(style), text):
            prefix = text[max(0, match.start() - 5):match.start()]
            if any(negative in prefix for negative in ('不喜欢', '不要', '排除', '不想要', '不考虑')):
                continue
            style_candidates.append((match.start(), len(style), style))
    if style_candidates:
        updates['style'] = max(style_candidates, key=lambda item: (item[0], item[1]))[2]

    if any(word in text for word in ('没有孩子', '没孩子', '孩子不住', '小孩不住', '不带孩子')):
        updates['has_kids'] = False
    elif any(word in text for word in ('孩子', '小孩', '宝宝', '儿童', '儿子', '女儿')):
        updates['has_kids'] = True
    kids_age_match = re.search(
        r'(?:孩子|小孩|宝宝|儿童|儿子|女儿)(?:大概|今年)?\s*'
        r'([一二两三四五六七八九十\d]{1,3})\s*岁',
        text,
    )
    if kids_age_match:
        updates['kids_age'] = f'{kids_age_match.group(1)}岁'
    if any(word in text for word in (
        '没有老人同住', '没有老人', '没老人', '老人不同住', '老人不住', '父母不同住',
    )):
        updates['has_elderly'] = False
    elif any(word in text for word in ('老人', '父母同住', '爸妈同住')):
        updates['has_elderly'] = True
    if any(word in text for word in ('猫', '狗', '宠物')):
        pets = [animal for animal in ('猫', '狗', '宠物') if animal in text]
        updates['pets'] = '、'.join(pets)

    household_bits = []
    family_match = re.search(r'(?:一家|家里)([一二两三四五六七八九\d]+)口', text)
    if family_match:
        household_bits.append(f'{family_match.group(1)}口之家')
    elif any(word in text for word in ('两人居住', '两个人住', '夫妻两人', '夫妻俩')):
        household_bits.append('两人居住')
    if updates.get('has_kids'):
        household_bits.append('有孩子')
    if updates.get('has_elderly'):
        household_bits.append('有老人同住')
    if household_bits:
        updates['household'] = '、'.join(household_bits)

    events = []
    event_map = {
        '婚期': ('结婚', '婚期', '婚房'),
        '换房': ('换房', '刚买房', '新房'),
        '升学': ('上学', '升学', '学区'),
        '备孕': ('备孕', '孕妇', '怀孕'),
        '开业': ('开店', '开业'),
    }
    for label, words in event_map.items():
        if any(word in text for word in words):
            events.append(label)
    if events:
        updates['recent_events'] = events
        # Keep only controlled event labels. Raw free text may contain names,
        # addresses, identity numbers, or payment data and must not enter profile storage.
        updates['situation'] = '近期事件：' + '、'.join(events)

    timeline_match = re.search(
        rf'((?:{CHINESE_MONTH}|[一二三四五六七八九十\d]+个?月后|年底|年前|年后|春节前|国庆前|婚期前|开学前|尽快)'
        r'[^，。,.]{0,12}(?:入住|完工|装好)?)',
        text,
    )
    if timeline_match:
        updates['desired_timeline'] = timeline_match.group(1)
    elif any(word in text for word in ('时间比较灵活', '时间灵活', '不着急入住')):
        updates['desired_timeline'] = '时间灵活'

    if any(word in text for word in (
        '不可以联系', '不能联系', '不同意联系', '不愿意留电话', '不想联系',
        '不要联系', '别联系', '拒绝联系',
    )):
        updates['consent_to_contact'] = False
    elif any(word in text for word in ('可以联系我', '同意联系', '愿意留电话', '请联系我', '预约量房')):
        updates['consent_to_contact'] = True
    if expected_field and expected_field not in updates:
        updates.update(_contextual_profile_update(text, expected_field))
    return updates


def empathy_prefix(emotion: str, pain_points: list[str], recent_events: list[str]) -> str:
    """Return a short acknowledgment without inventing shared experience."""
    if emotion == 'anxious':
        return '听起来你现在最需要的是把不确定的部分一项项理清，先不用急着做决定。'
    if emotion in ('hesitant', 'distrustful', 'defensive'):
        return '你的顾虑很合理，装修金额大、周期长，把风险问清楚再决定是负责任的做法。'
    if recent_events:
        return f'你提到{recent_events[0]}，时间和居住安排确实需要一起统筹。'
    if pain_points:
        return f'我记下了你最在意的“{pain_points[0]}”，后面的建议会优先围绕它展开。'
    return '明白了，我会根据你刚才说的信息逐步整理方案。'
