"""Turns a review (one result per check) into the report the app shows.

Clause, category and quote always come from the rulebook. A rule the review left out is reported
as "to verify": silence is never a pass, and the verdict is "clear" only if every rule was answered.
"""
from rulebook import BY_ID, CATEGORIES, RULES

SEVERITY = {'fail': 0, 'missing': 1, 'verify': 2, 'pass': 3, 'not_applicable': 4}
NOT_REVIEWED = dict(ka='ამ პუნქტზე შედეგი არ მიღებულა — შეამოწმეთ ხელით.', en='No result came back for this clause: check it by hand.')


def locate(check, anchors, sizes):
    """Page and box for a finding: the union of the text it cites, else the box it gave, else none."""
    by_id = {a['id']: a for a in anchors}
    cited = [by_id[i] for i in check.get('anchors') or [] if i in by_id]
    if cited:
        page = cited[0]['page']
        boxes = [a['box'] for a in cited if a['page'] == page]
        return page, [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]
    page = check.get('page')
    if not isinstance(page, int) or not 1 <= page <= len(sizes):
        return None, None
    box = check.get('box')
    if box and len(box) == 4 and 0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1:
        return page, box
    return page, None


def finding(check, anchors, sizes):
    rule = BY_ID[check['rule_id']]
    page, box = locate(check, anchors, sizes)
    return dict(rule=rule['id'], category=rule['category'], title_ka=rule['ka'], title_en=rule['en'], required_ka=rule['req_ka'],
                required_en=rule['req_en'], quote=rule['quote'], source=rule['source'], status=check['status'],
                found=check.get('found') or '', explanation_ka=check.get('explanation_ka') or '', explanation_en=check.get('explanation_en') or '',
                fix_ka=check.get('fix_ka') or '', fix_en=check.get('fix_en') or '', page=page, box=box)


def verdict(counts):
    if counts['fail']:
        return 'fail'
    if counts['missing']:
        return 'missing'
    return 'verify' if counts['verify'] else 'clear'


def assemble(review, anchors, sizes):
    checks = [c for c in review['checks'] if c['rule_id'] in BY_ID]
    answered = {c['rule_id'] for c in checks}
    checks += [dict(rule_id=r['id'], status='verify', explanation_ka=NOT_REVIEWED['ka'], explanation_en=NOT_REVIEWED['en'])
               for r in RULES if r['id'] not in answered]
    findings = sorted((finding(c, anchors, sizes) for c in checks), key=lambda f: SEVERITY[f['status']])
    for number, item in enumerate(findings, 1):
        item['number'] = number
    counts = {status: sum(f['status'] == status for f in findings) for status in SEVERITY}
    return dict(building=review['building'], findings=findings, counts=counts, verdict=verdict(counts),
                categories=[dict(key=key, ka=ka, en=en, chapters=chapters) for key, ka, en, chapters in CATEGORIES])
