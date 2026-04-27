import pytest
from httpx import AsyncClient, ASGITransport
import sys
sys.path.insert(0, 'src')

from main import app


class TestSchedule:
    @pytest.fixture
    async def client(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as ac:
            yield ac

    @pytest.mark.asyncio
    async def test_schedule_endpoint(self, client):
        response = await client.get('/api/schedule')
        assert response.status_code == 200
        data = response.json()
        assert 'enabled' in data
        assert 'start_time' in data
        assert 'end_time' in data
        assert 'within_schedule' in data
        assert 'trading_days' in data

    @pytest.mark.asyncio
    async def test_schedule_times_format(self, client):
        response = await client.get('/api/schedule')
        data = response.json()
        assert len(data['start_time']) == 5
        assert len(data['end_time']) == 5
        assert ':' in data['start_time']
        assert ':' in data['end_time']

    @pytest.mark.asyncio
    async def test_trading_days_list(self, client):
        response = await client.get('/api/schedule')
        data = response.json()
        assert isinstance(data['trading_days'], list)
        assert len(data['trading_days']) > 0