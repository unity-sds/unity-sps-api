import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ..main import app

client = TestClient(app)

@pytest.fixture
def test_client():
    return client

@pytest.fixture
def prewarm_request_id(test_client):
    request = {'num_nodes': 10}
    resp = test_client.post('/sps/prewarm', json=request)
    return resp.json()['request_id']
    
def test_healthcheck(test_client):
    resp = test_client.get(f'/sps/health-check')
    assert resp.status_code == 200

def test_create_prewarm(test_client):
    request = {'num_nodes': 10}
    resp = test_client.post('/sps/prewarm', json=request)
    assert resp.status_code == 200
    assert 'message' in resp.json()
    assert 'request_id' in resp.json()

def test_get_prewarm(prewarm_request_id, test_client):
    resp = test_client.get(f'/sps/prewarm/{prewarm_request_id}')
    assert resp.status_code == 200
    assert 'message' in resp.json()
    assert 'request_id' in resp.json()

def test_delete_prewarm(prewarm_request_id, test_client):
    resp = test_client.delete(f'/sps/prewarm/{prewarm_request_id}')
    assert resp.status_code == 200
    assert 'message' in resp.json()
    assert 'request_id' in resp.json()
