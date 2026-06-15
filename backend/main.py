from contextlib import asynccontextmanager
import logging
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.database import check_database_health
from routers import ai_copilot, analytics, campaigns, customers, orders, receipts, segments

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger("zuri-crm-api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("ZURI CRM API startup complete")
    yield
    logger.info("ZURI CRM API shutdown complete")


app = FastAPI(
    title="ZURI CRM API",
    description=(
        "AI-Native Mini CRM for ZURI - a D2C fashion brand. "
        "Built for Xeno Engineering Take-Home Assignment."
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

app.include_router(customers.router, prefix="/api/customers", tags=["customers"])
app.include_router(orders.router, prefix="/api/orders", tags=["orders"])
app.include_router(segments.router, prefix="/api/segments", tags=["segments"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["campaigns"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(receipts.router, prefix="/api/receipts", tags=["receipts"])
app.include_router(ai_copilot.router, prefix="/api/ai", tags=["ai-copilot"])


@app.get("/", tags=["health"])
async def root() -> dict[str, str]:
    return {"service": "ZURI CRM API", "status": "running", "version": "1.0.0"}


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    db_healthy = await check_database_health()
    return {
        "status": "healthy" if db_healthy else "degraded",
        "database": "connected" if db_healthy else "disconnected",
        "service": "zuri-crm-backend",
    }
