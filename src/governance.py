from __future__ import annotations
import re
import logging
from typing import Optional, Tuple, List

from .config import GovernanceConfig, DeclarativeKnowledge

logger = logging.getLogger("GovernanceLayer")

class GovernanceLayer:
    """
    The Ethical & Strategic Gatekeeper:
    - Blocks jailbreaks.
    - Enforces the 'SEO Super Genius' mission.
    - Prevents mission creep outside of the 15 Skill Tables.
    """
    def __init__(self, config: GovernanceConfig) -> None:
        self.config = config
        
        self.jailbreak_patterns = [
            re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
            re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.I),
            re.compile(r"system\s+override", re.I),
            re.compile(r"disregard\s+any\s+filters", re.I),
            re.compile(r"stay\s+out\s+of\s+character", re.I),
        ]

    def is_killed(self) -> bool:
        return bool(self.config.kill_switches.get("global", False))

    def _detect_prompt_injection(self, user_input: str) -> bool:
        return any(pattern.search(user_input) for pattern in self.jailbreak_patterns)

    def enforce_boundaries(
        self,
        user_input: str,
        intent_data: dict, # Now receiving the Dict from Reasoning
        declarative: DeclarativeKnowledge,
    ) -> Tuple[bool, Optional[str]]:
        """
        The production gatekeeper. Overhauled for Mission Alignment.
        """
        if self.is_killed():
            return False, "System is administratively disabled."

        # 1. Prompt Injection Shield
        if self._detect_prompt_injection(user_input):
            logger.warning(f"Injection attempt blocked: {user_input[:50]}...")
            return False, "Security violation: Instruction override blocked."

        # 2. Mission Alignment Check (Directive #1)
        # If the intent isn't related to the 15 departments, flag it.
        intent = intent_data.get("intent", "general")
        primary_skill_id = intent_data.get("primary_skill_id", 14)

        # 3. Domain Boundary (Strictly SEO / Growth / Tech)
        restricted_topics = ["politics", "medical advice", "unrelated gaming", "illegal"]
        if any(topic in user_input.lower() for topic in restricted_topics):
            return False, "Request falls outside the Digital Nomad SEO domain."

        # 4. Professionalism Guard (Directive #10 - Psychology/Trust)
        # We block insults to maintain the 'Authority' signal of the brand.
        bad_words = ["idiot", "stupid", "worthless"]
        if any(bad in user_input.lower() for bad in bad_words):
            return False, "Input violates professional brand voice boundaries."

        return True, None
