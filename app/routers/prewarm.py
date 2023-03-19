from fastapi import APIRouter
from pydantic import BaseModel
import boto3
import botocore
from functools import wraps


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
    request_id: str


class HealthCheckResponse(BaseModel):
    message: str


class ScaleRequest(BaseModel):
    cluster_name: str
    nodegroup_name: str
    desired_size: int


class ScaleResponse(BaseModel):
    success: bool
    message: str
    nodegroup_update: dict


@router.post("/prewarm")
async def create_prewarm_request(req: PrewarmRequest) -> PrewarmResponse:
    return {
        "success": True,
        "message": "Prewarm is not implemented, this request has no effect.",
        "request_id": f"{req.num_nodes}",
    }


@router.get("/prewarm/{request_id}")
async def get_prewarm_request(request_id: str) -> PrewarmResponse:
    return {
        "success": True,
        "message": f"Status for prewarm request ID {request_id}.",
        "request_id": request_id,
    }


@router.delete("/prewarm/{request_id}")
async def delete_prewarm_request(request_id: str) -> PrewarmResponse:
    return {
        "success": True,
        "message": f"Prewarm request ID {request_id} deleted.",
        "request_id": request_id,
    }


@router.get("/health-check")
async def health_check() -> HealthCheckResponse:
    return {"message": "The U-SPS On-Demand API is running and accessible"}


def is_valid_desired_size(func):
    @wraps(func)
    def wrapper(req):
        try:
            eks = boto3.client("eks")
            current_max_size = 0
            response = eks.describe_nodegroup(
                clusterName=req.cluster_name,
                nodegroupName=req.nodegroup_name,
            )
            nodegroup = response["nodegroup"]
            current_max_size = nodegroup["scalingConfig"]["maxSize"]

            # Check if desired size is larger than current max size
            if req.desired_size > current_max_size:
                return ScaleResponse(
                    success=False,
                    message=f"Desired size {req.desired_size} is larger than current max size {current_max_size}",
                    nodegroup_update=None,
                )
            else:
                return func(req)
        except botocore.exceptions.ClientError as e:
            return ScaleResponse(
                success=False,
                message=f"Error occurred while checking desired size: {str(e)}",
                nodegroup_update=None,
            )
        except Exception as e:
            return ScaleResponse(
                success=False,
                message=f"Unexpected error occurred while checking desired size: {str(e)}",
                nodegroup_update=None,
            )

    return wrapper


@router.post("/scale")
@is_valid_desired_size
def update_nodegroup_size(req: ScaleRequest) -> ScaleResponse:
    try:
        eks = boto3.client("eks")
        response = eks.update_nodegroup_config(
            clusterName=req.cluster_name,
            nodegroupName=req.nodegroup_name,
            scalingConfig={"desiredSize": req.desired_size},
        )
        scale_response = ScaleResponse(
            success=True,
            message="Nodegroup updated successfully",
            nodegroup_update=response["update"],
        )
    except botocore.exceptions.ClientError as e:
        scale_response = ScaleResponse(
            success=False,
            message=f"Error occurred while updating nodegroup: {str(e)}",
            nodegroup_update=None,
        )
    except Exception as e:
        scale_response = ScaleResponse(
            success=False,
            message=f"Unexpected error occurred while updating nodegroup: {str(e)}",
            nodegroup_update=None,
        )
    return scale_response
