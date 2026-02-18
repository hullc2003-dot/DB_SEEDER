import logging
from typing import Dict, Any, List
from supabase import Client

logger = logging.getLogger(__name__)

SPECIALIST_TABLES = [
    "website_builder_mastery",
    "seo",
    "psychology_empathy",
    "website_types",
    "analytics",
    "content_design",
    "multimodal_visual_search",
    "ai_prompt_engineering",
    "code_skills",
    "schema_skills",
    "meta_skills",
    "backlinks",
    "social_media",
    "master_strategy",
    "critical_thinking",
]


class GapAnalyzer:
    """
    Scans specialist tables for empty or incomplete rows.

    A row is considered empty if:
        content IS NULL OR content = ''
    """

    def __init__(self, supabase: Client):
        self.supabase = supabase

    def analyze(self) -> Dict[str, List[Dict[str, Any]]]:
        report: Dict[str, List[Dict[str, Any]]] = {}

        for table in SPECIALIST_TABLES:
            try:
                empty_rows = self._find_empty_rows(table)
                if empty_rows:
                    report[table] = empty_rows
            except Exception:
                logger.exception(f"Error analyzing gaps in {table}")

        return report

    def _find_empty_rows(self, table: str) -> List[Dict[str, Any]]:
        resp = (
            self.supabase
            .table(table)
            .select("id, title, content")
            .or_("content.is.null,content.eq.''")
            .range(0, 9999)
            .execute()
        )
        return resp.data or []
