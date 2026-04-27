from datetime import datetime, timezone
import io
from fastapi import APIRouter, HTTPException
import qrcode

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.outreach import OpenHouseCheckin, OpenHouseCheckinResponse
from app.services.n8n import n8n
from app.services.r2 import upload_bytes
from app.services.supabase import supabase
from app.services.twilio_svc import send_sms

router = APIRouter(prefix="/open-house", tags=["open-house"])
log = get_logger(__name__)


@router.post("/checkin", response_model=OpenHouseCheckinResponse)
async def open_house_checkin(payload: OpenHouseCheckin) -> OpenHouseCheckinResponse:
    clients = await supabase.select("clients", {"id": f"eq.{payload.client_id}", "select": "*"})
    if not clients:
        raise HTTPException(404, f"client {payload.client_id} not found")
    client = clients[0]

    lead_row = {
        "client_id": payload.client_id,
        "listing_id": payload.listing_id,
        "name": payload.attendee_name,
        "email": payload.attendee_email,
        "phone": payload.attendee_phone,
        "interest_level": payload.interest_level,
        "source": "open_house",
        "status": "new",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    inserted = await supabase.insert("leads", lead_row)
    lead_id = str(inserted[0].get("id")) if inserted else ""

    sequence_started = False
    try:
        await n8n.fire_webhook(
            "open-house-followup",
            {
                "lead_id": lead_id,
                "client_id": payload.client_id,
                "attendee": payload.model_dump(),
                "agent": {
                    "name": client.get("agent_name"),
                    "phone": client.get("agent_phone"),
                    "email": client.get("agent_email"),
                },
            },
        )
        sequence_started = True
    except Exception as e:
        log.warning("n8n_openhouse_webhook_failed", err=str(e))

    if payload.interest_level == "hot" and client.get("agent_phone"):
        try:
            send_sms(
                to=client["agent_phone"],
                body=(
                    f"HOT LEAD at open house: {payload.attendee_name} | "
                    f"{payload.attendee_phone} | listing {payload.listing_id}"
                ),
            )
        except Exception as e:
            log.warning("hot_lead_sms_failed", err=str(e))

    log.info("open_house_checkin", lead_id=lead_id, level=payload.interest_level)
    return OpenHouseCheckinResponse(lead_id=lead_id, sequence_started=sequence_started)


@router.get("/qr/{listing_id}")
async def open_house_qr(listing_id: str) -> dict[str, str]:
    target = f"{settings.APP_BASE_URL}/open-house/form?listing_id={listing_id}"
    img = qrcode.make(target)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    url = upload_bytes(
        key=f"{listing_id}/qr.png",
        data=buf.read(),
        content_type="image/png",
    )
    return {"listing_id": listing_id, "qr_url": url, "checkin_url": target}
