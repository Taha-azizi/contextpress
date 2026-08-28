from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StageConfig:
    enabled: bool = True
    aggressiveness: float = 0.5  # 0.0 = minimal, 1.0 = maximum compression


@dataclass
class Profile:
    name: str
    structure: StageConfig
    lexical: StageConfig
    filler: StageConfig
    abbrev: StageConfig
    alias: StageConfig
    repetition: StageConfig
    trim: StageConfig
    resolution: StageConfig
    recency: StageConfig
    budget: StageConfig
    role_aware: bool = True  # enables speaker-side awareness


PROFILES: dict[str, Profile] = {
    "chat": Profile(
        name="chat",
        structure=StageConfig(enabled=True, aggressiveness=0.45),
        lexical=StageConfig(enabled=True, aggressiveness=0.5),
        filler=StageConfig(enabled=True, aggressiveness=0.7),
        abbrev=StageConfig(enabled=True, aggressiveness=0.55),
        alias=StageConfig(enabled=True, aggressiveness=0.55),
        repetition=StageConfig(enabled=True, aggressiveness=0.6),
        trim=StageConfig(enabled=True, aggressiveness=0.55),
        resolution=StageConfig(enabled=True, aggressiveness=0.8),
        recency=StageConfig(enabled=True, aggressiveness=0.5),
        budget=StageConfig(enabled=True),
        role_aware=True,
    ),
    "rag_doc": Profile(
        name="rag_doc",
        structure=StageConfig(enabled=True, aggressiveness=0.5),
        lexical=StageConfig(enabled=False),  # wording swaps are for chat, not documents
        filler=StageConfig(enabled=True, aggressiveness=0.5),
        abbrev=StageConfig(enabled=False),  # keep document wording intact
        alias=StageConfig(enabled=False),
        repetition=StageConfig(enabled=True, aggressiveness=0.8),
        trim=StageConfig(enabled=True, aggressiveness=0.4),
        resolution=StageConfig(enabled=False),  # no resolution in documents
        recency=StageConfig(enabled=True, aggressiveness=0.3),  # relevance scoring instead
        budget=StageConfig(enabled=True),
        role_aware=False,  # no speaker sides in documents
    ),
    "agent": Profile(
        name="agent",
        structure=StageConfig(enabled=True, aggressiveness=0.75),
        lexical=StageConfig(enabled=True, aggressiveness=0.5),
        filler=StageConfig(enabled=True, aggressiveness=0.4),
        abbrev=StageConfig(enabled=True, aggressiveness=0.5),
        alias=StageConfig(enabled=True, aggressiveness=0.5),
        repetition=StageConfig(enabled=True, aggressiveness=0.7),
        trim=StageConfig(enabled=True, aggressiveness=0.45),
        resolution=StageConfig(enabled=True, aggressiveness=0.9),  # task completion detection
        recency=StageConfig(enabled=True, aggressiveness=0.6),
        budget=StageConfig(enabled=True),
        role_aware=True,
    ),
}
