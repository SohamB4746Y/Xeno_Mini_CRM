from __future__ import annotations

import asyncio
import re
from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
import logging
import os
import statistics
import uuid
from typing import Any

from groq import Groq
from dotenv import load_dotenv
from sqlalchemy import delete as sa_delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import Campaign, CampaignAnalytics, Communication, Customer, Order, Segment
from services.campaign_launcher import dispatch_campaign
from services.message_renderer import render_message_for_customer
from services.segment_engine import evaluate_segment, preview_segment, refresh_segment_count

load_dotenv()

logger = logging.getLogger(__name__)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are ZURI's AI Marketing Intelligence — the embedded AI brain
of ZURI's CRM system. You are not a chatbot. You are an active participant in
ZURI's marketing operations.

ABOUT ZURI:
ZURI is an Indian D2C women's fashion brand selling sarees, kurtas, lehengas,
western wear, and accessories. Customers are primarily women aged 18-54 across
Mumbai, Delhi, Bangalore, Chennai, Hyderabad, Pune, Kolkata, and other Indian cities.
Customer tiers: Bronze (new/low value), Silver (regular), Gold (high value),
Platinum (top spenders).

YOUR CORE RESPONSIBILITIES:
1. PROACTIVELY SURFACE OPPORTUNITIES — Before the marketer asks, analyze the
   customer base and identify who needs to be reached. Open every conversation
   by calling get_dashboard_summary and get_proactive_opportunities to understand
   the current state.

2. EXECUTE CAMPAIGNS END-TO-END — When the marketer gives you a goal, you handle
   everything: find the right customers, build the segment, draft the message,
   pick the channel, and create the campaign. The marketer describes intent;
   you do the work.

3. EXPLAIN IN PLAIN LANGUAGE — Describe exactly what you are doing and why.
   Never use technical jargon. Speak like a sharp marketing strategist, not
   an engineer. A marketer who has never written SQL should understand every
   decision you make.

4. ALWAYS CONFIRM BEFORE LAUNCHING — Before firing any campaign, create it as
   a draft and show a clear preview. Ask for explicit confirmation before calling
   launch_campaign. Never launch unless the marketer has explicitly said "yes",
   "launch it", "go ahead", "confirm", "do it", or given clear approval.

5. FOLLOW UP WITH INTELLIGENCE — When asked about campaign performance, don't
   just report numbers. Interpret them. "Your open rate of 67% is 2x your average
   — here is what worked." That is what a marketing intelligence system does.

CAMPAIGN WORKFLOW (always follow these steps):
1. Use query_customers to find the right audience
2. Use create_segment to save the audience
3. Use draft_campaign_message to generate a message
4. Use create_campaign to create a DRAFT campaign
5. Show the campaign preview and ASK for confirmation
6. ONLY after explicit confirmation, use launch_campaign

CAMPAIGN PREVIEW FORMAT (always use this before asking for confirmation):
─────────────────────────────────────────
🚀 CAMPAIGN PREVIEW
─────────────────────────────────────────
📋 Name: [campaign name]
👥 Audience: [segment name] — [N] customers
📱 Channel: [channel] ([why this channel])
💬 Message preview: "[first 120 chars]..."
📊 Expected reach: ~[N × 0.92] delivered
📈 Based on ZURI's history: ~[X]% open rate
─────────────────────────────────────────
Type "launch it" to confirm, or tell me
what you'd like to change.

CHANNEL INTELLIGENCE (use this reasoning when recommending channels):
- WhatsApp: Highest engagement (55%+ open rate). Best for urgent, personal,
  time-sensitive messages. Keep under 300 chars. Best for customers who prefer it.
- SMS: Broadest reach, no internet needed. Very concise. Best for flash sales.
- Email: Rich content, detailed offers, loyalty updates. Best for longer messages.
- RCS: Like WhatsApp for Android. Interactive cards. Best for catalogue browsing.
Always check the segment's preferred_channel distribution first using the tool.

SEGMENT INTELLIGENCE (think in RFM terms):
- Champions: bought recently, frequently, high spend → reward and upsell
- Loyal Customers: frequent, moderate recency → keep engaged, prevent churn
- At Risk: were frequent, now 60-90 days since last purchase → intervene now
- Lapsed: 90-180 days no purchase → re-engagement offer needed
- Hibernating: 180+ days → win-back campaign with strong offer
- High Value New: 1-2 orders but high spend → nurture into loyal customers

MESSAGE PERSONALIZATION:
Always use these tokens in message templates:
{{name}} — customer's first name
{{city}} — their city (Mumbai, Delhi, etc.)
{{tier}} — their tier (Gold, Platinum, etc.)
{{last_product}} — last product they bought from ZURI
{{days_since_purchase}} — days since last purchase
{{total_orders}} — how many times they've bought
{{total_spend}} — total amount spent at ZURI

PERSONALITY:
- Decisive, data-driven, action-oriented
- Uses Indian context (₹ for prices, festive seasons like Diwali/Navratri)
- Never says "I cannot" — you have tools, use them
- When you do not know something, call a tool to find out
- After completing an action, always explain what just happened and what to expect next

