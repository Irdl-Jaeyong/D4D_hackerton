import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from deduplicate_chat_data import read_rows,stable
from review_and_split_data import family,origins
class TrainingSplit(unittest.TestCase):
    def setUp(self):
        self.folder=ROOT/'config/training'
        self.rows={name:read_rows(self.folder/(name+'_candidates.jsonl')) for name in ('train','validation','test')}
    def test_every_record_once_no_source_or_family_leakage(self):
        original=read_rows(ROOT/'config/training_review_deduplicated.jsonl')
        all_rows=[row for rows in self.rows.values() for row in rows]
        self.assertEqual(len(all_rows),1060)
        self.assertEqual({stable(r) for r in original},{stable(r) for r in all_rows})
        self.assertEqual(len({(r['kind'],r['record']['id']) for r in all_rows}),1060)
        for a,b in [('train','validation'),('train','test'),('validation','test')]:
            self.assertFalse({family(r) for r in self.rows[a]} & {family(r) for r in self.rows[b]})
            self.assertFalse({o for r in self.rows[a] for o in origins(r)} & {o for r in self.rows[b] for o in origins(r)})
    def test_retrieval_reference_has_no_heldout_answers_or_sources(self):
        ref=json.loads((self.folder/'train_reference_catalog.json').read_text())
        held=self.rows['validation']+self.rows['test']
        held_origins={o for r in held for o in origins(r)}
        self.assertFalse({'scenario:'+r['id'] for r in ref['scenarios']} & held_origins)
        self.assertFalse({'faq:'+r['id'] for r in ref['faqs']} & held_origins)
        source=json.loads((ROOT/'config/web_faq_60.json').read_text())
        held_topics={r['record']['topic_id'] for r in held if r['kind']!='scenario_dialogue'}
        held_urls={r['source']['url'] for r in source['topics'] if r['id'] in held_topics}
        self.assertFalse({r['source']['url'] for r in ref['topics']} & held_urls)
    def test_50_representatives_have_specific_findings_not_training_approval(self):
        report=json.loads((self.folder/'representative_review_50.json').read_text())
        sample=read_rows(self.folder/'representative_samples_50.jsonl')
        self.assertEqual(len(sample),50);self.assertEqual(len(report['reviews']),50)
        self.assertEqual(len({r['record_id'] for r in report['reviews']}),50)
        self.assertTrue(all(r['issues'] and not r['expert_review'] and not r['training_approved'] for r in report['reviews']))
        self.assertEqual(len({family(r) for r in sample if r['kind']=='scenario_dialogue'}),20)
        self.assertEqual(len({r['record']['topic_id'] for r in sample if r['kind']!='scenario_dialogue'}),10)
    def test_split_manifest_is_honest_about_pending_review(self):
        report=json.loads((self.folder/'split_manifest.json').read_text())
        self.assertFalse(report['ready_for_training'])
        self.assertTrue(all(report['checks'].values()))
        for name,rows in self.rows.items():self.assertEqual(report['splits'][name]['count'],len(rows))
