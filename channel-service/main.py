from contextlib import asynccontextmanager
import logging
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.send import router as send_router
from services.simulator import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger("zuri-channel-service")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "ZURI Channel Service started\n"
        "  delivery_rate=%s, open_rate=%s, click_rate=%s\n"
        "  demo_mode=%s\n"
        "  Ready to accept send requests",
        config.delivery_rate,
        config.open_rate,
        config.click_rate,
        config.demo_mode,
    )
    yield
    logger.info("ZURI Channel Service shutdown complete")


app = FastAPI(
    title="ZURI Channel Service",
    description=(
        "Stub messaging channel service that simulates WhatsApp/SMS/Email/RCS "
        "delivery with realistic async callbacks. Built for Xeno Engineering Assignment."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(send_router, tags=["channel"])


@app.get("/", tags=["health"])
async def root() -> dict[str, str]:
    return {
        "service": "ZURI Channel Service",
        "status": "running",
        "description": "Stub messaging provider - simulates WhatsApp/SMS/Email/RCS delivery",
    }
