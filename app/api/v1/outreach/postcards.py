from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.outreach import PostcardResponse
from app.services.lob import addresses_within_radius, create_postcard
from app.services.supabase import supabase

router = APIRouter(prefix="/postcards", tags=["postcards"])
log = get_logger(__name__)

POSTCARD_UNIT_COST = 0.85
MARKUP_MULTIPLIER = 2.87


async def _send_postcard_run(listing_id: str, kind: Literal["just-listed", "just-sold"]) -> PostcardResponse:
    listings = await supabase.select("listings", {"id": f"eq.{listing_id}", "select": "*"})
    if not listings:
        raise HTTPException(404, f"listing {listing_id} not found")
    listing = listings[0]
    client_id = listing.get("client_id")

    clients = await supabase.select("clients", {"id": f"eq.{client_id}", "select": "*"})
    client = clients[0] if clients else {}

    nearby = await addresses_within_radius(
        address_line1=listing.get("address_line1", ""),
        city=listing.get("city", ""),
        state=listing.get("state", ""),
        zip_code=listing.get("zip", ""),
        radius_miles=0.5,
    )
    address_count = len(nearby) or 50

    badge = "Just Listed" if kind == "just-listed" else "Just Sold"
    listing_url = f"{settings.APP_BASE_URL}/listing-bot/{listing_id}"
    front_html = (
        f"<html><body style='font-family:sans-serif;text-align:center'>"
        f"<img src='{listing.get('photo_url','')}' style='width:100%'/>"
        f"<h1>{badge}</h1>"
        f"<h2>{listing.get('address_line1','')}</h2>"
        f"<h3>${listing.get('price', 0):,}</h3>"
        f"<p>{client.get('agent_name','')} | {client.get('brokerage','')}</p>"
        f"</body></html>"
    )
    back_html = (
        f"<html><body style='font-family:sans-serif'>"
        f"<h2>{client.get('agent_name','')}</h2>"
        f"<p>{client.get('agent_phone','')}<br>{client.get('agent_email','')}</p>"
        f"<p>Scan to chat with my AI listing assistant:</p>"
        f"<img src='https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={listing_url}'/>"
        f"</body></html>"
    )

    from_address = {
        "name": client.get("agent_name", "Agent"),
        "address_line1": client.get("brokerage_address", "1 Main St"),
        "address_city": client.get("brokerage_city", ""),
        "address_state": client.get("brokerage_state", ""),
        "address_zip": client.get("brokerage_zip", ""),
    }

    lob_id: str | None = None
    if nearby:
        first = nearby[0]
        to_address = {
            "name": first.get("recipient", "Neighbor"),
            "address_line1": first.get("primary_line", listing.get("address_line1", "")),
            "address_city": first.get("city", listing.get("city", "")),
            "address_state": first.get("state", listing.get("state", "")),
            "address_zip": first.get("zip_code", listing.get("zip", "")),
        }
        try:
            res = await create_postcard(
                to_address=to_address,
                from_address=from_address,
                front=front_html,
                back=back_html,
                description=f"AgentEnginez {badge} {listing_id}",
            )
            lob_id = res.get("id")
        except Exception as e:
            log.warning("lob_postcard_failed", err=str(e))

    cost = round(POSTCARD_UNIT_COST * address_count, 2)
    markup_billed = round(cost * MARKUP_MULTIPLIER, 2)

    await supabase.insert("postcards", {
        "client_id": client_id,
        "listing_id": listing_id,
        "kind": kind,
        "lob_id": lob_id,
        "address_count": address_count,
        "cost": cost,
        "markup_billed": markup_billed,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await supabase.insert("billing_addons", {
        "client_id": client_id,
        "kind": "postcard_campaign",
        "amount": markup_billed,
        "cost": cost,
        "ref_listing_id": listing_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    log.info("postcard_campaign_sent", listing_id=listing_id, kind=kind, lob_id=lob_id, count=address_count)
    return PostcardResponse(
        listing_id=listing_id,
        lob_id=lob_id,
        address_count=address_count,
        cost=cost,
        markup_billed=markup_billed,
    )


@router.post("/just-listed/{listing_id}", response_model=PostcardResponse)
async def just_listed(listing_id: str) -> PostcardResponse:
    return await _send_postcard_run(listing_id, "just-listed")


@router.post("/just-sold/{listing_id}", response_model=PostcardResponse)
async def just_sold(listing_id: str) -> PostcardResponse:
    return await _send_postcard_run(listing_id, "just-sold")
