import sys,unittest,random
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from random_fault_trial import RandomFaultTrial
class RandomFaultTest(unittest.TestCase):
    def fleet(self):return [{'id':f'UAV-{i:02}','type':'UAV','connected':True,'telemetry':{'z':60},'readiness':{'operational_state':'waiting','battery_percent':90}} for i in range(1,6)]
    def test_interval_and_session_limit(self):
        trial=RandomFaultTrial({'enabled':True,'interval_seconds':30,'max_injections':3,'max_faulted':3},now=0,rng=random.Random(1))
        vehicles=self.fleet();history=[]
        self.assertIsNone(trial.choose(vehicles,history,29))
        for t in (30,60,90):
            id=trial.choose(vehicles,history,t);self.assertIsNotNone(id);history.append(id)
            next(v for v in vehicles if v['id']==id)['fault']={'phase':'returning'}
        self.assertEqual(len(set(history)),3);self.assertIsNone(trial.choose(vehicles,history,120))
    def test_stale_grounded_faulted_and_unavailable_excluded(self):
        trial=RandomFaultTrial({'enabled':True,'interval_seconds':1,'max_injections':3,'max_faulted':3},0)
        vehicles=self.fleet();vehicles[0]['connected']=False;vehicles[1]['fault']={};vehicles[2]['telemetry']['z']=1;vehicles[3]['readiness']['operational_state']='unavailable'
        self.assertEqual(trial.choose(vehicles,[],1),'UAV-05')
    def test_missing_data_does_not_create_failure_and_existing_fault_cap_holds(self):
        cfg={'enabled':True,'interval_seconds':1,'max_injections':3,'max_faulted':1}
        vehicles=self.fleet();vehicles[0]['fault']={'phase':'charging'}
        self.assertIsNone(RandomFaultTrial(cfg,0).choose(vehicles,[],1))
        self.assertIsNone(RandomFaultTrial(cfg,0).choose([],[],1))
