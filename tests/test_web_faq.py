import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from web_faq import DATA,retrieve_faq,briefing,TOPICS
class WebFAQ(unittest.TestCase):
    def test_60_distinct_questions_180_answers_with_sources(self):
        self.assertEqual(len(DATA['faqs']),60);self.assertEqual(sum(len(r['answers']) for r in DATA['faqs']),180)
        self.assertEqual(len({r['question'] for r in DATA['faqs']}),60)
        for row in DATA['faqs']:
            self.assertEqual(retrieve_faq(row['question'])['id'],row['id'])
            self.assertTrue(TOPICS[row['topic_id']]['source']['url'].startswith('https://'))
            result=briefing(row,{'formations':{'usv':'circle','uav':'hemisphere'}})
            self.assertTrue(all(not p['tasks'] for p in result['plans']))
    def test_concrete_fault_is_not_general_faq(self):
        self.assertIsNone(retrieve_faq('UAV-01이 흔들리면 프로펠러 고장이라고 보면 돼?'))
        self.assertIsNone(retrieve_faq('우현 300m에 선박 2척이 접근해'))

    def test_600_situations_6000_proposal_answers(self):
        import json
        from web_faq import examples_for_faq
        path=Path(__file__).resolve().parents[1]/'config/faq_situations_600.jsonl'
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(len(rows),600);self.assertEqual(len({r['id'] for r in rows}),600)
        self.assertEqual(len({r['user_question'] for r in rows}),600)
        self.assertEqual(sum(len(r['answers']) for r in rows),6000)
        from collections import Counter
        self.assertTrue(all(n==10 for n in Counter(r['faq_id'] for r in rows).values()))
        for row in rows:
            self.assertTrue(row['synthetic']);self.assertFalse(row['automatic_execution'])
            self.assertEqual(len({a['id'] for a in row['answers']}),10)
            self.assertTrue(all(a['execution']=='proposal_only' and a['limit'] for a in row['answers']))
        examples=examples_for_faq('FAQ-001','배터리 자료 갱신이 지연돼')
        self.assertEqual(len(examples),1);self.assertEqual(len(examples[0]['response_perspectives']),10)
