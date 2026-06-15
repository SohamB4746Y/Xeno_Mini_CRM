from __future__ import annotations

import asyncio
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
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import Campaign, CampaignAnalytics, Communication, Customer, Segment
from services.campaign_launcher import dispatch_campaign
from services.message_renderer import render_message_for_customer
from services.segment_engine import evaluate_segment, preview_segment, refresh_segment_count

load_dotenv()

logger = logging.getLogger(__name__)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

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
   pick the channel, and launch the campaign. The marketer describes intent;
   you do the work.

3. EXPLAIN IN PLAIN LANGUAGE — Describe exactly what you are doing and why.
   Never use technical jargon. Speak like a sharp marketing strategist, not
   an engineer. A marketer who has never written SQL should understand every
   decision you make.

4. ALWAYS CONFIRM BEFORE LAUNCHING — Before firing any campaign, show a clear
   preview and ask for explicit confirmation. Never call create_and_launch_campaign
   unless the marketer has explicitly said "yes", "launch it", "go ahead",
   "confirm", "do it", or given clear approval.

5. FOLLOW UP WITH INTELLIGENCE — When asked about campaign performance, don't
   just report numbers. Interpret them. "Your open rate of 67% is 2x your average
   — here is what worked." That is what a marketing intelligence system does.

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
"""

TOOLS = [{'type': 'function',
  'function': {'name': 'get_dashboard_summary',
               'description': 'Get a real-time summary of the ZURI CRM: total customers, active segments, recent '
                              'campaign performance, and overall health of the customer base. Call this at the start '
                              'of every conversation to understand the current state.',
               'parameters': {'type': 'object', 'properties': {}, 'required': []}}},
 {'type': 'function',
  'function': {'name': 'get_proactive_opportunities',
               'description': 'Analyze the customer base to identify the top marketing opportunities right now — '
                              'lapsed customers, at-risk customers, high-value segments not recently contacted, and '
                              'performance trends. Returns structured opportunity data.',
               'parameters': {'type': 'object', 'properties': {}, 'required': []}}},
 {'type': 'function',
  'function': {'name': 'query_customers',
               'description': 'Query customers using behavioral and demographic filters to understand a potential '
                              'audience. Use this to check audience size and composition BEFORE creating a segment. '
                              'Returns count and sample customers.',
               'parameters': {'type': 'object',
                              'properties': {'filter_rules': {'type': 'object',
                                                              'description': "Filter rules: {operator: 'AND'|'OR', "
                                                                             'conditions: [{field, operator, value}]}. '
                                                                             'Supported fields: total_orders, '
                                                                             'total_spend, last_purchase_at (use '
                                                                             'days_ago_gte/days_ago_lte), tier, '
                                                                             'preferred_channel, city, gender, age. '
                                                                             'Operators: eq, neq, gte, lte, gt, lt, '
                                                                             'in, not_in, days_ago_gte, days_ago_lte.',
                                                              'properties': {'operator': {'type': 'string',
                                                                                          'enum': ['AND', 'OR']},
                                                                             'conditions': {'type': 'array',
                                                                                            'items': {'type': 'object'}}},
                                                              'required': ['operator', 'conditions']},
                                             'sample_size': {'type': 'integer',
                                                             'description': 'Number of sample customers to return '
                                                                            '(default 3, max 5)',
                                                             'default': 3}},
                              'required': ['filter_rules']}}},
 {'type': 'function',
  'function': {'name': 'create_segment',
               'description': 'Create and save a named customer segment in the CRM database. Call query_customers '
                              'first to verify the audience size. Sets ai_generated=true automatically.',
               'parameters': {'type': 'object',
                              'properties': {'name': {'type': 'string',
                                                      'description': 'Short, descriptive segment name'},
                                             'description': {'type': 'string',
                                                             'description': 'Plain English description of who is in '
                                                                            'this segment and why'},
                                             'filter_rules': {'type': 'object',
                                                              'description': 'Same format as query_customers '
                                                                             'filter_rules'},
                                             'prompt_used': {'type': 'string',
                                                             'description': "The marketer's original natural language "
                                                                            'request that created this segment'}},
                              'required': ['name', 'description', 'filter_rules', 'prompt_used']}}},
 {'type': 'function',
  'function': {'name': 'get_segment_insights',
               'description': 'Get deep analytics about a saved segment — customer count, average spend, tier '
                              'breakdown, top cities, preferred channel distribution, top product categories. Use this '
                              'to explain WHY a segment is worth targeting.',
               'parameters': {'type': 'object',
                              'properties': {'segment_id': {'type': 'string', 'description': 'UUID of the segment'}},
                              'required': ['segment_id']}}},
 {'type': 'function',
  'function': {'name': 'suggest_best_channel',
               'description': "Analyze a segment's preferred channel distribution and compare with historical campaign "
                              'performance by channel to recommend the optimal delivery channel for maximum '
                              'engagement.',
               'parameters': {'type': 'object',
                              'properties': {'segment_id': {'type': 'string',
                                                            'description': 'UUID of the segment to analyze'}},
                              'required': ['segment_id']}}},
 {'type': 'function',
  'function': {'name': 'create_and_launch_campaign',
               'description': 'Create a campaign and immediately launch it to the segment. CRITICAL: Only call this '
                              'when confirmed=true AND the marketer has explicitly approved. Show the campaign preview '
                              'first and get confirmation before calling this.',
               'parameters': {'type': 'object',
                              'properties': {'name': {'type': 'string', 'description': 'Campaign name'},
                                             'segment_id': {'type': 'string',
                                                            'description': 'UUID of the target segment'},
                                             'channel': {'type': 'string',
                                                         'enum': ['whatsapp', 'sms', 'email', 'rcs'],
                                                         'description': 'Delivery channel'},
                                             'message_template': {'type': 'string',
                                                                  'description': 'Personalized message template with '
                                                                                 'tokens: {{name}}, {{city}}, '
                                                                                 '{{tier}}, {{last_product}}, '
                                                                                 '{{days_since_purchase}}, '
                                                                                 '{{total_orders}}, {{total_spend}}'},
                                             'confirmed': {'type': 'boolean',
                                                           'description': 'MUST be true. The marketer has explicitly '
                                                                          'confirmed they want to launch this '
                                                                          'campaign.'}},
                              'required': ['name', 'segment_id', 'channel', 'message_template', 'confirmed']}}},
 {'type': 'function',
  'function': {'name': 'get_campaign_analytics',
               'description': 'Get performance analytics for campaigns. Without campaign_id returns the last 5 '
                              'campaigns with full stats. With campaign_id returns detailed analytics for one campaign '
                              'including open rate, click rate, conversion rate.',
               'parameters': {'type': 'object',
                              'properties': {'campaign_id': {'type': 'string',
                                                             'description': 'Optional: specific campaign UUID. If '
                                                                            'omitted, returns last 5 campaigns.'}},
                              'required': []}}},
 {'type': 'function',
  'function': {'name': 'get_existing_segments',
               'description': 'Get all existing saved segments in the CRM with their names, descriptions, customer '
                              'counts, and filter rules. Use this to avoid creating duplicate segments and to '
                              'reference existing audiences.',
               'parameters': {'type': 'object', 'properties': {}, 'required': []}}}]

ToolExecutor = Callable[[AsyncSession, dict[str, Any]], Awaitable[dict[str, Any]]]


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
        return uuid.UUID(value)
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
    filter_rules = tool_input["filter_rules"]
    count, sample = await preview_segment(db, filter_rules, sample_size=sample_size)
    full_sample = await _load_full_customers(db, sample)
    return {
        "total_count": count,
        "sample_customers": [_customer_sample(customer) for customer in full_sample],
        "filter_rules_used": filter_rules,
    }


async def execute_create_segment(db: AsyncSession, tool_input: dict[str, Any]) -> dict[str, Any]:
    segment = Segment(
        name=tool_input["name"],
        description=tool_input["description"],
        filter_rules=tool_input["filter_rules"],
        ai_generated=True,
        prompt_used=tool_input["prompt_used"],
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


async def execute_create_and_launch_campaign(db: AsyncSession, tool_input: dict[str, Any]) -> dict[str, Any]:
    if tool_input.get("confirmed") is not True:
        return {"error": "Campaign launch requires explicit marketer confirmation first."}

    segment_id = _safe_uuid(tool_input["segment_id"])
    segment = await db.get(Segment, segment_id)
    if segment is None or not segment.is_active:
        return {"error": "Segment not found"}

    segment_customers, total = await evaluate_segment(db, segment.filter_rules)
    if total == 0:
        return {"error": "Segment has no customers"}
    customers = await _load_full_customers(db, segment_customers)

    campaign = Campaign(
        name=tool_input["name"],
        segment_id=segment.id,
        channel=tool_input["channel"],
        message_template=tool_input["message_template"],
        ai_generated_message=True,
        ai_generated_segment=True,
        status="draft",
    )
    db.add(campaign)
    await db.flush()

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
        "message": "Campaign is live! Communications are being dispatched to the channel service.",
    }


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


TOOL_EXECUTORS: dict[str, ToolExecutor] = {
    "get_dashboard_summary": execute_get_dashboard_summary,
    "get_proactive_opportunities": execute_get_proactive_opportunities,
    "query_customers": execute_query_customers,
    "create_segment": execute_create_segment,
    "get_segment_insights": execute_get_segment_insights,
    "suggest_best_channel": execute_suggest_best_channel,
    "create_and_launch_campaign": execute_create_and_launch_campaign,
    "get_campaign_analytics": execute_get_campaign_analytics,
    "get_existing_segments": execute_get_existing_segments,
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
    return await asyncio.to_thread(
        client.chat.completions.create,
        model=MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
    )


async def process_chat(
    db: AsyncSession,
    conversation_history: list[dict[str, Any]],
    new_message: str,
) -> dict[str, Any]:
    """
    Processes a user message through the Groq agent with OpenAI-compatible tool use.
    Runs the full agentic loop until the model gives a final text response.
    Returns the response and updated conversation history.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(_normalize_history_message(message) for message in conversation_history)
    messages.append({"role": "user", "content": new_message})

    tools_used: list[str] = []
    actions_taken: list[dict[str, Any]] = []
    max_iterations = 10
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
                try:
                    tool_input = json.loads(raw_arguments)
                except json.JSONDecodeError:
                    tool_input = {}
                    result = {"error": "Invalid tool arguments", "raw_arguments": raw_arguments}
                else:
                    logger.info(
                        "Executing AI tool",
                        extra={"tool_name": tool_name, "tool_input": json.dumps(tool_input, default=str)[:500]},
                    )
                    try:
                        executor = TOOL_EXECUTORS.get(tool_name)
                        if executor:
                            result = await executor(db, tool_input)
                        else:
                            result = {"error": f"Unknown tool: {tool_name}"}

                        tools_used.append(tool_name)
                        if tool_name == "create_and_launch_campaign" and "campaign_id" in result:
                            actions_taken.append(
                                {
                                    "type": "campaign_launched",
                                    "campaign_id": result["campaign_id"],
                                    "campaign_name": result.get("campaign_name"),
                                    "total_recipients": result.get("total_recipients"),
                                }
                            )
                        elif tool_name == "create_segment" and "segment_id" in result:
                            actions_taken.append(
                                {
                                    "type": "segment_created",
                                    "segment_id": result["segment_id"],
                                    "segment_name": result.get("name"),
                                    "customer_count": result.get("customer_count"),
                                }
                            )
                    except Exception as exc:
                        logger.exception("AI tool failed", extra={"tool_name": tool_name})
                        result = {"error": str(exc), "tool": tool_name}

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


async def generate_proactive_insights(db: AsyncSession) -> list[dict[str, Any]]:
    """
    Analyzes the customer base and returns 3-5 actionable opportunity cards.
    These are displayed on the AI copilot panel on load, before the marketer says anything.
    This is the "AI drives" feature — proactive intelligence without being asked.
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
