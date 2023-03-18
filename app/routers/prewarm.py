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

# Assuming this code is running inside a Kubernetes pod
config.load_incluster_config()

# Initialize the Kubernetes API client
v1 = client.AppsV1Api()


class PrewarmRequest(BaseModel):
    num_nodes: int


class PrewarmResponse(BaseModel):
    success: bool
    message: str
    request_id: str


class HealthCheckResponse(BaseModel):
    message: str


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


@router.post("/scale-up")
async def scale_up(num_nodes: int) -> dict:
    daemonset_name = "verdi"
    daemonset = v1.read_namespaced_daemon_set(daemonset_name, "default")
    daemonset.spec.replicas = num_nodes
    v1.patch_namespaced_daemon_set(
        name=daemonset_name, namespace="default", body=daemonset
    )
    return {"message": f"Scaled {daemonset_name} to {num_nodes} replicas"}


@router.post("/scale-down")
async def scale_down(num_nodes: int) -> dict:
    daemonset_name = "verdi"
    daemonset = v1.read_namespaced_daemon_set(daemonset_name, "default")
    daemonset.spec.replicas = num_nodes
    v1.patch_namespaced_daemon_set(
        name=daemonset_name, namespace="default", body=daemonset
    )
    return {"message": f"Scaled {daemonset_name} to {num_nodes} replicas"}
