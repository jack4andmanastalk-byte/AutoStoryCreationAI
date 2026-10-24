"""Persistent creative-project foundation (schema version 1)."""

from .adapter import PROJECT_PROTOCOL, PipelineInput, adapt_work_spec
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
    "ResumeError",
    "ResumeProvider",
    "SCHEMA_VERSION",
    "StageCheckpoint",
    "WorkNode",
    "adapt_work_spec",
    "WorkNodeRevision",
    "WorkProject",
    "WorkSpec",
]
