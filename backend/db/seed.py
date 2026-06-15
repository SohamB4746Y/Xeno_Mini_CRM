from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
import os
from pathlib import Path
import random
import re
from typing import Any
from uuid import UUID, uuid4

import asyncpg
from dotenv import load_dotenv

load_dotenv()

RANDOM_SEED = 20260615
CUSTOMER_COUNT = 250

CITY_STATE_DISTRIBUTION = [
    (("Mumbai", "Maharashtra"), 63),
    (("Delhi", "Delhi"), 50),
    (("Bangalore", "Karnataka"), 38),
    (("Chennai", "Tamil Nadu"), 25),
    (("Hyderabad", "Telangana"), 25),
    (("Pune", "Maharashtra"), 20),
    (("Kolkata", "West Bengal"), 12),
    (("Ahmedabad", "Gujarat"), 7),
    (("Jaipur", "Rajasthan"), 5),
    (("Surat", "Gujarat"), 5),
]

AGE_BUCKETS = [
    ((18, 24), 50),
    ((25, 34), 88),
    ((35, 44), 62),
    ((45, 54), 38),
    ((55, 68), 12),
]

GENDER_DISTRIBUTION = [("female", 175), ("male", 50), ("other", 25)]
CHANNEL_DISTRIBUTION = [("whatsapp", 100), ("email", 75), ("sms", 50), ("rcs", 25)]
TARGET_TIER_DISTRIBUTION = [("bronze", 100), ("silver", 75), ("gold", 50), ("platinum", 25)]

FIRST_NAMES = {
    "female": [
        "Aarohi", "Aditi", "Ananya", "Avni", "Diya", "Ishita", "Kavya", "Meera", "Naina", "Pooja",
        "Riya", "Saanvi", "Shruti", "Tanvi", "Zara", "Anika", "Mira", "Nandini", "Priya", "Roshni",
        "Lakshmi", "Meenakshi", "Aishwarya", "Divya", "Keerthi", "Madhumita", "Rukmini", "Sahana",
        "Anushka", "Sayani", "Moumita", "Ritwika", "Mitali", "Sohini", "Sneha", "Ira", "Jhanvi",
    ],
    "male": [
        "Aarav", "Aditya", "Arjun", "Dev", "Ishaan", "Kabir", "Karan", "Rahul", "Rohan", "Vihaan",
        "Siddharth", "Nikhil", "Vikram", "Sourav", "Arindam", "Ritwik", "Sanjay", "Pranav", "Harsh",
    ],
    "other": [
        "Aadi", "Arya", "Daksh", "Ekam", "Ira", "Jai", "Kiran", "Mahi", "Noor", "Reva",
        "Rumi", "Sasha", "Tara", "Veda", "Zian",
    ],
}

LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Mehta", "Kapoor", "Malhotra", "Iyer", "Menon", "Nair", "Raman",
    "Subramanian", "Krishnan", "Chatterjee", "Banerjee", "Mukherjee", "Das", "Ghosh", "Patel",
    "Shah", "Desai", "Joshi", "Kulkarni", "Rao", "Reddy", "Khan", "Singh", "Agarwal", "Bose",
]

