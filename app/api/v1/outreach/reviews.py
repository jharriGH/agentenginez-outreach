from datetime import datetime, timedelta, timezone
from typing import Any
import httpx
from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.outreach import (
    ReviewRequest,
    ReviewRequestResponse,
    ReviewMonitorResponse,
)
from app.services.openai_svc import generate_review_response
from app.services.resend_svc import send_email
from app.services.supabase import supabase
from app.services.twilio_svc import send_sms

router = APIRouter(prefix="/reviews", tags=["reviews"])
log = get_logger(__name__)


def _gbp_review_link(place_id: str) -> str:
    return f"https://search.google.com/local/writereview?placeid={place_id}"


@router.post("/request/{client_id}", response_model=ReviewRequestResponse)
async def request_review(client_id: str, payload: ReviewRequest) -> ReviewRequestResponse:
    clients = await supabase.select("clients", {"id": f"eq.{client_id}", "select": "*"})
    if not clients:
        raise HTTPException(404, f"client {client_id} not found")
    client = clients[0]
    place_id = client.get("gbp_place_id", "")
    review_link = _gbp_review_link(place_id) if place_id else f"{settings.APP_BASE_URL}/review/{client_id}"
    agent_name = client.get("agent_name", "your agent")

    sms_body = (
        f"Hi {payload.closing_client_name}, it was a joy helping you close. "
        f"Would you take 30 seconds to leave a Google review? {review_link} — {agent_name}"
    )
    sms_sid = None
    try:
        res = send_sms(to=payload.closing_client_phone, body=sms_body)
        sms_sid = res.get("sid")
    except Exception as e:
        log.warning("review_request_sms_failed", err=str(e))

    inserted = await supabase.insert("review_requests", {
        "client_id": client_id,
        "closing_client_name": payload.closing_client_name,
        "closing_client_phone": payload.closing_client_phone,
        "closing_client_email": payload.closing_client_email,
        "review_link": review_link,
        "status": "requested",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    request_id = str(inserted[0].get("id")) if inserted else ""
    log.info("review_requested", client_id=client_id, request_id=request_id)
    return ReviewRequestResponse(client_id=client_id, request_id=request_id, sms_sid=sms_sid)


async def _gbp_list_reviews(account_id: str, location_id: str) -> list[dict[str, Any]]:
    if not settings.GOOGLE_BUSINESS_API_KEY:
        return []
    url = (
        f"https://mybusiness.googleapis.com/v4/accounts/{account_id}"
        f"/locations/{location_id}/reviews"
    )
    headers = {"Authorization": f"Bearer {settings.GOOGLE_BUSINESS_API_KEY}"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        if r.status_code >= 400:
            log.warning("gbp_list_failed", status=r.status_code)
            return []
        return r.json().get("reviews", [])


async def _gbp_post_reply(
    account_id: str, location_id: str, review_id: str, comment: str
) -> bool:
    if not settings.GOOGLE_BUSINESS_API_KEY:
        return False
    url = (
        f"https://mybusiness.googleapis.com/v4/accounts/{account_id}"
        f"/locations/{location_id}/reviews/{review_id}/reply"
    )
    headers = {
        "Authorization": f"Bearer {settings.GOOGLE_BUSINESS_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.put(url, headers=headers, json={"comment": comment})
        if r.status_code >= 400:
            log.warning("gbp_reply_failed", status=r.status_code, body=r.text[:200])
            return False
        return True


@router.post("/monitor-and-respond", response_model=ReviewMonitorResponse)
async def monitor_and_respond() -> ReviewMonitorResponse:
    active = await supabase.select(
        "clients", {"status": "eq.active", "select": "*"}
    )
    responded = 0
    for client in active:
        account_id = client.get("gbp_account_id")
        location_id = client.get("gbp_location_id")
        if not (account_id and location_id):
            continue
        reviews = await _gbp_list_reviews(account_id, location_id)
        for rev in reviews:
            if rev.get("reviewReply"):
                continue
            review_id = rev.get("reviewId") or rev.get("name", "").split("/")[-1]
            existing = await supabase.select(
                "reviews", {"gbp_review_id": f"eq.{review_id}", "select": "id"}
            )
            if existing:
                continue
            stars_map = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}
            rating = stars_map.get(rev.get("starRating", "FIVE"), 5)
            text = rev.get("comment", "")
            try:
                ai_reply = generate_review_response(
                    review_text=text,
                    rating=rating,
                    agent_name=client.get("agent_name", "Agent"),
                    brokerage=client.get("brokerage", ""),
                )
            except Exception as e:
                log.warning("ai_reply_failed", err=str(e))
                continue
            posted = await _gbp_post_reply(account_id, location_id, review_id, ai_reply)
            await supabase.insert("reviews", {
                "client_id": client["id"],
                "gbp_review_id": review_id,
                "rating": rating,
                "review_text": text,
                "ai_response": ai_reply,
                "responded": posted,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            if posted:
                responded += 1
    log.info("review_monitor_complete", scanned=len(active), responded=responded)
    return ReviewMonitorResponse(
        clients_scanned=len(active), reviews_responded=responded
    )
