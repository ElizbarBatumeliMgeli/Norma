"""Every quote in the rulebook must exist word for word in the text it names."""
from pathlib import Path
import json
import re
import unittest

from rulebook import BASE, CATEGORY_KEYS, RULES

DATA = Path(__file__).parent / 'data' / 'regulation'


def flat(text):
    return re.sub(r'\s+', ' ', text.replace('­', ''))


class RulebookTest(unittest.TestCase):
    def test_quotes_are_verbatim_in_their_source(self):
        original = flat((DATA / 'regulation_2016.txt').read_text(encoding='utf-8'))
        amendments = json.loads((DATA / 'amendments.json').read_text(encoding='utf-8'))
        text = {f'№{a["number"]} ({a["date"][:4]})': flat((DATA / 'amendments' / a['file']).read_text(encoding='utf-8')) for a in amendments}
        for rule in RULES:
            source = original if rule['source'] == BASE else text[rule['source']]
            self.assertIn(flat(rule['quote']), source, rule['id'])

    def test_rules_are_well_formed(self):
        self.assertEqual(len({r['id'] for r in RULES}), len(RULES))
        for rule in RULES:
            self.assertIn(rule['category'], CATEGORY_KEYS)
            for field in ('ka', 'req_ka'):
                self.assertTrue(any('ა' <= c <= 'ჿ' for c in rule[field]), rule['id'])


if __name__ == '__main__':
    unittest.main()
