import asyncio
import os
import uuid
from datetime import datetime
from functools import wraps
from typing import Dict, List

import boto3
import botocore
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from kubernetes import client, config
from pydantic import BaseModel, Field

# Load the Kubernetes configuration
config.load_incluster_config()

REGION_NAME = os.environ.get("AWS_REGION_NAME")
EKS_CLUSTER_NAME = os.environ.get("EKS_CLUSTER_NAME")
VERDI_NODE_GROUP_NAME = os.environ.get("VERDI_NODE_GROUP_NAME")
VERDI_DAEMONSET_NAMESPACE = os.environ.get("VERDI_DAEMONSET_NAMESPACE")
VERDI_DAEMONSET_NAME = os.environ.get("VERDI_DAEMONSET_NAME")

router = APIRouter(
    prefix="/sps",
    tags=["sps"],
    responses={
        200: {"description": "Success"},
        400: {"description": "Invalid parameters"},
        401: {"description": "Unauthorized"},
        500: {"description": "Execution failed"},
    },
)


class PrewarmRequest(BaseModel):
    num_nodes: int


class PrewarmResponse(BaseModel):
    success: bool
    message: str
    prewarm_request_id: str = None


class PrewarmRequestInfo(BaseModel):
    status: str
    last_update_timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    num_nodes: int
    ready_nodes: int
    node_group_update: dict = Field(default=None)
    error: str = Field(default=None)


prewarm_requests_lock = asyncio.Lock()
prewarm_requests_queue: asyncio.Queue = asyncio.Queue()
prewarm_requests: Dict[str, PrewarmRequestInfo] = {}


class ReadyNodesResponse(BaseModel):
    ready_nodes: int


class NodeGroupInfo(BaseModel):
    instance_types: List[str]
    desired_size: int
    min_size: int
    max_size: int
    ready_nodes: int


class HealthCheckResponse(BaseModel):
    message: str


def get_ready_nodes_in_daemonset() -> int:
    v1 = client.AppsV1Api()
    daemonset = v1.read_namespaced_daemon_set(
        VERDI_DAEMONSET_NAME, VERDI_DAEMONSET_NAMESPACE
    )
    return daemonset.status.number_ready


async def scale_nodes(num_nodes: int, request_id: str):
    try:
        eks = boto3.client("eks", region_name=REGION_NAME)

        ready_nodes = get_ready_nodes_in_daemonset()
        async with prewarm_requests_lock:
            prewarm_requests[request_id] = PrewarmRequestInfo(
                status="Running",
                num_nodes=num_nodes,
                ready_nodes=ready_nodes,
            )
        update_response = eks.update_nodegroup_config(
            clusterName=EKS_CLUSTER_NAME,
            nodegroupName=VERDI_NODE_GROUP_NAME,
            scalingConfig={"desiredSize": num_nodes},
        )
        node_group_update_id = update_response["update"]["id"]
        await asyncio.sleep(5)

        while True:
            ready_nodes = get_ready_nodes_in_daemonset()
            describe_update_response = eks.describe_update(
                name=EKS_CLUSTER_NAME,
                nodegroupName=VERDI_NODE_GROUP_NAME,
                updateId=node_group_update_id,
            )
            async with prewarm_requests_lock:
                prewarm_requests[
                    request_id
                ].last_update_timestamp = datetime.utcnow().isoformat()
                prewarm_requests[request_id].ready_nodes = ready_nodes
                prewarm_requests[
                    request_id
                ].node_group_update = describe_update_response["update"]

            if ready_nodes == num_nodes:
                async with prewarm_requests_lock:
                    prewarm_requests[request_id].status = "Succeeded"
                break

            await asyncio.sleep(5)  # Check the DaemonSet status every 5 seconds

    except Exception as e:
        async with prewarm_requests_lock:
            prewarm_requests[request_id].status = "Failed"
            prewarm_requests[request_id].error = str(e)


