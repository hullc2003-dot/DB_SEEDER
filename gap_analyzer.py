import logging
from typing import Dict, Any, List, Optional

from supabase_client import get_supabase_client
from config import SPECIALIST_TABLES

logger = logging.getLogger(__name__)


class GapAnalyzer:
    """
    Scans specialist tables for empty or incomplete rows.

    A row is considered empty if:
        content IS NULL OR content = ''
    """

    def __init__(self, supabase_client: Optional[object] = None):
        # Allow injection for testing; default to centralized client
        self.supabase = supabase_client or get_supabase_client()

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
            .from_(table)            # modern fluent API
            .select("id, title, content")
            .or_("content.is.null,content.eq.''")
            .range(0, 9999)
            .execute()
        )
        # SDK responses can be objects or dicts; normalize to .data or ['data']
        data = getattr(resp, "data", None)
        if data is None and isinstance(resp, dict):
            data = resp.get("data")
        return data or []
