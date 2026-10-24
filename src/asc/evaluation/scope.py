"""Load the active evaluation scope without changing protocol-v1 itself."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SCOPE_PATH = REPO_ROOT / "configs" / "evaluation_scope.yaml"
LAYERS = {"L1", "L2", "L3"}
GATES = {"G1", "G2", "G3", "G4", "G5"}


class EvaluationScopeError(ValueError):
    """The scope file is missing required, machine-checkable fields."""


def load_evaluation_scope(path: str | Path | None = None) -> dict:
    scope_path = Path(path) if path is not None else DEFAULT_SCOPE_PATH
    try:
        payload = yaml.safe_load(scope_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise EvaluationScopeError(f"cannot read evaluation scope {scope_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise EvaluationScopeError("evaluation scope must be a mapping")
    if payload.get("schema") != "evaluation-scope-v1":
        raise EvaluationScopeError("evaluation scope schema must be evaluation-scope-v1")
    if not payload.get("protocol") or not payload.get("decided_on"):
        raise EvaluationScopeError("evaluation scope needs protocol and decided_on")
    active = payload.get("active_layers")
    frozen = payload.get("frozen_layers")
    if not isinstance(active, list) or not active or not set(active) <= LAYERS:
        raise EvaluationScopeError("active_layers must be a non-empty subset of L1/L2/L3")
    if len(active) != len(set(active)):
        raise EvaluationScopeError("active_layers contains duplicates")
    if not isinstance(frozen, dict) or not set(frozen) <= LAYERS:
        raise EvaluationScopeError("frozen_layers must be a mapping keyed by L1/L2/L3")
    if set(active) & set(frozen):
        raise EvaluationScopeError("a layer cannot be both active and frozen")
    if set(payload.get("gate_status") or {}) != GATES:
        raise EvaluationScopeError("gate_status must cover G1 through G5 exactly")
    if not isinstance(payload.get("claims"), dict):
        raise EvaluationScopeError("claims must be a mapping")
    return payload
