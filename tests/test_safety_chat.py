import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from safety_chat import answer,CASES
class ChatTests(unittest.TestCase):
 def setUp(self):self.state={'vehicles':[{'id':'UAV-01','connected':True,'readiness':{'battery_percent':61}}]}
 def test_missing_then_followup(self):
  a=answer('배터리 부족해',self.state);self.assertTrue(a['clarification_questions']);self.assertEqual(a['recommendations'],[])
  b=answer('UAV-01',self.state,a['clarification_context']);self.assertEqual(len(b['recommendations']),3);self.assertIn('61',b['reply']);self.assertFalse(b['executed'])
 def test_unknown_id(self):self.assertTrue(answer('UAV-99 통신 끊김',self.state)['clarification_questions'])
 def test_no_commands(self):
  a=answer('우현 300m에 부유물이 있어',self.state);self.assertEqual(len(a['recommendations']),3);self.assertNotIn('tasks',a);self.assertFalse(a['executed'])
 def test_sources(self):
  for c in CASES:
   a=answer(c['question']+' UAV-01',self.state);self.assertTrue(a['web_sources']);self.assertFalse(a['executed'])
if __name__=='__main__':unittest.main()
