from typing import Literal
from pydantic import BaseModel, EmailStr


class EquityTriggerResponse(BaseModel):
    client_id: str
    prospects_queued: int
    sequence_ids: list[str]


class PostcardResponse(BaseModel):
    listing_id: str
    lob_id: str | None
    address_count: int
    cost: float
    markup_billed: float


class OpenHouseCheckin(BaseModel):
    client_id: str
    attendee_name: str
    attendee_email: EmailStr
    attendee_phone: str
    listing_id: str
    interest_level: Literal["hot", "warm", "cool"] = "warm"


class OpenHouseCheckinResponse(BaseModel):
    lead_id: str
    sequence_started: bool


class ReferralRequestResponse(BaseModel):
    client_id: str
    contacted_count: int
    referral_ids: list[str]


class ReferralRewardResponse(BaseModel):
    referral_id: str
    lob_check_id: str | None
    amount_paid: float
    amount_billed: float


class ReviewRequest(BaseModel):
    closing_client_name: str
    closing_client_phone: str
    closing_client_email: EmailStr


class ReviewRequestResponse(BaseModel):
    client_id: str
    request_id: str
    sms_sid: str | None


class ReviewMonitorResponse(BaseModel):
    clients_scanned: int
    reviews_responded: int