def is_valid_num_nodes(func):
    @wraps(func)
    async def wrapper(req, *args, **kwargs):
        try:
            eks = boto3.client("eks", region_name=REGION_NAME)
            response = eks.describe_nodegroup(
                clusterName=EKS_CLUSTER_NAME,
                nodegroupName=VERDI_NODE_GROUP_NAME,
            )
            node_group = response["nodegroup"]
            current_desired_size = node_group["scalingConfig"]["desiredSize"]
            max_size = node_group["scalingConfig"]["maxSize"]
            min_size = node_group["scalingConfig"]["minSize"]

            if req.num_nodes > max_size:
                message = f"Requested number of nodes ({req.num_nodes}) is larger than the node group's max size ({max_size})"
                return JSONResponse(
                    status_code=422,
                    content={"message": message},
                )
            elif req.num_nodes < min_size:
                message = f"Requested number of nodes ({req.num_nodes}) is smaller than the node group's min size ({min_size})"
                return JSONResponse(
                    status_code=422,
                    content={"message": message},
                )
            elif req.num_nodes == current_desired_size:
                message = f"Requested number of nodes ({req.num_nodes}) is already equal to the current desired size"
                return JSONResponse(
                    status_code=422,
                    content={"message": message},
                )
            else:
                return await func(req, *args, **kwargs)
        except botocore.exceptions.ClientError as e:
            message = (
                f"Error occurred while validating requested number of nodes: {str(e)}"
            )
            return JSONResponse(
                status_code=500,
                content={"message": message},
            )
        except Exception as e:
            message = f"Unexpected error occurred while validating requested number of nodes: {str(e)}"
            return JSONResponse(
                status_code=500,
                content={"message": message},
            )

    return wrapper


async def process_prewarm_queue():
    while True:
        request_info = await prewarm_requests_queue.get()
        num_nodes = request_info["num_nodes"]
        request_id = request_info["request_id"]
        await scale_nodes(num_nodes, request_id)
        prewarm_requests_queue.task_done()


@router.post("/prewarm")
@is_valid_num_nodes
async def create_prewarm_request(req: PrewarmRequest) -> PrewarmResponse:
    try:
        # Generate a unique request ID
        request_id = str(uuid.uuid4())
        ready_nodes = get_ready_nodes_in_daemonset()
        async with prewarm_requests_lock:
            prewarm_requests[request_id] = PrewarmRequestInfo(
                status="Accepted",
                num_nodes=req.num_nodes,
                ready_nodes=ready_nodes,
            )

        # Add the request to the prewarm_requests_queue
        await prewarm_requests_queue.put(
            {
                "num_nodes": req.num_nodes,
                "request_id": request_id,
            }
        )

        prewarm_response = PrewarmResponse(
            success=True,
            message=f"Prewarm request accepted with ID {request_id}",
            prewarm_request_id=request_id,
        )

    except Exception as e:
        prewarm_response = PrewarmResponse(
            success=False,
            message=f"Unexpected error occurred while creating prewarm request: {str(e)}",
        )

    return prewarm_response


@router.get("/prewarm/{prewarm_request_id}")
async def get_prewarm_status(prewarm_request_id: str) -> PrewarmRequestInfo:
    async with prewarm_requests_lock:
        if prewarm_request_id not in prewarm_requests:
            raise HTTPException(status_code=404, detail="Prewarm request not found")
        response = prewarm_requests[prewarm_request_id]
    return response


@router.get("/ready-nodes")
async def ready_nodes() -> ReadyNodesResponse:
    try:
        ready_nodes = get_ready_nodes_in_daemonset()
        ready_nodes_response = ReadyNodesResponse(ready_nodes=ready_nodes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    return ready_nodes_response


@router.get("/node-group-info")
async def get_node_group_info() -> NodeGroupInfo:
    eks = boto3.client("eks", region_name=REGION_NAME)
    try:
        response = eks.describe_nodegroup(
            clusterName=EKS_CLUSTER_NAME,
            nodegroupName=VERDI_NODE_GROUP_NAME,
        )
        node_group = response["nodegroup"]
        scaling_config = node_group["scalingConfig"]
        instance_types = node_group["instanceTypes"]
        desired_size = scaling_config["desiredSize"]
        min_size = scaling_config["minSize"]
        max_size = scaling_config["maxSize"]
        ready_nodes = get_ready_nodes_in_daemonset()
        node_group_info = NodeGroupInfo(
            instance_types=instance_types,
            desired_size=desired_size,
            min_size=min_size,
            max_size=max_size,
            ready_nodes=ready_nodes,
        )
    except botocore.exceptions.ClientError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error occurred while getting node group info: {str(e)}",
        )
    return node_group_info


@router.get("/health-check")
async def health_check() -> HealthCheckResponse:
    return {"message": "The U-SPS On-Demand API is running and accessible"}
