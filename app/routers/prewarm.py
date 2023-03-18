from fastapi import APIRouter
from pydantic import BaseModel
from kubernetes import client, config

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
    num_nodes: int
    daemonset_name: str
    namespace: str = "default"


class ScaleResponse(BaseModel):
    success: bool
    message: str
    num_nodes: int


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


@router.post("/scale")
async def scale(request: ScaleRequest) -> ScaleResponse:
    try:
        config.load_incluster_config()
        v1 = client.AppsV1Api()

        daemonset = v1.read_namespaced_daemon_set(
            request.daemonset_name, request.namespace
        )
        if request.num_nodes == daemonset.spec.replicas:
            scale_response = ScaleResponse(
                success=True,
                message=f"{request.daemonset_name} is already scaled to {request.num_nodes} replicas",
                num_nodes=request.num_nodes,
            )

        daemonset.spec.replicas = request.num_nodes
        v1.patch_namespaced_daemon_set(
            name=request.daemonset_name, namespace=request.namespace, body=daemonset
        )
        message = f"Scaled {request.daemonset_name} to {request.num_nodes} replicas in {request.namespace} namespace"
        scale_response = ScaleResponse(
            success=True, message=message, num_nodes=request.num_nodes
        )
    except Exception as e:
        error_msg = f"Failed to scale {request.daemonset_name} to {request.num_nodes} replicas in {request.namespace} namespace: {str(e)}"
        scale_response = ScaleResponse(
            success=False, message=error_msg, num_nodes=request.num_nodes
        )

    return scale_response
