"""Generic reliability fault injection, independent of any scenario or contact."""
import random
class RandomFaultTrial:
    def __init__(self,config,now,rng=None):
        self.config=config;self.next_at=now+config['interval_seconds'];self.rng=rng or random.SystemRandom()
    def choose(self,vehicles,history,now):
        if not self.config['enabled'] or now<self.next_at:return None
        self.next_at=now+self.config['interval_seconds']
        if len(history)>=self.config['max_injections'] or sum('fault' in v for v in vehicles)>=self.config['max_faulted']:return None
        candidates=[v['id'] for v in vehicles if v['type']=='UAV' and v['id'] not in history and v.get('connected') and 'fault' not in v and (v.get('telemetry') or {}).get('z',0)>8 and (v.get('readiness') or {}).get('operational_state')!='unavailable' and ((v.get('readiness') or {}).get('battery_percent') or 0)>=35]
        return self.rng.choice(candidates) if candidates else None
