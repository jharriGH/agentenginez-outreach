"""n8n workflow definitions for AgentEnginez Track C.

GOAT rule: never modify or delete existing workflows. GET /workflows first,
verify by name, POST new only, then activate separately.

Run:
    python -m scripts.n8n_workflows
"""

from __future__ import annotations
import asyncio
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.services.n8n import n8n

configure_logging("INFO")
log = get_logger(__name__)

ASTERISK_HOST = settings.ASTERISK_VPS_IP
SUPABASE_REST = f"{settings.SUPABASE_URL}/rest/v1"
APP_BASE = settings.APP_BASE_URL
TWILIO_FROM = settings.TWILIO_FROM_NUMBER


def _wait_node(name: str, hours: int) -> dict[str, Any]:
    return {
        "parameters": {"unit": "hours", "amount": hours},
        "name": name,
        "type": "n8n-nodes-base.wait",
        "typeVersion": 1,
        "position": [0, 0],
    }


def equity_sequence_workflow() -> dict[str, Any]:
    nodes = [
        {
            "parameters": {
                "httpMethod": "POST",
                "path": "equity-sequence",
                "responseMode": "onReceived",
                "options": {},
            },
            "name": "Webhook",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 1,
            "position": [240, 300],
            "webhookId": "equity-sequence",
        },
        {
            "parameters": {
                "url": f"http://{ASTERISK_HOST}:8088/ari/channels",
                "method": "POST",
                "authentication": "genericCredentialType",
                "genericAuthType": "httpBasicAuth",
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": (
                    '={\n  "endpoint": "PJSIP/{{$json["prospect"]["phone"]}}@twilio",\n'
                    '  "extension": "s",\n  "context": "ava-outbound",\n'
                    '  "priority": 1,\n  "callerId": "' + TWILIO_FROM + '",\n'
                    '  "variables": {\n    "AVA_NAME": "={{$json["ava_vars"]["name"]}}",\n'
                    '    "AVA_AGENT": "={{$json["ava_vars"]["agent"]}}",\n'
                    '    "AVA_BROKERAGE": "={{$json["ava_vars"]["brokerage"]}}",\n'
                    '    "AVA_STREET": "={{$json["ava_vars"]["street"]}}",\n'
                    '    "AVA_NUMBER": "={{$json["ava_vars"]["number"]}}"\n  }\n}'
                ),
            },
            "name": "T+0 AVA Call (Asterisk ARI)",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4,
            "position": [460, 300],
        },
        {**_wait_node("Wait 24hr", 24), "position": [680, 300]},
        {
            "parameters": {
                "url": "https://api.voicedrop.ai/v1/ringless_voicemail",
                "method": "POST",
                "sendHeaders": True,
                "headerParameters": {"parameters": [
                    {"name": "Authorization", "value": "Bearer " + (settings.VOICEDROP_API_KEY or "VOICEDROP_API_KEY")},
                    {"name": "Content-Type", "value": "application/json"},
                ]},
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": (
                    '={\n  "to": "{{$node["Webhook"].json["prospect"]["phone"]}}",\n'
                    '  "from": "' + TWILIO_FROM + '",\n'
                    '  "audio_url": "https://agentenginez.com/audio/equity-rvm.mp3"\n}'
                ),
            },
            "name": "T+24h RVM (VoiceDrop)",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4,
            "position": [900, 300],
        },
        {**_wait_node("Wait 72hr", 72), "position": [1120, 300]},
        {
            "parameters": {
                "url": "https://api.resend.com/emails",
                "method": "POST",
                "sendHeaders": True,
                "headerParameters": {"parameters": [
                    {"name": "Authorization", "value": "Bearer " + (settings.RESEND_API_KEY or "RESEND_API_KEY")},
                    {"name": "Content-Type", "value": "application/json"},
                ]},
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": (
                    '={\n  "from": "hello@agentenginez.com",\n'
                    '  "to": "{{$node["Webhook"].json["prospect"]["email"]}}",\n'
                    '  "subject": "Quick market update for {{$node["Webhook"].json["prospect"]["street"]}}",\n'
                    '  "html": "<p>Hi {{$node[\\"Webhook\\"].json[\\"ava_vars\\"][\\"name\\"]}},</p>'
                    '<p>Homes on your street are commanding record prices. '
                    'Reply for a free market update.</p><p>— '
                    '{{$node[\\"Webhook\\"].json[\\"ava_vars\\"][\\"agent\\"]}}</p>"\n}'
                ),
            },
            "name": "T+72h Email (Resend)",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4,
            "position": [1340, 300],
        },
        {**_wait_node("Wait 168hr", 168), "position": [1560, 300]},
        {
            "parameters": {
                "url": "https://api.twilio.com/2010-04-01/Accounts/" + (settings.TWILIO_ACCOUNT_SID or "TWILIO_SID") + "/Messages.json",
                "method": "POST",
                "authentication": "genericCredentialType",
                "genericAuthType": "httpBasicAuth",
                "sendBody": True,
                "contentType": "form-urlencoded",
                "bodyParameters": {"parameters": [
                    {"name": "From", "value": TWILIO_FROM},
                    {"name": "To", "value": "={{$node[\"Webhook\"].json[\"prospect\"][\"phone\"]}}"},
                    {"name": "Body", "value": "Hi {{$node[\"Webhook\"].json[\"ava_vars\"][\"name\"]}}, just checking in — would you like a free home value report? Reply YES. — {{$node[\"Webhook\"].json[\"ava_vars\"][\"agent\"]}}"},
                ]},
            },
            "name": "T+168h SMS (Twilio)",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4,
            "position": [1780, 300],
        },
        {
            "parameters": {
                "url": SUPABASE_REST + "/outreach_sequences?id=eq.{{$node[\"Webhook\"].json[\"sequence_id\"]}}",
                "method": "PATCH",
                "sendHeaders": True,
                "headerParameters": {"parameters": [
                    {"name": "apikey", "value": settings.SUPABASE_SERVICE_KEY or "SUPABASE_SERVICE_KEY"},
                    {"name": "Authorization", "value": "Bearer " + (settings.SUPABASE_SERVICE_KEY or "SUPABASE_SERVICE_KEY")},
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "Content-Profile", "value": "agentenginez"},
                ]},
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": '={\n  "status": "completed"\n}',
            },
            "name": "Mark Sequence Complete",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4,
            "position": [2000, 300],
        },
    ]
    connections = {
        "Webhook": {"main": [[{"node": "T+0 AVA Call (Asterisk ARI)", "type": "main", "index": 0}]]},
        "T+0 AVA Call (Asterisk ARI)": {"main": [[{"node": "Wait 24hr", "type": "main", "index": 0}]]},
        "Wait 24hr": {"main": [[{"node": "T+24h RVM (VoiceDrop)", "type": "main", "index": 0}]]},
        "T+24h RVM (VoiceDrop)": {"main": [[{"node": "Wait 72hr", "type": "main", "index": 0}]]},
        "Wait 72hr": {"main": [[{"node": "T+72h Email (Resend)", "type": "main", "index": 0}]]},
        "T+72h Email (Resend)": {"main": [[{"node": "Wait 168hr", "type": "main", "index": 0}]]},
        "Wait 168hr": {"main": [[{"node": "T+168h SMS (Twilio)", "type": "main", "index": 0}]]},
        "T+168h SMS (Twilio)": {"main": [[{"node": "Mark Sequence Complete", "type": "main", "index": 0}]]},
    }
    return {
        "name": "Agent 9 — Equity Sequence",
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
    }


