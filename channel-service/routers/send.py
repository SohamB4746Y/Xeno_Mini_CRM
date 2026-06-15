from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, status

from models.send_request import SendRequest, SendResponse
from services.simulator import simulate_communication

router = APIRouter()


@router.post("/send", response_model=SendResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_messages(
    request: SendRequest,
    background_tasks: BackgroundTasks,
) -> SendResponse:
    job_ids: list[str] = []

    for communication in request.communications:
        job_id = str(uuid4())
        job_ids.append(job_id)
        background_tasks.add_task(
            simulate_communication,
            communication.communication_id,
            communication.channel,
            communication.callback_url,
        )

    return SendResponse(
        accepted=len(request.communications),
        job_ids=job_ids,
        status="accepted",
    )


@router.get("/health")
async def health() -> dict[str, str]:
    return {"service": "zuri-channel-service", "status": "ok"}
