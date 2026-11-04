"""Search over the bundled text of Resolution №41 and its amendments, for the assistant.

The original 2016 text is public on matsne.gov.ge; the consolidated text is paid. So a clause may
appear in the 2016 text and again in amendments: the newest amendment that restates it is in force.
"""
from functools import lru_cache
import json
from pathlib import Path
import re

DATA = Path(__file__).parent / 'data' / 'regulation'
CLAUSE = re.compile(r'\b\d{3,4}(?:\.\d+)+\b|\b\d{3,4}\b')


def amendments():
    return json.loads((DATA / 'amendments.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def passages():
    """(source label, order, text): one per line, newest amendment last. Order 0 is the 2016 text."""
    found = [('№41 (2016)', 0, line.strip()) for line in (DATA / 'regulation_2016.txt').read_text(encoding='utf-8').splitlines() if line.strip()]
    for order, item in enumerate(amendments(), 1):
        label = f'№{item["number"]} ({item["date"]})'
        found += [(label, order, line.strip().lstrip('„"')) for line in (DATA / 'amendments' / item['file']).read_text(encoding='utf-8').splitlines() if line.strip()]
    return found


def search(query, limit=8):
    """Passages for a clause number or keywords, the newest first when a clause is restated."""
    clauses = CLAUSE.findall(query)
    terms = [t.lower() for t in re.findall(r'[\w-]{3,}', query) if t not in clauses]
    scored = []
    for index, (source, order, text) in enumerate(passages()):
        lower = text.lower()
        score = sum(30 for clause in clauses if text.startswith((clause + ' ', clause + '.', f'ცხრილი {clause}')))
        score += sum(3 for clause in clauses if clause in text)
        # Georgian words change their endings, so a shortened stem also counts.
        score += sum(2 if term in lower else 1 if len(term) > 5 and term[:-2] in lower else 0 for term in terms)
        if score:
            scored.append((score, order, source, text, index))
    scored.sort(key=lambda item: (-item[0], -item[1]))
    return [dict(source=source, text=with_table(index, text)) for _, _, source, text, index in scored[:limit]]


def with_table(index, text):
    """Table cells are one per line: a short hit brings the rows after it, so its numbers are not lost."""
    if len(text) < 120:
        following = [p[2] for p in passages()[index + 1:index + 30] if p[0] == passages()[index][0]]
        text = ' | '.join([text] + following)
    return text[:1500]
