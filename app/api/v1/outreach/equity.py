from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

from app.core.logging import get_logger
from app.schemas.outreach import EquityTriggerResponse
from app.services.kjle import fetch_homeowner_leads
from app.services.n8n import n8n
from app.services.supabase import supabase

router = APIRouter(prefix="/equity", tags=["equity"])
log = get_logger(__name__)

AVA_SCRIPT = (
    "Hi {name}, this is {agent} with {brokerage}. Homes on {street} are selling "
    "for record prices — yours may be worth more than you think. I would love "
    "to give you a free market update. Call me back at {number} or I will "
    "follow up tomorrow."
)


@router.post("/trigger/{client_id}", response_model=EquityTriggerResponse)
async def trigger_equity_outreach(client_id: str) -> EquityTriggerResponse:
    """Pull homeowner leads from KJLE (5+ yr ownership, $100K+ equity), filter against
    existing outreach_sequences, and trigger n8n Agent 9 sequence per prospect."""
    clients = await supabase.select("clients", {"id": f"eq.{client_id}", "select": "*"})
    if not clients:
        raise HTTPException(404, f"client {client_id} not found")
    client = clients[0]
    zip_code = client.get("zip") or client.get("brokerage_zip") or ""
    if not zip_code:
        raise HTTPException(400, "client missing zip")

    leads = await fetch_homeowner_leads(zip_code=zip_code, equity_min=100_000)
    log.info("kjle_leads_fetched", count=len(leads), zip=zip_code)

    cutoff_year = datetime.now(timezone.utc).year - 5
    eligible = [
        l for l in leads
        if (l.get("equity") or 0) >= 100_000
        and (l.get("year_purchased") or cutoff_year + 1) <= cutoff_year
    ]

    existing = await supabase.select(
        "outreach_sequences",
        {"client_id": f"eq.{client_id}", "select": "prospect_phone"},
    )
    seen_phones = {row.get("prospect_phone") for row in existing if row.get("prospect_phone")}
    fresh = [l for l in eligible if l.get("phone") not in seen_phones]

    sequence_ids: list[str] = []
    for prospect in fresh:
        ava_vars = {
            "name": prospect.get("first_name", "there"),
            "agent": client.get("agent_name", "your agent"),
            "brokerage": client.get("brokerage", "the brokerage"),
            "street": prospect.get("street", "your street"),
            "number": client.get("agent_phone", ""),
        }
        sequence_row = {
            "client_id": client_id,
            "channel": "equity_outreach",
            "prospect_name": f"{prospect.get('first_name','')} {prospect.get('last_name','')}".strip(),
            "prospect_phone": prospect.get("phone"),
            "prospect_email": prospect.get("email"),
            "prospect_address": prospect.get("address"),
            "status": "queued",
            "script_vars": ava_vars,
            "ava_script": AVA_SCRIPT.format(**ava_vars),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            inserted = await supabase.insert("outreach_sequences", sequence_row)
            seq_id = inserted[0].get("id") if inserted else None
        except Exception as e:
            log.warning("sequence_insert_failed", err=str(e))
            seq_id = None

        try:
            await n8n.fire_webhook(
                "equity-sequence",
                {
                    "sequence_id": seq_id,
                    "client_id": client_id,
                    "prospect": prospect,
                    "ava_vars": ava_vars,
                },
            )
        except Exception as e:
            log.warning("n8n_equity_webhook_failed", err=str(e), seq_id=seq_id)

        if seq_id:
            sequence_ids.append(str(seq_id))

    log.info("equity_outreach_triggered", client_id=client_id, queued=len(sequence_ids))
    return EquityTriggerResponse(
        client_id=client_id,
        prospects_queued=len(sequence_ids),
        sequence_ids=sequence_ids,
    )
