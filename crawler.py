# crawler.py - Auto-discovers internal URLs from a seed URL

import asyncio
import logging
import re
from typing import Set, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("Crawler")

# — CONFIGURATION —

MAX_PAGES = 100          # Hard cap — prevents runaway crawls on large sites
REQUEST_TIMEOUT = 10     # Seconds per request
CRAWL_DELAY = 1.0        # Seconds between requests — be polite to servers
MAX_DEPTH = 3            # How many links deep to follow from seed URL

# File extensions to skip — not useful for text content

SKIP_EXTENSIONS = {
".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
".mp4", ".mp3", ".zip", ".tar", ".gz", ".exe", ".css", ".js"
}

# URL patterns to skip — typically navigation noise

SKIP_PATTERNS = [
r"/tag/", r"/category/", r"/author/", r"/page/\d+",
r"?", r"#", r"/feed/", r"/wp-", r"/cdn-cgi/"
]

def _is_valid_url(url: str, base_domain: str) -> bool:
    """
    Check if a URL is worth crawling.

    Rules:
        - Must be on the same domain as the seed URL
        - Must not have a skippable file extension
        - Must not match skip patterns
        - Must be http or https

    Args:
        url:         URL to validate
        base_domain: Domain of the seed URL

    Returns:
        True if the URL should be crawled
    """
    try:
        parsed = urlparse(url)

        # Must be http/https
        if parsed.scheme not in ("http", "https"):
            return False

        # Must be same domain
        if parsed.netloc != base_domain:
            return False

        # Skip unwanted extensions
        path = parsed.path.lower()
        if any(path.endswith(ext) for ext in SKIP_EXTENSIONS):
            return False

        # Skip unwanted patterns
        full_url = url.lower()
        if any(re.search(pattern, full_url) for pattern in SKIP_PATTERNS):
            return False

        return True

    except Exception:
        return False

def _extract_links(html: str, current_url: str, base_domain: str) -> Set[str]:
    """
    Extract all valid internal links from a page's HTML.

    Args:
        html:         Raw HTML string
        current_url:  URL of the current page (for resolving relative links)
        base_domain:  Domain to stay within

    Returns:
        Set of absolute URLs found on the page
    """
    soup = BeautifulSoup(html, "html.parser")
    links = set()

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()

        # Skip empty, mailto, tel links
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue

        # Resolve relative URLs to absolute
        absolute = urljoin(current_url, href)

        # Strip fragments
        absolute = absolute.split("#")[0].rstrip("/")

        if _is_valid_url(absolute, base_domain):
            links.add(absolute)

    return links

def _fetch_page(url: str) -> Optional[str]:
    """
    Fetch a single page and return its HTML.

    Args:
        url: URL to fetch

    Returns:
        HTML string or None if fetch fails
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; SEOBot/1.0; "
                "+https://your-render-domain.com)"
            )
        }
        response = requests.get(url, timeout=REQUEST_TIMEOUT, headers=headers)
        response.raise_for_status()

        # Only process HTML pages
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            logger.info(f"Skipping non-HTML page: {url}")
            return None

        return response.text

    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None

async def crawl(seed_url: str) -> List[str]:
    """
    Crawl a website starting from a seed URL and return all discovered URLs.

    Uses breadth-first search up to MAX_DEPTH levels deep.
    Respects CRAWL_DELAY between requests.
    Hard caps at MAX_PAGES total.

    Args:
        seed_url: Starting URL to crawl from

    Returns:
        List of discovered URLs ready for the learning pipeline

    Raises:
        ValueError: If the seed URL is invalid or unreachable
    """
    parsed_seed = urlparse(seed_url)
    if not parsed_seed.scheme or not parsed_seed.netloc:
        raise ValueError(f"Invalid seed URL: {seed_url}")

    base_domain = parsed_seed.netloc
    seed_url = seed_url.rstrip("/")

    logger.info(f"Starting crawl from: {seed_url} (domain: {base_domain})")
    logger.info(f"Limits — max pages: {MAX_PAGES}, max depth: {MAX_DEPTH}")

    visited: Set[str] = set()
    discovered: List[str] = []

    # Queue entries are (url, depth)
    queue: List[tuple] = [(seed_url, 0)]

    loop = asyncio.get_event_loop()

    while queue and len(discovered) < MAX_PAGES:
        current_url, depth = queue.pop(0)

        # Skip if already visited
        if current_url in visited:
            continue

        visited.add(current_url)

        logger.info(
            f"Crawling [{len(discovered) + 1}/{MAX_PAGES}] "
            f"depth={depth}: {current_url}"
        )

        # Fetch page in thread pool — requests is synchronous
        html = await loop.run_in_executor(None, _fetch_page, current_url)

        if html is None:
            logger.warning(f"Skipping {current_url} — fetch returned nothing")
            continue

        # This page is valid — add to discovered list
        discovered.append(current_url)

        # If we haven't hit max depth, find more links
        if depth < MAX_DEPTH:
            new_links = _extract_links(html, current_url, base_domain)
            new_links -= visited  # Don't re-queue already visited pages

            added = 0
            for link in sorted(new_links):  # Sort for deterministic crawl order
                if link not in [q[0] for q in queue]:
                    queue.append((link, depth + 1))
                    added += 1

            logger.info(f"Found {len(new_links)} links, queued {added} new")

        # Be polite — delay between requests
        if queue:
            await asyncio.sleep(CRAWL_DELAY)

    logger.info(
        f"Crawl complete — "
        f"discovered: {len(discovered)} pages, "
        f"visited: {len(visited)} URLs, "
        f"remaining in queue: {len(queue)}"
    )

    return discovered
