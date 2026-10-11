"""Bounded random scenario scheduling; all requests use the normal scenario API path."""
import random
from collections import Counter
from defense_scenarios import DEFENSE_SCENARIOS

class ScenarioGenerator:
    def __init__(self,config,rng=None,now=0):
        allowed={'crossing','debris','rescue','fault'}|set(DEFENSE_SCENARIOS)
        if not config['scenarios'] or not set(config['scenarios'])<=allowed:raise ValueError('Unsupported automatic scenario')
        if not config['fault_types'] or not set(config['fault_types'])<={'payload','propulsion','communication'}:raise ValueError('Unsupported fault type')
        if not 0<config['interval_seconds'][0]<=config['interval_seconds'][1]:raise ValueError('Invalid automatic interval')
        if min(config['max_pending'],config['max_per_scenario'],config['max_faulted_vehicles'])<1:raise ValueError('Invalid automatic scenario limits')
        self.config=config
        self.rng=rng or random.Random()
        self.next_at=now+config['initial_delay_seconds']
    def next_request(self,state,now,manual=False):
        if not manual and (not self.config['enabled'] or now<self.next_at):return None
        if not any(v['id']=='SHIP-01' and v['connected'] for v in state['vehicles']):return None
        self.next_at=now+self.rng.uniform(*self.config['interval_seconds'])
        queue=state.get('approval_queue',[])
        if len(queue)>=self.config['max_pending']:return None
        active=state.get('active_mission')
        counts=Counter(m['scenario'] for m in queue+([active] if active else []))
        assigned={t['vehicle'] for t in (active or {}).get('approved',{}).get('tasks',[])}
        healthy=[v['id'] for v in state['vehicles'] if v['type'] in ('UAV','USV') and v['connected'] and not v.get('fault') and v.get('readiness',{}).get('available') and v['id'] not in assigned]
        can_fault=healthy and sum(bool(v.get('fault')) for v in state['vehicles'])<self.config['max_faulted_vehicles']
        choices=[k for k in self.config['scenarios'] if (not manual or k in DEFENSE_SCENARIOS) and counts[k]<self.config['max_per_scenario'] and (k not in ('fault','communication_interference') or can_fault)]
        if not choices:return None
        kind=self.rng.choice(choices);request={'scenario':kind}
        if kind=='fault':request.update(vehicle_id=self.rng.choice(healthy),fault_type=self.rng.choice(self.config['fault_types']))
        return request
