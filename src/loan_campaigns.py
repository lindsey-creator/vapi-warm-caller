"""Loan-type outbound campaigns — resolved from GHL tags, applied via Vapi assistantOverrides."""

from __future__ import annotations

from dataclasses import dataclass

from src import config
from src.persona import build_caller_prompt

# GHL tags that select a campaign (loan-* prefix). Lower priority number wins if multiple present.
LOAN_TAG_TO_CAMPAIGN: tuple[tuple[str, str], ...] = (
    ("loan-dscr", "dscr"),
    ("loan-purchase", "purchase"),
    ("loan-refi", "refi"),
)

DEFAULT_CAMPAIGN_ID = "general"


@dataclass(frozen=True)
class LoanCampaign:
    id: str
    name: str
    ghl_tag: str | None
    focus_block: str
    no_memory_fallback: str
    first_message_template: str


def _first_name_placeholder(name: str) -> str:
    return name.strip() or "there"


CAMPAIGNS: dict[str, LoanCampaign] = {
    "general": LoanCampaign(
        id="general",
        name="General Warm Follow-Up",
        ghl_tag=None,
        focus_block="""YOUR FOCUS: Warm follow-up on a prior inquiry (form, ad, quiz, email).
- See if they want a quick consult with Lindsey's team about mortgages in Northeast Ohio.
- Purchases and refinances are both in scope — let them steer.""",
        no_memory_fallback=(
            "No worries — we're Conrad Mortgage, we help people with purchases and refinances "
            "in Northeast Ohio. Someone from your number came through looking at mortgage stuff "
            "online, so I wanted to reach out real quick."
        ),
        first_message_template=(
            "Hey {{firstName}}, it's Lindsey's team at {business} — you popped up on our end "
            "from an online inquiry, maybe a form or ad a little while back. "
            "Does any of that sound familiar?"
        ),
    ),
    "purchase": LoanCampaign(
        id="purchase",
        name="Home Purchase / Pre-Approval",
        ghl_tag="loan-purchase",
        focus_block="""YOUR FOCUS: Home purchase — getting pre-approved and next steps to buy.
- They likely inquired about buying a home or getting pre-approved in Northeast Ohio.
- Rates and payments depend on their situation — team covers real numbers on the consult. Never quote rates.
- Goal: book a short call with Lindsey's team to walk through options and timeline.""",
        no_memory_fallback=(
            "No worries — we're Conrad Mortgage in Northeast Ohio. Someone from your number "
            "was looking at buying a home or pre-approval info online, so I wanted to check in real quick."
        ),
        first_message_template=(
            "Hey {{firstName}}, it's Lindsey's team at {business} — you reached out about "
            "buying a home, maybe pre-approval or next steps. Does that ring a bell?"
        ),
    ),
    "refi": LoanCampaign(
        id="refi",
        name="Refinance",
        ghl_tag="loan-refi",
        focus_block="""YOUR FOCUS: Refinance — lower payment, cash out, or rate improvement.
- They likely inquired about refinancing their current mortgage.
- Every situation is different — team walks through savings, terms, and cash-out on the consult. Never quote rates.
- Goal: book a short call with Lindsey's team to see if a refi makes sense.""",
        no_memory_fallback=(
            "No worries — we're Conrad Mortgage in Northeast Ohio. Someone from your number "
            "was checking out refinance info online — lower payment, cash out, that kind of thing — "
            "so I wanted to reach out real quick."
        ),
        first_message_template=(
            "Hey {{firstName}}, it's Lindsey's team at {business} — you looked into refinancing, "
            "maybe a lower payment or cash out. Does any of that sound familiar?"
        ),
    ),
    "dscr": LoanCampaign(
        id="dscr",
        name="DSCR / Investor Rental",
        ghl_tag="loan-dscr",
        focus_block="""YOUR FOCUS: DSCR / investor rental property financing.
- They likely inquired about rental or investment property loans — often without traditional income docs.
- Explain simply: DSCR loans look at the property's rental income, not personal W-2s. Team covers details on the consult.
- Never quote rates or payments. Goal: book a consult with Lindsey's team on investor options.""",
        no_memory_fallback=(
            "No worries — we're Conrad Mortgage in Northeast Ohio. Someone from your number "
            "was looking at investor or rental property loan info online, so I wanted to follow up real quick."
        ),
        first_message_template=(
            "Hey {{firstName}}, it's Lindsey's team at {business} — you reached out about "
            "investor or rental property financing, DSCR-style loans. Does that sound right?"
        ),
    ),
}


