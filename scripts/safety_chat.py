"""Read-only reference retrieval. Never builds tactical assignments or commands."""
import json,re
from queue_chat import briefing as queue_briefing
from interface_chat import briefing as interface_briefing
from fault_explanation import explain,is_reason_question
from safety_risk_briefing import answer_risks
from five_question_briefing import route as five_route
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FAQ=json.loads((ROOT/'config/web_faq_60.json').read_text())
CASES=json.loads((ROOT/'config/chat_safety_cases_20.json').read_text())
CARDS=json.loads((ROOT/'config/defense_scenarios_200.json').read_text())['scenarios']
def grams(text):
 text=re.sub(r'[^a-z0-9가-힣]','',text.lower());return {text[i:i+2] for i in range(len(text)-1)}
def answer(message,snapshot,previous=None):
 query=((previous+'\n') if previous else '')+message
 screen=interface_briefing(query,snapshot)
 if screen:return screen
 queued=queue_briefing(query,snapshot)
 if queued:return queued
 routed=five_route(message,snapshot,previous)
 if routed:return routed
 if is_reason_question(query) or (re.search(r'(?:UAV|USV)-\d{2}',query,re.I) and any(w in query for w in ('상태 알려','상태야','뭐하고','뭐 하고','하는 중'))):return explain(query,snapshot)
 if any(w in query for w in ('위험','어떻게 해야','어떻게 해','대응','어떡','뭘 해야')):return answer_risks(query,snapshot)
 rows=[{'question':r['question'],'kind':'faq','record':r} for r in FAQ['faqs']]+[{'question':r['question'],'kind':'safe','record':r} for r in CASES]
 # Existing cards contribute situation/check questions only, never their tactical plans.
 rows += [{'question':r['situation'],'kind':'card','record':r} for r in CARDS if any(w in r['category'] for w in ('고장','배터리','통신','충돌','부유물','구조','기상','복귀'))]
 q=grams(query)
 ranked=sorted(rows,key=lambda r:len(q&grams(r['question']))/max(1,len(q|grams(r['question']))),reverse=True)
 best=ranked[0];score=len(q&grams(best['question']))/max(1,len(q|grams(best['question'])))
 if score<.08:best=None
 record=best['record'] if best else {};sources=[]
 check=record.get('check') or record.get('clarifying_question') or '기체 번호, 관측한 증상, 발생 시각과 현재 연결 상태'
 if best and best['kind']=='card':check=' · '.join(record['check_before_decision'])
 if best and best['kind']=='faq':
  topic=next(t for t in FAQ['topics'] if t['id']==record['topic_id']);sources=[topic['source']]
 elif best and best['kind']=='safe':sources=[record['source']]
 missing=[]
 if any(w in query for w in ('고장','배터리','통신','복귀','흔들','전압','끊')) and not re.search(r'(?:UAV|USV)-\d{2}',query,re.I):missing.append('어느 기체인가요? 예: UAV-01 또는 USV-02.')
 if any(w in query for w in ('충돌','부유물','접근','구조')):
  if not any(w in query for w in ('좌현','우현','전방','후방','정면')):missing.append('함선 기준 어느 방향인가요?')
  if not re.search(r'\d+\s*(?:m|미터|km|킬로미터)',query,re.I):missing.append('함선에서 몇 미터 떨어져 있나요?')
 vehicles=snapshot.get('vehicles',[]);ids=re.findall(r'(?:UAV|USV)-\d{2}',query.upper())
 unknown=[i for i in ids if not any(v['id']==i for v in vehicles)]
 if unknown:missing.append('등록되지 않은 기체 번호입니다: '+', '.join(unknown))
 status=[]
 for v in vehicles:
  if v['id'] in ids:
   r=v.get('readiness',{});status.append(f"{v['id']}: {'연결' if v['connected'] else '미연결'} · 배터리 {r.get('battery_percent','정보 없음')} (시뮬레이션 추정)")
 recommendations=[]
 if not missing:
  for i,(title,text) in enumerate([('상태 확인',f'{check}을 확인하고 보고값과 실제 계측을 구분합니다.'),('설정·기록 교차 검토','해당 기체의 설정과 로그를 비교합니다. 문서에 있는 기능이 현재 시뮬레이터에 구현됐다고 가정하지 않습니다.'),('신규 작업 보류·운용자 검토','확인되지 않은 조건에 의존하는 새 작업을 보류하는 안을 검토합니다. 복귀·정비 또는 재개는 운용자가 상태를 확인하고 판단합니다.')],1):recommendations.append({'number':i,'title':title,'explanation':text})
 summary=('참고 사례: '+record.get('question',record.get('situation',''))) if best else '관련 사례를 확정하기 어렵습니다. 상황을 더 구체적으로 알려주세요.'
 if not best and not missing:missing=['어떤 기체에 어떤 증상이 발생했나요?'];recommendations=[]
 reply='\n'.join([summary,*status,*missing,*[f"{r['number']}. {r['title']}: {r['explanation']}" for r in recommendations],'대화는 조회·검토용이며 승인이나 이동 명령을 실행하지 않습니다.'])
 return {'reply':reply,'recommendations':recommendations,'clarification_questions':missing,'clarification_context':query[-6000:] if missing else None,'web_sources':sources,'reference_id':record.get('id'),'executed':False,'llm_used':False,'retrieval_method':'reference_search','model_note':'모델 가중치 학습이 아닌 자료 검색 기반 답변','catalog_count':len(rows)}
