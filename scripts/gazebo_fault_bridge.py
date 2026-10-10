#!/usr/bin/env python3
"""Persistent Gazebo propulsion fault publisher. Only explicit simulated faults."""
import json,os,subprocess,time,urllib.request
os.environ.setdefault('IGN_PARTITION','navis-d4d')
BACKEND_URL = os.environ.get('NAVIS_BACKEND_URL','http://127.0.0.1:18082').rstrip('/')
if __name__=='__main__':
    publisher=None
    try:
        while True:
            try:
                if publisher is None or publisher.poll() is not None:
                    publisher=subprocess.Popen(['/tmp/navis_visual/NavisFaultPublisher'],stdin=subprocess.PIPE,text=True)
                with urllib.request.urlopen(BACKEND_URL+'/api/formations',timeout=.5) as response:s=json.load(response)
                ids=sorted(id for id,kind in s.get('fault_modes',{}).items() if id.startswith('USV-') and kind in ('propulsion','communication'))
                publisher.stdin.write(','.join(ids)+'\n');publisher.stdin.flush()
            except (OSError,ValueError,KeyError):pass
            time.sleep(.5)
    finally:
        if publisher is not None:publisher.terminate()
