"""
Database Seeding Script for api-scaling.

Populates the 'items' table with realistic architecture and scaling items.
Supports inserting via:
1. Running HTTP API (e.g., http://localhost/items)
2. Direct SQLAlchemy Database connection (app.database.SessionLocal)
"""

import sys
import logging
from typing import List, Dict
import urllib.request
import urllib.error
import json

from app.database import SessionLocal, Item, check_db_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed")

SAMPLE_ITEMS: List[Dict[str, str]] = [
    {
        "title": "Load Balancer Config",
        "description": "Nginx reverse proxy and round-robin upstream configuration",
    },
    {
        "title": "Database Connection Pooling",
        "description": "SQLAlchemy QueuePool with 20 persistent connections and max 10 overflow",
    },
    {
        "title": "Horizontal Pod Autoscaler",
        "description": "Kubernetes HPA resource definition targeting 70% average CPU utilization",
    },
    {
        "title": "Redis Cache Layer",
        "description": "In-memory distributed cache for sub-millisecond query responses",
    },
    {
        "title": "Rate Limiting Middleware",
        "description": "Token bucket algorithm limiting clients to 100 requests per minute",
    },
    {
        "title": "Asynchronous Task Queue",
        "description": "Celery background worker queue backed by RabbitMQ for async operations",
    },
    {
        "title": "Prometheus Metrics Exporter",
        "description": "Instrumentation endpoint exposing latency, request throughput, and error rates",
    },
    {
        "title": "Grafana Monitoring Dashboard",
        "description": "Real-time metrics visualization for API latency, p95/p99 percentiles, and DB pool stats",
    },
    {
        "title": "Read Replica Cluster",
        "description": "PostgreSQL streaming replication to offload heavy read queries from primary",
    },
    {
        "title": "CDN Edge Caching",
        "description": "Cloudflare edge caching rules for static assets and cacheable API endpoints",
    },
]


def seed_via_api(base_url: str = "http://localhost") -> bool:
    """Seed items by sending POST requests to the API."""
    items_url = f"{base_url.rstrip('/')}/items"
    logger.info("Attempting to seed via API at %s ...", items_url)

    # First fetch existing items
    try:
        req = urllib.request.Request(items_url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            existing_titles = {item["title"] for item in data}
            logger.info("Found %d existing items via API.", len(existing_titles))
    except Exception as exc:
        logger.warning("Could not reach API at %s: %s", items_url, exc)
        return False

    inserted_count = 0
    for item in SAMPLE_ITEMS:
        if item["title"] in existing_titles:
            logger.info("Item already exists (skipping): '%s'", item["title"])
            continue

        payload = json.dumps(item).encode("utf-8")
        req = urllib.request.Request(
            items_url,
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status in (200, 201):
                    res_body = json.loads(resp.read().decode())
                    logger.info("Inserted item [ID %s]: '%s'", res_body.get("id"), item["title"])
                    inserted_count += 1
        except Exception as exc:
            logger.error("Failed to insert item '%s': %s", item["title"], exc)

    logger.info("API Seeding complete. Successfully added %d new items.", inserted_count)
    return True


def seed_via_direct_db() -> bool:
    """Seed items directly into the database configured via app.database."""
    logger.info("Attempting to seed directly into database...")
    is_healthy, msg = check_db_connection()
    if not is_healthy:
        logger.warning("Direct database connection is unavailable: %s", msg)
        return False

    db = SessionLocal()
    inserted_count = 0
    try:
        existing_items = db.query(Item).all()
        existing_titles = {i.title for i in existing_items}
        logger.info("Found %d existing items in direct database.", len(existing_titles))

        for item_data in SAMPLE_ITEMS:
            if item_data["title"] in existing_titles:
                logger.info("Item already exists (skipping): '%s'", item_data["title"])
                continue

            new_item = Item(
                title=item_data["title"],
                description=item_data["description"],
            )
            db.add(new_item)
            inserted_count += 1

        db.commit()
        logger.info("Direct DB seeding complete. Successfully added %d new items.", inserted_count)
        return True
    except Exception as exc:
        db.rollback()
        logger.error("Failed seeding direct database: %s", exc)
        return False
    finally:
        db.close()


def main():
    logger.info("Starting database seeding...")
    api_success = seed_via_api()
    db_success = seed_via_direct_db()

    if not api_success and not db_success:
        logger.error("Failed to seed items via both API and direct database connection.")
        sys.exit(1)

    logger.info("Seeding process finished.")


if __name__ == "__main__":
    main()

