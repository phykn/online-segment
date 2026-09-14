from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src import ROOT
from src.api.router import router
from src.config import config
from src.session import sessions


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
