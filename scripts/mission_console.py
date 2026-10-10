"""Non-combat briefing plans; battery and endurance are simulated, not sensed."""
import math
SCENARIOS={
 'crossing':{'title':'접근 선박 확인','summary':'우현 전방의 가상 선박이 접근 중입니다. 의도와 충돌 여부는 미확인입니다.','offset':[110,-90],'unknown':'실제 센서 탐지·충돌 예측은 연결되지 않았습니다.'},
 'debris':{'title':'항로 장애물 확인','summary':'전방에 가상 부유물이 보고되었습니다. 위치 확인이 필요합니다.','offset':[140,30],'unknown':'장애물 형상과 안전 우회 경로는 미검증입니다.'},
 'rescue':{'title':'해상 구조 지원','summary':'좌현에 가상 익수자 신고가 접수되었습니다. 추가 관측이 필요합니다.','offset':[50,100],'unknown':'실제 익수자 인식·구조 장비는 연결되지 않았습니다.'}}

def readiness(vehicle,elapsed_seconds=0):
    kind=vehicle['type'];t=max(0,elapsed_seconds)
    number=int(vehicle['id'].split('-')[1])
    # Bounded demonstration consumption, tied to simulator time (never wall time).
    capacity=35 if kind=='UAV' else 180
    battery=round(max(0,96-(number*7)%27-t/60/capacity*100),1) if kind!='SHIP' else None
    available=vehicle['connected'] and battery is not None and battery>=35
    return {'battery_percent':battery,'battery_source':'simulated' if battery is not None else 'unavailable',
            'endurance_minutes':round(battery/100*capacity,1) if battery is not None else None,
            'available':available,'reason':'통신 데이터 지연' if not vehicle['connected'] else '잔량 35% 미만' if battery is not None and battery<35 else '지원 기체' if kind=='SHIP' else '배정 가능',
            'task':'담당 위치 유지' if kind!='SHIP' else '함선 직진',
            'operational_state':'unavailable' if not vehicle['connected'] or kind!='SHIP' and not available else 'waiting' if kind=='UAV' else 'defending'}

def options(vehicles,formation,scenario,target_offset=None):
    leader=next((v for v in vehicles if v['type']=='SHIP' and v['connected']),None)
    if not leader:return []
    offset=target_offset if target_offset is not None else SCENARIOS[scenario]['offset'];target=(leader['telemetry']['x']+offset[0],leader['telemetry']['y']+offset[1])
    def rank(kind):
        result=[]
        for v in vehicles:
            if v['type']!=kind or not v['readiness']['available']:continue
            p=v['telemetry'];r=v['readiness'];distance=math.hypot(p['x']-target[0],p['y']-target[1])
            eta=distance/(10 if kind=='UAV' else 3)
            if r['endurance_minutes']*60<2*eta+300:continue
            score=eta+(100-r['battery_percent'])*.8
            result.append((score,v['id'],eta,r['battery_percent']))
        return sorted(result)
    drones=rank('UAV');boats=rank('USV')
    result=[]
    specs=[('observe','추가 관측',formation['usv'],formation['uav'],'기존 대형 유지 · 확인 정보 확보','확인까지 시간이 필요합니다.'),
           ('verify','관측·현장 확인','columns','box','관측과 확인 임무 후보를 함께 준비','대형 전환 시간이 필요합니다.'),
           ('prepare','항로 확인 준비','v','v','항로 확인과 복귀 여유 확보','함선 감속·우회는 자동 실행하지 않습니다.')]
    for key,title,usv,uav,benefit,cost in specs:
        tasks=[]
        for candidates,task in [(drones,'접근 대상 추가 관측' if scenario=='crossing' else '신고 위치 관측'),(boats,'현장 확인·통신 계획')]:
            if candidates and (candidates is drones or key=='verify'):
                _,id,eta,battery=candidates[0]
                tasks.append({'vehicle':id,'task':task,'eta_seconds':round(eta),'reason':f'배터리 {battery}% · 통신 정상 · 복귀 여유 조건 충족'})
        if key=='prepare' and len(drones)>1:
            _,id,eta,battery=drones[1];tasks.append({'vehicle':id,'task':'대체 항로 관측 계획','eta_seconds':round(eta),'reason':f'배터리 {battery}% · 관측 기체와 중복 배정 없음'})
        result.append({'id':key,'title':title,'formations':{'usv':usv,'uav':uav},'tasks':tasks,'benefit':benefit,'tradeoff':cost,
                       'available':bool(drones) and (key!='verify' or bool(boats)),
                       'validation':'연결·시뮬레이션 잔량·복귀 여유 조건 확인. ETA는 직선 거리 추정이며 경로 안전 검증 전입니다.'})
    return result
