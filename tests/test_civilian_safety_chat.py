import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from safety_chat import answer
class CivilianSafetyTests(unittest.TestCase):
 def test_report_not_detection(self):
  a=answer('우현 300m에서 선박이 접근해 위험해?',{'vehicles':[]});self.assertEqual(a['answer_type'],'civilian_safety');self.assertFalse(a['evidence'][0]['verified_detection']);self.assertFalse(a['executed']);self.assertEqual(a['recommendations'],[]);self.assertIn('인명 위험',a['reply'])
 def test_missing_info(self):self.assertEqual(len(answer('위협이 있어 어떻게 해?',{'vehicles':[]})['clarification_questions']),2)
 def test_followup(self):
  a=answer('선박이 접근해',{'vehicles':[]});b=answer('우현 300m',{'vehicles':[]},a['clarification_context']);self.assertFalse(b['clarification_questions'])
if __name__=='__main__':unittest.main()
