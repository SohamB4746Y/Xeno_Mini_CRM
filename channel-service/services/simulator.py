import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
import logging
import os
import random
from typing import Any

from dotenv import load_dotenv

from models.send_request import CallbackPayload
from services.retry_handler import post_with_retry

# Channel Service Simulator
# Tradeoff: FastAPI BackgroundTasks handles async simulation for demo scale.
# At production scale with millions of messages, this would be replaced with
# a dedicated message queue (Redis Streams or Kafka) with worker processes
# consuming jobs and firing callbacks with guaranteed delivery and dead-letter
# queues for failed callbacks. The callback contract and probability model
# implemented here remain the same regardless of the queue backend.

load_dotenv()

logger = logging.getLogger(__name__)

FAILURE_REASONS = [
    "invalid_phone_number",
    "user_opted_out",
    "network_error",
    "message_too_long",
    "rate_limit_exceeded",
    "carrier_blocked",
    "invalid_email_address",
    "mailbox_full",
]


def _float_env(name: str, default: str) -> float:
    raw_value = os.getenv(name, default)
    try:
        return float(raw_value)
    except ValueError:
        logger.warning("Invalid float environment value; using default", extra={"name": name, "value": raw_value})
        return float(default)


def _bool_env(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _delay_range(prefix: str, default_min: str, default_max: str) -> tuple[float, float]:
    minimum = _float_env(f"{prefix}_MIN", default_min)
    maximum = _float_env(f"{prefix}_MAX", default_max)
    if minimum > maximum:
        logger.warning(
            "Delay minimum exceeded maximum; swapping values",
            extra={"prefix": prefix, "minimum": minimum, "maximum": maximum},
        )
        return maximum, minimum
    return minimum, maximum


@dataclass(frozen=True)
class SimulatorConfig:
    delivery_rate: float
    open_rate: float
    read_rate: float
    click_rate: float
    conversion_rate: float
    failure_rate: float
    sent_delay: tuple[float, float]
    delivery_delay: tuple[float, float]
    open_delay: tuple[float, float]
    read_delay: tuple[float, float]
    click_delay: tuple[float, float]
    conversion_delay: tuple[float, float]
    demo_mode: bool

    @classmethod
    def from_env(cls) -> "SimulatorConfig":
        return cls(
            delivery_rate=_float_env("DELIVERY_RATE", "0.92"),
            open_rate=_float_env("OPEN_RATE", "0.55"),
            read_rate=_float_env("READ_RATE", "0.70"),
            click_rate=_float_env("CLICK_RATE", "0.30"),
            conversion_rate=_float_env("CONVERSION_RATE", "0.12"),
            failure_rate=_float_env("FAILURE_RATE", "0.08"),
            sent_delay=_delay_range("SENT_DELAY", "1", "4"),
            delivery_delay=_delay_range("DELIVERY_DELAY", "3", "12"),
            open_delay=_delay_range("OPEN_DELAY", "15", "60"),
            read_delay=_delay_range("READ_DELAY", "5", "30"),
            click_delay=_delay_range("CLICK_DELAY", "30", "120"),
            conversion_delay=_delay_range("CONVERSION_DELAY", "60", "300"),
            demo_mode=_bool_env("DEMO_MODE"),
        )


config = SimulatorConfig.from_env()


def random_delay(delay_range: tuple[float, float]) -> float:
    if config.demo_mode:
        return random.uniform(0.5, 2.0)
    return random.uniform(delay_range[0], delay_range[1])


def _probability_hit(probability: float) -> bool:
    bounded_probability = min(max(probability, 0.0), 1.0)
    return random.random() < bounded_probability


async def fire_callback(
    callback_url: str,
    communication_id: str,
    event: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    payload = CallbackPayload(
        communication_id=communication_id,
        event=event,
        timestamp=datetime.now(UTC).isoformat(),
        metadata=metadata or {},
    )

    logger.info(
        "Firing channel callback",
        extra={"communication_id": communication_id, "event": event, "callback_url": callback_url},
    )
    succeeded = await post_with_retry(callback_url, payload.model_dump())
    if succeeded:
        logger.info(
            "Channel callback delivered",
            extra={"communication_id": communication_id, "event": event},
        )
    else:
        logger.error(
            "Channel callback failed after retries",
            extra={"communication_id": communication_id, "event": event},
        )


async def simulate_communication(
    communication_id: str,
    channel: str,
    callback_url: str,
) -> None:
    logger.info(
        "Starting communication simulation",
        extra={"communication_id": communication_id, "channel": channel},
    )

    await asyncio.sleep(random_delay(config.sent_delay))
    await fire_callback(callback_url, communication_id, "sent")

    if _probability_hit(config.failure_rate):
        await asyncio.sleep(random_delay(config.delivery_delay))
        await fire_callback(
            callback_url,
            communication_id,
            "failed",
            {"reason": random.choice(FAILURE_REASONS)},
        )
        return

    await asyncio.sleep(random_delay(config.delivery_delay))
    await fire_callback(callback_url, communication_id, "delivered")

    if not _probability_hit(config.open_rate):
        return
    await asyncio.sleep(random_delay(config.open_delay))
    await fire_callback(callback_url, communication_id, "opened")

    if not _probability_hit(config.read_rate):
        return
    await asyncio.sleep(random_delay(config.read_delay))
    await fire_callback(callback_url, communication_id, "read")

    if not _probability_hit(config.click_rate):
        return
    await asyncio.sleep(random_delay(config.click_delay))
    await fire_callback(callback_url, communication_id, "clicked")

    if not _probability_hit(config.conversion_rate):
        return
    await asyncio.sleep(random_delay(config.conversion_delay))
    await fire_callback(callback_url, communication_id, "converted")
