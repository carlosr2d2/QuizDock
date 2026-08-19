from pydantic import BaseModel, Field


class ErrorReportCreate(BaseModel):
    path: str = Field(default="/", max_length=500)
    message: str = Field(min_length=1, max_length=2000)
    detail: str | None = Field(default=None, max_length=8000)
    user_agent: str | None = Field(default=None, max_length=500)


class ErrorReportAck(BaseModel):
    status: str = "received"
