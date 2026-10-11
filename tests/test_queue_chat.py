import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from safety_chat import answer
class QueueChatTests(unittest.TestCase):
 def test_live_card_not_generic(self):
  s={'vehicles':[],'approval_queue':[{'id':7,'source':'synthetic','card':{'title':'가상 접근','summary':'가상 대상 이동','offset':[10,20]},'risk':{'reason':'현재 근거','score':70},'options':[{'tasks':['DO NOT PASS']}]}]};before=copy.deepcopy(s)
  a=answer('1순위 무슨 상황이야?',s);self.assertEqual(a['queue_reference']['mission_id'],7);self.assertIn('현재 근거',a['reply']);self.assertNotIn('DO NOT PASS',str(a));self.assertFalse(a['executed']);self.assertEqual(s,before)
 def test_absent(self):self.assertTrue(answer('2순위 설명',{'vehicles':[],'approval_queue':[]})['clarification_questions'])
if __name__=='__main__':unittest.main()
