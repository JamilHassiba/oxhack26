"""Shared request/response models. The contract between Jamil, Alex and Evan:
change these together and regenerate the frontend client."""

from typing import Annotated

from pydantic import BaseModel, StringConstraints


class ChatRequest(BaseModel):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class ChatResponse(BaseModel):
    task_id: str