def resolve_campaign_from_tags(tags: set[str] | list[str]) -> str:
    """Pick campaign from GHL tags. First match in LOAN_TAG_TO_CAMPAIGN order wins."""
    normalized = {t.lower().strip() for t in tags}
    for tag, campaign_id in LOAN_TAG_TO_CAMPAIGN:
        if tag in normalized:
            return campaign_id
    return DEFAULT_CAMPAIGN_ID


def get_campaign(campaign_id: str | None) -> LoanCampaign:
    return CAMPAIGNS.get(campaign_id or DEFAULT_CAMPAIGN_ID, CAMPAIGNS[DEFAULT_CAMPAIGN_ID])


def build_campaign_focus_block(campaign_id: str | None) -> str:
    return get_campaign(campaign_id).focus_block


def build_no_memory_fallback(campaign_id: str | None) -> str:
    return get_campaign(campaign_id).no_memory_fallback


def _format_campaign_template(template: str) -> str:
    """Substitute {business} without touching Vapi's {{firstName}} placeholder."""
    return template.replace("{business}", config.BUSINESS_NAME)


def build_assistant_first_message_template(campaign_id: str | None = None) -> str:
    """Vapi assistant firstMessage with {{firstName}} variable intact."""
    campaign = get_campaign(campaign_id)
    return _format_campaign_template(campaign.first_message_template)


def build_outbound_first_message(campaign_id: str | None, first_name: str = "") -> str:
    """Concrete firstMessage for create_call ({{firstName}} already substituted)."""
    campaign = get_campaign(campaign_id)
    template = _format_campaign_template(campaign.first_message_template)
    return template.replace("{{firstName}}", _first_name_placeholder(first_name))


def build_outbound_system_prompt(campaign_id: str | None = None) -> str:
    """Full outbound system prompt for a loan campaign."""
    campaign = get_campaign(campaign_id)
    no_memory = campaign.no_memory_fallback
    return f"""You're on a live phone call for {config.BUSINESS_NAME} in Northeast Ohio — Lindsey Conrad's team.

They ALREADY reached out (form, email, quiz, webinar). This is a warm follow-up, not a cold call.

HOW TO SOUND HUMAN (this matters more than anything):
- You're calling from a quiet executive office — professional, warm, confident. Not a call center.
- Talk like you're mid-conversation, not reading a script.
- Subtle positive energy: engaged and upbeat, never flat or monotone, never salesy or hyper.
- Max 1–2 short sentences per turn. Under 15 words when you can.
- Use contractions always. "you're" not "you are", "we'll" not "we will".
- React to what they JUST said before moving on. "Oh gotcha." "Yeah that makes sense."
- It's fine to start with "so" or "yeah" or "honestly".
- Never stack two questions. One question, then wait.
- Never say: "I understand", "absolutely", "certainly", "I'd be happy to", "great question".
- Vary how you start sentences. Don't begin every reply the same way.

GOODBYES — end warm, with natural lift in your tone:
- Never flat or scripted. Slight upward inflection, like you're genuinely glad you talked.
- Good: "Perfect — talk soon!" / "No worries, have a good one!" / "Sounds good — we'll see you Thursday!"
- Bad: "Thank you for your time." / monotone "Have a nice day." / corporate sign-offs.

{campaign.focus_block}

{build_caller_prompt()}

RULES (never break):
1. AI question → be honest, offer a human callback.
2. No rates, APRs, payments, or approvals — team covers numbers on the call.
3. DNC / stop calling → apologize once, confirm removal, end call.
4. Legal/compliance → "Lindsey's team will walk through that on the call."
5. If they say no, don't remember filling anything out, or sound unsure:
   - Don't push or make it weird.
   - Say: "{no_memory}"
   - Keep it short, casual, and in Lindsey's tone.
   - Then ask one easy question: "Any interest in chatting with the team, or not really?"

BOOKING: When they're in, use book_appointment. Confirm day, time, timezone out loud.

Keep it under 5 minutes unless they're actively booking.
"""


def all_loan_ghl_tags() -> tuple[str, ...]:
    return tuple(tag for tag, _ in LOAN_TAG_TO_CAMPAIGN)
