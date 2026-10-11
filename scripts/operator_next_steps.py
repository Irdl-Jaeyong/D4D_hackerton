"""Evidence-based safety checks, never motion or tactical instructions."""
import re
CHECKS={
 'link':('마지막 수신 시각과 링크 연결 상태를 확인하세요.','통신 손실 보호 설정과 연결 기록을 검토한 후 새 임무 배정 여부를 판단하세요.'),
 'fault':('등록된 고장 종류와 현재 복귀·착함·정비 단계를 확인하세요.','정상 상태와 정비 결과를 확인한 뒤 운용자가 재개 여부를 판단하세요. 충전 완료만으로 고장 해제를 판단하지 마세요.'),
 'battery':('모의 잔량의 수신 시각과 복귀 거리·예상 소모를 확인하세요.','복귀 에너지 여유를 검토하고 운용자가 임무 지속 또는 귀환 필요성을 판단하세요.'),
 'unstable':('기울기 계측과 수신 시각을 확인하고 제어·센서 기록을 비교하세요.','원인 확인 전 새 배정 보류를 검토하고 운용자가 임무 지속 가능성을 판단하세요.'),
 'separation':('두 기체의 최신 위치·시간 동기화·목표 경로 겹침을 확인하세요.','검증된 안전 경로를 확인한 뒤 운용자가 추가 이동 가능 여부를 판단하세요.')}
def attach(result,query,snapshot):
 if result.get('answer_type')=='interface_help':return result
 kind=None
 ids=re.findall(r'(?:UAV|USV|SHIP)-\d{2}',query.upper())
 if result.get('queue_reference'):
  ref=result['queue_reference'];card=next((m for m in snapshot.get('approval_queue',[]) if m['id']==ref['mission_id']),{})
  vehicle=card.get('vehicle_id')
  if vehicle:ids=[vehicle]
 for v in snapshot.get('vehicles',[]):
  if v['id'] not in ids:continue
  if not v.get('connected'):kind='link'
  elif v.get('fault'):kind='fault'
  elif v.get('readiness',{}).get('battery_percent') is not None and v['readiness']['battery_percent']<35:kind='battery'
  elif max(abs((v.get('telemetry') or {}).get('roll',0)),abs((v.get('telemetry') or {}).get('pitch',0)))>.22:kind='unstable'
  break
 if kind is None and result.get('answer_type')=='safety_risk' and result.get('evidence'):kind=result['evidence'][0].get('kind','').split('-')[0]
 if kind in CHECKS:now,decision=CHECKS[kind]
 elif result.get('queue_reference'):
  now='해당 상황 카드의 위치·보고 시각·관측 기록을 확인하세요.'
  decision='확인된 사실과 가상 시나리오를 구분하고, 근거가 부족하면 추가 관측 정보를 요청하세요. 이 안내는 전투 대응이나 이동 명령이 아닙니다.'
 elif result.get('clarification_questions'):
  now=' · '.join(result['clarification_questions']);decision='추가 정보가 확인된 뒤 검토하세요. 현재 정보로 실행 여부를 확정하지 마세요.'
 else:now='선택 기체의 현재 임무와 최신 수신 상태를 확인하세요.';decision='현재 상태만으로 새 작업을 실행하지 말고 필요한 기체·상황 정보를 먼저 확인하세요.'
 result['next_steps']={'now':now,'human_decision':decision,'automatic_execution':False};return result

def render(result):
 steps=result.get('next_steps')
 if steps:result['reply']+='\n\n지금 할 일: '+steps['now']+'\n사람이 판단할 항목: '+steps['human_decision']
 return result
