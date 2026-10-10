import asyncio
import unittest

import httpx
from app import create_app
from simulator_diagnostics import GazeboDiagnostics, parse_statistics

class DiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_message_does_not_claim_simulator_is_running(self):
        async def missing():raise asyncio.TimeoutError()
        data=await GazeboDiagnostics(reader=missing,cooldown=0).probe()
        self.assertEqual(data["state"],"no_data")
        self.assertIsNone(data["current"])
        self.assertIsNone(data["last_received_at"])

    async def test_connected_then_disconnected_preserves_historical_only(self):
        now=[10.0];responses=[{"simTime":{"sec":"2","nsec":500000000},"iterations":"50"},None]
        async def reader():
            result=responses.pop(0)
            if result is None:raise asyncio.TimeoutError()
            return result
        adapter=GazeboDiagnostics(reader=reader,clock=lambda:now[0],cooldown=0)
        first=await adapter.probe()
        self.assertEqual(first["state"],"connected")
        self.assertEqual(first["current"]["sim_time_seconds"],2.5)
        now[0]+=8
        self.assertIsNone(adapter.snapshot()["current"])
        second=await adapter.probe()
        self.assertEqual(second["state"],"disconnected")
        self.assertIsNone(second["current"])
        self.assertEqual(second["last_received"],first["current"])
        self.assertEqual(second["last_received_at"],first["last_received_at"])

    async def test_diagnostic_api_does_not_change_synthetic_records(self):
        async def reader():return {"simTime":{"sec":"1"}}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(diagnostics=GazeboDiagnostics(reader=reader))),base_url="http://testserver") as client:
            before=(await client.get('/api/records')).json()
            response=await client.get('/api/simulator')
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['source'],'actual_gazebo_statistics')
            self.assertEqual((await client.get('/api/records')).json(),before)
            self.assertEqual((await client.post('/api/simulator')).status_code,405)

    async def test_invalid_data_and_concurrent_probes(self):
        calls=[]
        async def reader():calls.append(1);await asyncio.sleep(.01);return {"simTime":{"sec":"3"}}
        adapter=GazeboDiagnostics(reader=reader)
        a,b=await asyncio.gather(adapter.probe(),adapter.probe())
        self.assertEqual(len(calls),1)
        self.assertEqual(a['current'],b['current'])
        for data in [{}, {"simTime":[]}, {"simTime":{"sec":"-1"}}, {"simTime":{"nsec":1000000000}}, {"simTime":{},"realTimeFactor":"nan"}]:
            with self.assertRaises((ValueError,TypeError,KeyError)):parse_statistics(data)

if __name__=='__main__':unittest.main(verbosity=2)
