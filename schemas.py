from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime

class RuleCreate(BaseModel):
    keyword: str
    dm_message: str

class RuleResponse(BaseModel):
    rule_id: str
    keyword: str
    dm_message: str

class StatsResponse(BaseModel):
    sent: int
    failed: int
    queued: int
    duplicates_blocked: int

class SetupRequest(BaseModel):
    name: str
    email: str
    phone: str
    whatsapp: str | None = None
    linkedin_url: str

class SimulateRequest(BaseModel):
    webhook_url: str
    count: int = 500
    duration_seconds: int = 10

class WebhookDataFrom(BaseModel):
    user_id: str
    username: str

class WebhookData(BaseModel):
    comment_id: str
    post_id: Optional[str] = None
    text: Optional[str] = None
    created_at: Optional[datetime] = None
    from_: Optional[WebhookDataFrom] = Field(None, alias="from")

class WebhookPayload(BaseModel):
    event_id: str
    event_type: str
    sent_at: datetime
    data: WebhookData
