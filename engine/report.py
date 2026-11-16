"""Turns a review (one result per check) into the report the app shows.

Clause, category and quote always come from the rulebook. A rule the review left out is reported
as "to verify": silence is never a pass, and the verdict is "clear" only if every rule was answered.
Results measured from CAD files join the AI's: measuring is exact, so it settles what the AI left open.

A project is reviewed one section (discipline) at a time. A rule that none of the added drawings can show
is "not checked": it is left out of the verdict, so checking only the fire protection drawings does not
fill the report with low-voltage or architecture clauses to verify. A rule whose section the AI could not
review says so.
"""
import measure
from rulebook import BY_ID, CATEGORIES, RULES, SECTIONS
import sections

SEVERITY = {'fail': 0, 'missing': 1, 'verify': 2, 'pass': 3, 'not_applicable': 4, 'not_checked': 5}
NOT_REVIEWED = dict(ka='ამ პუნქტზე შედეგი არ მიღებულა — შეამოწმეთ ხელით.', en='No result came back for this clause: check it by hand.')
NOT_MEASURED = dict(ka='ეს პუნქტი ნახაზიდან ავტომატურად არ იზომება. შესამოწმებლად საჭიროა AI ან სპეციალისტი.',
                    en='This clause cannot be measured from the drawing automatically. It needs the AI or a specialist.')
SECTION_FAILED = dict(ka='ამ განყოფილების შემოწმება AI-მ ვერ შეძლო — სცადეთ თავიდან ან შეამოწმეთ ხელით.',
                      en='The AI could not review this section: try again or check it by hand.')
NAME = {key: dict(ka=ka, en=en) for key, ka, en in SECTIONS}


def no_drawings(rule):
    """Why a rule was not checked: none of the disciplines that show it were added."""
    ka = ', '.join(NAME[key]['ka'] for key in rule['on'])
    en = ', '.join(NAME[key]['en'].lower() for key in rule['on'])
    return dict(ka=f'ამ შემოწმებაში არ შედის: პროექტს არ ახლავს ამ პუნქტის ნახაზები ({ka}).',
                en=f'Not part of this check: the project has no drawings that show this clause ({en}).')


def unanswered(rule, review):
    """What to say about a rule with no result."""
    if not review:
        return NOT_MEASURED
    coverage, done = review.get('coverage'), review.get('sections') or {}
    if coverage is None:
        return NOT_REVIEWED
    asked = coverage.get(rule['id']) or []
    if not asked:
        return no_drawings(rule)
    if all(done.get(key, {}).get('status') == 'failed' for key in asked):
        return SECTION_FAILED
    return NOT_REVIEWED


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
    found_ka = check.get('found_ka') or check.get('found') or ''
    found_en = check.get('found_en') or check.get('found') or ''
    return dict(rule=rule['id'], category=rule['category'], sections=list(rule['on']), title_ka=rule['ka'], title_en=rule['en'], required_ka=rule['req_ka'],
                required_en=rule['req_en'], quote=rule['quote'], source=rule['source'], status=check['status'],
                found=found_en or found_ka, found_ka=found_ka, found_en=found_en, explanation_ka=check.get('explanation_ka') or '', explanation_en=check.get('explanation_en') or '',
                fix_ka=check.get('fix_ka') or '', fix_en=check.get('fix_en') or '', page=page, box=box, measured=bool(check.get('measured')))


def verdict(counts):
    if counts['fail']:
        return 'fail'
    if counts['missing']:
        return 'missing'
    return 'verify' if counts['verify'] else 'clear'


def combined(checks, measured):
    """A measured result replaces the AI's, unless the AI found something worse: it may have seen what measuring cannot."""
    by_rule = {c['rule_id']: c for c in checks}
    for check in measured:
        current = by_rule.get(check['rule_id'])
        if current is None or SEVERITY[check['status']] <= SEVERITY[current['status']] or current['status'] in ('verify', 'not_applicable'):
            by_rule[check['rule_id']] = check
    return list(by_rule.values())


def measured_building(name, summary):
    """The heading of a report that had no AI: only what the drawings' numbers say."""
    top = summary['top_level'] if summary else None
    storeys = summary['storeys'] if summary else 0
    return dict(name=name, occupancy='', storeys=storeys or None, top_floor_m=top, high_rise=top > measure.HIGH_RISE_M if top is not None else None, sprinklered=None,
                summary_ka=f'გაიზომა {storeys} სართული.' if storeys else 'ნახაზები გაიხსნა.', summary_en=f'{storeys} storeys measured.' if storeys else 'The drawings were opened.')


def section_list(sizes, review):
    """The project's sections, with how many sheets each has and whether the AI reviewed it.
    Empty for a drawing whose sheets have no discipline."""
    if not any(p.get('discipline') for p in sizes):
        return []
    done = (review or {}).get('sections') or {}
    found = []
    for key, ka, en in SECTIONS:
        sheets = sum(p.get('discipline') == key or (key == 'architecture' and p.get('discipline') not in NAME) for p in sizes)
        state = done.get(key, {})
        found.append(dict(key=key, ka=ka, en=en, sheets=sheets, status=state.get('status') or ('not_reviewed' if sheets else 'no_drawings'),
                          error=state.get('error')))
    return found


def assemble(review, anchors, sizes, measured=None, name=''):
    reviewed = [c for c in review['checks'] if c['rule_id'] in BY_ID] if review else []
    checks = combined(reviewed, measure.checks(measured)) if measured else reviewed
    answered = {c['rule_id'] for c in checks}
    checked = {r['id'] for _, _, rules in sections.plan(sizes) for r in rules} if sizes else {r['id'] for r in RULES}
    for r in RULES:
        if r['id'] in answered:
            continue
        if r['id'] not in checked:
            reason, status = no_drawings(r), 'not_checked'
        else:
            reason, status = unanswered(r, review), 'verify'
        checks.append(dict(rule_id=r['id'], status=status, explanation_ka=reason['ka'], explanation_en=reason['en']))
    findings = sorted((finding(c, anchors, sizes) for c in checks), key=lambda f: SEVERITY[f['status']])
    for number, item in enumerate(findings, 1):
        item['number'] = number
    counts = {status: sum(f['status'] == status for f in findings) for status in SEVERITY}
    return dict(building=review['building'] if review else measured_building(name, measured), findings=findings, counts=counts, verdict=verdict(counts), ai_used=bool(review),
                categories=[dict(key=key, ka=ka, en=en, chapters=chapters) for key, ka, en, chapters in CATEGORIES],
                sections=section_list(sizes, review))
