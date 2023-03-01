from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(
    prefix="/od",
    tags=["on-demand"],
    responses={
        200: {"description": "Success"},
        400: {"description": "Invalid parameters"},
        401: {"description": "Unauthorized"},
        500: {"description": "Execution failed"},
    },
)


class PrewarmResponse(BaseModel):
    success: bool
    message: str
    request_id: str


@router.post("/prewarm")
async def create_prewarm_request(
    gpu_needed: bool = False, disk_space_in_gb: int = 20, mem_size_in_gb: int = 4
) -> PrewarmResponse:
    return {
        "success": True,
        "message": f"Got gpu_needed:{gpu_needed}, disk_space_in_gb: {disk_space_in_gb}, mem_size_in_gb: {mem_size_in_gb}",
        "request_id": "some-request-id",
    }


@router.get("/prewarm/{request_id}")
async def get_prewarm_request(request_id: str) -> PrewarmResponse:
    return {
        "success": True,
        "message": f"Status for prewarm request ID {request_id}",
        "request_id": request_id,
    }
