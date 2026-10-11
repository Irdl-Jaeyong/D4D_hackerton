"""Question-to-example retrieval and deterministic resource allocation.
No model-generated vehicle IDs, diagnoses or commands.
"""
import json,math,re
from pathlib import Path
from formation_motion import CATALOG
CATALOG_CARDS=json.loads((Path(__file__).resolve().parents[1]/'config/defense_scenarios_200.json').read_text())['scenarios']
KEYWORDS={
 '미확인 선박 접근':['접근','신원','미확인','따라오','선박'], '충돌 가능성':['충돌','교차','추월','가로지','급회전'],
 '복수 접근·혼잡':['여러','혼잡','동시에 접근','모여','다수'], '부유물·항로 장애물':['장애물','부유물','통나무','어망','로프','컨테이너'],
 '인명·구조 지원':['구조','익수','사람','구명','전복'], '파도·해상 상태':['파도','파고','해상','너울'],
 '바람·비행 환경':['바람','돌풍','횡풍','풍속'], '항법·위치 신뢰도':['gnss','gps','항법','위치 오류','지도','고도 센서'],
 '통신·데이터 지연':['통신','끊','지연','미수신','멈춘 영상'], '배터리·복귀 여유':['배터리','잔량','저잔량','에너지','충전 안'],
 'UAV 고장·비행 이상':['프로펠러','비행','기울','흔들','진동','고장'], 'USV 고장·추종 이상':['추진','조향','침수','회전','고장'],
 '센서 오인·불일치':['오인','가짜','센서','탐지','오염','반사'], '대형 유지·전환':['대형','슬롯','간격','전환','겹친'],
 '착함·충전·갑판 운영':['착함','갑판','충전','정비','온도'], '명령·데이터 무결성':['승인','명령','과거','버전','중복','없는 기체'],
 '함선 상태·항로':['감속','가속','함선 정지','변침','화재','함선 고장'], '연안·항만·제한 공간':['항만','연안','방파제','교각','수로','양식장'],
 '야간·가시성 저하':['야간','안개','역광','어둡','가시','밝기'], '복합 상황·운용자 부담':['동시에','복합','겹','여러 위험','우선순위','승인 대기']}
def normalized(text):
    text=text.lower().replace('드론','uav').replace('무인 수상정','usv').replace('무인배','usv').replace('떨려','흔들').replace('떨리','흔들')
    for word in ['어떻게','할까','해줘','해야','바꿀까','알려줘','지금','해주세요']:text=text.replace(word,'')
    return re.sub(r'[^a-z0-9가-힣]','',text)
def grams(text):
    t=normalized(text);return {t[i:i+2] for i in range(len(t)-1)}
def retrieve(question,scenario_id=None):
    explicit=scenario_id or (re.search(r'\bDEF[- ]?(\d{3})\b',question,re.I).group(1) if re.search(r'\bDEF[- ]?(\d{3})\b',question,re.I) else None)
    if explicit:
        id=explicit if explicit.startswith('DEF-') else 'DEF-'+explicit
        card=next((c for c in CATALOG_CARDS if c['id']==id),None)
        if not card:raise ValueError('없는 상황 카드 번호입니다.')
        return card,[{'id':card['id'],'category':card['category'],'situation':card['situation']}],'explicit_card'
    q=question.lower().replace('드론','uav').replace('무인배','usv');g=grams(q);rank=[]
    for card in CATALOG_CARDS:
        category=card['category'];cg=grams(card['situation']);overlap=len(g&cg)/max(1,len(g))
        hits=sum(k in q for k in KEYWORDS[category])
        boost=.12*min(3,hits)
        if category=='UAV 고장·비행 이상':boost+=.25 if 'uav' in q and any(k in q for k in ['흔들','기울','고장','프로펠러','진동','떨']) else -.1
        if category=='USV 고장·추종 이상':boost+=.25 if 'usv' in q and any(k in q for k in ['추진','조향','고장','침수','회전']) else -.1
        score=overlap*.65+boost
        rank.append((score,card['id'],hits,card))
    rank.sort(key=lambda x:(-x[0],x[1]));top=rank[0]
    candidates=[{'id':r[3]['id'],'category':r[3]['category'],'situation':r[3]['situation']} for r in rank[:3]]
    if top[0]<.22 or top[2]==0:return None,candidates,'needs_information'
    return top[3],candidates,'keyword_example'

def build_plans(card,vehicles,formation,target_offset=None,reported_ids=()):
    leader=next((v for v in vehicles if v['type']=='SHIP' and v['connected']),None)
    target=(leader['telemetry']['x']+target_offset[0],leader['telemetry']['y']+target_offset[1]) if leader and target_offset is not None else None
    excluded=set(reported_ids) if card['category'] in ('UAV 고장·비행 이상','USV 고장·추종 이상','배터리·복귀 여유') else set()
    def rank(kind):
        result=[]
        for v in vehicles:
            if v['type']!=kind or v['id'] in excluded or not v['connected'] or not v['readiness']['available']:continue
            r=v['readiness'];p=v['telemetry']
            eta=math.hypot(p['x']-target[0],p['y']-target[1])/(10 if kind=='UAV' else 3) if target else 0
            if r['endurance_minutes']*60<2*eta+300:continue
            result.append((eta+(100-r['battery_percent'])*.8,v['id'],eta,r['battery_percent']))
        return sorted(result)
    ranks={kind:rank(kind) for kind in ('UAV','USV')};plans=[]
    for id,proposal in zip(('observe','verify','prepare'),card['recommendations']):
        tasks=[];missing=[]
        for kind,key in [('UAV','uav'),('USV','usv')]:
            count=proposal['requests'][key];chosen=ranks[kind][:count]
            if len(chosen)<count:missing.append(f'{kind} 필요 {count} / 배정 가능 {len(chosen)}')
            for _,vehicle,eta,battery in chosen:
                execution='observe_target' if kind=='UAV' and target is not None else 'keep_station' if kind=='UAV' else 'plan_only'
                tasks.append({'vehicle':vehicle,'task':'신고 위치 추가 관측' if execution=='observe_target' else '현재 담당 구역 감시 · 추가 출동 없음' if execution=='keep_station' else '상태 확인·연락 지원 계획',
                              'execution':execution,'eta_seconds':round(eta),'distance_m':round(eta*(10 if kind=='UAV' else 3),1) if target is not None else None,'target_world':{'x':round(target[0],2),'y':round(target[1],2)} if target else None,
                              'reason':f'추정 잔량 {battery}% · 최신 통신 · 복귀 여유 확인'+(' · 목표 위치 미지정, 기존 구역 유지' if target is None else '')})
        modes={g:formation[g] if mode=='current' else mode for g,mode in proposal['formations'].items()}
        assert all(mode in CATALOG[g] for g,mode in modes.items())
        if not leader:missing.append('함선 최신 위치 미수신')
        plans.append({'id':id,'title':proposal['title'].split('. ',1)[-1],'formations':modes,'tasks':tasks,'action':proposal['action'],
                      'benefit':proposal['action'],'tradeoff':proposal['tradeoff'],'requests':proposal['requests'],'available':not missing,
                      'unavailable_reason':' / '.join(missing),'validation':'기체는 현재 상태로 배정. 목표 위치가 없으면 새 출동 없음. ETA는 직선 추정이며 안전 경로 검증 전입니다.',
                      'execution_scope':'대형 적용과 지정 좌표의 UAV 관측만 실행 가능. 함선 운항 변경·USV 출동·정비·충전 조정은 제안입니다.'})
    return plans
