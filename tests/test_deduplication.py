import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from deduplicate_chat_data import chat_key,faq_key,read_rows
from chat_scenario_briefing import dialogue_examples,example_context
from web_faq import situation_examples
class Deduplication(unittest.TestCase):
    def verify(self,original_name,cleaned_name,key):
        raw=read_rows(ROOT/'config'/original_name);clean=read_rows(ROOT/'config'/cleaned_name)
        original={row['id']:row for row in raw}
        self.assertEqual(set(original),{id for row in clean for id in row['source_ids']})
        self.assertEqual(len(clean),len({key(row) for row in clean}))
        for row in clean:
            for id in row['source_ids']:self.assertEqual(key(row),key(original[id]))
        return clean
    def test_chat_preserves_all_distinct_geometry_and_engine_results(self):
        clean=self.verify('chat_examples_1800.jsonl','chat_examples_deduplicated.jsonl',chat_key)
        self.assertEqual(len(clean),900)
        self.assertEqual({r['scenario_id'] for r in clean},{r['scenario_id'] for r in read_rows(ROOT/'config/chat_examples_1800.jsonl')})
        self.assertEqual(sum(len(row['question_variants']) for row in clean),1800)
    def test_faq_preserves_question_aliases_and_answers(self):
        clean=self.verify('faq_situations_600.jsonl','faq_situations_deduplicated.jsonl',faq_key)
        self.assertEqual(len(clean),100)
        self.assertEqual(sum(len(row['question_variants']) for row in clean),600)
        grouped=situation_examples();self.assertEqual(len(grouped),60)
        self.assertTrue(all(len(rows)==10 for rows in grouped.values()))
    def test_runtime_uses_cleaned_data_and_resource_variants(self):
        grouped=dialogue_examples()
        self.assertEqual(sum(len(rows) for rows in grouped.values()),900)
        for id in grouped:
            examples=example_context({'scenario':{'id':id}})
            self.assertEqual(len(examples),3)
            self.assertEqual(len({r['variant'] for r in examples}),3)
    def test_review_counts_match_actual_data(self):
        rows=read_rows(ROOT/'config/training_review_deduplicated.jsonl')
        report=json.loads((ROOT/'config/deduplication_manifest.json').read_text())
        self.assertEqual(len(rows),report['review_records'])
        self.assertEqual(len(rows),1060)
        self.assertEqual(report['stored_answer_blocks_after'],3880)
