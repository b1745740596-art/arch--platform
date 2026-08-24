"""Shared personal-data detection and redaction at external-model boundaries."""

from __future__ import annotations

import re


_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    # Match identity/bank-card-like values before telephone numbers so shorter
    # patterns cannot leave identifying fragments behind.
    (
        re.compile(r'(?<!\d)(?:\d[\s-]?){17}[\dXx](?!\d)'),
        '[身份证号已脱敏]',
    ),
    (
        re.compile(r'(?<!\d)(?:\d[\s-]?){15,18}\d(?!\d)'),
        '[长号码已脱敏]',
    ),
    (
        re.compile(r'(?<!\d)(?:\+?86[\s-]?)?1[3-9](?:[\s-]?\d){9}(?!\d)'),
        '[手机号已脱敏]',
    ),
    (
        re.compile(
            r'(?<!\d)0\d{2,3}[\s-]?\d{7,8}'
            r'(?:[\s-]?(?:转|ext\.?)\s*\d{1,6})?(?!\d)',
            re.IGNORECASE,
        ),
        '[固定电话已脱敏]',
    ),
    (
        re.compile(
            r'(?:联系电话|联系号码|座机|固定电话|电话)\s*[：:为是]?\s*'
            r'\d(?:[\s-]?\d){6,11}(?!\d)',
        ),
        '[联系电话已脱敏]',
    ),
    (
        re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+', re.IGNORECASE),
        '[邮箱已脱敏]',
    ),
    (
        re.compile(
            r'(?:详细地址|地址|住址|我家?住(?:在)?|家住(?:在)?|住在|门牌号|房号|小区地址)'
            r'\s*[：:为是]?\s*[^，。,.;；\n]{2,100}',
        ),
        '[具体地址已脱敏]',
    ),
    (
        re.compile(
            r'(?<![\u4e00-\u9fff])'
            r'(?:[\u4e00-\u9fff]{2,12}(?:省|自治区|市))?'
            r'[\u4e00-\u9fff]{2,16}(?:市|区|县|新区)'
            r'[\u4e00-\u9fff\d]{1,40}(?:路|街|道|巷|弄|胡同)'
            r'\s*\d{1,6}\s*号'
            r'(?:[\u4e00-\u9fff\d-]{0,30}(?:栋|幢|单元|室|房))?',
        ),
        '[具体地址已脱敏]',
    ),
    (
        re.compile(
            r'(?P<prefix>我叫|叫我|称呼我|联系人(?:姓名)?|业主姓名|客户姓名|姓名)'
            r'\s*[：:为是]?\s*'
            r'(?:[\u4e00-\u9fff·]{1,10}|[A-Za-z][A-Za-z .\'-]{0,40})'
            r'(?=[，。,.;；\s\n]|$)',
            re.IGNORECASE,
        ),
        r'\g<prefix>[姓名已脱敏]',
    ),
)


def redact_sensitive_text(value: str) -> str:
    """Redact common direct identifiers before storage or model transmission."""
    text = value or ''
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def contains_sensitive_personal_data(value: str) -> bool:
    """Return whether redaction would remove personal data from ``value``."""
    text = value or ''
    return redact_sensitive_text(text) != text
