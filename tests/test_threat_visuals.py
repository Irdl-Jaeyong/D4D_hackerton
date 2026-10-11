import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from threat_visuals import view
class ThreatVisuals(unittest.TestCase):
    def setUp(self):
        self.vehicles=[{'id':'UAV-01','type':'UAV','connected':True,'telemetry':{'x':10,'y':0,'z':60}}]
        self.contacts=[{'mission_id':1,'contact_type':'air','x':100,'y':0,'z':70,'name':'situation_1'}]
        self.missions={1:{'id':1,'scene_origin':{'sim_time':0}}}
    def test_only_simulated_air_surface_threats_target_fresh_drone(self):
        result=view(self.vehicles,self.contacts,self.missions,1)
        self.assertEqual(result['items'][0]['target'],'UAV-01')
        self.assertEqual(result['items'][0]['status'],'대응 대기')
        self.assertEqual(result['items'][0]['outcome'],'피해·방어 성공 미판정')
        self.assertTrue(result['effects'])
        self.assertEqual(view(self.vehicles,[{**self.contacts[0],'contact_type':'underwater'}],self.missions,1)['effects'],[])
        self.vehicles[0]['connected']=False
        self.assertEqual(view(self.vehicles,self.contacts,self.missions,1)['effects'],[])
    def test_observation_status_requires_fresh_unblocked_assigned_vehicle(self):
        self.missions[1]['approved']={'tasks':[{'vehicle':'UAV-01'}]}
        self.missions[1]['execution']={'tasks':{'UAV-01':{'stage':'tracking','blocked':False}}}
        result=view(self.vehicles,self.contacts,self.missions,1)
        self.assertEqual(result['items'][0]['status'],'접촉 관측 유지')
        self.missions[1]['execution']['tasks']['UAV-01']['blocked']=True
        self.assertEqual(view(self.vehicles,self.contacts,self.missions,1)['items'][0]['status'],'대응 상태 확인 필요')
    def test_effect_moves_by_sim_time_without_mutating_vehicle(self):
        a=view(self.vehicles,self.contacts,self.missions,.2);b=view(self.vehicles,self.contacts,self.missions,1)
        self.assertNotEqual(a['effects'][0]['x'],b['effects'][0]['x'])
        self.assertNotIn('fault',self.vehicles[0])
        self.assertEqual(view(self.vehicles,self.contacts,self.missions,None)['effects'],[])
