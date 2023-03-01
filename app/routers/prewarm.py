from fastapi import APIRouter
from pydantic import BaseModel

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


class PrewarmResponse(BaseModel):
    success: bool
    message: str
    request_id: str


@router.post("/prewarm")
async def create_prewarm_request(
    num_nodes: int =10
) -> PrewarmResponse:
    return {
        "success": True,
        "message": "Prewarm is not implemented, this request has no effect.",
        "request_id": "some-request-id",
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
