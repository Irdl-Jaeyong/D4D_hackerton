import sys,unittest,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))

class SceneTests(unittest.TestCase):
    def test_scene_is_missing_before_anchor(self):
        from scenario_scene import targets
        self.assertEqual(targets([{'id':1,'scenario':'rescue','scene_origin':None}],None),[])
    def test_targets_distinct_follow_sim_time_and_refresh_keeps_anchor(self):
        from scenario_scene import targets
        origin={'x':100,'y':20,'yaw':0,'sim_time':50}
        missions=[{'id':i,'scenario':kind,'scene_origin':dict(origin),'risk':{'priority':'P2'}} for i,kind in enumerate(['crossing','debris','rescue'],1)]
        start=targets(missions,50);later=targets(missions,70)
        self.assertEqual(len({x['name'] for x in start}),3)
        self.assertGreater(later[0]['y'],start[0]['y'])
        self.assertEqual(later[1]['x'],start[1]['x'])
        self.assertEqual(targets(missions,50),start)
        self.assertEqual(targets(missions[1:],70),later[1:])
        self.assertEqual(targets(missions,500)[0]['y'],20-55)
    def test_multiple_crossing_ships_remain_separate_after_approach(self):
        from scenario_scene import targets
        missions=[{'id':i,'scenario':'crossing','scene_slot':i,'scene_origin':{'x':0,'y':0,'yaw':0,'sim_time':0},'risk':{}} for i in range(3)]
        positions=targets(missions,100)
        self.assertEqual(len({(t['x'],t['y']) for t in positions}),3)
    def test_approved_situation_remains_visible(self):
        from scenario_scene import targets
        m={'id':4,'scenario':'rescue','scene_origin':{'x':0,'y':0,'yaw':0,'sim_time':0},'risk':{'priority':'P1'},'approved':{'id':'verify'}}
        self.assertEqual(targets([m],1)[0]['mission_id'],4)
    def test_all_models_valid_sdf_and_priority_changes_marker(self):
        from scenario_scene import model_sdf
        for scenario in ['crossing','debris','rescue']:
            target={'name':'situation_7','scenario':scenario,'priority':'P0','x':0,'y':0,'z':0,'yaw':0}
            xml=ET.fromstring(model_sdf(target))
            self.assertEqual(xml.find('model').attrib['name'],'situation_7')
            self.assertGreater(len(xml.findall('.//visual')),5)
            self.assertNotEqual(model_sdf(target),model_sdf({**target,'priority':'P3'}))
if __name__=='__main__':unittest.main()
