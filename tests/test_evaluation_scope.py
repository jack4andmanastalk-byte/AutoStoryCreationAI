"""The user's L2/L3 freeze must remain visible to new experiment runs."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.evaluation.scope import load_evaluation_scope  # noqa: E402


def test_current_scope_is_l1_only_with_l2_l3_frozen():
    scope = load_evaluation_scope()
    assert scope["mode"] == "l1-only"
    assert scope["provider_constraint"] == "arena-only"
    assert scope["active_layers"] == ["L1"]
    assert set(scope["frozen_layers"]) == {"L2", "L3"}
    assert scope["gate_status"]["G3"] == "frozen_not_measured"
    assert scope["gate_status"]["G4"] == "frozen_not_measured"
    assert scope["gate_status"]["G5"] == "unmet_with_unversioned_arena"
    assert scope["claims"]["protocol_v1_functioning"] == "not_claimed"


def test_scope_document_is_linked_and_does_not_replace_the_protocol():
    scope_doc = REPO_ROOT / "docs" / "evaluation_scope.md"
    text = scope_doc.read_text(encoding="utf-8")
    assert "L2（モデル判定）と" in text
    assert "G3/G4 は `frozen_not_measured`" in text
    assert "protocol-v1 の合格証拠ではなく" in text
    protocol = (REPO_ROOT / "docs" / "protocol.md").read_text(encoding="utf-8")
    # Freezing operations must not erase the pre-registered gates.
    for gate in ("G1", "G2", "G3", "G4", "G5"):
        assert f"| {gate} |" in protocol