PRODUCT_CATALOG = {
    "sarees": [
        ("Banarasi Silk Saree - Ruby Red", 9500),
        ("Kanjivaram Silk Saree - Emerald Green", 12500),
        ("Chanderi Cotton Saree - Ivory Gold", 4200),
        ("Linen Saree - Indigo Bloom", 3200),
        ("Designer Organza Saree - Rose Mist", 7800),
    ],
    "kurtas": [
        ("Anarkali Kurta Set - Mustard", 3600),
        ("Cotton Kurta - Block Print Blue", 1800),
        ("Embroidered Kurta Set - Wine", 5200),
        ("Straight Kurta - Sage Green", 2200),
        ("Festive Sharara Kurta Set - Coral", 6800),
    ],
    "lehengas": [
        ("Bridal Lehenga - Maroon Zari", 24500),
        ("Party Lehenga - Champagne Sequin", 14800),
        ("Printed Casual Lehenga - Peach", 8500),
        ("Velvet Lehenga - Midnight Blue", 18500),
    ],
    "western": [
        ("Wrap Dress - Floral Noir", 2800),
        ("Denim Jacket - Washed Blue", 3200),
        ("Satin Top - Copper", 1900),
        ("Wide Leg Denim - Charcoal", 2600),
        ("Midi Dress - Emerald", 4200),
    ],
    "accessories": [
        ("Kundan Earrings - Pearl Drop", 1200),
        ("Embroidered Potli Bag - Gold", 1500),
        ("Kolhapuri Sandals - Tan", 1400),
        ("Oxidised Silver Necklace", 950),
        ("Beaded Clutch - Wine", 1800),
    ],
}


@dataclass
class CustomerSeed:
    id: UUID
    name: str
    email: str
    phone: str
    city: str
    state: str
    age: int
    gender: str
    preferred_channel: str
    target_tier: str
    created_at: datetime


def build_weighted_values(distribution: list[tuple[Any, int]]) -> list[Any]:
    values: list[Any] = []
    for value, count in distribution:
        values.extend([value] * count)
    random.shuffle(values)
    return values


def normalize_database_url(url: str) -> str:
    normalized = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if "sslmode=require" in normalized and "ssl=" not in normalized:
        normalized = re.sub(r"([?&])sslmode=require(&?)", r"\1ssl=require\2", normalized)
        normalized = normalized.rstrip("?&")
    return normalized


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required to run the seed script")
    return normalize_database_url(url)


def progress(message: str) -> None:
    print(message, flush=True)


