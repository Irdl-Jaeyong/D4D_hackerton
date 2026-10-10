"""Exclusive vehicle ownership across concurrent, human-approved missions."""
import copy
import math
import time
from defense_scenarios import DEFENSE_SCENARIOS,defense_goal

TERMINAL={'completed','cancelled'}
def active_missions(missions):
    return [m for m in missions.values() if m.get('approved') and m.get('execution',{}).get('status') not in TERMINAL]

def execution_tasks(item):
    return item.get('execution_tasks',item.get('approved',{}).get('tasks',[]))

def planning_pool(vehicles,missions,release_id=None):
    reserved={t['vehicle'] for m in active_missions(missions) if m['id']!=release_id for t in execution_tasks(m)}
    pool=copy.deepcopy(vehicles)
    for v in pool:
        healthy=v['readiness'].get('physical_available',v['readiness']['available'])
        v['readiness']['available']=healthy and v['id'] not in reserved
    return pool

def terminate_for_transfer(item,target_id):
    item['cancel_requested']=True
    item['execution']={**item.get('execution',{}),'status':'cancelled','ended_at':time.time(),'reason':'operator_resource_transfer'}
    item['replaced_by']=target_id
    item['intervention']=None

def replacements(item,pool):
    """Return a dry-run replacement list and remaining missing roles."""
    by_id={v['id']:v for v in pool};ship=by_id.get('SHIP-01');tasks=copy.deepcopy(execution_tasks(item));changes=[];missing=[]
    for index,task in enumerate(tasks):
        if item.get('execution',{}).get('tasks',{}).get(task['vehicle'],{}).get('stage')=='completed':continue
        current=by_id.get(task['vehicle'])
        if current and current['readiness'].get('physical_available',current['readiness']['available']):continue
        kind=task['vehicle'].split('-')[0];goal=task.get('target_world') or item.get('target_world')
        contacts=item.get('threats',[])
        if ship and ship['connected'] and item['scenario'] in DEFENSE_SCENARIOS and contacts:
            contact=contacts[min(task.get('contact_index',0),len(contacts)-1)]
            p=ship['telemetry'];goal=defense_goal(kind,(p['x'],p['y']),(contact['x'],contact['y']),task.get('role_slot',0),contact.get('contact_type','surface'),task.get('goal_policy'))
        choices=[]
        if ship and ship['connected'] and goal:
            for v in pool:
                if v['type']!=kind or not v['readiness']['available']:continue
                p=v['telemetry'];r=v['readiness'];eta=math.hypot(p['x']-goal[0],p['y']-goal[1])/(10 if kind=='UAV' else 3)
                if r['endurance_minutes']*60>=2*eta+300:choices.append((eta+(100-r['battery_percent'])*.8,v['id'],eta))
        if not choices:
            missing.append({'vehicle':task['vehicle'],'kind':kind,'task':task['task'],'contact_index':task.get('contact_index',0)})
            continue
        _,name,eta=min(choices);by_id[name]['readiness']['available']=False
        replacement={**task,'vehicle':name,'replaces':task['vehicle'],'eta_seconds':round(eta),'reason':f"{task['vehicle']} 역할 자동 대체 · 동일 역할·접촉·복귀 여유 확인"}
        if goal:replacement['target_world']=list(goal)
        tasks[index]=replacement
        changes.append({'from':task['vehicle'],'to':name,'task':task['task'],'at':time.time()})
    return tasks,changes,missing

def commit_replacements(item,tasks,changes,missing):
    if changes:
        item['execution_tasks']=tasks
        item['assignment_revision']=item.get('assignment_revision',0)+1
        item.setdefault('reassignments',[]).extend(changes)
        current=item.setdefault('execution',{}).setdefault('tasks',{})
        for change in changes:current.pop(change['from'],None)
        item['execution']['tasks']={name:data for name,data in current.items() if name in {t['vehicle'] for t in tasks}}
    item['intervention']=({'kind':'capacity_shortage','missing':missing,'message':f"대체 기체 {len(missing)}대 부족 · 기존 정상 기체는 임무 유지 · 다른 임무 중단 여부를 결정하세요."} if missing else None)

def reconcile(missions,vehicles):
    # Stable order prioritizes existing higher-risk missions without stealing their vehicles.
    for item in sorted(active_missions(missions),key=lambda m:(-(m.get('risk_at_approval',m.get('risk',{})).get('score') or 0),m['id'])):
        if item.get('cancel_requested'):continue
        pool=planning_pool(vehicles,missions)
        tasks,changes,missing=replacements(item,pool)
        commit_replacements(item,tasks,changes,missing)

def notices(missions):
    rows=[]
    for item in active_missions(missions):
        if item.get('intervention'):
            rows.append({'id':f"mission-{item['id']}",'mission_id':item['id'],'level':'decision','title':item['card']['title'],'message':item['intervention']['message']})
        elif item.get('reassignments'):
            last=item['reassignments'][-1]
            rows.append({'id':f"mission-{item['id']}",'mission_id':item['id'],'level':'info','title':item['card']['title'],'message':f"자동 대체 {len(item['reassignments'])}건 · 최근 {last['from']} → {last['to']} · 추가 승인 없이 기존 역할 유지"})
    return rows
