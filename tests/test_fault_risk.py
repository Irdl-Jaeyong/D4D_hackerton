import math,unittest
from scripts.fault_motion import FaultReturn,deck_slot
from scripts.risk_monitor import assess

class FaultRiskTests(unittest.TestCase):
    def test_landing_is_gradual_then_stays_on_unique_deck_slot(self):
        run=FaultReturn(1,[60,50,80],0)
        old=list(run.point);phases=set()
        for i in range(1,2001):
            p=run.step(i*.1,.1);phases.add(run.phase)
            self.assertLessEqual(abs(p[2]-old[2]),.200001)
            self.assertLessEqual(math.dist(p[:2],old[:2]),math.sqrt(2)*.400001)
            old=list(p)
        self.assertTrue({'unstable','returning','landing','charging'}<=phases)
        self.assertEqual(run.point,deck_slot(1))
        self.assertEqual(run.step(1000,.1),deck_slot(1))
        self.assertEqual(len({tuple(deck_slot(i)) for i in range(1,41)}),40)
    def test_no_loss_of_altitude_while_returning_across_ship(self):
        run=FaultReturn(2,[40,-60,85],0)
        for i in range(1,120):run.step(i*.1,.1)
        self.assertEqual(run.point[2],85)
        self.assertEqual(run.phase,'returning')
    def test_risks_rank_missing_telemetry_and_detect_tilt(self):
        vehicles=[{'id':'UAV-01','type':'UAV','connected':True,'telemetry':{'x':0,'y':0,'z':80,'roll':.3},'readiness':{'battery_percent':80}},
                  {'id':'USV-01','type':'USV','connected':False,'age_seconds':12,'telemetry':None,'readiness':{'battery_percent':80}}]
        result=assess(vehicles)
        self.assertEqual(result[0]['kind'],'link')
        self.assertEqual(result[1]['kind'],'unstable')
    def test_docked_fault_does_not_rank_above_in_flight_fault(self):
        base={'type':'UAV','connected':True,'telemetry':{'x':0,'y':0,'z':3.8},'readiness':{'battery_percent':80}}
        result=assess([{**base,'id':'UAV-01','fault':{'phase':'charging'}},{**base,'id':'UAV-02','fault':{'phase':'returning'}}])
        self.assertEqual(result[0]['vehicle'],'UAV-02')

if __name__=='__main__':unittest.main()
