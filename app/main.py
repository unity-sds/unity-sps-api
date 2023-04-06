import asyncio
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from .routers import prewarm

app = FastAPI(
    title="Unity SPS REST API",
    version="0.0.1",
    description="Unity SPS Operations",
    root_path=f"/{os.environ.get('STAGE')}/" if "STAGE" in os.environ else None,
)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(prewarm.process_prewarm_queue())


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(prewarm.router)

handler = Mangum(app)