IMPORTANT TOOL CALLING RULES:
- When calling tools, always output valid JSON for the arguments.
- For filter_rules, conditions must be a JSON array of objects, NOT a string.
- Each condition object must have: field (string), operator (string), value (any).
- Boolean values must be true or false (not strings).
- Number values must be numbers (not strings).
"""

# ---------------------------------------------------------------------------
# Tool schemas — 16 tools total
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_dashboard_summary",
            "description": (
                "Get real-time CRM summary: total customers by tier, active segments, "
                "campaign performance, average rates. Call first in every conversation."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_proactive_opportunities",
            "description": (
                "Analyze customer base to find top marketing opportunities: lapsed, "
                "at-risk, uncontacted high-value, performance trends."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_customers",
            "description": (
                "Query customers with filters. Returns count and sample. "
                "Use BEFORE creating segments to verify audience. "
                "filter_rules format: {\"operator\":\"AND\",\"conditions\":[{\"field\":\"tier\",\"operator\":\"eq\",\"value\":\"gold\"}]}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filter_rules": {
                        "type": "object",
                        "description": "Filter rules with operator (AND/OR) and conditions array",
                        "properties": {
                            "operator": {"type": "string", "enum": ["AND", "OR"]},
                            "conditions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "field": {"type": "string"},
                                        "operator": {"type": "string"},
                                        "value": {},
                                    },
                                },
                            },
                        },
                        "required": ["operator", "conditions"],
                    },
                    "sample_size": {
                        "type": "integer",
                        "description": "Number of sample customers (default 3, max 5)",
                        "default": 3,
                    },
                },
                "required": ["filter_rules"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_orders",
            "description": (
                "Query order data for analytics. Returns order stats, top products, "
                "revenue by tier, and recent order samples. Use for retention analysis."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Optional: specific customer UUID",
                    },
                    "tier": {
                        "type": "string",
                        "description": "Optional: filter by tier (bronze/silver/gold/platinum)",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Optional: only orders within last N days",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_segment",
            "description": (
                "Create and save a named customer segment. Call query_customers "
                "first to verify audience size. Sets ai_generated=true automatically."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Short segment name"},
                    "description": {"type": "string", "description": "Plain English description"},
                    "filter_rules": {
                        "type": "object",
                        "description": "Same format as query_customers filter_rules",
                    },
                    "prompt_used": {
                        "type": "string",
                        "description": "Original natural language request",
                    },
                },
                "required": ["name", "description", "filter_rules", "prompt_used"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_segment_insights",
            "description": (
                "Deep analytics for a segment: customer count, avg spend, "
                "tier breakdown, top cities, channel preference, spend distribution."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "segment_id": {"type": "string", "description": "UUID of the segment"},
                },
                "required": ["segment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_best_channel",
            "description": (
                "Analyze segment channel preference and historical performance "
                "to recommend optimal delivery channel."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "segment_id": {"type": "string", "description": "UUID of the segment"},
                },
                "required": ["segment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_campaign",
            "description": (
                "Create a DRAFT campaign (does NOT launch). "
                "After creating, show preview and ask for confirmation. "
                "Only call launch_campaign after explicit approval."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Campaign name"},
                    "segment_id": {"type": "string", "description": "UUID of target segment"},
                    "channel": {
                        "type": "string",
                        "enum": ["whatsapp", "sms", "email", "rcs"],
                        "description": "Delivery channel",
                    },
                    "message_template": {
                        "type": "string",
                        "description": "Message template with tokens like {{name}}, {{city}}, etc.",
                    },
                },
                "required": ["name", "segment_id", "channel", "message_template"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "launch_campaign",
            "description": (
                "Launch a draft campaign. CRITICAL: ONLY call after the marketer "
                "has explicitly approved. Requires campaign_id from create_campaign."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "UUID of campaign to launch"},
                },
                "required": ["campaign_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_campaign_analytics",
            "description": (
                "Get campaign performance. Without campaign_id returns last 5 campaigns. "
                "With campaign_id returns one campaign's detailed analytics."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {
                        "type": "string",
                        "description": "Optional: specific campaign UUID",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_existing_segments",
            "description": (
                "List all active segments with names, descriptions, customer counts. "
                "Use to avoid duplicates and reference existing audiences."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_campaign_message",
            "description": (
                "Generate a personalized campaign message template for a segment. "
                "Returns a message using ZURI tokens ({{name}}, {{city}}, etc.) "
                "appropriate for the channel and audience."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "segment_description": {
                        "type": "string",
                        "description": "Who the segment contains",
                    },
                    "campaign_goal": {
                        "type": "string",
                        "description": "What the campaign aims to achieve",
                    },
                    "channel": {
                        "type": "string",
                        "enum": ["whatsapp", "sms", "email", "rcs"],
                        "description": "Target channel",
                    },
                },
                "required": ["segment_description", "campaign_goal", "channel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_executive_report",
            "description": (
                "Generate a comprehensive executive report with actual CRM data: "
                "customer metrics, campaign performance, revenue analysis, "
                "retention rates, top segments, top products, and opportunities."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_insights",
            "description": (
                "Get customer base analytics: tier distribution, city distribution, "
                "channel preferences, spend analysis, retention metrics."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tier": {
                        "type": "string",
                        "description": "Optional: filter by tier",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_campaign",
            "description": "Delete a draft campaign. Cannot delete running or completed campaigns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "UUID of campaign to delete"},
                },
                "required": ["campaign_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_campaign",
            "description": "Update a draft campaign's name, message, or channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "UUID of campaign"},
                    "name": {"type": "string", "description": "New campaign name"},
                    "message_template": {"type": "string", "description": "New message template"},
                    "channel": {
                        "type": "string",
                        "enum": ["whatsapp", "sms", "email", "rcs"],
                        "description": "New channel",
                    },
                },
                "required": ["campaign_id"],
            },
        },
    },
]

ToolExecutor = Callable[[AsyncSession, dict[str, Any]], Awaitable[dict[str, Any]]]


# ---------------------------------------------------------------------------
# Argument repair and normalization
# ---------------------------------------------------------------------------


def _repair_json(raw: str) -> dict[str, Any]:
    """Attempt to repair malformed JSON from LLM tool calls."""
    # Strip markdown code fences
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```\w*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
        cleaned = cleaned.strip()

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fix single quotes → double quotes
    try:
        fixed = cleaned.replace("'", '"')
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # Fix trailing commas
    try:
        fixed = re.sub(r",\s*([}\]])", r"\1", cleaned)
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON object from surrounding text
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Last resort: empty dict
    logger.warning("Could not repair JSON: %s", raw[:200])
    return {}


def _normalize_tool_input(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize and repair common LLM argument mistakes."""
    normalized = dict(tool_input)

    # Fix filter_rules.conditions being a string instead of array
    if "filter_rules" in normalized:
        rules = normalized["filter_rules"]
        if isinstance(rules, str):
            try:
                rules = json.loads(rules)
                normalized["filter_rules"] = rules
            except (json.JSONDecodeError, TypeError):
                pass

        if isinstance(rules, dict):
            conditions = rules.get("conditions")
            if isinstance(conditions, str):
                try:
                    rules["conditions"] = json.loads(conditions)
                except (json.JSONDecodeError, TypeError):
                    rules["conditions"] = []
            elif conditions is None:
                rules["conditions"] = []
            elif not isinstance(conditions, list):
                rules["conditions"] = [conditions] if isinstance(conditions, dict) else []

            # Ensure operator exists
            if "operator" not in rules:
                rules["operator"] = "AND"

            # Normalize each condition
            for cond in rules.get("conditions", []):
                if isinstance(cond, dict):
                    # Fix value types
                    val = cond.get("value")
                    op = cond.get("operator", "")
                    field = cond.get("field", "")

                    # Numeric fields: coerce string to number
                    if field in ("total_orders", "total_spend", "age") and isinstance(val, str):
                        try:
                            cond["value"] = int(val)
                        except ValueError:
                            try:
                                cond["value"] = float(val)
                            except ValueError:
                                pass

                    # days_ago operators: coerce to int
                    if op in ("days_ago_gte", "days_ago_lte") and isinstance(val, str):
                        try:
                            cond["value"] = int(val)
                        except ValueError:
                            pass

                    # in/not_in operators: ensure value is list
                    if op in ("in", "not_in") and not isinstance(val, list):
                        if isinstance(val, str):
                            cond["value"] = [v.strip() for v in val.split(",")]
                        else:
                            cond["value"] = [val]

    # Fix confirmed field (string "true" → bool True)
    if "confirmed" in normalized:
        val = normalized["confirmed"]
        if isinstance(val, str):
            normalized["confirmed"] = val.lower() in ("true", "yes", "1")

    # Fix sample_size as string
    if "sample_size" in normalized and isinstance(normalized["sample_size"], str):
        try:
            normalized["sample_size"] = int(normalized["sample_size"])
        except ValueError:
            normalized["sample_size"] = 3

    # Fix days as string
    if "days" in normalized and isinstance(normalized["days"], str):
        try:
            normalized["days"] = int(normalized["days"])
        except ValueError:
            normalized["days"] = 90

    return normalized


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def to_float(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0.0)


def _isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _days_since(value: datetime | None) -> int | None:
    if value is None:
        return None
    now = datetime.now(value.tzinfo or UTC)
    return max((now - value).days, 0)


def _safe_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"Invalid UUID: {value}") from exc


async def _load_full_customers(db: AsyncSession, customers: list[Customer]) -> list[Customer]:
    customer_ids = [customer.id for customer in customers]
    if not customer_ids:
        return []
    result = await db.execute(select(Customer).where(Customer.id.in_(customer_ids)))
    full_customers = list(result.scalars().all())
    customer_by_id = {customer.id: customer for customer in full_customers}
    return [customer_by_id[customer_id] for customer_id in customer_ids if customer_id in customer_by_id]


def _customer_sample(customer: Customer) -> dict[str, Any]:
    return {
        "name": customer.name,
        "city": customer.city,
        "tier": customer.tier,
        "total_spend": to_float(customer.total_spend),
        "total_orders": customer.total_orders,
        "days_since_purchase": _days_since(customer.last_purchase_at),
        "preferred_channel": customer.preferred_channel,
    }


