from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.outreach import ReferralRequestResponse, ReferralRewardResponse
from app.services.lob import create_check
from app.services.resend_svc import send_email
from app.services.supabase import supabase
from app.services.twilio_svc import send_sms

router = APIRouter(prefix="/referrals", tags=["referrals"])
log = get_logger(__name__)

GIFT_CARD_AMOUNT = 25.00
GIFT_CARD_BILL_AMOUNT = 35.00
TOUCH_INTERVALS_DAYS = [30, 60, 90]


@router.post("/request/{client_id}", response_model=ReferralRequestResponse)
async def request_referrals(client_id: str) -> ReferralRequestResponse:
    clients = await supabase.select("clients", {"id": f"eq.{client_id}", "select": "*"})
    if not clients:
        raise HTTPException(404, f"client {client_id} not found")
    client = clients[0]
    agent_name = client.get("agent_name", "")
    landing = f"{settings.APP_BASE_URL}/refer/{client_id}"

    now = datetime.now(timezone.utc)
    sold = await supabase.select(
        "listings",
        {"client_id": f"eq.{client_id}", "status": "eq.sold", "select": "*"},
    )

    referral_ids: list[str] = []
    contacted = 0
    for listing in sold:
        sold_at_str = listing.get("sold_at") or listing.get("closed_at")
        if not sold_at_str:
            continue
        try:
            sold_at = datetime.fromisoformat(sold_at_str.replace("Z", "+00:00"))
        except Exception:
            continue
        days_since = (now - sold_at).days

        for interval in TOUCH_INTERVALS_DAYS:
            if abs(days_since - interval) > 3:
                continue
            past = await supabase.select(
                "referrals",
                {
                    "listing_id": f"eq.{listing['id']}",
                    "interval_days": f"eq.{interval}",
                    "select": "id",
                },
            )
            if past:
                continue

            past_client_phone = listing.get("buyer_phone") or listing.get("seller_phone")
            past_client_email = listing.get("buyer_email") or listing.get("seller_email")
            past_client_name = (
                listing.get("buyer_name") or listing.get("seller_name") or "there"
            )
            address = listing.get("address_line1", "your home")

            sms_body = (
                f"Hi {past_client_name}, it was a pleasure helping you with {address}. "
                f"Know anyone buying or selling? Reply REFER and I will take great care of them. — {agent_name}"
            )
            try:
                if past_client_phone:
                    send_sms(to=past_client_phone, body=sms_body)
            except Exception as e:
                log.warning("referral_sms_failed", err=str(e))

            try:
                if past_client_email:
                    send_email(
                        to=past_client_email,
                        subject=f"A favor from {agent_name}",
                        html=(
                            f"<p>Hi {past_client_name},</p>"
                            f"<p>It was a pleasure helping you with {address}. "
                            f"If you know anyone buying or selling, please send them my way: "
                            f"<a href='{landing}'>{landing}</a></p>"
                            f"<p>— {agent_name}</p>"
                        ),
                    )
            except Exception as e:
                log.warning("referral_email_failed", err=str(e))

            try:
                inserted = await supabase.insert("referrals", {
                    "client_id": client_id,
                    "listing_id": listing["id"],
                    "interval_days": interval,
                    "referrer_name": past_client_name,
                    "referrer_phone": past_client_phone,
                    "referrer_email": past_client_email,
                    "status": "requested",
                    "created_at": now.isoformat(),
                })
                if inserted:
                    referral_ids.append(str(inserted[0].get("id")))
                contacted += 1
            except Exception as e:
                log.warning("referral_insert_failed", err=str(e))

    log.info("referrals_requested", client_id=client_id, contacted=contacted)
    return ReferralRequestResponse(
        client_id=client_id, contacted_count=contacted, referral_ids=referral_ids
    )


@router.post("/reward/{referral_id}", response_model=ReferralRewardResponse)
async def reward_referral(referral_id: str) -> ReferralRewardResponse:
    rows = await supabase.select(
        "referrals", {"id": f"eq.{referral_id}", "select": "*"}
    )
    if not rows:
        raise HTTPException(404, f"referral {referral_id} not found")
    referral = rows[0]
    client_id = referral.get("client_id")

    clients = await supabase.select("clients", {"id": f"eq.{client_id}", "select": "*"})
    client = clients[0] if clients else {}

    to_address = {
        "name": referral.get("referrer_name", "Friend"),
        "address_line1": referral.get("referrer_address_line1", "1 Main St"),
        "address_city": referral.get("referrer_city", ""),
        "address_state": referral.get("referrer_state", ""),
        "address_zip": referral.get("referrer_zip", ""),
    }
    from_address = {
        "name": client.get("agent_name", "Agent"),
        "address_line1": client.get("brokerage_address", "1 Main St"),
        "address_city": client.get("brokerage_city", ""),
        "address_state": client.get("brokerage_state", ""),
        "address_zip": client.get("brokerage_zip", ""),
    }

    lob_check_id = None
    try:
        bank_account_id = client.get("lob_bank_account_id", "")
        if bank_account_id:
            res = await create_check(
                to_address=to_address,
                from_address=from_address,
                bank_account_id=bank_account_id,
                amount=GIFT_CARD_AMOUNT,
                memo="Referral thank-you",
                message=f"Thank you from {client.get('agent_name','')}!",
            )
            lob_check_id = res.get("id")
    except Exception as e:
        log.warning("lob_check_failed", err=str(e))

    try:
        if referral.get("referrer_email"):
            send_email(
                to=referral["referrer_email"],
                subject="Thanks for the referral!",
                html=(
                    f"<p>Thanks for thinking of me. A $25 gift is on the way.</p>"
                    f"<p>— {client.get('agent_name','')}</p>"
                ),
            )
        if referral.get("referrer_phone"):
            send_sms(
                to=referral["referrer_phone"],
                body=f"Thanks for the referral! A $25 gift is on the way. — {client.get('agent_name','')}",
            )
    except Exception as e:
        log.warning("referral_thanks_failed", err=str(e))

    await supabase.update(
        "referrals",
        {"id": referral_id},
        {"status": "rewarded", "rewarded_at": datetime.now(timezone.utc).isoformat()},
    )
    await supabase.insert("billing_addons", {
        "client_id": client_id,
        "kind": "referral_reward",
        "amount": GIFT_CARD_BILL_AMOUNT,
        "cost": GIFT_CARD_AMOUNT,
        "ref_referral_id": referral_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    log.info("referral_rewarded", referral_id=referral_id, lob_check_id=lob_check_id)
    return ReferralRewardResponse(
        referral_id=referral_id,
        lob_check_id=lob_check_id,
        amount_paid=GIFT_CARD_AMOUNT,
        amount_billed=GIFT_CARD_BILL_AMOUNT,
    )
