"""Screen help and live formation labels, without tactical recommendations."""
from formation_motion import CATALOG

def context(snapshot):
 f=snapshot.get('formations') or {}
 return {'formation_catalog':CATALOG,'selected_formations':{g:{'key':f.get(g),'label':CATALOG[g].get(f.get(g),'수신 대기'),'transition':f.get('status',{}).get(g)} for g in CATALOG},'camera':{'view':snapshot.get('camera_view'),'available':snapshot.get('camera_available')},'buttons':{'대형 설정':'대형 박스를 클릭하면 선택한 형태로 점진 재배치합니다. 대화 자체는 대형을 변경하지 않습니다.','승인대기열':'상황을 클릭해 상세를 검토합니다.','전체 보기':'함대 전체 카메라로 돌아갑니다.','선택 기체':'선택한 기체의 1인칭 시점을 요청합니다.','초기화':'카메라 확대와 이동을 초기화합니다.'},'limits':'화면 사용법·현재 상태 설명만. 공격 대응·전술 배정 추천 없음.'}
def briefing(question,snapshot):
 if not any(w in question for w in ('대형','버튼','화면 사용','카메라 시점','확대','초기화','전체 보기')):return None
 info=context(snapshot);f=info['selected_formations']
 if '대형' in question:
  if any(w in question for w in ('뭐가','종류','어떤 대형들','설정에','목록')):
   reply='USV 대형: '+', '.join(CATALOG['usv'].values())+'\n드론 대형: '+', '.join(CATALOG['uav'].values())+'\n대형 설정에서 해당 박스를 클릭하면 현재 위치에서 점진적으로 재배치해요.'
  else:
   reply='현재 선택: USV '+f['usv']['label']+' / 드론 '+f['uav']['label']
   for g in ('usv','uav'):
    t=f[g]['transition'];reply+='\n'+g.upper()+': '+('대형 전환 중' if t and t.get('moving') else '상태 수신 대기' if not t else '선택 대형 유지 중')
 else:
  matches=[k+': '+v for k,v in info['buttons'].items() if k in question]
  reply='\n'.join(matches) if matches else '어느 버튼인가요? 버튼에 적힌 이름을 알려주세요.'
 return {'reply':reply,'answer_type':'interface_help','interface_reference':info,'evidence':[],'recommendations':[],'clarification_questions':[],'clarification_context':None,'web_sources':[],'executed':False,'llm_used':False,'retrieval_method':'live_interface_reference'}
