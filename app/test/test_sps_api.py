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
    query_params = {
        "cluster_name": "unity-test-sps-hysds-eks-multinode",
        "node_group_name": "VerdiNodeGroup",
    }
    # prewarm_request_id = "237a3dc8-441d-3ef6-9ebf-2ec7c13ea522"
    prewarm_request_id = "5814f574-02a7-3de3-8d23-cdfa30a5995d"
    # query_params = {
    #     "cluster_name": "cluster-name",
    #     "node_group_name": "node-group-name",
    # }
    # prewarm_request_id = "prewarm-request-id"
    resp = test_client.get(f"/sps/prewarm/{prewarm_request_id}", params=query_params)
    full_url = test_client.get(
        f"/sps/prewarm/{prewarm_request_id}", params=query_params
    ).request.url
    print(full_url)
    print(resp.json())
    assert resp.status_code == 200
    assert "node_group_update" in resp.json()


import requests


def test_get_prewarm_status_requests(test_client):
    query_params = {
        "cluster_name": "unity-test-sps-hysds-eks-multinode",
        "node_group_name": "VerdiNodeGroup",
    }
    prewarm_request_id = "5814f574-02a7-3de3-8d23-cdfa30a5995d"
    url = f"http://a769b73032a074a28b3b0aab0d60d1fd-427874917.us-west-2.elb.amazonaws.com:5002/sps/prewarm/{prewarm_request_id}"
    resp = requests.get(url, params=query_params)
    print(resp.url)
    print(resp.json())
    assert resp.status_code == 200
    assert "node_group_update" in resp.json()
