from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import os

@dataclass
class ProviderConfig:
    provider_router_strategy: str = "random"
    default_model: str = "openai:gpt-4.1-mini"
    fallback_models: List[str] = field(default_factory=lambda: [
        "groq:llama-3-70b",
        "openrouter:gpt-4.1-mini",
    ])
    cost_per_1k_tokens: Dict[str, float] = field(default_factory=lambda: {
        "openai": 0.01,
        "groq": 0.002,
        "openrouter": 0.008,
    })
    tokens_per_minute: float = 1000.0
    debug_routing: bool = False
    usage: Dict[str, Any] = field(default_factory=dict)

@dataclass
class GovernanceConfig:
    master_enabled: bool = True
    audit_logging: bool = True
    kill_switches: Dict[str, bool] = field(default_factory=lambda: {
        "global": False
    })
    safety_policies: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": True,
        "strict_mode": False
    })

@dataclass
class MemoryConfig:
    rag_enabled: bool = True
    vector_db_path: str = "data/memory.db"
    # Placeholder for the active database client
    db_client: Any = None 

@dataclass
class DeclarativeKnowledge:
    personality: Dict[str, str] = field(default_factory=lambda: {
        "tone": "helpful",
        "style": "concise"
    })
    rules: Dict[str, str] = field(default_factory=lambda: {
        "primary": "Always be polite",
        "secondary": "Verify facts"
    })
    boundaries: Dict[str, Any] = field(default_factory=lambda: {
        "allow_harm": False,
        "no_insults": True
    })

@dataclass
class ProceduralReasoning:
    strategies: Dict[str, str] = field(default_factory=lambda: {
        "explanation": "chain_of_thought",
        "planning": "step_by_step",
        "default": "direct_answer"
    })

@dataclass
class LearningConfig:
    daily_learning_enabled: bool = True
    reflection_prompts: List[str] = field(default_factory=lambda: [
        "What did we learn from this interaction?"
    ])
    proposal_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "confidence": 0.8
    })
    
    # Configuration for the LearningRouter
    router_toggles: Dict[str, bool] = field(default_factory=lambda: {
        "use_md": True,
        "use_url": False,
        "use_logic_tables": True,
        "use_op_logic_tables": False
    })

    # --- REQUIRED FOR LEARNINGLAYER ---
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

@dataclass
class BrainState:
    """
    The central state of the agent. 
    Defaults are provided for all fields to ensure safe instantiation.
    """
    agent_id: str = "gemini-agent-v2"
    version: str = "2.1.0"
    governance: GovernanceConfig = field(default_factory=GovernanceConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    providers: ProviderConfig = field(default_factory=ProviderConfig)
    procedural: ProceduralReasoning = field(default_factory=ProceduralReasoning)
    learning: LearningConfig = field(default_factory=LearningConfig)
    declarative: DeclarativeKnowledge = field(default_factory=DeclarativeKnowledge)
