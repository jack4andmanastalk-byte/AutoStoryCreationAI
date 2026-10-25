"""Persistent creative-project foundation (schema version 1)."""

from .adapter import PROJECT_PROTOCOL, PipelineInput, adapt_work_spec
from .bundle import (
    BUNDLE_TYPE,
    BundleError,
    ReplayBundle,
    export_bundle,
    restore_bundle,
    verify_bundle,
)
from .continuation import ContinuationContext
from .context import AncestorContext, ContextPacket, build_context_packet
from .model import (
    ArtifactRef,
    ProjectSnapshot,
    WorkLink,
    StageCheckpoint,
    WorkNode,
    WorkNodeRevision,
    WorkProject,
    WorkSpec,
)
from .nested import CompositionResult, NestedError, ProjectComposer
from .resume import ResumeError, ResumeProvider
from .runner import (
    ProjectDependencyError,
    ProjectRunError,
    ProjectRunPending,
    ProjectRunResult,
    ProjectRunner,
    ProjectTreeRunResult,
)
from .schema import SCHEMA_VERSION, ProjectValidationError
from .store import (
    MAX_NESTING_DEPTH,
    ProjectCorruptError,
    ProjectError,
    ProjectExistsError,
    ProjectLockError,
    ProjectNotFoundError,
    ProjectStore,
)

__all__ = [
    "AncestorContext",
    "ArtifactRef",
    "BUNDLE_TYPE",
    "BundleError",
    "ContinuationContext",
    "ContextPacket",
    "CompositionResult",
    "NestedError",
    "MAX_NESTING_DEPTH",
    "PROJECT_PROTOCOL",
    "PipelineInput",
    "ProjectComposer",
    "ProjectCorruptError",
    "ProjectError",
    "ProjectExistsError",
    "ProjectLockError",
    "ProjectNotFoundError",
    "ProjectDependencyError",
    "ProjectRunError",
    "ProjectRunPending",
    "ProjectRunResult",
    "ProjectTreeRunResult",
    "ProjectRunner",
    "ProjectSnapshot",
    "ProjectStore",
    "ProjectValidationError",
    "ReplayBundle",
    "ResumeError",
    "ResumeProvider",
    "SCHEMA_VERSION",
    "StageCheckpoint",
    "WorkNode",
    "adapt_work_spec",
    "WorkLink",
    "WorkNodeRevision",
    "WorkProject",
    "WorkSpec",
    "build_context_packet",
    "export_bundle",
    "restore_bundle",
    "verify_bundle",
]
