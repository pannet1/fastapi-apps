import pytest
from httpx import AsyncClient, ASGITransport
import sys
sys.path.insert(0, 'src')

from main import app


class TestLogicApp:
    @pytest.fixture
    async def client(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as ac:
            yield ac

    @pytest.mark.asyncio
    async def test_start_logic(self, client):
        response = await client.post('/api/logic/start')
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'started'
        assert 'startup_data' in data

    @pytest.mark.asyncio
    async def test_status_when_stopped(self, client):
        await client.post('/api/logic/stop')
        response = await client.get('/api/logic/status')
        assert response.status_code == 200
        data = response.json()
        assert data['running'] == False

    @pytest.mark.asyncio
    async def test_stop_logic(self, client):
        await client.post('/api/logic/start')
        response = await client.post('/api/logic/stop')
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'stopped'

    @pytest.mark.asyncio
    async def test_cannot_stop_when_not_running(self, client):
        await client.post('/api/logic/stop')
        response = await client.post('/api/logic/stop')
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'already_stopped'

    @pytest.mark.asyncio
    async def test_get_data_when_stopped(self, client):
        await client.post('/api/logic/stop')
        response = await client.get('/api/logic/data')
        # Returns 503 when logic not running
        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_pause_logic(self, client):
        response = await client.post('/api/logic/pause?reason=test&duration=10')
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'paused'
        assert data['reason'] == 'test'