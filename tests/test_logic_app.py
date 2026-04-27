import pytest
import os
from httpx import AsyncClient, ASGITransport
import sys

# Skip PID lock for testing
os.environ['SKIP_PID_LOCK'] = '1'
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

    @pytest.mark.asyncio
    async def test_new_session_on_start(self, client):
        """Verify new session is created on every start."""
        # Start first time
        response1 = await client.post('/api/logic/start')
        data1 = response1.json()
        session1 = data1['startup_data']['session_id']
        assert session1 is not None
        
        # Stop
        await client.post('/api/logic/stop')
        
        # Start second time
        response2 = await client.post('/api/logic/start')
        data2 = response2.json()
        session2 = data2['startup_data']['session_id']
        assert session2 is not None
        
        # Sessions should be different
        assert session1 != session2, "Each start should generate a new session"