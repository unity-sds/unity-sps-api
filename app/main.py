import os
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from mangum import Mangum
import asyncio

from .routers import prewarm


app = FastAPI(
    title="Unity SPS REST API",
    version="0.0.1",
    description="Unity SPS Operations",
    root_path=f"/{os.environ.get('STAGE')}/" if "STAGE" in os.environ else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(prewarm.router)

handler = Mangum(app)