def unique_email(name: str, index: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", ".", name.lower()).strip(".")
    return f"{slug}.{index:03d}@example.com"


def indian_phone(index: int) -> str:
    prefix = random.choice(["6", "7", "8", "9"])
    return f"+91{prefix}{random.randint(100000000, 999999999):09d}"[:-3] + f"{index:03d}"


def random_datetime_between(start: datetime, end: datetime) -> datetime:
    seconds = int((end - start).total_seconds())
    if seconds <= 0:
        return end
    return start + timedelta(seconds=random.randint(0, seconds))


def build_customers() -> list[CustomerSeed]:
    cities = build_weighted_values(CITY_STATE_DISTRIBUTION)
    genders = build_weighted_values(GENDER_DISTRIBUTION)
    channels = build_weighted_values(CHANNEL_DISTRIBUTION)
    tiers = build_weighted_values(TARGET_TIER_DISTRIBUTION)
    age_ranges = build_weighted_values(AGE_BUCKETS)
    customers: list[CustomerSeed] = []
    now = datetime.now(UTC)

    for index in range(CUSTOMER_COUNT):
        gender = genders[index]
        first_name = random.choice(FIRST_NAMES[gender])
        last_name = random.choice(LAST_NAMES)
        name = f"{first_name} {last_name}"
        city, state = cities[index]
        age_min, age_max = age_ranges[index]
        customers.append(
            CustomerSeed(
                id=uuid4(),
                name=name,
                email=unique_email(name, index + 1),
                phone=indian_phone(index + 1),
                city=city,
                state=state,
                age=random.randint(age_min, age_max),
                gender=gender,
                preferred_channel=channels[index],
                target_tier=tiers[index],
                created_at=random_datetime_between(now - timedelta(days=730), now - timedelta(days=30)),
            )
        )
    return customers


def tier_order_plan(target_tier: str) -> tuple[int, int, tuple[int, int]]:
    if target_tier == "platinum":
        return random.randint(10, 15), random.randint(1, 28), (1800, 5200)
    if target_tier == "gold":
        return random.randint(5, 8), random.randint(10, 58), (1100, 2600)
    if target_tier == "silver":
        return random.randint(3, 4), random.randint(18, 60), (650, 1150)
    return 2, random.randint(70, 330), (500, 900)


def choose_status(order_number: int, target_tier: str) -> str:
    if order_number == 0:
        return "completed"
    if target_tier == "bronze":
        return random.choices(["completed", "returned", "cancelled"], weights=[82, 12, 6], k=1)[0]
    return random.choices(["completed", "returned", "cancelled"], weights=[86, 9, 5], k=1)[0]


def choose_order_categories(customer_index: int, order_number: int, item_count: int) -> list[str]:
    saree_fan = customer_index % 5 == 0
    categories = list(PRODUCT_CATALOG.keys())
    if saree_fan and order_number < 3:
        return ["sarees"] + random.choices(categories, k=item_count - 1)
    return random.choices(categories, weights=[25, 30, 10, 22, 13], k=item_count)


def build_order_items(customer_index: int, order_number: int, target_amount: int) -> list[dict[str, Any]]:
    max_items = min(4, max(1, target_amount // 500))
    item_count = random.randint(1, max_items)
    if target_amount < 1200:
        categories = ["accessories"]
    elif target_amount < 2500:
        categories = random.choices(["accessories", "kurtas", "western"], weights=[40, 35, 25], k=item_count)
    else:
        categories = choose_order_categories(customer_index, order_number, item_count)
    items: list[dict[str, Any]] = []
    remaining = Decimal(target_amount)

    for item_index, category in enumerate(categories):
        product_name, catalog_price = random.choice(PRODUCT_CATALOG[category])
        quantity = 1
        if item_index == len(categories) - 1:
            price = max(Decimal("500.00"), remaining)
        else:
            variance = Decimal(str(random.uniform(0.75, 1.15)))
            price = Decimal(catalog_price) * variance
            price = min(price, remaining - Decimal("500.00") * (len(categories) - item_index - 1))
            price = max(Decimal("500.00"), price)
            remaining -= price
        items.append(
            {
                "product_id": str(uuid4()),
                "name": product_name,
                "category": category,
                "quantity": quantity,
                "price": float(round(price, 2)),
            }
        )
    return items


def calculate_amount(items: list[dict[str, Any]]) -> Decimal:
    amount = sum(Decimal(str(item["price"])) * item["quantity"] for item in items)
    return amount.quantize(Decimal("0.01"))


def final_tier(total_spend: Decimal, total_orders: int) -> str:
    if total_spend > Decimal("20000") or total_orders >= 10:
        return "platinum"
    if total_spend > Decimal("8000") or total_orders >= 5:
        return "gold"
    if total_spend > Decimal("2000") or total_orders >= 3:
        return "silver"
    return "bronze"


async def reset_database(connection: asyncpg.Connection) -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    progress("Resetting database from schema.sql...")
    await connection.execute(schema_path.read_text(encoding="utf-8"))


async def insert_customers(connection: asyncpg.Connection, customers: list[CustomerSeed]) -> None:
    progress("Creating customers... 0/250 done")
    rows = [
        (
            customer.id,
            customer.name,
            customer.email,
            customer.phone,
            customer.city,
            customer.state,
            customer.age,
            customer.gender,
            "bronze",
            customer.preferred_channel,
            customer.created_at,
        )
        for customer in customers
    ]
    await connection.executemany(
        """
        INSERT INTO customers (
            id, name, email, phone, city, state, age, gender, tier,
            preferred_channel, created_at, updated_at
        )
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$11)
        """,
        rows,
    )
    progress("Creating customers... 250/250 done")


async def insert_orders_and_update_customers(connection: asyncpg.Connection, customers: list[CustomerSeed]) -> None:
    progress("Creating orders...")
    now = datetime.now(UTC)
    order_rows: list[tuple[Any, ...]] = []
    customer_metrics: dict[UUID, dict[str, Any]] = {}

    for customer_index, customer in enumerate(customers):
        order_count, recency_days, amount_range = tier_order_plan(customer.target_tier)
        newest_order_date = now - timedelta(days=recency_days)
        oldest_order_date = max(customer.created_at, now - timedelta(days=720))
        completed_spend = Decimal("0")
        completed_orders = 0
        last_purchase_at: datetime | None = None

        for order_number in range(order_count):
            if order_number == 0:
                order_date = newest_order_date
            else:
                order_date = random_datetime_between(oldest_order_date, newest_order_date)
            status = choose_status(order_number, customer.target_tier)
            target_amount = random.randint(*amount_range)
            if customer.target_tier == "platinum" and order_number == 0:
                target_amount = random.randint(4500, 12000)
            if customer.target_tier == "gold" and order_number == 0:
                target_amount = random.randint(2500, 7000)
            items = build_order_items(customer_index, order_number, target_amount)
            amount = calculate_amount(items)

            order_rows.append(
                (
                    uuid4(),
                    customer.id,
                    order_date,
                    amount,
                    status,
                    random.choices(["website", "app", "store"], weights=[50, 35, 15], k=1)[0],
                    json.dumps(items),
                    order_date,
                )
            )

            if status == "completed":
                completed_spend += amount
                completed_orders += 1
                if last_purchase_at is None or order_date > last_purchase_at:
                    last_purchase_at = order_date

        customer_metrics[customer.id] = {
            "total_spend": completed_spend,
            "total_orders": completed_orders,
            "last_purchase_at": last_purchase_at,
            "tier": final_tier(completed_spend, completed_orders),
        }

    await connection.executemany(
        """
        INSERT INTO orders (id, customer_id, order_date, amount, status, channel, items, created_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8)
        """,
        order_rows,
    )

    await connection.executemany(
        """
        UPDATE customers
        SET total_spend = $2,
            total_orders = $3,
            last_purchase_at = $4,
            tier = $5,
            updated_at = NOW()
        WHERE id = $1
        """,
        [
            (
                customer_id,
                metrics["total_spend"],
                metrics["total_orders"],
                metrics["last_purchase_at"],
                metrics["tier"],
            )
            for customer_id, metrics in customer_metrics.items()
        ],
    )
    progress(f"Creating orders... {len(order_rows)} orders done")


async def segment_customer_ids(connection: asyncpg.Connection, segment_name: str) -> list[UUID]:
    if segment_name == "Champions":
        rows = await connection.fetch(
            """
            SELECT id FROM customers
            WHERE total_orders >= 5
              AND total_spend > 10000
              AND last_purchase_at >= NOW() - INTERVAL '30 days'
            """
        )
    elif segment_name == "Loyal Customers":
        rows = await connection.fetch(
            """
            SELECT id FROM customers
            WHERE total_orders >= 3
              AND last_purchase_at >= NOW() - INTERVAL '60 days'
            """
        )
    elif segment_name == "At Risk":
        rows = await connection.fetch(
            """
            SELECT id FROM customers
            WHERE total_orders >= 3
              AND last_purchase_at < NOW() - INTERVAL '60 days'
              AND last_purchase_at >= NOW() - INTERVAL '120 days'
            """
        )
    elif segment_name == "Lapsed Customers":
        rows = await connection.fetch(
            """
            SELECT id FROM customers
            WHERE last_purchase_at < NOW() - INTERVAL '120 days'
            """
        )
    elif segment_name == "High Value New":
        rows = await connection.fetch(
            """
            SELECT id FROM customers
            WHERE total_orders < 3
              AND total_spend > 8000
            """
        )
    elif segment_name == "Saree Enthusiasts":
        rows = await connection.fetch(
            """
            SELECT customer_id AS id
            FROM orders
            CROSS JOIN LATERAL jsonb_array_elements(items) AS item
            WHERE status = 'completed'
              AND item->>'category' = 'sarees'
            GROUP BY customer_id
            HAVING COUNT(*) >= 2
            """
        )
    else:
        raise ValueError(f"Unknown segment {segment_name}")
    return [row["id"] for row in rows]


def segment_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "Champions",
            "description": "High-value frequent shoppers who bought from ZURI in the last 30 days.",
            "filter_rules": {
                "operator": "AND",
                "conditions": [
                    {"field": "total_orders", "operator": "gte", "value": 5},
                    {"field": "last_purchase_at", "operator": "days_ago_lte", "value": 30},
                    {"field": "total_spend", "operator": "gt", "value": 10000},
                ],
            },
        },
        {
            "name": "Loyal Customers",
            "description": "Repeat shoppers with three or more completed orders and recent activity.",
            "filter_rules": {
                "operator": "AND",
                "conditions": [
                    {"field": "total_orders", "operator": "gte", "value": 3},
                    {"field": "last_purchase_at", "operator": "days_ago_lte", "value": 60},
                ],
            },
        },
        {
            "name": "At Risk",
            "description": "Previously frequent buyers who have been inactive for 60 to 120 days.",
            "filter_rules": {
                "operator": "AND",
                "conditions": [
                    {"field": "total_orders", "operator": "gte", "value": 3},
                    {"field": "last_purchase_at", "operator": "days_ago_gte", "value": 60},
                    {"field": "last_purchase_at", "operator": "days_ago_lte", "value": 120},
                ],
            },
        },
        {
            "name": "Lapsed Customers",
            "description": "Customers who have not purchased for at least 120 days.",
            "filter_rules": {
                "operator": "AND",
                "conditions": [
                    {"field": "last_purchase_at", "operator": "days_ago_gte", "value": 120},
                ],
            },
        },
        {
            "name": "High Value New",
            "description": "Newer customers with fewer than three orders but high spend.",
            "filter_rules": {
                "operator": "AND",
                "conditions": [
                    {"field": "total_orders", "operator": "lt", "value": 3},
                    {"field": "total_spend", "operator": "gt", "value": 8000},
                ],
            },
        },
        {
            "name": "Saree Enthusiasts",
            "description": "Customers who bought saree items at least twice.",
            "filter_rules": {
                "operator": "AND",
                "conditions": [
                    {"field": "category_purchase_count", "operator": "gte", "category": "sarees", "value": 2},
                ],
            },
        },
    ]


async def insert_segments(connection: asyncpg.Connection) -> dict[str, UUID]:
    progress("Creating segments...")
    segment_ids: dict[str, UUID] = {}
    for definition in segment_definitions():
        customer_ids = await segment_customer_ids(connection, definition["name"])
        segment_id = await connection.fetchval(
            """
            INSERT INTO segments (
                name, description, filter_rules, ai_generated, customer_count, created_at, updated_at
            )
            VALUES ($1,$2,$3::jsonb,FALSE,$4,NOW(),NOW())
            RETURNING id
            """,
            definition["name"],
            definition["description"],
            json.dumps(definition["filter_rules"]),
            len(customer_ids),
        )
        segment_ids[definition["name"]] = segment_id
    progress("Creating segments... 6/6 done")
    return segment_ids


async def latest_completed_product(connection: asyncpg.Connection, customer_id: UUID) -> str:
    row = await connection.fetchrow(
        """
        SELECT items
        FROM orders
        WHERE customer_id = $1 AND status = 'completed'
        ORDER BY order_date DESC
        LIMIT 1
        """,
        customer_id,
    )
    if not row:
        return "ZURI favorite"
    items = row["items"]
    if isinstance(items, str):
        items = json.loads(items)
    return items[0]["name"] if items else "ZURI favorite"


def render_message(template: str, customer: asyncpg.Record, last_product: str) -> str:
    days_since_purchase = 0
    if customer["last_purchase_at"]:
        days_since_purchase = (datetime.now(UTC) - customer["last_purchase_at"]).days
    replacements = {
        "{{name}}": customer["name"],
        "{{city}}": customer["city"],
        "{{tier}}": customer["tier"].title(),
        "{{last_product}}": last_product,
        "{{total_orders}}": str(customer["total_orders"]),
        "{{total_spend}}": f"{float(customer['total_spend']):,.0f}",
        "{{days_since_purchase}}": str(days_since_purchase),
    }
    message = template
    for token, value in replacements.items():
        message = message.replace(token, value)
    return message


def communication_outcome(channel: str) -> dict[str, bool]:
    base = {
        "delivered": random.random() < {"email": 0.94, "whatsapp": 0.96, "sms": 0.90}.get(channel, 0.92),
        "opened": False,
        "read": False,
        "clicked": False,
        "converted": False,
    }
    if not base["delivered"]:
        return base
    base["opened"] = random.random() < {"email": 0.52, "whatsapp": 0.68, "sms": 0.35}.get(channel, 0.55)
    if not base["opened"]:
        return base
    base["read"] = random.random() < 0.72
    if not base["read"]:
        return base
    base["clicked"] = random.random() < {"email": 0.24, "whatsapp": 0.34, "sms": 0.18}.get(channel, 0.30)
    if not base["clicked"]:
        return base
    base["converted"] = random.random() < 0.12
    return base


def status_from_outcome(outcome: dict[str, bool]) -> str:
    if not outcome["delivered"]:
        return "failed"
    for status in ["converted", "clicked", "read", "opened", "delivered"]:
        if outcome[status]:
            return status
    return "delivered"


async def insert_historical_campaigns(connection: asyncpg.Connection, segment_ids: dict[str, UUID]) -> None:
    progress("Creating historical campaigns...")
    campaigns = [
        {
            "name": "Diwali Collection Launch",
            "segment": "Champions",
            "channel": "email",
            "days_ago": 30,
            "template": "Hi {{name}}, ZURI's Diwali edit is live. Since you loved {{last_product}}, here is an early-access festive curation for our {{tier}} members.",
        },
        {
            "name": "Monsoon Sale",
            "segment": "Loyal Customers",
            "channel": "whatsapp",
            "days_ago": 15,
            "template": "Hi {{name}}, your ZURI monsoon picks are ready. Enjoy styles inspired by {{last_product}} with a loyalty offer today.",
        },
        {
            "name": "Win Back",
            "segment": "Lapsed Customers",
            "channel": "sms",
            "days_ago": 7,
            "template": "Hi {{name}}, it has been {{days_since_purchase}} days since your last ZURI order. Come back for a special offer on new arrivals.",
        },
    ]

    for campaign in campaigns:
        customer_ids = await segment_customer_ids(connection, campaign["segment"])
        launched_at = datetime.now(UTC) - timedelta(days=campaign["days_ago"])
        completed_at = launched_at + timedelta(hours=8)
        campaign_id = await connection.fetchval(
            """
            INSERT INTO campaigns (
                name, segment_id, channel, message_template, status, total_recipients,
                launched_at, completed_at, created_at, updated_at
            )
            VALUES ($1,$2,$3,$4,'completed',$5,$6,$7,$6,$7)
            RETURNING id
            """,
            campaign["name"],
            segment_ids[campaign["segment"]],
            campaign["channel"],
            campaign["template"],
            len(customer_ids),
            launched_at,
            completed_at,
        )

        counters = {
            "sent": 0,
            "delivered": 0,
            "failed": 0,
            "opened": 0,
            "read": 0,
            "clicked": 0,
            "converted": 0,
        }

        for customer_id in customer_ids:
            customer = await connection.fetchrow("SELECT * FROM customers WHERE id = $1", customer_id)
            last_product = await latest_completed_product(connection, customer_id)
            message = render_message(campaign["template"], customer, last_product)
            outcome = communication_outcome(campaign["channel"])
            final_status = status_from_outcome(outcome)
            sent_at = launched_at + timedelta(minutes=random.randint(0, 20))
            delivered_at = sent_at + timedelta(minutes=random.randint(1, 8)) if outcome["delivered"] else None
            failed_at = sent_at + timedelta(minutes=random.randint(1, 5)) if not outcome["delivered"] else None
            opened_at = delivered_at + timedelta(minutes=random.randint(5, 120)) if outcome["opened"] and delivered_at else None
            read_at = opened_at + timedelta(minutes=random.randint(2, 40)) if outcome["read"] and opened_at else None
            clicked_at = read_at + timedelta(minutes=random.randint(5, 90)) if outcome["clicked"] and read_at else None
            converted_at = clicked_at + timedelta(minutes=random.randint(30, 360)) if outcome["converted"] and clicked_at else None
            communication_id = await connection.fetchval(
                """
                INSERT INTO communications (
                    campaign_id, customer_id, channel, personalized_message, status,
                    sent_at, delivered_at, opened_at, read_at, clicked_at, converted_at,
                    failed_at, failure_reason, channel_message_id, created_at, updated_at
                )
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$6,NOW())
                RETURNING id
                """,
                campaign_id,
                customer_id,
                campaign["channel"],
                message,
                final_status,
                sent_at,
                delivered_at,
                opened_at,
                read_at,
                clicked_at,
                converted_at,
                failed_at,
                "Provider rejected message" if final_status == "failed" else None,
                f"zuri_{campaign_id}_{customer_id}",
            )

            event_payload = {"source": "seed", "campaign_name": campaign["name"]}
            event_times = {
                "sent": sent_at,
                "delivered": delivered_at,
                "failed": failed_at,
                "opened": opened_at,
                "read": read_at,
                "clicked": clicked_at,
                "converted": converted_at,
            }
            for event_type, event_time in event_times.items():
                if event_time:
                    await connection.execute(
                        """
                        INSERT INTO webhook_events (communication_id, event_type, received_at, payload)
                        VALUES ($1,$2,$3,$4::jsonb)
                        """,
                        communication_id,
                        event_type,
                        event_time,
                        json.dumps(event_payload),
                    )
                    counters[event_type] += 1

        sent = counters["sent"] or 1
        delivered = counters["delivered"] or 1
        await connection.execute(
            """
            INSERT INTO campaign_analytics (
                campaign_id, total_sent, total_delivered, total_failed, total_opened,
                total_read, total_clicked, total_converted, delivery_rate, open_rate,
                click_rate, conversion_rate, updated_at
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,NOW())
            """,
            campaign_id,
            counters["sent"],
            counters["delivered"],
            counters["failed"],
            counters["opened"],
            counters["read"],
            counters["clicked"],
            counters["converted"],
            Decimal(counters["delivered"] * 100 / sent).quantize(Decimal("0.01")),
            Decimal(counters["opened"] * 100 / delivered).quantize(Decimal("0.01")),
            Decimal(counters["clicked"] * 100 / delivered).quantize(Decimal("0.01")),
            Decimal(counters["converted"] * 100 / sent).quantize(Decimal("0.01")),
        )
    progress("Creating historical campaigns... 3/3 done")


async def print_summary(connection: asyncpg.Connection) -> None:
    tables = [
        "customers",
        "orders",
        "segments",
        "campaigns",
        "communications",
        "campaign_analytics",
        "webhook_events",
    ]
    progress("\nSeed summary")
    for table in tables:
        count = await connection.fetchval(f"SELECT COUNT(*) FROM {table}")
        progress(f"- {table}: {count}")
    tier_rows = await connection.fetch("SELECT tier, COUNT(*) AS count FROM customers GROUP BY tier ORDER BY tier")
    progress("- tier mix: " + ", ".join(f"{row['tier']}={row['count']}" for row in tier_rows))


async def main() -> None:
    random.seed(RANDOM_SEED)
    connection = await asyncpg.connect(database_url())
    try:
        async with connection.transaction():
            await reset_database(connection)
            customers = build_customers()
            await insert_customers(connection, customers)
            await insert_orders_and_update_customers(connection, customers)
            segment_ids = await insert_segments(connection)
            await insert_historical_campaigns(connection, segment_ids)
        await print_summary(connection)
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
