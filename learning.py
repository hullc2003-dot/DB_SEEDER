# learning.py - Fetches and extracts clean text from a URL

import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("Learning")

def run_learning_pipeline(url: str) -> dict:
    """
    Fetch a URL and return clean plain text + raw HTML.

    Args:
        url: The page URL to scrape

    Returns:
        Dict with status_msg, word_count, raw_text, html

    Raises:
        ValueError: If the request fails or returns non-200 status
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; SEOBot/1.0)"
            )
        }
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()  # Raises on 4xx/5xx responses

    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching {url}")
        raise ValueError(f"Request timed out: {url}")

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error fetching {url}: {e}")
        raise ValueError(f"HTTP error {response.status_code} for {url}: {str(e)}")

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed for {url}: {e}")
        raise ValueError(f"Request failed for {url}: {str(e)}")

    # Parse and clean HTML
    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    # Strip script and style tags — pure content only
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.extract()

    plain_text = soup.get_text(separator=" ")

    # Collapse excess whitespace
    plain_text = " ".join(plain_text.split())

    word_count = len(plain_text.split())

    logger.info(f"Fetched {url} — {word_count} words extracted")

    return {
        "status_msg": "text retrieved",
        "word_count": word_count,
        "raw_text": plain_text,
        "html": html
    }
