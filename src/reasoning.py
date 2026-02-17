from __future__ import annotations
from typing import List, Dict, Any, Optional
from .config import DeclarativeKnowledge, ProceduralReasoning

class ReasoningLayer:
    """
    Overhauled Strategic Reasoning:
    - Skill Category Detection (The 15 Tables)
    - SEO Strategic Mapping
    - Specialist Prompt Construction
    """

    # Mapping keywords to your specific Table IDs
    SKILL_MAP = {
        "wordpress": 1, "theme": 1, "hosting": 1,
        "keywords": 2, "backlink": 12, "technical": 2,
        "psychology": 3, "bias": 3, "behavior": 3,
        "landing": 4, "saas": 4, "ecommerce": 4,
        "analytics": 5, "ga4": 5, "heatmaps": 5,
        "copywriting": 6, "storytelling": 6, "voice": 6,
        "visual": 7, "video": 7, "image": 7,
        "prompt": 8, "gpt": 8, "llm": 8,
        "html": 9, "css": 9, "javascript": 9,
        "json-ld": 10, "schema": 10, "entities": 10,
        "meta": 11, "canonical": 11, "indexing": 11,
        "social": 13, "engagement": 13,
        "monetization": 14, "funnel": 14, "positioning": 14,
        "logic": 15, "systems": 15, "prioritization": 15
    }

    def __init__(self, procedural: ProceduralReasoning) -> None:
        self.procedural = procedural

    def detect_intent(self, user_input: str) -> Dict[str, Any]:
        """
        Detects which of the 15 Departments should handle the request.
        """
        text = user_input.lower()
        detected_skills = []
        
        # Skill Table Detection
        for keyword, skill_id in self.SKILL_MAP.items():
            if keyword in text:
                detected_skills.append(skill_id)
        
        # Primary Strategy Intent
        intent = "general_research"
        if any(x in text for x in ["plan", "strategy", "roadmap"]):
            intent = "strategic_planning"
        elif any(x in text for x in ["fix", "optimize", "implement"]):
            intent = "technical_execution"
        elif any(x in text for x in ["analyze", "audit", "check"]):
            intent = "audit_analysis"

        return {
            "intent": intent,
            "primary_skill_id": detected_skills[0] if detected_skills else 14, # Defaults to Master Strategy
            "all_affected_skills": list(set(detected_skills))
        }

    def select_strategy(self, intent_data: Dict[str, Any]) -> str:
        """
        Selects the reasoning path based on the SEO Pillar it's addressing.
        """
        intent = intent_data["intent"]
        skill_id = intent_data["primary_skill_id"]
        
        # Custom SEO Strategy Selection Logic
        if intent == "strategic_planning":
            return "high_level_architect"
        if skill_id in [9, 10, 11]: # Technical Departments
            return "technical_specialist"
        if skill_id in [3, 6, 13]: # Human Centric Departments
            return "behavioral_psychologist"
            
        return "balanced_seo_genius"

    def build_prompt(
        self,
        user_input: str,
        intent_data: Dict[str, Any],
        strategy: str,
        declarative: DeclarativeKnowledge,
        context_chunks: List[str],
    ) -> str:
        """
        Constructs the final 'Specialist' prompt that forces the LLM 
        to think within the constraints of your 15 Tables.
        """
        skill_id = intent_data["primary_skill_id"]
        
        # Injecting directives from Agent.md (Personality)
        system_context = (
            f"ACT AS: A Super Genius SEO Specialist focused on Revenue and Authority.\n"
            f"DEPARTMENT: Table {skill_id} Focus.\n"
            f"REASONING MODE: {strategy}.\n"
            f"CONSTRAINT: Use WordPress FREE version features only. Prioritize Psychology."
        )

        context_str = "\n".join(context_chunks) if context_chunks else "No relevant mastery nodes found."

        return (
            f"{system_context}\n"
            f"--- DATABASE CONTEXT (MASTERY NODES) ---\n"
            f"{context_str}\n\n"
            f"--- TASK ---\n"
            f"User Objective: {user_input}\n"
            f"Strategic Goal: Analyze this through the lens of Table {skill_id} and output LogicNodes for the Rewriter.\n\n"
            f"Assistant:"
        )
