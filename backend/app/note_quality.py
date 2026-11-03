"""Conservative cleanup shared by generated, imported and historical notes."""
from copy import deepcopy
import re

PATTERN_RULE = ('每个句型的 usage 必须具体说明该表达的交际目的、适用场合或搭配，不能只复述话题。'
                '禁止使用“根据具体语境完成表达与回应”等通用套话；无法确定时留空。'
                '不同句型不要重复相同说明；例句应展示具体用法，不要照抄句型标题。')


def text_key(text):
    return re.sub(r'[\s.…。!！?？]+', '', str(text or '')).casefold()


def clean_notes(data):
    result = deepcopy(data)
    patterns = result.get('patterns') or []
    for p in patterns:
        usage = str(p.get('usage') or '').strip()
        if ('根据具体语境' in usage and ('表达' in usage or '回应' in usage)):
            p['usage'] = ''
        seen = set()
        examples = []
        for e in p.get('examples') or []:
            if not isinstance(e, dict):
                examples.append(e)
                continue
            key = (text_key(e.get('text')), str(e.get('translation') or '').strip())
            if key not in seen:
                examples.append(e)
                seen.add(key)
        p['examples'] = examples
    return result
