"""Hang up endpoint used by the chat's Hang up button. Owner: Alex."""

from fastapi import APIRouter, HTTPException, status

from app.services import hang_up

router = APIRouter(tags=["calls"])


@router.post("/calls/{call_id}/hang-up", status_code=status.HTTP_202_ACCEPTED)
async def hang_up_call(call_id: str) -> dict:
    """Ends a live call. The `ended` event follows on the call's event stream once the phone line closes."""
    try:
        await hang_up.hang_up(call_id)
    except hang_up.CallNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Call not found.") from None
    except hang_up.CallAlreadyEnded:
        raise HTTPException(status.HTTP_409_CONFLICT, "This call has already ended.") from None
    except hang_up.HangUpUnavailable as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from None
    except hang_up.HangUpFailed as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from None
    return {"status": "hanging_up"}
