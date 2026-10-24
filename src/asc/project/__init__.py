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
from .model import (
    ArtifactRef,
    ProjectSnapshot,
    StageCheckpoint,
    WorkNode,
    WorkNodeRevision,
    WorkProject,
    WorkSpec,
)
from .resume import ResumeError, ResumeProvider
from .runner import ProjectRunError, ProjectRunPending, ProjectRunResult, ProjectRunner
from .schema import SCHEMA_VERSION, ProjectValidationError
from .store import (
    ProjectCorruptError,
    ProjectError,
    ProjectExistsError,
    ProjectLockError,
    ProjectNotFoundError,
    ProjectStore,
)

__all__ = [
    "ArtifactRef",
    "BUNDLE_TYPE",
    "BundleError",
    "ContinuationContext",
    "PROJECT_PROTOCOL",
    "PipelineInput",
    "ProjectCorruptError",
    "ProjectError",
    "ProjectExistsError",
    "ProjectLockError",
    "ProjectNotFoundError",
    "ProjectRunError",
    "ProjectRunPending",
    "ProjectRunResult",
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
    "WorkNodeRevision",
    "WorkProject",
    "WorkSpec",
    "export_bundle",
    "restore_bundle",
    "verify_bundle",
]
