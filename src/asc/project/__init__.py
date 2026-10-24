"""Persistent creative-project foundation (schema version 1)."""

from .model import (
    ArtifactRef,
    ProjectSnapshot,
    WorkNode,
    WorkNodeRevision,
    WorkProject,
    WorkSpec,
)
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
    "ProjectCorruptError",
    "ProjectError",
    "ProjectExistsError",
    "ProjectLockError",
    "ProjectNotFoundError",
    "ProjectSnapshot",
    "ProjectStore",
    "ProjectValidationError",
    "SCHEMA_VERSION",
    "WorkNode",
    "WorkNodeRevision",
    "WorkProject",
    "WorkSpec",
]
