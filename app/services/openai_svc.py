from openai import OpenAI

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


def _client() -> OpenAI:
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def generate_review_response(
    review_text: str,
    rating: int,
    agent_name: str,
    brokerage: str,
) -> str:
    if not settings.OPENAI_API_KEY:
        return "Thank you for your feedback!"
    tone = "warm and grateful" if rating >= 4 else "professional, empathetic, de-escalating"
    prompt = (
        f"You are {agent_name} of {brokerage}. Write a {tone} reply (under 80 words) "
        f"to this {rating}-star review:\n\n{review_text}\n\n"
        "Sign off with the agent's first name only. Do not promise specifics."
    )
    res = _client().chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You write Google Business Profile review responses for real estate agents."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.6,
        max_tokens=200,
    )
    return res.choices[0].message.content.strip()
