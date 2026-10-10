import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from chat_scenario_briefing import example_context
class ChatExamples(unittest.TestCase):
    def test_all_examples_have_grounded_three_answers(self):
        rows=[json.loads(line) for line in (ROOT/'config/chat_examples_600.jsonl').read_text().splitlines()]
        self.assertEqual(len(rows),600);self.assertEqual(len({r['id'] for r in rows}),600)
        self.assertEqual(len({r['scenario_id'] for r in rows}),200)
        for row in rows:
            self.assertEqual(len(row['expected_recommendations']),3)
            known={v['id'] for v in row['snapshot']['vehicles'] if v['connected'] and v['readiness']['available']}
            for answer in row['expected_recommendations']:
                self.assertTrue(all(t['vehicle'] in known for t in answer['tasks']))
                self.assertFalse(set(row['checks']['reported_fault_excluded']) & {t['vehicle'] for t in answer['tasks']})
                if not answer['available']:self.assertTrue(answer['unavailable_reason'])
            self.assertTrue(row['synthetic']);self.assertTrue(row['checks']['no_auto_execution'])
    def test_prompt_examples_do_not_include_sample_assignments(self):
        examples=example_context({'scenario':{'id':'DEF-001'}})
        self.assertEqual(len(examples),3)
        self.assertNotIn('tasks',json.dumps(examples))
        self.assertEqual(example_context({'scenario':None}),[])

    def test_expanded_5400_responses_and_distinct_questions(self):
        rows=[json.loads(line) for line in (ROOT/'config/chat_examples_1800.jsonl').read_text().splitlines()]
        self.assertEqual(len(rows),1800)
        self.assertEqual(sum(len(row['expected_recommendations']) for row in rows),5400)
        self.assertEqual(len({row['messages'][1]['content'] for row in rows}),1800)
        for row in rows:
            eligible={v['id'] for v in row['snapshot']['vehicles'] if v['connected'] and v['readiness']['available']}-set(row['checks']['reported_fault_excluded'])
            for answer in row['expected_recommendations']:
                self.assertEqual(len(answer['decision_steps']),4)
                self.assertTrue(all(task['vehicle'] in eligible for task in answer['tasks']))
                if not answer['available']:self.assertTrue(answer['unavailable_reason'])
