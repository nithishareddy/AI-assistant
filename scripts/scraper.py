"""
Help center docs scraper — publishes pages to Kafka topic 'help-center-docs'.

Run: python scraper.py

Every 5 seconds the scraper checks the index page for links it hasn't yet
visited, fetches each new page, and publishes a JSON message to Kafka.
Already-visited URLs are tracked in memory so each page is only scraped once
per process lifetime.
"""

import json
import logging
import os
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../backend/.env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────
INDEX_URL = os.getenv("HELP_CENTER_INDEX_URL")
if not INDEX_URL:
    raise RuntimeError("HELP_CENTER_INDEX_URL not set — check backend/.env")
KAFKA_BROKER = "localhost:9092"
KAFKA_TOPIC = "help-center-docs"
POLL_INTERVAL = 5          # seconds between index re-checks
REQUEST_TIMEOUT = 15       # seconds per HTTP request
MAX_CONTENT_CHARS = 12000  # truncate very long pages before publishing
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; DevOpsAI-Scraper/1.0; "
        "+https://github.com/your-org/devops-ai-assistant)"
    )
}

# ── Helpers ──────────────────────────────────────────────────────────────────
def make_producer() -> KafkaProducer:
    """Create a Kafka producer, retrying until the broker is reachable."""
    while True:
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BROKER,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
                retries=3,
            )
            log.info("Connected to Kafka broker at %s", KAFKA_BROKER)
            return producer
        except NoBrokersAvailable:
            log.warning("Kafka broker not available, retrying in 5s…")
            time.sleep(5)


def fetch_page(url: str) -> tuple[str, str]:
    """Return (title, cleaned_text) for a URL, or ('', '') on error."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:
        log.warning("Failed to fetch %s: %s", url, exc)
        return "", ""

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove nav / header / footer noise
    for tag in soup.select("nav, header, footer, script, style, .breadcrumb, .toc"):
        tag.decompose()

    title = soup.title.get_text(strip=True) if soup.title else url

    # Prefer main content area
    main = soup.find("main") or soup.find("article") or soup.find("div", id="content") or soup.body
    text = main.get_text(separator="\n", strip=True) if main else soup.get_text(separator="\n", strip=True)

    # Collapse blank lines
    lines = [line for line in text.splitlines() if line.strip()]
    cleaned = "\n".join(lines)[:MAX_CONTENT_CHARS]
    return title, cleaned


def discover_links(index_url: str) -> set[str]:
    """Return all internal doc links found on the index page."""
    base = "{uri.scheme}://{uri.netloc}".format(uri=urlparse(index_url))
    base_path = index_url.rsplit("/", 1)[0]  # directory of the index

    try:
        resp = requests.get(index_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:
        log.warning("Could not fetch index %s: %s", index_url, exc)
        return set()

    soup = BeautifulSoup(resp.text, "html.parser")
    links: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("#") or href.startswith("javascript"):
            continue
        full = urljoin(base_path + "/", href).split("#")[0]
        # Only follow links within the same docs subtree
        if full.startswith(base_path):
            links.add(full)

    # Always include the index itself
    links.add(index_url)
    return links


# ── Main loop ────────────────────────────────────────────────────────────────
def main():
    producer = make_producer()
    visited: set[str] = set()

    log.info("Starting help center docs scraper. Index: %s", INDEX_URL)

    while True:
        all_links = discover_links(INDEX_URL)
        new_links = all_links - visited

        if new_links:
            log.info("Found %d new page(s) to scrape", len(new_links))
            for url in sorted(new_links):
                title, content = fetch_page(url)
                visited.add(url)

                if not content:
                    log.info("Skipped (empty): %s", url)
                    continue

                message = {
                    "url": url,
                    "title": title,
                    "content": content,
                    "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                producer.send(KAFKA_TOPIC, value=message)
                log.info("Published: %s  (%d chars)", url, len(content))

            producer.flush()
        else:
            log.debug("No new pages found, sleeping %ds…", POLL_INTERVAL)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