def postcard_trigger_workflow() -> dict[str, Any]:
    nodes = [
        {
            "parameters": {
                "httpMethod": "POST",
                "path": "listing-status-changed",
                "responseMode": "onReceived",
                "options": {},
            },
            "name": "Webhook (Supabase)",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 1,
            "position": [240, 300],
            "webhookId": "listing-status-changed",
        },
        {
            "parameters": {
                "conditions": {
                    "string": [
                        {"value1": "={{$json[\"record\"][\"status\"]}}", "operation": "equal", "value2": "active"},
                    ]
                }
            },
            "name": "Status == active?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 1,
            "position": [460, 200],
        },
        {
            "parameters": {
                "conditions": {
                    "string": [
                        {"value1": "={{$json[\"record\"][\"status\"]}}", "operation": "equal", "value2": "sold"},
                    ]
                }
            },
            "name": "Status == sold?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 1,
            "position": [460, 400],
        },
        {
            "parameters": {
                "url": APP_BASE + "/agentenginez/v1/outreach/postcards/just-listed/{{$json[\"record\"][\"id\"]}}",
                "method": "POST",
            },
            "name": "Trigger Just Listed",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4,
            "position": [700, 200],
        },
        {
            "parameters": {
                "url": APP_BASE + "/agentenginez/v1/outreach/postcards/just-sold/{{$json[\"record\"][\"id\"]}}",
                "method": "POST",
            },
            "name": "Trigger Just Sold",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4,
            "position": [700, 400],
        },
    ]
    connections = {
        "Webhook (Supabase)": {"main": [[
            {"node": "Status == active?", "type": "main", "index": 0},
            {"node": "Status == sold?", "type": "main", "index": 0},
        ]]},
        "Status == active?": {"main": [[{"node": "Trigger Just Listed", "type": "main", "index": 0}], []]},
        "Status == sold?": {"main": [[{"node": "Trigger Just Sold", "type": "main", "index": 0}], []]},
    }
    return {
        "name": "Agent 10 — Postcard Trigger",
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
    }


