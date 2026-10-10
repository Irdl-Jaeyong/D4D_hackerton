"""Regressions for disappearing vessels and the hemispherical patrol envelope."""
import importlib.util
import itertools
import sys
import math
import unittest
from pathlib import Path
import xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('convoy',ROOT/'scripts/convoy_motion.py')
convoy=importlib.util.module_from_spec(spec);spec.loader.exec_module(convoy)


def project(p,camera):
    yaw,pitch=camera['yaw'],camera['pitch']
    x,y,z=(p[k]-camera[k] for k in ('x','y','z'))
    along=x*math.cos(yaw)+y*math.sin(yaw)
    depth=along*math.cos(pitch)-z*math.sin(pitch)
    left=-x*math.sin(yaw)+y*math.cos(yaw)
    up=along*math.sin(pitch)+z*math.cos(pitch)
    horizontal=math.tan(convoy.CAMERA['horizontal_fov']/2)
    return .5-left/(2*depth*horizontal),.5-up/(2*depth*horizontal*720/1280),depth


class PatrolGeometry(unittest.TestCase):
    def test_one_full_patrol_remains_on_hemisphere_and_separated(self):
        minimum=float('inf')
        for step in range(0,1521):
            t=step*.1;fleet=convoy.fleet_poses(t);lead=fleet['SHIP-01']
            drones=[p for name,p in fleet.items() if name.startswith('UAV-')]
            self.assertEqual(len(drones),40)
            for p in drones:
                relative=(p['x']-lead['x'],p['y'],p['z']-convoy.MOTION['hemisphere_center_height'])
                self.assertAlmostEqual(math.sqrt(sum(v*v for v in relative)),convoy.MOTION['hemisphere_radius'],places=8)
                self.assertGreater(p['z'],20)
            for a,b in itertools.combinations(drones,2):
                d=math.sqrt(sum((a[k]-b[k])**2 for k in ('x','y','z')))
                minimum=min(minimum,d)
                self.assertGreater(d,5)
        print(f'Minimum UAV spacing sampled over 152 simulation seconds: {minimum:.2f}m')

    def test_all_vehicle_geometry_stays_inside_camera_even_after_long_travel(self):
        for t in [step*.25 for step in range(610)]+[1000,5000,20000]:
            fleet=convoy.fleet_poses(t);camera=fleet['fleet_observer']
            for name,p in fleet.items():
                if name.startswith('SHIP'):half=(80,11,41)
                elif name.startswith('USV'):half=(4,3,3)
                elif name.startswith('UAV'):half=(1,1,1)
                else:continue
                # Conservative bounding corners also catch frame-edge clipping.
                for sx,sy,sz in itertools.product([-1,1],repeat=3):
                    q={k:p[k]+sign*size for k,sign,size in zip(('x','y','z'),(sx,sy,sz),half)}
                    u,v,depth=project(q,camera)
                    self.assertGreater(depth,1)
                    self.assertTrue(.03<u<.97 and .03<v<.97,(name,t,u,v))

    def test_ocean_is_flat_below_every_hull(self):
        ns={'c':'http://www.collada.org/2005/11/COLLADASchema'}
        tree=E.parse(ROOT/'ros_ws/src/navis_sim/models/navis_ocean/meshes/waterlow.dae')
        for array in tree.findall('.//c:float_array',ns):
            if 'POSITION' in array.get('id',''):
                self.assertEqual(set(map(float,array.text.split()[2::3])),{0})
        world=E.parse(ROOT/'ros_ws/src/navis_sim/worlds/prep.sdf')
        mesh=world.find(".//model[@name='ocean']/link/visual/geometry/mesh/uri").text
        self.assertTrue(mesh.endswith('/waterlow.dae'))
        fleet=convoy.fleet_poses(10000)
        self.assertLess(fleet['ocean']['z'],.7-.45*3/2)
        self.assertEqual(fleet['ocean']['x'],fleet['SHIP-01']['x'])

    def test_inspection_camera_is_separate_and_looks_at_selected_aircraft(self):
        import re
        world=E.parse(ROOT/'ros_ws/src/navis_sim/worlds/prep.sdf')
        self.assertIsNotNone(world.find(".//model[@name='inspection_camera']/link/sensor"))
        command=convoy.poses(0,inspection={'id':'UAV-02'})
        match=re.search(r'name:"inspection_camera" position \{x:([-0-9.]+) y:([-0-9.]+) z:([-0-9.]+)',command)
        self.assertIsNotNone(match)
        point=list(map(float,match.groups()));target=convoy.fleet_poses(0)['UAV-02']
        self.assertAlmostEqual(math.dist(point,[target[k] for k in ('x','y','z')]),math.sqrt(136),places=4)
    def test_render_cameras_are_rigidly_attached_to_straight_flagship(self):
        world=E.parse(ROOT/'ros_ws/src/navis_sim/worlds/prep.sdf')
        sensors=world.findall(".//model[@name='SHIP-01']/link/sensor")
        self.assertEqual(len(sensors),2)
        self.assertIsNone(world.find(".//model[@name='fleet_observer']/link/sensor"))
        for mode in ('wide','detail'):
            view=convoy.FLEET['camera_views'][mode]
            sensor=next(s for s in sensors if s.get('name')=='fleet_camera_'+mode)
            local=list(map(float,sensor.find('pose').text.split()))
            self.assertEqual(local[:2],view['offset'][:2])
            self.assertAlmostEqual(local[2]+2.4,view['offset'][2])
            self.assertEqual(local[3:],[0,view['pitch'],view['yaw']])
        initial=convoy.fleet_poses(0)
        for t in [1,20,600,20000]:
            fleet=convoy.fleet_poses(t);ship=fleet['SHIP-01']
            self.assertEqual((ship['y'],ship['yaw'],ship['pitch']),(0,0,0))
            self.assertAlmostEqual(ship['x'],convoy.MOTION['ship_speed']*t)
            self.assertEqual(project(ship,fleet['fleet_observer']),project(initial['SHIP-01'],initial['fleet_observer']))

    def test_wakes_follow_past_stern_and_hull_motion_leaves_camera_level(self):
        for t in [30,100,600]:
            fleet=convoy.fleet_poses(t)
            self.assertEqual(fleet['SHIP-01']['roll'],0)
            self.assertLess(abs(fleet['SHIP-01_hull']['roll']),.011)
            for index in range(10):
                for segment in [0,9,19]:
                    age=(segment+.5)*.9
                    x,y,yaw=convoy.vessel_pose(t-age,index)
                    wake=fleet[f'wake_USV-{index+1:02}_{segment:02}']
                    self.assertAlmostEqual(wake['x'],x-2.5*math.cos(yaw))
                    self.assertAlmostEqual(wake['y'],y-2.5*math.sin(yaw))
                hull=fleet[f'USV-{index+1:02}']
                self.assertLess(abs(hull['z']-.7),.156)
                x,y,yaw=convoy.vessel_pose(t,index)
                a,b,next_yaw=convoy.vessel_pose(t+.01,index)
                self.assertLess(abs(math.atan2(math.sin(next_yaw-yaw),math.cos(next_yaw-yaw)))/.01,.05)

    def test_physics_usv_is_dynamic_and_never_receives_pose_commands(self):
        world=E.parse(ROOT/'ros_ws/src/navis_sim/worlds/prep.sdf')
        boat=world.find(".//model[@name='USV-01']")
        self.assertEqual(boat.find('static').text,'false')
        self.assertEqual(float(boat.find('link/inertial/mass').text),250)
        self.assertEqual(len(boat.findall('link/collision')),2)
        plugin=boat.find("plugin[@name='navis::MaritimeEscort']")
        self.assertIsNotNone(plugin.find('wavefield/wave'))
        for i in range(10):
            self.assertNotIn(f'name:"USV-{i+1:02}"',convoy.poses(60))
            boat=world.find(f".//model[@name='USV-{i+1:02}']")
            self.assertEqual(boat.find('static').text,'false')
        command=convoy.poses(30,history={'USV-01':[(0,0,0,0),(30,30,0,0)]})
        self.assertIn('name:"wake_USV-01_00" position {x:27.05000 y:0.00000',command)

    def test_civilian_crosses_escort_area_without_crossing_flagship_hull(self):
        for t in [0,20,40,60,110,179,180]:
            fleet=convoy.fleet_poses(t);civil=fleet['CIV-01'];ship=fleet['SHIP-01']
            self.assertAlmostEqual(civil['x']-ship['x'],105)
            self.assertAlmostEqual(civil['y'],120-3*(t%180))
            self.assertGreater(civil['x']-ship['x'],80+4)
        self.assertGreater(convoy.fleet_poses(0)['CIV-01']['y'],75)
        self.assertLess(convoy.fleet_poses(70)['CIV-01']['y'],-75)

    def test_figure_eight_has_a_crossing_and_continuous_tangent(self):
        a=convoy.figure_eight(math.pi/2);b=convoy.figure_eight(3*math.pi/2)
        self.assertLess(math.hypot(a[0]-b[0],a[1]-b[1]),1e-8)
        self.assertGreater(abs(a[2]*b[3]-a[3]*b[2]),.1)
        for t in range(300):
            p=convoy.fleet_poses(t*.2);q=convoy.fleet_poses(t*.2+.001)
            for name in p:
                if name.startswith(('SHIP','USV','UAV')):
                    self.assertLess(math.sqrt(sum((p[name][k]-q[name][k])**2 for k in ('x','y','z'))),.02)

if __name__=='__main__':unittest.main()