def _average(values: list[Any]) -> float:
    numeric_values = [to_float(value) for value in values]
    return sum(numeric_values) / len(numeric_values) if numeric_values else 0.0


def _campaign_analytics_payload(campaign: Campaign, avg_open_rate: float) -> dict[str, Any]:
    analytics = campaign.analytics
    open_rate = to_float(analytics.open_rate) if analytics else 0.0
    if open_rate >= avg_open_rate + 5:
        performance_summary = "above average"
    elif open_rate <= avg_open_rate - 5:
        performance_summary = "below average"
    else:
        performance_summary = "average"

    return {
        "campaign_id": str(campaign.id),
        "name": campaign.name,
        "channel": campaign.channel,
        "status": campaign.status,
        "total_recipients": campaign.total_recipients,
        "total_sent": analytics.total_sent if analytics else 0,
        "total_delivered": analytics.total_delivered if analytics else 0,
        "total_opened": analytics.total_opened if analytics else 0,
        "total_clicked": analytics.total_clicked if analytics else 0,
        "total_converted": analytics.total_converted if analytics else 0,
        "delivery_rate": to_float(analytics.delivery_rate) if analytics else 0.0,
        "open_rate": open_rate,
        "click_rate": to_float(analytics.click_rate) if analytics else 0.0,
        "conversion_rate": to_float(analytics.conversion_rate) if analytics else 0.0,
        "launched_at": _isoformat(campaign.launched_at),
        "performance_summary": performance_summary,
    }


# ---------------------------------------------------------------------------
# Tool executors
# ---------------------------------------------------------------------------


async def execute_get_dashboard_summary(db: AsyncSession, tool_input: dict[str, Any]) -> dict[str, Any]:
    total_customers = int(await db.scalar(select(func.count(Customer.id))) or 0)
    tier_rows = await db.execute(select(Customer.tier, func.count(Customer.id)).group_by(Customer.tier))
    tier_counts = {tier: int(count) for tier, count in tier_rows.all()}
    active_segments = int(await db.scalar(select(func.count(Segment.id)).where(Segment.is_active.is_(True))) or 0)
    campaigns_total = int(await db.scalar(select(func.count(Campaign.id))) or 0)
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    campaigns_this_month = int(
        await db.scalar(select(func.count(Campaign.id)).where(Campaign.created_at >= month_start)) or 0
    )
    total_sent = int(await db.scalar(select(func.coalesce(func.sum(CampaignAnalytics.total_sent), 0))) or 0)
    avg_delivery_rate = to_float(
        await db.scalar(select(func.avg(CampaignAnalytics.delivery_rate)).where(CampaignAnalytics.total_sent > 0))
    )
    avg_open_rate = to_float(
        await db.scalar(select(func.avg(CampaignAnalytics.open_rate)).where(CampaignAnalytics.total_sent > 0))
    )
    avg_click_rate = to_float(
        await db.scalar(select(func.avg(CampaignAnalytics.click_rate)).where(CampaignAnalytics.total_sent > 0))
    )

    best_row = (
        await db.execute(
            select(Campaign.name, Campaign.channel, CampaignAnalytics.open_rate, CampaignAnalytics.click_rate)
            .join(CampaignAnalytics, CampaignAnalytics.campaign_id == Campaign.id)
            .order_by(CampaignAnalytics.open_rate.desc())
            .limit(1)
        )
    ).one_or_none()
    best_campaign = None
    if best_row:
        best_campaign = {
            "name": best_row.name,
            "open_rate": to_float(best_row.open_rate),
            "click_rate": to_float(best_row.click_rate),
            "channel": best_row.channel,
        }

    recent_rows = (
        await db.execute(
            select(Campaign, CampaignAnalytics)
            .outerjoin(CampaignAnalytics, CampaignAnalytics.campaign_id == Campaign.id)
            .order_by(Campaign.created_at.desc())
            .limit(3)
        )
    ).all()
    recent_campaigns = [
        {
            "name": campaign.name,
            "status": campaign.status,
            "total_sent": analytics.total_sent if analytics else 0,
            "open_rate": to_float(analytics.open_rate) if analytics else 0.0,
        }
        for campaign, analytics in recent_rows
    ]

    contacted_exists = select(Communication.id).where(Communication.customer_id == Customer.id).exists()
    customers_never_contacted = int(await db.scalar(select(func.count(Customer.id)).where(~contacted_exists)) or 0)

    return {
        "total_customers": total_customers,
        "bronze_count": tier_counts.get("bronze", 0),
        "silver_count": tier_counts.get("silver", 0),
        "gold_count": tier_counts.get("gold", 0),
        "platinum_count": tier_counts.get("platinum", 0),
        "active_segments": active_segments,
        "campaigns_total": campaigns_total,
        "campaigns_this_month": campaigns_this_month,
        "total_sent": total_sent,
        "avg_delivery_rate": avg_delivery_rate,
        "avg_open_rate": avg_open_rate,
        "avg_click_rate": avg_click_rate,
        "best_campaign": best_campaign,
        "recent_campaigns": recent_campaigns,
        "customers_never_contacted": customers_never_contacted,
    }


