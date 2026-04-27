import pytest
import os
from httpx import AsyncClient, ASGITransport
import sys

# Skip PID lock for testing
os.environ['SKIP_PID_LOCK'] = '1'
sys.path.insert(0, 'src')

from main import app


class TestPages:
    @pytest.fixture
    async def client(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as ac:
            yield ac

    @pytest.mark.asyncio
    async def test_root_page(self, client):
        response = await client.get('/')
        assert response.status_code == 200
        assert 'text/html' in response.headers['content-type']

    @pytest.mark.asyncio
    async def test_logic_page(self, client):
        response = await client.get('/logic')
        assert response.status_code == 200
        assert 'text/html' in response.headers['content-type']

    @pytest.mark.asyncio
    async def test_logs_endpoint(self, client):
        response = await client.get('/api/admin/logs')
        assert response.status_code == 200
        data = response.json()
        assert 'content' in data
        assert 'status' in data

    @pytest.mark.asyncio
    async def test_memory_endpoint(self, client):
        response = await client.get('/api/memory')
        assert response.status_code == 200
        data = response.json()
        assert 'running' in data
        assert 'schedule_enabled' in data

    @pytest.mark.asyncio
    async def test_home_redirect(self, client):
        response = await client.get('/home', follow_redirects=False)
        assert response.status_code == 307  # Redirect