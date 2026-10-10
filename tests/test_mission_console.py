import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mission_console import readiness,options

def vehicle(id,x=0,y=0,connected=True):
    v={'id':id,'type':id.split('-')[0],'connected':connected,'telemetry':{'x':x,'y':y,'sim_time':100}}
    v['readiness']=readiness(v)
    return v
class MissionConsole(unittest.TestCase):
    def test_three_operational_states(self):
        self.assertEqual(vehicle('USV-01')['readiness']['operational_state'],'defending')
        self.assertEqual(vehicle('UAV-01')['readiness']['operational_state'],'waiting')
        self.assertEqual(vehicle('UAV-01',connected=False)['readiness']['operational_state'],'unavailable')

    def test_offline_and_low_energy_excluded(self):
        ship=vehicle('SHIP-01');offline=vehicle('UAV-01',connected=False);low=vehicle('UAV-02');low['readiness']=readiness(low,1800)
        plans=options([ship,offline,low],{'usv':'circle','uav':'hemisphere'},'crossing')
        self.assertEqual(len(plans),3)
        self.assertTrue(all(not p['available'] for p in plans))
        self.assertTrue(all(not p['tasks'] for p in plans))
    def test_three_plans_reserve_and_unique_assignment(self):
        vehicles=[vehicle('SHIP-01'),vehicle('UAV-01'),vehicle('UAV-02',100,-90),vehicle('USV-01')]
        plans=options(vehicles,{'usv':'columns','uav':'box'},'crossing')
        self.assertEqual(len(plans),3)
        self.assertTrue(all(p['available'] for p in plans))
        for p in plans:
            ids=[t['vehicle'] for t in p['tasks']]
            self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(plans[0]['tasks'][0]['vehicle'],'UAV-02')
    def test_far_vehicle_without_return_reserve_excluded(self):
        plans=options([vehicle('SHIP-01'),vehicle('UAV-01',100000)],{'usv':'circle','uav':'hemisphere'},'crossing')
        self.assertTrue(all(not p['available'] for p in plans))
    def test_no_fresh_leader_no_plans(self):
        self.assertEqual(options([vehicle('SHIP-01',connected=False)],{'usv':'circle','uav':'hemisphere'},'crossing'),[])
if __name__=='__main__':unittest.main()
