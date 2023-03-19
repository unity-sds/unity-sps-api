import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ..main import app

client = TestClient(app)


@pytest.fixture
def test_client():
    return client


def test_healthcheck(test_client):
    resp = test_client.get(f"/sps/health-check")
    assert resp.status_code == 200


def test_create_prewarm(test_client):
    request = {
        "cluster_name": "cluster-name",
        "node_group_name": "node-group-name",
        "desired_size": 5,
    }
    resp = test_client.post("/sps/prewarm", json=request)
    assert resp.status_code == 200
    assert "success" in resp.json()
    assert "message" in resp.json()
    assert "node_group_update" in resp.json()


def test_get_prewarm_status(test_client):
    # query_params = {
    #     "cluster_name": "unity-test-sps-hysds-eks-multinode",
    #     "node_group_name": "defaultgroupNodeGroup",
    # }
    # prewarm_request_id = "901e88da-c9f9-3f33-855c-142ae66749f3"
    query_params = {
        "cluster_name": "cluster-name",
        "node_group_name": "node-group-name",
    }
    prewarm_request_id = "prewarm-request-id"
    resp = test_client.get(f"/sps/prewarm/{prewarm_request_id}", params=query_params)
    assert resp.status_code == 200
    assert "node_group_update" in resp.json()
