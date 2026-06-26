from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes import router as v1_router
from app.core.config import get_settings
from app.core.exceptions import FVEError
from app.core.logging import setup_logging

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.debug)
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://frontend:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix=settings.api_prefix)


@app.exception_handler(FVEError)
async def fve_error_handler(request, exc: FVEError):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=422, content={"error": exc.code, "message": exc.message})


@app.get("/")
async def root():
    return {"name": settings.app_name, "docs": "/docs", "api": settings.api_prefix}