def open_house_followup_workflow() -> dict[str, Any]:
    def _branch_sms(name: str, x: int, y: int) -> dict[str, Any]:
        return {
            "parameters": {
                "url": "https://api.twilio.com/2010-04-01/Accounts/" + (settings.TWILIO_ACCOUNT_SID or "TWILIO_SID") + "/Messages.json",
                "method": "POST",
                "authentication": "genericCredentialType",
                "genericAuthType": "httpBasicAuth",
                "sendBody": True,
                "contentType": "form-urlencoded",
                "bodyParameters": {"parameters": [
                    {"name": "From", "value": TWILIO_FROM},
                    {"name": "To", "value": "={{$node[\"Webhook\"].json[\"attendee\"][\"attendee_phone\"]}}"},
                    {"name": "Body", "value": "Thanks for visiting today! Reach out anytime. — {{$node[\"Webhook\"].json[\"agent\"][\"name\"]}}"},
                ]},
            },
            "name": name,
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4,
            "position": [x, y],
        }

    nodes = [
        {
            "parameters": {
                "httpMethod": "POST",
                "path": "open-house-followup",
                "responseMode": "onReceived",
                "options": {},
            },
            "name": "Webhook",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 1,
            "position": [240, 300],
            "webhookId": "open-house-followup",
        },
        _branch_sms("T+0 SMS Thank-you", 460, 300),
        {
            "parameters": {"unit": "minutes", "amount": 15},
            "name": "Wait 15min",
            "type": "n8n-nodes-base.wait",
            "typeVersion": 1,
            "position": [680, 300],
        },
        {
            "parameters": {
                "url": "https://api.resend.com/emails",
                "method": "POST",
                "sendHeaders": True,
                "headerParameters": {"parameters": [
                    {"name": "Authorization", "value": "Bearer " + (settings.RESEND_API_KEY or "RESEND_API_KEY")},
                    {"name": "Content-Type", "value": "application/json"},
                ]},
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": (
                    '={\n  "from": "hello@agentenginez.com",\n'
                    '  "to": "{{$node[\\"Webhook\\"].json[\\"attendee\\"][\\"attendee_email\\"]}}",\n'
                    '  "subject": "Thanks for visiting the open house",\n'
                    '  "html": "<p>Hi {{$node[\\"Webhook\\"].json[\\"attendee\\"][\\"attendee_name\\"]}},</p>'
                    '<p>Listing details + my AI assistant: '
                    '<a href=\\"' + APP_BASE + '/listing-bot/{{$node[\\"Webhook\\"].json[\\"attendee\\"][\\"listing_id\\"]}}\\">chat now</a>.</p>"\n}'
                ),
            },
            "name": "T+15min Email (Resend)",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4,
            "position": [900, 300],
        },
        {
            "parameters": {
                "conditions": {"string": [
                    {"value1": "={{$node[\"Webhook\"].json[\"attendee\"][\"interest_level\"]}}", "operation": "equal", "value2": "hot"},
                ]}
            },
            "name": "Hot Lead?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 1,
            "position": [1120, 300],
        },
        {
            "parameters": {"unit": "minutes", "amount": 60},
            "name": "Wait 60min (hot)",
            "type": "n8n-nodes-base.wait",
            "typeVersion": 1,
            "position": [1340, 200],
        },
        {
            "parameters": {
                "url": f"http://{ASTERISK_HOST}:8088/ari/channels",
                "method": "POST",
                "authentication": "genericCredentialType",
                "genericAuthType": "httpBasicAuth",
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": (
                    '={\n  "endpoint": "PJSIP/{{$node[\\"Webhook\\"].json[\\"attendee\\"][\\"attendee_phone\\"]}}@twilio",\n'
                    '  "extension": "s",\n  "context": "ava-outbound",\n'
                    '  "priority": 1,\n  "callerId": "' + TWILIO_FROM + '"\n}'
                ),
            },
            "name": "AVA Hot Call",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4,
            "position": [1560, 200],
        },
        {
            "parameters": {
                "conditions": {"string": [
                    {"value1": "={{$node[\"Webhook\"].json[\"attendee\"][\"interest_level\"]}}", "operation": "regex", "value2": "^(hot|warm)$"},
                ]}
            },
            "name": "Hot or Warm?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 1,
            "position": [1340, 400],
        },
        {
            "parameters": {"unit": "hours", "amount": 24},
            "name": "Wait 24hr",
            "type": "n8n-nodes-base.wait",
            "typeVersion": 1,
            "position": [1560, 400],
        },
        {
            "parameters": {
                "url": "https://api.resend.com/emails",
                "method": "POST",
                "sendHeaders": True,
                "headerParameters": {"parameters": [
                    {"name": "Authorization", "value": "Bearer " + (settings.RESEND_API_KEY or "RESEND_API_KEY")},
                    {"name": "Content-Type", "value": "application/json"},
                ]},
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": (
                    '={\n  "from": "hello@agentenginez.com",\n'
                    '  "to": "{{$node[\\"Webhook\\"].json[\\"attendee\\"][\\"attendee_email\\"]}}",\n'
                    '  "subject": "Your neighborhood market report",\n'
                    '  "html": "<p>Hi {{$node[\\"Webhook\\"].json[\\"attendee\\"][\\"attendee_name\\"]}}, here is the latest market data for the area.</p>"\n}'
                ),
            },
            "name": "T+24hr Market Report",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4,
            "position": [1780, 400],
        },
    ]
    connections = {
        "Webhook": {"main": [[{"node": "T+0 SMS Thank-you", "type": "main", "index": 0}]]},
        "T+0 SMS Thank-you": {"main": [[{"node": "Wait 15min", "type": "main", "index": 0}]]},
        "Wait 15min": {"main": [[{"node": "T+15min Email (Resend)", "type": "main", "index": 0}]]},
        "T+15min Email (Resend)": {"main": [[
            {"node": "Hot Lead?", "type": "main", "index": 0},
            {"node": "Hot or Warm?", "type": "main", "index": 0},
        ]]},
        "Hot Lead?": {"main": [[{"node": "Wait 60min (hot)", "type": "main", "index": 0}], []]},
        "Wait 60min (hot)": {"main": [[{"node": "AVA Hot Call", "type": "main", "index": 0}]]},
        "Hot or Warm?": {"main": [[{"node": "Wait 24hr", "type": "main", "index": 0}], []]},
        "Wait 24hr": {"main": [[{"node": "T+24hr Market Report", "type": "main", "index": 0}]]},
    }
    return {
        "name": "Agent 11 — Open House Follow-Up",
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
    }


