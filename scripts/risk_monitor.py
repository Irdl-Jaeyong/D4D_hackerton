"""Explainable demo thresholds over current telemetry; no inferred hostile intent."""
import math

def assess(vehicles):
    risks=[]
    def add(v,kind,score,title,evidence):
        risks.append({'id':v['id']+':'+kind,'vehicle':v['id'],'kind':kind,'score':score,
                      'title':title,'evidence':evidence,'telemetry':v.get('telemetry')})
    for v in vehicles:
        r=v['readiness'];p=v.get('telemetry') or {};id=v['id']
        if not v['connected']:
            add(v,'link',100,'통신 상태 확인 필요',f'{id} 최신 위치 미수신 · 마지막 수신 {v.get("age_seconds")}초');continue
        if v.get('fault') and not v.get('automatic_return'):
            phase=v['fault'].get('phase','pending')
            phase_label={'pending':'고장 처리 대기','unstable':'자세 불안정','returning':'복귀 중','landing':'착함 중','charging':'갑판 충전·정비 중','moored':'함선 측면 정비 대기','emergency_descent':'추진 정지 · 비상 하강','ditched':'수면 도달 · 회수 필요','drifting':'추진 차단 · 표류','failsafe_return':'통신 두절 · 비상 복귀 시연'}.get(phase,phase)
            add(v,'fault',95 if phase not in ('charging','moored') else 65,'추진 고장 · 긴급 회수' if v.get('fault_type')=='propulsion' else '고장 기체 복귀·정비',f'{id} · {phase_label} · 임무 배정 제외 · 모의 고장')
        tilt=max(abs(p.get('roll',0)),abs(p.get('pitch',0)))
        if tilt>.22:add(v,'unstable',90,'자세 불안정',f'{id} 최대 기울기 {math.degrees(tilt):.1f}° · 시연 기준 12.6° 초과')
        battery=r.get('battery_percent')
        if battery is not None and battery<35:add(v,'battery',85,'복귀 잔량 부족',f'{id} 추정 배터리 {battery}% · 35% 기준 미만')
    live=[v for v in vehicles if v['connected'] and v['type']=='UAV' and not v.get('fault')]
    for i,v in enumerate(live):
        p=v['telemetry']
        for other in live[i+1:]:
            q=other['telemetry'];distance=math.dist([p[k] for k in ('x','y','z')],[q[k] for k in ('x','y','z')])
            if distance<5:add(v,'separation-'+other['id'],98,'기체 간격 부족',f'{v["id"]} / {other["id"]} 3D 간격 {distance:.1f}m · 5m 시연 기준')
    return sorted(risks,key=lambda r:(-r['score'],r['id']))
