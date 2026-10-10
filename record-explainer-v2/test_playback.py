import asyncio
import json
import unittest
import httpx
from app import create_app, RECORDS
from playback import FRAMES

class PlaybackGateway:
    async def summarize(self, records):
        return json.dumps({'items':[{'record_id':r['id'],'record_time':r['time'],
            'summary':r['raw'],'supporting_quotes':[r['raw']]} for r in records]})

class PlaybackTests(unittest.IsolatedAsyncioTestCase):
    def client(self,gateway=None):
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(gateway or PlaybackGateway())),base_url='http://testserver')

    async def test_frames_change_ids_and_content_without_mutating_originals(self):
        c=self.client();before=(await c.get('/api/records')).json()
        frames=[(await c.get(f'/api/playback?frame={i}')).json() for i in range(3)]
        self.assertEqual(len({r['id'] for f in frames for r in f['records']}),9)
        self.assertNotEqual(frames[0]['records'][0]['raw'],frames[1]['records'][0]['raw'])
        self.assertEqual(before,(await c.get('/api/records')).json())
        self.assertTrue(all(f['synthetic'] for f in frames))
        record=frames[0]['records'][0]
        self.assertEqual((await c.post(f"/api/records/{record['id']}/read")).status_code,200)
        self.assertFalse((await c.get('/api/playback?frame=1')).json()['records'][0]['read'])

    async def test_summary_is_bound_to_requested_frame_and_invalid_frames_rejected(self):
        c=self.client()
        for i in range(3):
            r=await c.post('/api/summary',json={'playback_frame':i})
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.json()['playback_frame'],i)
            self.assertEqual([x['record_id'] for x in r.json()['items']],[x['id'] for x in FRAMES[i]])
        for value in [-1,3,True,'1']:
            self.assertEqual((await c.post('/api/summary',json={'playback_frame':value})).status_code,422)
        self.assertEqual((await c.get('/api/playback?frame=3')).status_code,422)

    async def test_other_frame_quotes_and_stale_model_result_rejected(self):
        class Stale(PlaybackGateway):
            async def summarize(self,records):return await super().summarize(FRAMES[0])
        self.assertEqual((await self.client(Stale()).post('/api/summary',json={'playback_frame':1})).status_code,502)

    async def test_parallel_frame_reads_do_not_change_pending_summary_snapshot(self):
        started=asyncio.Event();release=asyncio.Event()
        class Slow(PlaybackGateway):
            async def summarize(self,records):
                started.set();await release.wait();return await super().summarize(records)
        c=self.client(Slow());task=asyncio.create_task(c.post('/api/summary',json={'playback_frame':0}))
        await started.wait()
        self.assertEqual((await c.get('/api/playback?frame=2')).json()['frame'],2)
        release.set();r=await task
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['playback_frame'],0)
        self.assertEqual(r.json()['items'][0]['record_id'],FRAMES[0][0]['id'])
