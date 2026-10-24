"""Generation pipeline (Plan -> Design -> Draft -> Revise -> Voice).

S0 drafts from a single prompt; S1 plans a canon first, designs the documents
the skills check, then drafts; S2 revises the draft against its audit; S3
restyles the revised chapters against a voice guide.
"""
from .llm import (
    CommandProvider, GenerationRequest, GenerationResult, Provider, ProviderError,
    ScriptedProvider, digest, load_scripted_responses,
)
from .design import (
    DOCS as DESIGN_DOCS, Design, DesignError, DocResult, build_design,
    design_notes_for_chapter,
)
from .draft import (
    Draft, DraftError, ChapterDraft, build_story, canon_brief, chapter_plan,
    check_chapter, clean_text, draft_story,
)
from .plan import (
    Plan, PlanError, build_plan, canon_coverage, normalise_canon, parse_plan,
    validate_payload,
)
from .prompts import PromptError, PromptTemplate, load_prompt
from .revise import Revision, RevisionError, build_revision
from .run import RunLedger, git_commit, make_run_id
from .tasks import PROTOCOL_VERSION, Task, TaskError, TaskSet, load_tasks
from .voicepass import VoicePass, VoicePassError, build_voice_pass, voice_guide_text

__all__ = [
    "CommandProvider", "GenerationRequest", "GenerationResult", "Provider",
    "ProviderError", "ScriptedProvider", "digest", "load_scripted_responses",
    "Plan", "PlanError", "build_plan", "canon_coverage", "normalise_canon",
    "parse_plan", "validate_payload",
    "DESIGN_DOCS", "Design", "DesignError", "DocResult", "build_design",
    "design_notes_for_chapter",
    "Draft", "DraftError", "ChapterDraft", "build_story", "canon_brief",
    "chapter_plan", "check_chapter", "clean_text", "draft_story",
    "Revision", "RevisionError", "build_revision",
    "VoicePass", "VoicePassError", "build_voice_pass", "voice_guide_text",
    "PromptError", "PromptTemplate", "load_prompt",
    "RunLedger", "git_commit", "make_run_id",
    "PROTOCOL_VERSION", "Task", "TaskError", "TaskSet", "load_tasks",
]
