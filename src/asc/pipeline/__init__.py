"""Generation pipeline (Plan -> Draft -> Check -> Act).

Phase 2-A implements the Plan step only: a frozen task becomes a canon that the
continuity audit can read. Drafting and revision follow in later steps.
"""
from .llm import (
    CommandProvider, GenerationRequest, GenerationResult, Provider, ProviderError,
    ScriptedProvider, digest, load_scripted_responses,
)
from .plan import (
    Plan, PlanError, build_plan, canon_coverage, normalise_canon, parse_plan,
    validate_payload,
)
from .prompts import PromptError, PromptTemplate, load_prompt
from .run import RunLedger, git_commit, make_run_id
from .tasks import PROTOCOL_VERSION, Task, TaskError, TaskSet, load_tasks

__all__ = [
    "CommandProvider", "GenerationRequest", "GenerationResult", "Provider",
    "ProviderError", "ScriptedProvider", "digest", "load_scripted_responses",
    "Plan", "PlanError", "build_plan", "canon_coverage", "normalise_canon",
    "parse_plan", "validate_payload",
    "PromptError", "PromptTemplate", "load_prompt",
    "RunLedger", "git_commit", "make_run_id",
    "PROTOCOL_VERSION", "Task", "TaskError", "TaskSet", "load_tasks",
]
