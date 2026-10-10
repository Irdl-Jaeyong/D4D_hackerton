import unittest,sys,random
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from auto_scenarios import ScenarioGenerator

class AutoScenarios(unittest.TestCase):
    def setUp(self):
        self.config={'enabled':True,'initial_delay_seconds':5,'interval_seconds':[20,20],'max_pending':6,'max_per_scenario':2,'max_faulted_vehicles':6,'scenarios':['crossing','debris','rescue','fault'],'fault_types':['payload','propulsion','communication']}
        self.state={'vehicles':[{'id':'SHIP-01','type':'SHIP','connected':True},{'id':'UAV-01','type':'UAV','connected':True,'readiness':{'available':True}}],'approval_queue':[],'active_mission':None}
    def test_timing_and_only_configured_scenarios(self):
        g=ScenarioGenerator(self.config,random.Random(1),now=0)
        self.assertIsNone(g.next_request(self.state,4))
        r=g.next_request(self.state,5);self.assertIn(r['scenario'],self.config['scenarios'])
        self.assertIsNone(g.next_request(self.state,24))
        self.assertIsNotNone(g.next_request(self.state,25))
    def test_disconnected_ship_disabled_and_queue_limit_do_not_generate(self):
        g=ScenarioGenerator(self.config,now=0)
        self.state['vehicles'][0]['connected']=False;self.assertIsNone(g.next_request(self.state,5))
        self.state['vehicles'][0]['connected']=True;self.state['approval_queue']=[{'scenario':'rescue'}]*6
        self.assertIsNone(g.next_request(self.state,6))
        self.assertIsNone(ScenarioGenerator({**self.config,'enabled':False},now=0).next_request(self.state,100))
    def test_no_duplicate_kind_flood_and_active_mission_not_replaced(self):
        self.state['approval_queue']=[{'scenario':k} for k in ['crossing','crossing','debris','debris']]
        self.state['active_mission']={'scenario':'rescue','approved':{'tasks':[]}}
        r=ScenarioGenerator({**self.config,'scenarios':['crossing','debris','rescue']},now=0).next_request(self.state,5)
        self.assertEqual(r['scenario'],'rescue');self.assertIsNotNone(self.state['active_mission'])
    def test_fault_uses_only_healthy_unassigned_vehicles_and_limits_faults(self):
        g=ScenarioGenerator({**self.config,'scenarios':['fault']},random.Random(2),now=0)
        self.state['active_mission']={'scenario':'crossing','approved':{'tasks':[{'vehicle':'UAV-01'}]}}
        self.assertIsNone(g.next_request(self.state,5))
        self.state['vehicles'].append({'id':'USV-02','type':'USV','connected':True,'readiness':{'available':True}})
        r=g.next_request(self.state,25);self.assertEqual(r['vehicle_id'],'USV-02');self.assertIn(r['fault_type'],self.config['fault_types'])
        self.state['vehicles'] += [{'id':f'UAV-{i:02}','type':'UAV','connected':True,'fault':{'phase':'charging'}} for i in range(2,8)]
        self.assertIsNone(g.next_request(self.state,45))

    def test_unknown_scenario_and_invalid_interval_are_rejected(self):
        for config in [{**self.config,'scenarios':['unknown']},{**self.config,'interval_seconds':[0,10]}]:
            with self.assertRaises(ValueError):ScenarioGenerator(config,now=0)
    def test_live_config_uses_two_minutes_and_four_pending(self):
        import json
        config=json.loads((Path(__file__).resolve().parents[1]/'config/auto_scenarios.json').read_text())
        self.assertEqual(config['interval_seconds'],[120,120]);self.assertEqual(config['max_pending'],4)
        g=ScenarioGenerator(config,random.Random(1),now=0)
        self.assertIsNone(g.next_request(self.state,9));self.assertIsNotNone(g.next_request(self.state,10))
        self.assertIsNone(g.next_request(self.state,129))
        self.state['approval_queue']=[{'scenario':'rescue'}]*4
        self.assertIsNone(g.next_request(self.state,130))
