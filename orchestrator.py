# orchestrator.py - Wires the full seeding pipeline from crawler to DB insert

import asyncio
import logging
from typing import Dict, Any

from config import BrainState, SPECIALIST_TABLES
# Import the module to access the crawler function and its specific process function
import crawler 
from learning import run_learning_pipeline
# Use an alias for the rewrite function to avoid collision with crawler's similarly named function
from rewrites import process_text_into_packages as rewrite_to_packages 
from embedder import embed_packages
from memory import insert_packages_to_supabase
from gap_analyzer import GapAnalyzer
from memory import get_supabase_client

logger = logging.getLogger("Orchestrator")

class SeedingOrchestrator:
    """
    Runs the full knowledge seeding pipeline:

    1. Gate check    — confirm config allows URL learning
    2. Crawler       — auto-discover all URLs from seed
    3. Fetch         — scrape raw text from each URL
    4. Rewrite       — summarize + classify into packages
    5. Embed         — generate 768d vectors via Gemini
    6. Insert        — write packages + vectors to Supabase
    7. Gap Analysis  — scan tables for empty rows post-insert
    """

    def __init__(self, brain: BrainState):
        self.brain = brain

    async def run(self, seed_url: str) -> Dict[str, Any]:
        """
        Execute the full seeding pipeline from a single seed URL.

        Args:
            seed_url: Starting URL — crawler will auto-discover all internal links

        Returns:
            Full pipeline report dict
        """
        report = {
            "seed_url": seed_url,
            "urls_discovered": 0,
            "urls_processed": 0,
            "urls_failed": 0,
            "total_packages": 0,
            "total_words": 0,
            "total_inserted": 0,
            "total_skipped": 0,
            "total_failed_inserts": 0,
            "gaps_found": {},
            "errors": [],
            "status": "started"
        }

        # ----------------------------------------------------------------
        # STEP 1 — GATE CHECK
        # ----------------------------------------------------------------
        logger.info("Step 1: Gate check...")

        if not self.brain.governance.master_enabled:
            report["status"] = "blocked"
            report["errors"].append("Blocked by governance — master_enabled is False")
            logger.warning("Pipeline blocked — master_enabled is False")
            return report

        if self.brain.governance.kill_switches.get("global", False):
            report["status"] = "blocked"
            report["errors"].append("Blocked by governance — global kill switch is active")
            logger.warning("Pipeline blocked — global kill switch active")
            return report

        if not self.brain.learning.router_toggles.get("use_url", False):
            report["status"] = "blocked"
            report["errors"].append("Blocked by config — use_url toggle is False")
            logger.warning("Pipeline blocked — use_url toggle is False")
            return report

        logger.info("Gate check passed — pipeline is active")

        # ----------------------------------------------------------------
        # STEP 2 — CRAWLER
        # ----------------------------------------------------------------
        logger.info(f"Step 2: Crawling from seed URL: {seed_url}")

        try:
            # Updated to use the module-based call to find the crawler function
            urls = await crawler.crawler(seed_url) 
            report["urls_discovered"] = len(urls)
            logger.info(f"Crawler complete — {len(urls)} URLs discovered")
        except Exception as e:
            report["status"] = "failed"
            report["errors"].append(f"Crawler failed: {str(e)}")
            logger.error(f"Crawler failed: {e}")
            return report

        if not urls:
            report["status"] = "failed"
            report["errors"].append("Crawler returned no URLs")
            logger.error("Crawler returned no URLs — aborting")
            return report

        # ----------------------------------------------------------------
        # STEP 3-6 — FETCH → REWRITE → EMBED → INSERT (per URL)
        # ----------------------------------------------------------------
        for i, url in enumerate(urls):
            logger.info(f"Processing URL {i + 1}/{len(urls)}: {url}")

            # STEP 3 — FETCH
            try:
                fetch_result = run_learning_pipeline(url)
                raw_text = fetch_result.get("raw_text", "")
                word_count = fetch_result.get("word_count", 0)
                logger.info(
                    f"Fetched {url} — "
                    f"{word_count} words, status: {fetch_result.get('status_msg')}"
                )
            except Exception as e:
                report["urls_failed"] += 1
                report["errors"].append(f"Fetch failed for {url}: {str(e)}")
                logger.error(f"Fetch failed for {url}: {e}")
                continue  # Move to next URL

            if not raw_text.strip():
                report["urls_failed"] += 1
                report["errors"].append(f"Empty content returned for {url}")
                logger.warning(f"Empty content for {url} — skipping")
                continue

            # STEP 4 — REWRITE
            try:
                # Updated to use the aliased rewrite function from rewrites.py
                packages, total_words = await rewrite_to_packages(raw_text)
                logger.info(
                    f"Rewrite complete — "
                    f"{len(packages)} packages, {total_words} words"
                )
            except Exception as e:
                report["urls_failed"] += 1
                report["errors"].append(f"Rewrite failed for {url}: {str(e)}")
                logger.error(f"Rewrite failed for {url}: {e}")
                continue

            if not packages:
                report["urls_failed"] += 1
                report["errors"].append(f"No packages produced for {url}")
                logger.warning(f"No packages produced for {url} — skipping")
                continue

            # STEP 5 — EMBED
            try:
                packages = await embed_packages(packages)
                logger.info(f"Embedding complete — {len(packages)} packages embedded")
            except Exception as e:
                report["urls_failed"] += 1
                report["errors"].append(f"Embedding failed for {url}: {str(e)}")
                logger.error(f"Embedding failed for {url}: {e}")
                continue

            # STEP 6 — INSERT
            try:
                insert_result = await insert_packages_to_supabase(packages, url)
                report["total_packages"] += len(packages)
                report["total_words"] += total_words
                report["total_inserted"] += insert_result["inserted_count"]
                report["total_skipped"] += insert_result["skipped_count"]
                report["total_failed_inserts"] += insert_result["failed_count"]
                report["urls_processed"] += 1
                logger.info(
                    f"Insert complete for {url} — "
                    f"inserted: {insert_result['inserted_count']} words, "
                    f"skipped: {insert_result['skipped_count']}, "
                    f"failed: {insert_result['failed_count']}"
                )
            except Exception as e:
                report["urls_failed"] += 1
                report["errors"].append(f"Insert failed for {url}: {str(e)}")
                logger.error(f"Insert failed for {url}: {e}")
                continue

        # ----------------------------------------------------------------
        # STEP 7 — GAP ANALYSIS
        # ----------------------------------------------------------------
        logger.info("Step 7: Running gap analysis...")

        try:
            client = get_supabase_client()
            analyzer = GapAnalyzer(supabase=client)
            gaps = analyzer.analyze()
            report["gaps_found"] = {
                table: len(rows) for table, rows in gaps.items()
            }
            total_gaps = sum(report["gaps_found"].values())
            logger.info(f"Gap analysis complete — {total_gaps} empty rows across {len(gaps)} tables")
        except Exception as e:
            report["errors"].append(f"Gap analysis failed: {str(e)}")
            logger.error(f"Gap analysis failed: {e}")

        # ----------------------------------------------------------------
        # FINAL STATUS
        # ----------------------------------------------------------------
        if report["urls_processed"] == 0:
            report["status"] = "failed"
        elif report["urls_failed"] > 0:
            report["status"] = "partial"
        else:
            report["status"] = "success"

        logger.info(
            f"Pipeline complete — "
            f"status: {report['status']}, "
            f"processed: {report['urls_processed']}/{report['urls_discovered']} URLs, "
            f"inserted: {report['total_inserted']} words"
        )

        return report
