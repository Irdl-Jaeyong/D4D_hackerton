import json
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from llm_dialogue import generate


class FleetSummaryTests(unittest.IsolatedAsyncioTestCase):
    def fixture(self):
        vehicles = [{'id': f'{kind}-{i:02}', 'type': kind, 'connected': True,
                     'readiness': {'operational_state': 'waiting', 'reason': '배정 가능'}}
                    for kind, count in [('SHIP', 1), ('UAV', 40), ('USV', 10)]
                    for i in range(1, count + 1)]
        return {'vehicles': vehicles}, {'answer_type': 'status', 'reply': '현재 상태', 'recommendations': []}

    async def call_model(self, text):
        snapshot, baseline = self.fixture()
        response = MagicMock()
        response.json.return_value = {'message': {'content': json.dumps({'explanation': text, 'answers': []})}}
        client = AsyncMock()
        client.post.return_value = response
        client.__aenter__.return_value = client
        with patch('llm_dialogue.httpx.AsyncClient', return_value=client):
            return await generate('전체 기체 상태를 요약해줘', snapshot, baseline, 'http://local', 'test')

    async def test_ship_is_not_counted_as_usv(self):
        result = await self.call_model('모든 기체가 연결되어 있어요.')
        self.assertIn('함선 1척 · UAV 40대 · USV 10대', result['reply'])
        self.assertIn('연결: 51/51대', result['reply'])
        self.assertTrue(result['llm_used'])

    async def test_rejects_observed_incorrect_model_inventory(self):
        with self.assertRaises(ValueError):
            await self.call_model('현재 11대의 USV와 39대의 UAV가 연결되어 있습니다.')
