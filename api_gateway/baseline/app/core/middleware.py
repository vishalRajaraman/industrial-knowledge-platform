from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .config import GatewaySettings


def configure_middleware(app: FastAPI, settings: GatewaySettings) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,  # Required for httpOnly cookie auth (credentials: "include")
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=settings.gzip_minimum_size)