async def execute_get_proactive_opportunities(db: AsyncSession, tool_input: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(UTC)
    lapsed_cutoff = now - timedelta(days=90)
    at_risk_start = now - timedelta(days=90)
    at_risk_end = now - timedelta(days=60)

    lapsed_result = await db.execute(
        select(Customer).where(Customer.last_purchase_at.is_not(None), Customer.last_purchase_at < lapsed_cutoff)
    )
    lapsed_customers = list(lapsed_result.scalars().all())
    lapsed_tiers = Counter(customer.tier for customer in lapsed_customers)

    at_risk_result = await db.execute(
        select(Customer).where(
            Customer.last_purchase_at >= at_risk_start,
            Customer.last_purchase_at <= at_risk_end,
            Customer.total_orders >= 2,
        )
    )
    at_risk_customers = list(at_risk_result.scalars().all())

    contacted_exists = select(Communication.id).where(Communication.customer_id == Customer.id).exists()
    uncontacted_result = await db.execute(
        select(Customer).where(Customer.tier.in_(["gold", "platinum"]), ~contacted_exists)
    )
    uncontacted_high_value = list(uncontacted_result.scalars().all())

    disengaged_champions = int(
        await db.scalar(
            select(func.count(Customer.id)).where(
                Customer.tier == "platinum",
                Customer.last_purchase_at.is_not(None),
                Customer.last_purchase_at < now - timedelta(days=45),
            )
        )
        or 0
    )

    recent_rows = (
        await db.execute(
            select(Campaign.channel, CampaignAnalytics.open_rate)
            .join(CampaignAnalytics, CampaignAnalytics.campaign_id == Campaign.id)
            .order_by(Campaign.created_at.desc())
            .limit(3)
        )
    ).all()
    open_rates = [to_float(row.open_rate) for row in recent_rows]
    if len(open_rates) >= 2 and open_rates[0] > open_rates[-1] + 2:
        trend = "improving"
    elif len(open_rates) >= 2 and open_rates[0] < open_rates[-1] - 2:
        trend = "declining"
    else:
        trend = "stable"
    channel_totals: dict[str, list[float]] = {}
    for row in recent_rows:
        channel_totals.setdefault(row.channel, []).append(to_float(row.open_rate))
    best_channel = max(channel_totals.items(), key=lambda item: sum(item[1]) / len(item[1]))[0] if channel_totals else "email"

    return {
        "lapsed_customers": {
            "count": len(lapsed_customers),
            "avg_spend": _average([customer.total_spend for customer in lapsed_customers]),
            "tier_breakdown": {tier: lapsed_tiers.get(tier, 0) for tier in ["bronze", "silver", "gold", "platinum"]},
        },
        "at_risk_customers": {
            "count": len(at_risk_customers),
            "avg_spend": _average([customer.total_spend for customer in at_risk_customers]),
        },
        "uncontacted_high_value": {
            "count": len(uncontacted_high_value),
            "avg_spend": _average([customer.total_spend for customer in uncontacted_high_value]),
        },
        "disengaged_champions": {"count": disengaged_champions},
        "performance_trend": {
            "trend": trend,
            "avg_open_rate": sum(open_rates) / len(open_rates) if open_rates else 0.0,
            "best_performing_channel": best_channel,
        },
    }


async def execute_query_customers(db: AsyncSession, tool_input: dict[str, Any]) -> dict[str, Any]:
    sample_size = min(int(tool_input.get("sample_size", 3)), 5)
    filter_rules = tool_input.get("filter_rules", {"operator": "AND", "conditions": []})
    count, sample = await preview_segment(db, filter_rules, sample_size=sample_size)
    full_sample = await _load_full_customers(db, sample)
    return {
        "total_count": count,
        "sample_customers": [_customer_sample(customer) for customer in full_sample],
        "filter_rules_used": filter_rules,
    }


async def execute_query_orders(db: AsyncSession, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Query order data for analytics, retention, and revenue analysis."""
    query = select(Order).order_by(Order.order_date.desc())
    customer_query = select(Customer)

    if tool_input.get("customer_id"):
        cid = _safe_uuid(tool_input["customer_id"])
        query = query.where(Order.customer_id == cid)

    if tool_input.get("tier"):
        tier_val = tool_input["tier"].lower()
        tier_customers = await db.execute(select(Customer.id).where(Customer.tier == tier_val))
        tier_ids = [r[0] for r in tier_customers.all()]
        if not tier_ids:
            return {"total_orders": 0, "total_revenue": 0, "message": f"No customers in {tier_val} tier"}
        query = query.where(Order.customer_id.in_(tier_ids))
        customer_query = customer_query.where(Customer.tier == tier_val)

    if tool_input.get("days"):
        cutoff = datetime.now(UTC) - timedelta(days=int(tool_input["days"]))
        query = query.where(Order.order_date >= cutoff)

    result = await db.execute(query)
    orders = list(result.scalars().all())

    total_revenue = sum(to_float(o.amount) for o in orders)
    avg_order_value = total_revenue / len(orders) if orders else 0.0

    # Top products
    product_counter: Counter = Counter()
    for order in orders:
        if order.items:
            for item in order.items:
                if isinstance(item, dict):
                    name = item.get("name", "Unknown")
                    product_counter[name] += 1

    # Customers with repeat orders
    customer_ids = [o.customer_id for o in orders]
    customer_order_counts = Counter(customer_ids)
    repeat_buyers = sum(1 for c in customer_order_counts.values() if c > 1)

    return {
        "total_orders": len(orders),
        "total_revenue": round(total_revenue, 2),
        "avg_order_value": round(avg_order_value, 2),
        "unique_customers": len(set(customer_ids)),
        "repeat_buyers": repeat_buyers,
        "repeat_rate": round(repeat_buyers / len(set(customer_ids)) * 100, 1) if customer_ids else 0,
        "top_products": [{"name": n, "count": c} for n, c in product_counter.most_common(5)],
        "recent_orders": [
            {
                "order_date": _isoformat(o.order_date),
                "amount": to_float(o.amount),
                "channel": o.channel,
                "items_count": len(o.items) if o.items else 0,
            }
            for o in orders[:5]
        ],
    }


async def execute_create_segment(db: AsyncSession, tool_input: dict[str, Any]) -> dict[str, Any]:
    segment = Segment(
        name=tool_input["name"],
        description=tool_input["description"],
        filter_rules=tool_input["filter_rules"],
        ai_generated=True,
        prompt_used=tool_input.get("prompt_used", "AI-created segment"),
        is_active=True,
    )
    db.add(segment)
    await db.commit()
    await db.refresh(segment)
    customer_count = await refresh_segment_count(db, segment.id)
    await db.refresh(segment)
    return {
        "segment_id": str(segment.id),
        "name": segment.name,
        "customer_count": customer_count,
        "created": True,
    }


async def execute_get_segment_insights(db: AsyncSession, tool_input: dict[str, Any]) -> dict[str, Any]:
    segment_id = _safe_uuid(tool_input["segment_id"])
    segment = await db.get(Segment, segment_id)
    if segment is None or not segment.is_active:
        return {"error": "Segment not found"}

    customers, total = await evaluate_segment(db, segment.filter_rules)
    customers = await _load_full_customers(db, customers)
    spends = [to_float(customer.total_spend) for customer in customers]
    orders = [customer.total_orders for customer in customers]
    tiers = Counter(customer.tier for customer in customers)
    cities = Counter(customer.city for customer in customers)
    channels = Counter(customer.preferred_channel for customer in customers)
    days_values = [_days_since(customer.last_purchase_at) for customer in customers]
    days_values = [value for value in days_values if value is not None]

    return {
        "segment_name": segment.name,
        "total_customers": total,
        "avg_spend": sum(spends) / len(spends) if spends else 0.0,
        "median_spend": statistics.median(spends) if spends else 0.0,
        "avg_orders": sum(orders) / len(orders) if orders else 0.0,
        "tier_breakdown": {tier: tiers.get(tier, 0) for tier in ["bronze", "silver", "gold", "platinum"]},
        "top_cities": [{"city": city, "count": count} for city, count in cities.most_common(5)],
        "channel_preference": {channel: channels.get(channel, 0) for channel in ["whatsapp", "sms", "email", "rcs"]},
        "avg_days_since_purchase": sum(days_values) / len(days_values) if days_values else 0.0,
        "spend_distribution": {
            "under_1000": sum(1 for spend in spends if spend < 1000),
            "1000_to_5000": sum(1 for spend in spends if 1000 <= spend < 5000),
            "5000_to_15000": sum(1 for spend in spends if 5000 <= spend < 15000),
            "over_15000": sum(1 for spend in spends if spend >= 15000),
        },
    }


async def execute_suggest_best_channel(db: AsyncSession, tool_input: dict[str, Any]) -> dict[str, Any]:
    segment_id = _safe_uuid(tool_input["segment_id"])
    segment = await db.get(Segment, segment_id)
    if segment is None or not segment.is_active:
        return {"error": "Segment not found"}

    customers, total = await evaluate_segment(db, segment.filter_rules)
    customers = await _load_full_customers(db, customers)
    channel_counts = Counter(customer.preferred_channel for customer in customers)
    channels = ["whatsapp", "sms", "email", "rcs"]
    preference = {
        channel: {
            "count": channel_counts.get(channel, 0),
            "percentage": (channel_counts.get(channel, 0) / total * 100) if total else 0.0,
        }
        for channel in channels
    }

    performance_rows = (
        await db.execute(
            select(Campaign.channel, func.count(Campaign.id), func.avg(CampaignAnalytics.open_rate))
            .join(CampaignAnalytics, CampaignAnalytics.campaign_id == Campaign.id)
            .group_by(Campaign.channel)
        )
    ).all()
    historical_defaults = {"whatsapp": 55.0, "email": 45.0, "sms": 30.0, "rcs": 40.0}
    historical = {
        channel: {"campaigns": 0, "avg_open_rate": historical_defaults[channel]}
        for channel in channels
    }
    for channel, campaign_count, avg_open_rate in performance_rows:
        historical[channel] = {"campaigns": int(campaign_count), "avg_open_rate": to_float(avg_open_rate)}

    scores = {
        channel: (preference[channel]["percentage"] * 0.4) + (historical[channel]["avg_open_rate"] * 0.6)
        for channel in channels
    }
    recommended_channel = max(scores, key=scores.get)
    reason = (
        f"{recommended_channel.title()} is the best fit because {preference[recommended_channel]['percentage']:.1f}% "
        f"of this audience prefers it and ZURI's historical open rate on this channel is "
        f"{historical[recommended_channel]['avg_open_rate']:.1f}%."
    )

    return {
        "segment_channel_preference": preference,
        "historical_performance_by_channel": historical,
        "recommended_channel": recommended_channel,
        "recommendation_reason": reason,
    }


async def execute_create_campaign(db: AsyncSession, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Create a DRAFT campaign (does NOT launch)."""
    segment_id = _safe_uuid(tool_input["segment_id"])
    segment = await db.get(Segment, segment_id)
    if segment is None or not segment.is_active:
        return {"error": "Segment not found"}

    segment_customers, total = await evaluate_segment(db, segment.filter_rules)
    if total == 0:
        return {"error": "Segment has no customers"}

    campaign = Campaign(
        name=tool_input["name"],
        segment_id=segment.id,
        channel=tool_input["channel"],
        message_template=tool_input["message_template"],
        ai_generated_message=True,
        ai_generated_segment=segment.ai_generated,
        status="draft",
        total_recipients=total,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    return {
        "campaign_id": str(campaign.id),
        "campaign_name": campaign.name,
        "status": "draft",
        "total_recipients": total,
        "segment_name": segment.name,
        "channel": campaign.channel,
        "message_template": campaign.message_template,
        "message": "Campaign created as DRAFT. Show the preview and ask for confirmation before launching.",
    }


async def execute_launch_campaign(db: AsyncSession, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Launch a draft campaign — creates communications and dispatches."""
    campaign_id = _safe_uuid(tool_input["campaign_id"])
    campaign = await db.execute(
        select(Campaign).options(selectinload(Campaign.analytics)).where(Campaign.id == campaign_id)
    )
    campaign = campaign.scalar_one_or_none()
    if campaign is None:
        return {"error": "Campaign not found"}
    if campaign.status not in ("draft", "paused"):
        return {"error": f"Campaign is {campaign.status}, can only launch draft or paused campaigns"}
    if campaign.segment_id is None:
        return {"error": "Campaign has no segment"}

    segment = await db.get(Segment, campaign.segment_id)
    if segment is None or not segment.is_active:
        return {"error": "Segment not found"}

    segment_customers, total = await evaluate_segment(db, segment.filter_rules)
    if total == 0:
        return {"error": "Segment has no customers"}

    customers = await _load_full_customers(db, segment_customers)

    # Clear old communications and analytics
    await db.execute(sa_delete(Communication).where(Communication.campaign_id == campaign.id))
    await db.execute(sa_delete(CampaignAnalytics).where(CampaignAnalytics.campaign_id == campaign.id))

    for customer in customers:
        personalized_message = await render_message_for_customer(db, campaign.message_template, customer)
        db.add(
            Communication(
                campaign_id=campaign.id,
                customer_id=customer.id,
                channel=campaign.channel,
                personalized_message=personalized_message,
                status="pending",
            )
        )

    db.add(CampaignAnalytics(campaign_id=campaign.id))
    campaign.status = "running"
    campaign.launched_at = datetime.now(UTC)
    campaign.total_recipients = len(customers)
    await db.commit()
    await db.refresh(campaign)

    asyncio.create_task(dispatch_campaign(campaign.id))

    return {
        "campaign_id": str(campaign.id),
        "campaign_name": campaign.name,
        "status": "launched",
        "total_recipients": len(customers),
        "segment_name": segment.name,
        "channel": campaign.channel,
        "message": "Campaign is live! Communications are being dispatched.",
    }


async def execute_create_and_launch_campaign(db: AsyncSession, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Legacy: create + launch atomically. Redirects through new create → launch flow."""
    if tool_input.get("confirmed") is not True:
        return {"error": "Campaign launch requires explicit marketer confirmation first."}

    create_result = await execute_create_campaign(db, tool_input)
    if "error" in create_result:
        return create_result

    launch_result = await execute_launch_campaign(db, {"campaign_id": create_result["campaign_id"]})
    return launch_result


async def execute_get_campaign_analytics(db: AsyncSession, tool_input: dict[str, Any]) -> dict[str, Any]:
    avg_open_rate = to_float(
        await db.scalar(select(func.avg(CampaignAnalytics.open_rate)).where(CampaignAnalytics.total_sent > 0))
    )

    query = (
        select(Campaign)
        .options(selectinload(Campaign.analytics))
        .order_by(Campaign.created_at.desc())
    )
    if tool_input.get("campaign_id"):
        query = query.where(Campaign.id == _safe_uuid(tool_input["campaign_id"]))
    else:
        query = query.limit(5)

    campaigns = list((await db.execute(query)).scalars().all())
    if tool_input.get("campaign_id") and not campaigns:
        return {"error": "Campaign not found"}

    return {"campaigns": [_campaign_analytics_payload(campaign, avg_open_rate) for campaign in campaigns]}


async def execute_get_existing_segments(db: AsyncSession, tool_input: dict[str, Any]) -> dict[str, Any]:
    result = await db.execute(
        select(Segment)
        .where(Segment.is_active.is_(True))
        .order_by(Segment.customer_count.desc(), Segment.created_at.desc())
    )
    segments = list(result.scalars().all())
    return {
        "segments": [
            {
                "segment_id": str(segment.id),
                "name": segment.name,
                "description": segment.description,
                "customer_count": segment.customer_count,
                "ai_generated": segment.ai_generated,
                "created_at": _isoformat(segment.created_at),
            }
            for segment in segments
        ],
        "total": len(segments),
    }


async def execute_draft_campaign_message(db: AsyncSession, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Generate a campaign message template based on segment and goal."""
    channel = tool_input.get("channel", "whatsapp")
    goal = tool_input.get("campaign_goal", "re-engage customers")
    segment_desc = tool_input.get("segment_description", "target customers")

    channel_limits = {"whatsapp": 280, "sms": 160, "email": 500, "rcs": 300}
    max_chars = channel_limits.get(channel, 280)

    if "lapsed" in goal.lower() or "re-engage" in goal.lower() or "win back" in goal.lower():
        templates = [
            f"Hi {{{{name}}}}! We miss you at ZURI 💜 It's been {{{{days_since_purchase}}}} days since your last order. "
            f"As a valued {{{{tier}}}} member, here's a special 20% off on your next purchase. "
            f"Your favourite styles are waiting! Shop now → zuri.in/comeback",
        ]
    elif "upsell" in goal.lower() or "reward" in goal.lower():
        templates = [
            f"Hey {{{{name}}}}! 🌟 Thank you for being a loyal {{{{tier}}}} member at ZURI. "
            f"We've curated an exclusive collection just for you in {{{{city}}}}. "
            f"With {{{{total_orders}}}} orders and counting, you deserve something special! "
            f"Shop your VIP picks → zuri.in/vip",
        ]
    elif "new" in goal.lower() or "welcome" in goal.lower():
        templates = [
            f"Welcome to ZURI, {{{{name}}}}! 🎉 We're thrilled to have you. "
            f"As a {{{{tier}}}} member in {{{{city}}}}, enjoy 15% off your first purchase. "
            f"Discover styles made for you → zuri.in/welcome",
        ]
    else:
        templates = [
            f"Hi {{{{name}}}}! 👋 ZURI has something special for you. "
            f"As a {{{{tier}}}} member with {{{{total_orders}}}} orders, you're one of our best customers. "
            f"Check out what's new in {{{{city}}}} → zuri.in/new",
        ]

    message = templates[0][:max_chars]

    return {
        "message_template": message,
        "channel": channel,
        "char_count": len(message),
        "max_chars": max_chars,
        "tokens_used": ["{{name}}", "{{tier}}", "{{city}}", "{{days_since_purchase}}", "{{total_orders}}"],
    }


async def execute_generate_executive_report(db: AsyncSession, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Generate comprehensive executive report from actual CRM data."""
    # Customer metrics
    total_customers = int(await db.scalar(select(func.count(Customer.id))) or 0)
    tier_rows = await db.execute(select(Customer.tier, func.count(Customer.id)).group_by(Customer.tier))
    tier_counts = {tier: int(count) for tier, count in tier_rows.all()}

    avg_spend = to_float(await db.scalar(select(func.avg(Customer.total_spend))) or 0)
    total_revenue = to_float(await db.scalar(select(func.sum(Customer.total_spend))) or 0)
    avg_orders = to_float(await db.scalar(select(func.avg(Customer.total_orders))) or 0)

    # Order metrics
    total_orders = int(await db.scalar(select(func.count(Order.id))) or 0)
    avg_order_value = to_float(await db.scalar(select(func.avg(Order.amount))) or 0)
    orders_30d = int(
        await db.scalar(
            select(func.count(Order.id)).where(
                Order.order_date >= datetime.now(UTC) - timedelta(days=30)
            )
        ) or 0
    )

    # Retention (customers who ordered more than once)
    repeat_result = await db.execute(
        select(func.count()).select_from(
            select(Order.customer_id)
            .group_by(Order.customer_id)
            .having(func.count(Order.id) > 1)
            .subquery()
        )
    )
    repeat_customers = int(repeat_result.scalar() or 0)
    retention_rate = round(repeat_customers / total_customers * 100, 1) if total_customers else 0

    # Retention by tier
    tier_retention = {}
    for tier in ["bronze", "silver", "gold", "platinum"]:
        tier_customer_ids = await db.execute(select(Customer.id).where(Customer.tier == tier))
        tier_ids = [r[0] for r in tier_customer_ids.all()]
        if tier_ids:
            repeat_in_tier = await db.execute(
                select(func.count()).select_from(
                    select(Order.customer_id)
                    .where(Order.customer_id.in_(tier_ids))
                    .group_by(Order.customer_id)
                    .having(func.count(Order.id) > 1)
                    .subquery()
                )
            )
            repeat_count = int(repeat_in_tier.scalar() or 0)
            tier_retention[tier] = round(repeat_count / len(tier_ids) * 100, 1)
        else:
            tier_retention[tier] = 0

    # Campaign metrics
    campaigns_total = int(await db.scalar(select(func.count(Campaign.id))) or 0)
    launched_campaigns = int(
        await db.scalar(select(func.count(Campaign.id)).where(Campaign.status.in_(["running", "completed"]))) or 0
    )
    avg_open = to_float(
        await db.scalar(select(func.avg(CampaignAnalytics.open_rate)).where(CampaignAnalytics.total_sent > 0))
    )
    avg_click = to_float(
        await db.scalar(select(func.avg(CampaignAnalytics.click_rate)).where(CampaignAnalytics.total_sent > 0))
    )
    total_sent = int(await db.scalar(select(func.coalesce(func.sum(CampaignAnalytics.total_sent), 0))) or 0)

    # Segment metrics
    active_segments = int(await db.scalar(select(func.count(Segment.id)).where(Segment.is_active.is_(True))) or 0)

    # City distribution
    city_rows = await db.execute(
        select(Customer.city, func.count(Customer.id)).group_by(Customer.city).order_by(func.count(Customer.id).desc()).limit(5)
    )
    top_cities = [{"city": city, "count": int(count)} for city, count in city_rows.all()]

    return {
        "report_type": "executive_summary",
        "generated_at": datetime.now(UTC).isoformat(),
        "customer_metrics": {
            "total_customers": total_customers,
            "tier_distribution": tier_counts,
            "avg_spend_per_customer": round(avg_spend, 2),
            "total_revenue": round(total_revenue, 2),
            "avg_orders_per_customer": round(avg_orders, 1),
        },
        "order_metrics": {
            "total_orders": total_orders,
            "avg_order_value": round(avg_order_value, 2),
            "orders_last_30_days": orders_30d,
        },
        "retention_metrics": {
            "overall_retention_rate": retention_rate,
            "repeat_customers": repeat_customers,
            "retention_by_tier": tier_retention,
        },
        "campaign_metrics": {
            "total_campaigns": campaigns_total,
            "launched_campaigns": launched_campaigns,
            "total_communications_sent": total_sent,
            "avg_open_rate": round(avg_open, 1),
            "avg_click_rate": round(avg_click, 1),
        },
        "segment_metrics": {
            "active_segments": active_segments,
        },
        "geography": {
            "top_cities": top_cities,
        },
    }


async def execute_get_customer_insights(db: AsyncSession, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Customer base analytics with optional tier filter."""
    query = select(Customer)
    if tool_input.get("tier"):
        query = query.where(Customer.tier == tool_input["tier"].lower())

    result = await db.execute(query)
    customers = list(result.scalars().all())

    if not customers:
        return {"error": "No customers found"}

    spends = [to_float(c.total_spend) for c in customers]
    orders = [c.total_orders for c in customers]
    tiers = Counter(c.tier for c in customers)
    cities = Counter(c.city for c in customers)
    channels = Counter(c.preferred_channel for c in customers)
    genders = Counter(c.gender for c in customers)
    ages = [c.age for c in customers if c.age]

    now = datetime.now(UTC)
    active_30 = sum(1 for c in customers if c.last_purchase_at and (now - c.last_purchase_at).days <= 30)
    active_90 = sum(1 for c in customers if c.last_purchase_at and (now - c.last_purchase_at).days <= 90)
    lapsed = sum(1 for c in customers if c.last_purchase_at and (now - c.last_purchase_at).days > 90)
    never_purchased = sum(1 for c in customers if c.last_purchase_at is None)

    return {
        "total_customers": len(customers),
        "avg_spend": round(sum(spends) / len(spends), 2) if spends else 0,
        "median_spend": round(statistics.median(spends), 2) if spends else 0,
        "total_revenue": round(sum(spends), 2),
        "avg_orders": round(sum(orders) / len(orders), 1) if orders else 0,
        "tier_distribution": {t: tiers.get(t, 0) for t in ["bronze", "silver", "gold", "platinum"]},
        "top_cities": [{"city": c, "count": n} for c, n in cities.most_common(5)],
        "channel_preference": {ch: channels.get(ch, 0) for ch in ["whatsapp", "sms", "email", "rcs"]},
        "gender_distribution": dict(genders),
        "age_stats": {
            "avg_age": round(sum(ages) / len(ages), 1) if ages else 0,
            "min_age": min(ages) if ages else 0,
            "max_age": max(ages) if ages else 0,
        },
        "activity": {
            "active_30_days": active_30,
            "active_90_days": active_90,
            "lapsed_90_plus_days": lapsed,
            "never_purchased": never_purchased,
        },
    }


async def execute_delete_campaign(db: AsyncSession, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Delete a draft campaign."""
    campaign_id = _safe_uuid(tool_input["campaign_id"])
    campaign = await db.get(Campaign, campaign_id)
    if campaign is None:
        return {"error": "Campaign not found"}
    if campaign.status not in ("draft",):
        return {"error": f"Cannot delete a {campaign.status} campaign. Only draft campaigns can be deleted."}

    name = campaign.name
    await db.execute(sa_delete(Communication).where(Communication.campaign_id == campaign_id))
    await db.execute(sa_delete(CampaignAnalytics).where(CampaignAnalytics.campaign_id == campaign_id))
    await db.delete(campaign)
    await db.commit()
    return {"deleted": True, "campaign_name": name}


async def execute_update_campaign(db: AsyncSession, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Update a draft campaign."""
    campaign_id = _safe_uuid(tool_input["campaign_id"])
    campaign = await db.get(Campaign, campaign_id)
    if campaign is None:
        return {"error": "Campaign not found"}
    if campaign.status != "draft":
        return {"error": f"Cannot update a {campaign.status} campaign"}

    if "name" in tool_input:
        campaign.name = tool_input["name"]
    if "message_template" in tool_input:
        campaign.message_template = tool_input["message_template"]
    if "channel" in tool_input:
        campaign.channel = tool_input["channel"]

    await db.commit()
    await db.refresh(campaign)

    return {
        "campaign_id": str(campaign.id),
        "name": campaign.name,
        "channel": campaign.channel,
        "status": campaign.status,
        "updated": True,
    }


# ---------------------------------------------------------------------------
# Tool executor registry
# ---------------------------------------------------------------------------

TOOL_EXECUTORS: dict[str, ToolExecutor] = {
    "get_dashboard_summary": execute_get_dashboard_summary,
    "get_proactive_opportunities": execute_get_proactive_opportunities,
    "query_customers": execute_query_customers,
    "query_orders": execute_query_orders,
    "create_segment": execute_create_segment,
    "get_segment_insights": execute_get_segment_insights,
    "suggest_best_channel": execute_suggest_best_channel,
    "create_campaign": execute_create_campaign,
    "launch_campaign": execute_launch_campaign,
    "create_and_launch_campaign": execute_create_and_launch_campaign,
    "get_campaign_analytics": execute_get_campaign_analytics,
    "get_existing_segments": execute_get_existing_segments,
    "draft_campaign_message": execute_draft_campaign_message,
    "generate_executive_report": execute_generate_executive_report,
    "get_customer_insights": execute_get_customer_insights,
    "delete_campaign": execute_delete_campaign,
    "update_campaign": execute_update_campaign,
}


# ---------------------------------------------------------------------------
# Context injection
# ---------------------------------------------------------------------------


async def _build_context_summary(db: AsyncSession) -> str:
    """Build a concise CRM context string injected before every AI request."""
    total_customers = int(await db.scalar(select(func.count(Customer.id))) or 0)
    tier_rows = await db.execute(select(Customer.tier, func.count(Customer.id)).group_by(Customer.tier))
    tiers = {t: int(c) for t, c in tier_rows.all()}

    active_segments = int(await db.scalar(select(func.count(Segment.id)).where(Segment.is_active.is_(True))) or 0)
    total_campaigns = int(await db.scalar(select(func.count(Campaign.id))) or 0)
    total_comms = int(await db.scalar(select(func.coalesce(func.sum(CampaignAnalytics.total_sent), 0))) or 0)

    avg_open = to_float(
        await db.scalar(select(func.avg(CampaignAnalytics.open_rate)).where(CampaignAnalytics.total_sent > 0))
    )

    recent = (
        await db.execute(
            select(Campaign.name, Campaign.status, Campaign.channel)
            .order_by(Campaign.created_at.desc())
            .limit(3)
        )
    ).all()
    recent_str = ", ".join(f"{r.name} ({r.status}, {r.channel})" for r in recent) if recent else "None"

    seg_rows = (
        await db.execute(
            select(Segment.name, Segment.customer_count)
            .where(Segment.is_active.is_(True))
            .order_by(Segment.customer_count.desc())
            .limit(3)
        )
    ).all()
    seg_str = ", ".join(f"{s.name} ({s.customer_count})" for s in seg_rows) if seg_rows else "None"

    return (
        f"[ZURI CRM CONTEXT] "
        f"Customers: {total_customers} "
        f"(Bronze:{tiers.get('bronze',0)}, Silver:{tiers.get('silver',0)}, "
        f"Gold:{tiers.get('gold',0)}, Platinum:{tiers.get('platinum',0)}). "
        f"Segments: {active_segments}. Campaigns: {total_campaigns}. "
        f"Communications sent: {total_comms}. Avg open rate: {avg_open:.1f}%. "
        f"Recent campaigns: {recent_str}. "
        f"Top segments: {seg_str}."
    )


# ---------------------------------------------------------------------------
# Groq integration
# ---------------------------------------------------------------------------


def _normalize_history_message(message: dict[str, Any]) -> dict[str, Any]:
    role = message.get("role", "user")
    normalized: dict[str, Any] = {"role": role, "content": message.get("content", "")}

    if role == "assistant" and message.get("tool_calls") is not None:
        normalized["tool_calls"] = message["tool_calls"]
    if role == "tool" and message.get("tool_call_id") is not None:
        normalized["tool_call_id"] = message["tool_call_id"]
    return normalized


def _assistant_message_to_dict(message: Any) -> dict[str, Any]:
    content = message.content or ""
    assistant_message: dict[str, Any] = {"role": "assistant", "content": content}

    tool_calls = getattr(message, "tool_calls", None) or []
    if tool_calls:
        assistant_message["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments or "{}",
                },
            }
            for tool_call in tool_calls
        ]
    return assistant_message


async def _create_groq_completion(messages: list[dict[str, Any]]) -> Any:
    try:
        return await asyncio.to_thread(
            client.chat.completions.create,
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
    except Exception as exc:
        error_msg = str(exc).lower()
        if "rate_limit" in error_msg or "429" in error_msg:
            logger.warning("Groq rate limit hit: %s", exc)
            raise RuntimeError(
                "I'm temporarily at my API limit. Please try again in a few minutes. "
                "In the meantime, you can use the dashboard and explore campaigns manually."
            ) from exc
        raise


async def process_chat(
    db: AsyncSession,
    conversation_history: list[dict[str, Any]],
    new_message: str,
) -> dict[str, Any]:
    """
    Processes a user message through the Groq agent with tool use.
    Includes context injection and argument repair.
    """
    # Build context summary and inject it
    try:
        context = await _build_context_summary(db)
    except Exception:
        context = "[ZURI CRM CONTEXT] Context loading failed — use tools to fetch data."

    system_with_context = f"{SYSTEM_PROMPT}\n\n{context}"

    messages = [{"role": "system", "content": system_with_context}]
    messages.extend(_normalize_history_message(message) for message in conversation_history)
    messages.append({"role": "user", "content": new_message})

    tools_used: list[str] = []
    actions_taken: list[dict[str, Any]] = []
    max_iterations = 12
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        try:
            response = await _create_groq_completion(messages)
        except Exception as exc:
            logger.exception("Groq API request failed")
            return {
                "response": f"I had trouble reaching the AI model: {exc}. Please try again in a moment.",
                "tools_used": tools_used,
                "actions_taken": actions_taken,
                "conversation_history": messages[1:],
            }

        choice = response.choices[0]
        message = choice.message
        finish_reason = choice.finish_reason

        if finish_reason == "stop":
            text_response = message.content or ""
            messages.append({"role": "assistant", "content": text_response})
            return {
                "response": text_response,
                "tools_used": tools_used,
                "actions_taken": actions_taken,
                "conversation_history": messages[1:],
            }

        if finish_reason == "tool_calls":
            messages.append(_assistant_message_to_dict(message))
            tool_calls = message.tool_calls or []

            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                raw_arguments = tool_call.function.arguments or "{}"

                # Attempt JSON parse with repair
                tool_input = _repair_json(raw_arguments)
                # Normalize arguments
                tool_input = _normalize_tool_input(tool_name, tool_input)

                logger.info(
                    "Executing AI tool",
                    extra={
                        "tool_name": tool_name,
                        "tool_input": json.dumps(tool_input, default=str)[:500],
                    },
                )

                try:
                    executor = TOOL_EXECUTORS.get(tool_name)
                    if executor:
                        result = await executor(db, tool_input)
                    else:
                        result = {"error": f"Unknown tool: {tool_name}"}

                    tools_used.append(tool_name)

                    # Track actions
                    if tool_name == "create_and_launch_campaign" and "campaign_id" in result:
                        actions_taken.append({
                            "type": "campaign_launched",
                            "campaign_id": result["campaign_id"],
                            "campaign_name": result.get("campaign_name"),
                            "total_recipients": result.get("total_recipients"),
                        })
                    elif tool_name == "launch_campaign" and "campaign_id" in result and result.get("status") == "launched":
                        actions_taken.append({
                            "type": "campaign_launched",
                            "campaign_id": result["campaign_id"],
                            "campaign_name": result.get("campaign_name"),
                            "total_recipients": result.get("total_recipients"),
                        })
                    elif tool_name == "create_campaign" and "campaign_id" in result:
                        actions_taken.append({
                            "type": "campaign_created",
                            "campaign_id": result["campaign_id"],
                            "campaign_name": result.get("campaign_name"),
                            "total_recipients": result.get("total_recipients"),
                        })
                    elif tool_name == "create_segment" and "segment_id" in result:
                        actions_taken.append({
                            "type": "segment_created",
                            "segment_id": result["segment_id"],
                            "segment_name": result.get("name"),
                            "customer_count": result.get("customer_count"),
                        })

                except Exception as exc:
                    logger.exception("AI tool failed", extra={"tool_name": tool_name})
                    result = {
                        "error": f"Tool execution failed: {exc}",
                        "tool": tool_name,
                        "suggestion": "Try again with different parameters or a simpler query.",
                    }

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, default=str),
                    }
                )
            continue

        logger.warning("Unexpected Groq finish reason", extra={"finish_reason": finish_reason})
        break

    return {
        "response": "I ran into an issue processing your request. Please try again.",
        "tools_used": tools_used,
        "actions_taken": actions_taken,
        "conversation_history": messages[1:],
    }


# ---------------------------------------------------------------------------
# Proactive insights (opportunity cards on copilot load)
# ---------------------------------------------------------------------------


async def generate_proactive_insights(db: AsyncSession) -> list[dict[str, Any]]:
    """
    Analyzes the customer base and returns 3-5 actionable opportunity cards.
    Displayed on the AI copilot panel before the marketer says anything.
    """
    opportunities_data = await execute_get_proactive_opportunities(db, {})
    await execute_get_dashboard_summary(db, {})

    cards: list[dict[str, Any]] = []

    lapsed = opportunities_data.get("lapsed_customers", {})
    if lapsed.get("count", 0) >= 5:
        cards.append(
            {
                "id": "opp_lapsed",
                "priority": "high",
                "icon": "🎯",
                "title": f"{lapsed['count']} lapsed customers ready for re-engagement",
                "description": f"These customers spent ₹{lapsed['avg_spend']:,.0f} on average but haven't bought in 90+ days. A targeted WhatsApp re-engagement campaign typically recovers 12-18% of this segment.",
                "suggested_action": "Launch re-engagement campaign",
                "estimated_audience": lapsed["count"],
                "suggested_filter_rules": {
                    "operator": "AND",
                    "conditions": [
                        {"field": "last_purchase_at", "operator": "days_ago_gte", "value": 90},
                    ],
                },
                "suggested_channel": "whatsapp",
                "quick_prompt": "Create a WhatsApp re-engagement campaign for customers who haven't bought in 90+ days",
            }
        )

    at_risk = opportunities_data.get("at_risk_customers", {})
    if at_risk.get("count", 0) >= 5:
        cards.append(
            {
                "id": "opp_at_risk",
                "priority": "high",
                "icon": "⚠️",
                "title": f"{at_risk['count']} customers slipping away — intervene now",
                "description": f"These customers used to buy regularly but haven't purchased in 60-90 days. At this stage, a well-timed offer can prevent full churn. Average spend: ₹{at_risk['avg_spend']:,.0f}.",
                "suggested_action": "Send early intervention campaign",
                "estimated_audience": at_risk["count"],
                "suggested_filter_rules": {
                    "operator": "AND",
                    "conditions": [
                        {"field": "last_purchase_at", "operator": "days_ago_gte", "value": 60},
                        {"field": "last_purchase_at", "operator": "days_ago_lte", "value": 90},
                        {"field": "total_orders", "operator": "gte", "value": 2},
                    ],
                },
                "suggested_channel": "whatsapp",
                "quick_prompt": "Create an at-risk intervention campaign for customers who bought 2+ times but haven't purchased in 60-90 days",
            }
        )

    uncontacted = opportunities_data.get("uncontacted_high_value", {})
    if uncontacted.get("count", 0) >= 3:
        cards.append(
            {
                "id": "opp_uncontacted_hv",
                "priority": "medium",
                "icon": "⭐",
                "title": f"{uncontacted['count']} high-value customers never contacted",
                "description": f"These Gold and Platinum customers (avg spend ₹{uncontacted['avg_spend']:,.0f}) have never received a campaign from ZURI. This is untapped revenue sitting in your database.",
                "suggested_action": "Launch VIP engagement campaign",
                "estimated_audience": uncontacted["count"],
                "suggested_filter_rules": {
                    "operator": "AND",
                    "conditions": [
                        {"field": "tier", "operator": "in", "value": ["gold", "platinum"]},
                    ],
                },
                "suggested_channel": "email",
                "quick_prompt": "Create a VIP campaign for Gold and Platinum customers who have never been contacted",
            }
        )

    perf = opportunities_data.get("performance_trend", {})
    if perf.get("avg_open_rate", 0) > 0:
        trend = perf.get("trend", "stable")
        icon = "📈" if trend == "improving" else ("📉" if trend == "declining" else "📊")
        cards.append(
            {
                "id": "opp_performance",
                "priority": "low",
                "icon": icon,
                "title": f"Campaign performance is {trend}",
                "description": f"Your recent campaigns average {perf['avg_open_rate']:.1f}% open rate. Best performing channel: {perf.get('best_performing_channel', 'email')}. {'Great momentum — keep going!' if trend == 'improving' else 'Consider refreshing your message strategy.' if trend == 'declining' else 'Steady performance. Try a new segment or channel to improve.'}",
                "suggested_action": "View campaign analytics",
                "estimated_audience": None,
                "quick_prompt": "Show me my recent campaign performance and tell me what's working",
            }
        )

    champions = opportunities_data.get("disengaged_champions", {})
    if champions.get("count", 0) >= 2:
        cards.append(
            {
                "id": "opp_champions",
                "priority": "medium",
                "icon": "👑",
                "title": f"{champions['count']} Platinum customers going quiet",
                "description": "Your top-tier Platinum customers haven't bought in 45+ days. These are your highest-value customers — a personal, exclusive message from ZURI can bring them back fast.",
                "suggested_action": "Send exclusive Platinum campaign",
                "estimated_audience": champions["count"],
                "suggested_filter_rules": {
                    "operator": "AND",
                    "conditions": [
                        {"field": "tier", "operator": "eq", "value": "platinum"},
                        {"field": "last_purchase_at", "operator": "days_ago_gte", "value": 45},
                    ],
                },
                "suggested_channel": "whatsapp",
                "quick_prompt": "Create an exclusive campaign for Platinum customers who haven't bought in 45+ days",
            }
        )

    priority_order = {"high": 0, "medium": 1, "low": 2}
    cards.sort(key=lambda card: priority_order.get(card["priority"], 3))
    return cards[:4]
