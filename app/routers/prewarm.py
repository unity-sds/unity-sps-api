from fastapi import APIRouter, Query, HTTPException

# from typing import Dict, Any
from pydantic import BaseModel  # , Field, root_validator, validator
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
    cluster_name: str
    node_group_name: str
    desired_size: int


class PrewarmResponse(BaseModel):
    success: bool
    message: str
    node_group_update: dict


# class PrewarmStatusRequest(BaseModel):
#     prewarm_request_id: str
#     cluster_name: str = Query(..., description="Name of the EKS cluster.")
#     node_group_name: str = Query(..., description="Name of the EKS node group.")


class PrewarmStatusResponse(BaseModel):
    node_group_update: dict


class HealthCheckResponse(BaseModel):
    message: str


def is_valid_desired_size(func):
    @wraps(func)
    def wrapper(req):
        try:
            eks = boto3.client("eks", region_name="us-west-2")
            response = eks.describe_nodegroup(
                clusterName=req.cluster_name,
                nodegroupName=req.node_group_name,
            )
            node_group = response["nodegroup"]
            max_size = node_group["scalingConfig"]["maxSize"]
            min_size = node_group["scalingConfig"]["minSize"]

            if req.desired_size > max_size:
                return PrewarmResponse(
                    success=False,
                    message=f"Desired size {req.desired_size} is larger than the node group's max size {max_size}",
                    node_group_update={},
                )
            elif req.desired_size < min_size:
                return PrewarmResponse(
                    success=False,
                    message=f"Desired size {req.desired_size} is smaller than the node group's min size {min_size}",
                    node_group_update={},
                )
            else:
                return func(req)
        except botocore.exceptions.ClientError as e:
            return PrewarmResponse(
                success=False,
                message=f"Error occurred while checking desired size: {str(e)}",
                node_group_update={},
            )
        except Exception as e:
            return PrewarmResponse(
                success=False,
                message=f"Unexpected error occurred while checking desired size: {str(e)}",
                node_group_update={},
            )

    return wrapper


@router.post("/prewarm")
@is_valid_desired_size
def create_prewarm_request(req: PrewarmRequest) -> PrewarmResponse:
    try:
        eks = boto3.client("eks", region_name="us-west-2")
        response = eks.update_nodegroup_config(
            clusterName=req.cluster_name,
            nodegroupName=req.node_group_name,
            scalingConfig={"desiredSize": req.desired_size},
        )
        prewarm_response = PrewarmResponse(
            success=True,
            message="Node group updated successfully",
            node_group_update=response["update"],
        )
    except botocore.exceptions.ClientError as e:
        prewarm_response = PrewarmResponse(
            success=False,
            message=f"Error occurred while updating node group: {str(e)}",
            node_group_update={},
        )
    except Exception as e:
        prewarm_response = PrewarmResponse(
            success=False,
            message=f"Unexpected error occurred while updating node group: {str(e)}",
            node_group_update={},
        )
    return prewarm_response


@router.get("/prewarm/{prewarm_request_id}")
async def get_prewarm_status(
    prewarm_request_id: str,
    cluster_name: str = Query(..., description="Name of the EKS cluster"),
    node_group_name: str = Query(..., description="Name of the EKS node group"),
) -> PrewarmStatusResponse:
    try:
        eks = boto3.client("eks", region_name="us-west-2")
        response = eks.describe_update(
            name=cluster_name,
            nodegroupName=node_group_name,
            updateId=prewarm_request_id,
        )
        prewarm_status_response = PrewarmStatusResponse(
            node_group_update=response["update"],
        )
    except botocore.exceptions.ClientError as e:
        raise HTTPException(status_code=400, detail=f"Bad request: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    return prewarm_status_response


@router.get("/health-check")
async def health_check() -> HealthCheckResponse:
    return {"message": "The U-SPS On-Demand API is running and accessible"}