def referral_cron_workflow() -> dict[str, Any]:
    nodes = [
        {
            "parameters": {
                "rule": {
                    "interval": [
                        {"field": "cronExpression", "expression": "0 9 1,15 * *"}
                    ]
                }
            },
            "name": "Cron 1st & 15th 9am PT",
            "type": "n8n-nodes-base.scheduleTrigger",
            "typeVersion": 1,
            "position": [240, 300],
        },
        {
            "parameters": {
                "url": SUPABASE_REST + "/clients?status=eq.active&select=id",
                "method": "GET",
                "sendHeaders": True,
                "headerParameters": {"parameters": [
                    {"name": "apikey", "value": settings.SUPABASE_SERVICE_KEY or "SUPABASE_SERVICE_KEY"},
                    {"name": "Authorization", "value": "Bearer " + (settings.SUPABASE_SERVICE_KEY or "SUPABASE_SERVICE_KEY")},
                    {"name": "Accept-Profile", "value": "agentenginez"},
                ]},
            },
            "name": "Get Active Clients",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4,
            "position": [460, 300],
        },
        {
            "parameters": {"options": {}},
            "name": "Split Clients",
            "type": "n8n-nodes-base.splitInBatches",
            "typeVersion": 2,
            "position": [680, 300],
        },
        {
            "parameters": {
                "url": APP_BASE + "/agentenginez/v1/outreach/referrals/request/{{$json[\"id\"]}}",
                "method": "POST",
            },
            "name": "POST referrals/request",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4,
            "position": [900, 300],
        },
    ]
    connections = {
        "Cron 1st & 15th 9am PT": {"main": [[{"node": "Get Active Clients", "type": "main", "index": 0}]]},
        "Get Active Clients": {"main": [[{"node": "Split Clients", "type": "main", "index": 0}]]},
        "Split Clients": {"main": [[{"node": "POST referrals/request", "type": "main", "index": 0}]]},
        "POST referrals/request": {"main": [[{"node": "Split Clients", "type": "main", "index": 0}]]},
    }
    return {
        "name": "Agent 12 — Referral Cron",
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1", "timezone": "America/Los_Angeles"},
    }


