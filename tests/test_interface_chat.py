import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from safety_chat import answer
class InterfaceChatTests(unittest.TestCase):
 def test_catalog(self):
  a=answer('대형 설정에 뭐가 있어?',{'formations':{},'vehicles':[]});self.assertIn('직육면체',a['reply']);self.assertIn('원형 호위',a['reply']);self.assertFalse(a['executed'])
 def test_current(self):
  a=answer('지금 어떤 대형이야?',{'formations':{'usv':'columns','uav':'box','status':{'uav':{'moving':True}}},'vehicles':[]});self.assertIn('양측 종대',a['reply']);self.assertIn('전환 중',a['reply'])
 def test_button(self):self.assertIn('카메라 확대',answer('초기화 버튼 뭐야?',{'vehicles':[]})['reply'])
if __name__=='__main__':unittest.main()
