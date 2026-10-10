"""Scenario-specific recommendations must reach the simulation controller."""
import sys,unittest,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mission_console import defense_options,readiness
from defense_scenarios import DEFENSE_SCENARIOS,contacts
from mission_execution import ObservationRun

def fleet():
    result=[]
    for kind,count in [('SHIP',1),('UAV',12),('USV',10)]:
        for i in range(1,count+1):
            v={'id':f'{kind}-{i:02}','type':kind,'connected':True,'telemetry':{'x':0,'y':0,'z':80 if kind=='UAV' else .7}}
            v['readiness']=readiness(v);result.append(v)
    return result

class ScenarioResponses(unittest.TestCase):
    def mission(self,scenario):
        m={'id':1,'scenario':scenario,'scene_origin':{'x':0,'y':0,'sim_time':0},'card':{'offset':[260,0]}}
        m['threats']=contacts(m,0);return m
    def test_all_nine_scenarios_have_three_distinct_titles_and_execution_signatures(self):
        all_titles=[]
        for scenario in DEFENSE_SCENARIOS:
            with self.subTest(scenario=scenario):
                plans=defense_options(fleet(),{'usv':'circle','uav':'hemisphere'},scenario)
                self.assertEqual(len(plans),3)
                self.assertEqual([p['id'] for p in plans],['observe','verify','prepare'])
                self.assertEqual(len({p['title'] for p in plans}),3)
                self.assertTrue(all(p['available'] for p in plans))
                signatures=[]
                for p in plans:
                    m=self.mission(scenario);m['approved']=p
                    run=ObservationRun(m,0,0)
                    for name,t in run.tasks.items():
                        if name.startswith('USV'):
                            x,y=t['target'][:2]
                            self.assertTrue(abs(x)>=100 or abs(y)>=42,'Surface goal must stay outside flagship footprint')
                    self.assertEqual(len({tuple(t['target']) for t in run.tasks.values()}),len(run.tasks),'Tasks must not share one physical goal')
                    signatures.append(tuple(sorted((round(t['target'][0],2),round(t['target'][1],2),t['target'][2]) for t in run.tasks.values())))
                self.assertEqual(len(set(signatures)),3,'Different labels must produce different actual targets')
                all_titles.extend(p['title'] for p in plans)
        self.assertEqual(len(set(all_titles)),27)
    def test_protection_response_keeps_surface_units_near_ship_after_contact_moves(self):
        m=self.mission('fast_approach');m['approved']=defense_options(fleet(),{'usv':'circle','uav':'hemisphere'},m['scenario'])[2]
        r=ObservationRun(m,0,0)
        homes={id:(0,0,.7 if id.startswith('USV') else 80) for id in r.tasks}
        observations={id:(10,(0,0,.7 if id.startswith('USV') else 80)) for id in r.tasks}
        r.step(10,15,homes,observations,{id:True for id in r.tasks},contacts=contacts(m,10))
        for id,t in r.tasks.items():
            if id.startswith('USV'):
                self.assertLess(math.hypot(t['target'][0]-15,t['target'][1]),100)
                self.assertEqual(t['goal_policy'],'protect')
    def test_priority_response_keeps_both_contacts_observed_and_adds_units_to_closest(self):
        c=[{'x':250,'y':100,'contact_type':'surface'},{'x':120,'y':-100,'contact_type':'surface'}]
        p=defense_options(fleet(),{'usv':'circle','uav':'hemisphere'},'multi_approach',contacts=c)[1]
        self.assertGreater(sum(t['contact_index']==1 for t in p['tasks']),sum(t['contact_index']==0 for t in p['tasks']))
        self.assertTrue(all(any(t['contact_index']==i and t['vehicle'].startswith(k) for t in p['tasks']) for i in (0,1) for k in ('UAV','USV')))
    def test_no_available_usvs_blocks_every_option_and_never_assigns_faulty_units(self):
        f=fleet()
        for v in f:
            if v['type']=='USV':v['readiness']['available']=False
        for scenario in DEFENSE_SCENARIOS:
            plans=defense_options(f,{'usv':'circle','uav':'hemisphere'},scenario)
            self.assertTrue(all(not p['available'] for p in plans))
            self.assertTrue(all(not t['vehicle'].startswith('USV') for p in plans for t in p['tasks']))
