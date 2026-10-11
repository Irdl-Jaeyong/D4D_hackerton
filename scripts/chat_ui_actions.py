"""Deterministic UI shortcuts. No approvals, motion or model-generated IDs."""
import re
def actions(message,snapshot):
    result=[]
    ids=re.findall(r'(?:UAV|USV|SHIP)-\d{2}',message.upper())
    if ids and any(w in message for w in ('선택','보여','상태','확인')):
        if any(v['id']==ids[0] for v in snapshot['vehicles']):result.append({'kind':'select_vehicle','vehicle_id':ids[0],'label':ids[0]+' 상태 보기'})
    rank=re.search(r'([12])\s*순위',message)
    queue=snapshot.get('approval_queue',[])[:2]
    if rank and len(queue)>=int(rank[1]):
        m=queue[int(rank[1])-1];result.append({'kind':'review_mission','mission_id':m['id'],'label':rank[1]+'순위 대응안 보기'})
    elif any(w in message for w in ('대응','위험','상황')) and queue:
        result.append({'kind':'review_mission','mission_id':queue[0]['id'],'label':'1순위 대응안 2개 보기'})
    if any(w in message for w in ('상황 생성','상황 만들어','상황 만들어줘','상황 넣어')):
        for key,word in [('debris','부유물'),('rescue','구조'),('crossing','접근 선박')]:
            if word in message:result.append({'kind':'create_scenario','scenario':key,'label':word+' 가상 상황 생성'});break
    return result
