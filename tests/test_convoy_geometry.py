"""Regressions for disappearing vessels and the hemispherical patrol envelope."""
import importlib.util
import itertools
import math
import unittest
from pathlib import Path
import xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1]
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
                self.assertAlmostEqual(math.sqrt(sum(v*v for v in relative)),52,places=8)
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
                if name.startswith('SHIP'):half=(29,8,14)
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
