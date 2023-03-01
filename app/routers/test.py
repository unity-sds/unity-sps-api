from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(
    prefix="/test",
    tags=["test"],
    responses={
        200: {"description": "Success"},
        400: {"description": "Invalid parameters"},
        401: {"description": "Unauthorized"},
        500: {"description": "Echo execution failed"},
    },
)


class EchoResponse(BaseModel):
    success: bool
    message: str


@router.get("/echo")
async def echo(echo_str: str) -> EchoResponse:
    return {"success": True, "message": f"{echo_str}"}
