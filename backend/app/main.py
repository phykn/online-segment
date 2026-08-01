from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import ROOT
from app.api.router import router
from app.config import config
from app.session import sessions


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    sessions.close()


app = FastAPI(title=config.server.title, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.server.origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

frontend = ROOT.parent / "frontend" / "dist"
if frontend.is_dir():
    app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
