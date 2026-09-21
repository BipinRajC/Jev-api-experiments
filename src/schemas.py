from typing import Any

from pydantic import BaseModel, Field


class SystemOneRequest(BaseModel):
    state: str | dict[str, Any] | list[Any]
    model: str
    questions: dict[str, dict[str, Any]] = Field(min_length=1)

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump()
