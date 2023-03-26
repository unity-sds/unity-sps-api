from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import boto3
import botocore
from kubernetes import client, config
from pydantic import BaseModel, Field
from typing import Dict
from functools import wraps
import os
import asyncio
import uuid


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
    desired_size: int


class PrewarmResponse(BaseModel):
    success: bool
    message: str
    prewarm_request_id: str


class PrewarmRequestInfo(BaseModel):
    status: str
    desired_size: int
    active_nodes: int
    node_group_update: dict = Field(default=None)
    error: str = Field(default=None)


prewarm_requests: Dict[str, PrewarmRequestInfo] = {}


class PrewarmRequestStatusResponse(BaseModel):
    status: str
    desired_size: int
    node_group_update: dict = None
    error: str = None


class ActiveNodesResponse(BaseModel):
    num_active_nodes: int


class HealthCheckResponse(BaseModel):
    message: str


def get_active_nodes_in_daemonset() -> int:
    v1 = client.AppsV1Api()
    daemonset = v1.read_namespaced_daemon_set(
        VERDI_DAEMONSET_NAME, VERDI_DAEMONSET_NAMESPACE
    )
    return daemonset.status.number_ready


async def scale_nodes(desired_size: int, request_id: str):
    try:
        eks = boto3.client("eks", region_name=REGION_NAME)

        active_nodes = get_active_nodes_in_daemonset()
        prewarm_requests[request_id] = PrewarmRequestInfo(
            status="Running",
            desired_size=desired_size,
            active_nodes=active_nodes,
        )

        update_response = eks.update_nodegroup_config(
            clusterName=EKS_CLUSTER_NAME,
            nodegroupName=VERDI_NODE_GROUP_NAME,
            scalingConfig={"desiredSize": desired_size},
        )
        node_group_update_id = update_response["update"]["id"]

        describe_update_response = eks.describe_update(
            name=EKS_CLUSTER_NAME,
            nodegroupName=VERDI_NODE_GROUP_NAME,
            updateId=node_group_update_id,
        )
        prewarm_requests[request_id].node_group_update = describe_update_response[
            "update"
        ]

        await asyncio.sleep(5)

        while True:
            active_nodes = get_active_nodes_in_daemonset()
            describe_update_response = eks.describe_update(
                name=EKS_CLUSTER_NAME,
                nodegroupName=VERDI_NODE_GROUP_NAME,
                updateId=node_group_update_id,
            )
            prewarm_requests[request_id].active_nodes = active_nodes
            prewarm_requests[request_id].node_group_update = describe_update_response[
                "update"
            ]

            if active_nodes == desired_size:
                prewarm_requests[request_id].status = "Succeeded"
                break

            await asyncio.sleep(5)  # Check the DaemonSet status every 5 seconds

    except Exception as e:
        prewarm_requests[request_id].status = "Failed"
        prewarm_requests[request_id].error = str(e)


def is_valid_desired_size(func):
    @wraps(func)
    def wrapper(req, *args, **kwargs):
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

            if req.desired_size > max_size:
                message = f"Desired size {req.desired_size} is larger than the node group's max size {max_size}"
                return JSONResponse(
                    status_code=422,
                    content={"message": message},
                )
            elif req.desired_size < min_size:
                message = f"Desired size {req.desired_size} is smaller than the node group's min size {min_size}"
                return JSONResponse(
                    status_code=422,
                    content={"message": message},
                )
            elif req.desired_size == current_desired_size:
                message = f"Desired size {req.desired_size} is already equal to the current desired size"
                return JSONResponse(
                    status_code=422,
                    content={"message": message},
                )
            else:
                return func(req, *args, **kwargs)
        except botocore.exceptions.ClientError as e:
            message = f"Error occurred while checking desired size: {str(e)}"
            return JSONResponse(
                status_code=500,
                content={"message": message},
            )
        except Exception as e:
            message = f"Unexpected error occurred while checking desired size: {str(e)}"
            return JSONResponse(
                status_code=500,
                content={"message": message},
            )

    return wrapper


@router.post("/prewarm")
@is_valid_desired_size
def create_prewarm_request(
    req: PrewarmRequest, background_tasks: BackgroundTasks
) -> PrewarmResponse:
    try:
        # Generate a unique request ID
        request_id = str(uuid.uuid4())

        # Start the scale_nodes function as a background task
        background_tasks.add_task(scale_nodes, req.desired_size, request_id)

        prewarm_response = PrewarmResponse(
            success=True,
            message=f"Prewarm request accepted with ID {request_id}",
            prewarm_request_id=request_id,
        )

    except Exception as e:
        prewarm_response = PrewarmResponse(
            success=False,
            message=f"Unexpected error occurred while creating prewarm request: {str(e)}",
            prewarm_request_id=None,
        )

    return prewarm_response


@router.get("/prewarm/{prewarm_request_id}")
async def get_prewarm_status(prewarm_request_id: str) -> PrewarmRequestStatusResponse:
    if prewarm_request_id not in prewarm_requests:
        raise HTTPException(status_code=404, detail="Prewarm request not found")

    prewarm_request = prewarm_requests[prewarm_request_id]

    prewarm_status_response = PrewarmRequestStatusResponse(
        status=prewarm_request.status,
        desired_size=prewarm_request.desired_size,
        node_group_update=prewarm_request.node_group_update,
        error=prewarm_request.error,
    )

    return prewarm_status_response


@router.get("/active-nodes")
async def active_nodes() -> ActiveNodesResponse:
    try:
        num_active_nodes = get_active_nodes_in_daemonset()
        active_nodes_response = ActiveNodesResponse(
            num_active_nodes=num_active_nodes,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    return active_nodes_response


@router.get("/health-check")
async def health_check() -> HealthCheckResponse:
    return {"message": "The U-SPS On-Demand API is running and accessible"}
