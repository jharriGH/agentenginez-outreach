# AgentEnginez — Track C: Outreach + Fulfillment

KJE Product #20. FastAPI service mounted under `/agentenginez/v1/outreach/` providing 5 modules:

1. **Equity Outreach Engine** — `/equity/trigger/{client_id}` — pulls KJLE leads (5+yr ownership, $100K+ equity), sequences AVA voice → RVM → email → SMS via n8n Agent 9.
2. **Postcard Automation** — `/postcards/just-listed`, `/postcards/just-sold` — Lob.com radius mailing with 2.87× markup.
3. **Open House Follow-Up** — `/open-house/checkin`, `/open-house/qr/{listing_id}` — branch by interest level via n8n Agent 11.
4. **Referral Engine** — `/referrals/request/{client_id}`, `/referrals/reward/{referral_id}` — past-client outreach + $25 gift card via Lob check.
5. **Reputation Autopilot** — `/reviews/request/{client_id}`, `/reviews/monitor-and-respond` — review request cadence + GPT-4o auto-response.

All Twilio calls FROM `+18666217044`. n8n workflows: Agents 9, 10, 11, 12.

## Run

```bash
pip install -r requirements.txt
cp .env.example .env  # fill in secrets
uvicorn app.main:app --reload
```

Health: `GET /health`
Docs: `GET /docs`
