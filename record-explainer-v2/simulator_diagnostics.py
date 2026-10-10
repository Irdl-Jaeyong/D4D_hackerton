"""Read-only Gazebo statistics; never publishes or invokes a service."""
import asyncio
from datetime import datetime, timezone
import json
import math
import os
import shutil
import signal
import time

WORLD = "civil_harbor_demo"
PARTITION = "d4d_civil_harbor"
TOPIC = f"/world/{WORLD}/stats"

async def read_statistics():
    binary = shutil.which("gz")
    if not binary:
        raise RuntimeError("Gazebo CLI가 없습니다.")
    env = os.environ.copy()
    env.update(GZ_PARTITION=PARTITION, GZ_IP="127.0.0.1")
    child = await asyncio.create_subprocess_exec(binary,"topic","-e","--json-output","-n","1","-t",TOPIC,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, env=env, start_new_session=True)
    try:
        output, _ = await asyncio.wait_for(child.communicate(), 3)
        if child.returncode:
            raise RuntimeError("Gazebo 통계 구독에 실패했습니다.")
        return json.loads(output.decode())
    finally:
        if child.returncode is None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(child.wait(), 2)
            except asyncio.TimeoutError:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await child.wait()

def parse_statistics(message):
    if not isinstance(message, dict) or not isinstance(message.get("simTime"), dict):
        raise ValueError("Invalid statistics envelope")
    sim = message["simTime"]
    sec, nsec = int(sim.get("sec", 0)), int(sim.get("nsec", 0))
    iterations = int(message.get("iterations", 0))
    factor = float(message.get("realTimeFactor", 0))
    paused = message.get("paused", False)
    if sec < 0 or not 0 <= nsec < 1_000_000_000 or iterations < 0 or not math.isfinite(factor) or factor < 0 or not isinstance(paused,bool):
        raise ValueError("Invalid statistics")
    return {"sim_time_seconds":sec+nsec/1e9,"iterations":iterations,"real_time_factor":factor,"paused":paused}

class GazeboDiagnostics:
    def __init__(self, reader=read_statistics, clock=time.monotonic, cooldown=1):
        self.reader,self.clock,self.cooldown=reader,clock,cooldown
        self.last=None
        self.received_clock=None
        self.received_at=None
        self.attempted_clock=None
        self.connected=False
        self.lock=asyncio.Lock()

    def snapshot(self):
        age=None if self.received_clock is None else max(0,self.clock()-self.received_clock)
        fresh=self.connected and age is not None and age <= 5
        return {"source":"actual_gazebo_statistics", "world":WORLD, "topic":TOPIC,
                "state":"connected" if fresh else "disconnected" if self.last else "no_data",
                "current":self.last if fresh else None, "last_received":self.last,
                "last_received_at":self.received_at, "age_seconds":None if age is None else round(age,3),
                "checked_at":datetime.now(timezone.utc).isoformat(),
                "note":"실제 통계 수신만 확인합니다. 프로세스 실행 여부·기체 연결·임무 수행을 확인하는 기능이 아닙니다."}

    async def probe(self):
        async with self.lock:
            if self.attempted_clock is not None and self.clock()-self.attempted_clock < self.cooldown:
                return self.snapshot()
            try:
                value=parse_statistics(await self.reader())
            except (OSError, RuntimeError, asyncio.TimeoutError, ValueError, KeyError, TypeError):
                self.connected=False
            else:
                self.last=value;self.received_clock=self.clock()
                self.received_at=datetime.now(timezone.utc).isoformat();self.connected=True
            self.attempted_clock=self.clock()
            return self.snapshot()
