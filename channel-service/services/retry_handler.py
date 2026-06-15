import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def post_with_retry(
    url: str,
    payload: dict[str, Any],
    max_retries: int = 3,
    base_delay: float = 2.0,
) -> bool:
    total_attempts = max_retries + 1

    for attempt in range(1, total_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
            if 200 <= response.status_code < 300:
                return True

            error_message = f"HTTP {response.status_code}: {response.text[:300]}"
        except httpx.HTTPError as exc:
            error_message = str(exc)

        if attempt == total_attempts:
            logger.error(
                "Callback POST failed after all retries",
                extra={"url": url, "attempt": attempt, "error": error_message},
            )
            return False

        delay = base_delay * (2 ** (attempt - 1))
        logger.warning(
            "Callback POST failed; retrying",
            extra={"url": url, "attempt": attempt, "next_delay_seconds": delay, "error": error_message},
        )
        await asyncio.sleep(delay)

    return False