WORKFLOWS = [
    equity_sequence_workflow,
    postcard_trigger_workflow,
    open_house_followup_workflow,
    referral_cron_workflow,
]


async def deploy_all() -> list[dict[str, Any]]:
    log.info("n8n_listing_existing")
    existing = await n8n.list_workflows()
    existing_names = {wf.get("name"): wf.get("id") for wf in existing}
    log.info("n8n_existing_count", count=len(existing_names))

    results: list[dict[str, Any]] = []
    for builder in WORKFLOWS:
        spec = builder()
        name = spec["name"]
        if name in existing_names:
            wf_id = existing_names[name]
            log.info("workflow_exists_skip_create", name=name, id=wf_id)
            results.append({"name": name, "id": wf_id, "created": False})
            continue
        try:
            created = await n8n.create_workflow(spec)
            wf_id = created.get("id") or (created.get("data") or {}).get("id")
            log.info("workflow_created", name=name, id=wf_id)
            try:
                await n8n.activate_workflow(wf_id)
                log.info("workflow_activated", name=name, id=wf_id)
            except Exception as e:
                log.warning("workflow_activate_failed", name=name, err=str(e))
            results.append({"name": name, "id": wf_id, "created": True})
        except Exception as e:
            log.error("workflow_create_failed", name=name, err=str(e))
            results.append({"name": name, "id": None, "created": False, "error": str(e)})
    return results


if __name__ == "__main__":
    out = asyncio.run(deploy_all())
    print("\n=== n8n deploy summary ===")
    for r in out:
        print(r)
