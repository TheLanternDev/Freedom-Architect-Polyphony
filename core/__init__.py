"""
Core domain Architekta Wolności.

Dwa AKSJOMATY pierwotne projektu:
- AKSJOMAT 1: Architektura Marzenia → `core.dream_architect`
- AKSJOMAT 2: Doprowadzanie Projektów Do Końca → `core.completion_enforcer`

Te dwa moduły są warstwą domenową ponad agentami: agenci dają głosy,
core pilnuje, żeby te głosy zawsze służyły spełnianiu marzeń i kończeniu
projektów w pełni funkcjonalnym stanie.
"""

from core.dream_architect import (
    DreamArchitecture,
    Milestone,
    NextMove,
    distill_dream,
    adistill_dream,
    DREAM_DISTILLATION_SYSTEM_PROMPT,
)
from core.completion_enforcer import (
    ProjectStatus,
    Project,
    FunctionalityItem,
    CompletionAudit,
    AGENT_COMPLETION_POSTSCRIPT,
    MAX_ACTIVE_PROJECTS,
    STALE_DAYS_AT_RISK,
    STALE_DAYS_STUCK,
    MIN_ARCHIVE_REASON_LEN,
    SYEZ_AKSJOMAT2_PROSE_APPEND,
    SYEZ_COMPLETION_AUDIT_REQUIREMENT,
    assert_full_functionality,
    classify_stale_status,
    enforce_active_project_limit,
    extract_completion_audit_from_prose,
    validate_archive_reason,
    validate_syez_prose_completion_audit,
    require_completion_audit,
    CompletionViolation,
)

__all__ = [
    # Aksjomat 1
    "DreamArchitecture",
    "Milestone",
    "NextMove",
    "distill_dream",
    "adistill_dream",
    "DREAM_DISTILLATION_SYSTEM_PROMPT",
    # Aksjomat 2
    "ProjectStatus",
    "Project",
    "FunctionalityItem",
    "CompletionAudit",
    "AGENT_COMPLETION_POSTSCRIPT",
    "MAX_ACTIVE_PROJECTS",
    "STALE_DAYS_AT_RISK",
    "STALE_DAYS_STUCK",
    "MIN_ARCHIVE_REASON_LEN",
    "SYEZ_AKSJOMAT2_PROSE_APPEND",
    "SYEZ_COMPLETION_AUDIT_REQUIREMENT",
    "assert_full_functionality",
    "enforce_active_project_limit",
    "classify_stale_status",
    "validate_archive_reason",
    "validate_syez_prose_completion_audit",
    "extract_completion_audit_from_prose",
    "require_completion_audit",
    "CompletionViolation",
]
