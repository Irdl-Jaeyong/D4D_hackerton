import sys,json,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from llm_dialogue import validate
class ModelValidationTests(unittest.TestCase):
 def test_valid(self):self.assertEqual(validate(json.dumps({'explanation':'통신 상태를 확인할 수 없어 새 작업을 맡기기 어렵습니다.','answers':[]}),0)['answers'],[])
 def test_wrong_count(self):
  with self.assertRaises(ValueError):validate('{"explanation":"설명","answers":[]}',3)
 def test_numbers_and_claims(self):
  for text in ['배터리 80%','UAV-01 정상','승인했습니다']:
   with self.subTest(text=text),self.assertRaises(ValueError):validate(json.dumps({'explanation':text,'answers':[]}),0)
 def test_grounded_numbers(self):
  raw=json.dumps({'explanation':'UAV-01 배터리 80%는 모의 값입니다.','answers':[]})
  self.assertTrue(validate(raw,0,'UAV-01 80'))
  with self.assertRaises(ValueError):validate(raw,0,'UAV-02 60')
 def test_three_alternatives(self):
  value={'explanation':'확인이 필요합니다.','answers':[{'number':i,'explanation':'상태를 확인합니다.'} for i in range(1,4)]}
  self.assertEqual(len(validate(json.dumps(value),3)['answers']),3)
if __name__=='__main__':unittest.main()
