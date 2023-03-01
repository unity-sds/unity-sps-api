import os
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from mangum import Mangum

from .routers import test, od


app = FastAPI(
        title="Unity On-Demand REST API",
        version="0.0.1",
        description="Unity On-Demand Operations",
        root_path=f"/{os.environ.get('STAGE')}/" if "STAGE" in os.environ else None
)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Hello from the On-Demand REST API!"}


app.include_router(od.router)
app.include_router(test.router)

handler = Mangum(app)
