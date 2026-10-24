"""Graph and condition checks for interactive branches.

Structural checks (references, reachability, termination, merges) run on the
bare graph. Condition checks run a bounded product search over
(node, flags) states to find edges that can never be taken and flags that
are required but never set. The search is capped; beyond the cap the
conditional findings are replaced by a low note instead of a guess.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .schema import BranchDoc

NODE_KINDS = {"scene", "choice", "ending"}

#: cap on (node, flags) states before the conditional search gives up
MAX_PRODUCT_STATES = 20000


@dataclass(frozen=True)
class Check:
    id: str
    acceptance_ja: str
    technique_ids: tuple[str, ...]


CHECKS = (
    Check("graph_grounded", "開始点・辺・選択肢の参照が実在する。",
          ("narrative/japan_2026:T093", "narrative/us_2026:T105")),
    Check("paths_reachable", "全節点に開始点から到達でき、袋小路の罠がない。",
          ("production/game_narrative_us:P30", "narrative/us_2026:T091")),
    Check("endings_terminated", "結末以外に行き止まりがなく、結末から辺が出ない。",
          ("narrative/us_2026:T091", "narrative/us_2026:T106")),
    Check("flags_declared", "条件・更新の旗が宣言され、意味がある。",
          ("production/game_narrative_us:P19",
           "narrative/japan_2026:T094")),
    Check("conditions_sound", "辿れない条件と、設定されない必須の旗がない。",
          ("narrative/japan_2026:T094", "narrative/us_2026:T092")),
    Check("options_meaningful", "選択肢が 2 件以上あり、表示と辺が対応する。",
          ("narrative/us_2026:T093", "narrative/us_2026:T090")),
    Check("merges_noted", "合流点に知識・状態の扱いの覚え書きがある。",
          ("narrative/us_2026:T091", "narrative/japan_2026:T093")),
)


def _finding(check: str, severity: str, message_ja: str, ref: str) -> dict:
    return {"check": check, "severity": severity,
            "message_ja": message_ja, "branch_ref": ref}


def check_branches(doc: BranchDoc) -> dict:
    findings: list[dict] = []
    nodes = {n.id: n for n in doc.nodes}
    flags = {f.id: f for f in doc.flags}
    outgoing: dict[str, list] = {nid: [] for nid in nodes}
    incoming: dict[str, set[str]] = {nid: set() for nid in nodes}
    for edge in doc.edges:
        if edge.from_id in outgoing:
            outgoing[edge.from_id].append(edge)
        if edge.to_id in incoming:
            incoming[edge.to_id].add(edge.from_id)

    # -- graph_grounded ---------------------------------------------------------
    if not doc.start:
        findings.append(_finding(
            "graph_grounded", "medium", "開始点（start）がない。", "start"))
    elif doc.start not in nodes:
        findings.append(_finding(
            "graph_grounded", "medium",
            f"開始点「{doc.start}」が節点にない。", "start"))
    for node in doc.nodes:
        if node.kind not in NODE_KINDS:
            findings.append(_finding(
                "graph_grounded", "medium",
                f"種別「{node.kind}」は {sorted(NODE_KINDS)} のいずれかにする。",
                f"nodes:{node.id}"))
    for edge in doc.edges:
        ref = f"edges[{edge.index}]"
        if not edge.from_id or not edge.to_id:
            findings.append(_finding(
                "graph_grounded", "medium",
                "辺の from か to が空欄。", ref))
            continue
        if edge.from_id not in nodes:
            findings.append(_finding(
                "graph_grounded", "medium",
                f"辺の from「{edge.from_id}」が節点にない。", ref))
        if edge.to_id not in nodes:
            findings.append(_finding(
                "graph_grounded", "medium",
                f"辺の to「{edge.to_id}」が節点にない。", ref))
        source = nodes.get(edge.from_id)
        if source is not None and source.kind == "choice" and not edge.via:
            findings.append(_finding(
                "graph_grounded", "medium",
                "選択肢からの辺に via（選択肢 ID）がない。", ref))
        if source is not None and source.kind != "choice" and edge.via:
            findings.append(_finding(
                "graph_grounded", "medium",
                f"via「{edge.via}」は選択肢の節点からの辺にだけ書く。", ref))
        if source is not None and source.kind == "choice" and edge.via:
            option_ids = {o.id for o in source.options}
            if edge.via not in option_ids:
                findings.append(_finding(
                    "graph_grounded", "medium",
                    f"via「{edge.via}」が節点 {source.id} の選択肢にない。",
                    ref))

    # -- paths_reachable -----------------------------------------------------------
    if doc.start in nodes:
        seen = {doc.start}
        queue = deque([doc.start])
        while queue:
            here = queue.popleft()
            for edge in outgoing.get(here, []):
                if edge.to_id in nodes and edge.to_id not in seen:
                    seen.add(edge.to_id)
                    queue.append(edge.to_id)
        for nid in nodes:
            if nid not in seen:
                findings.append(_finding(
                    "paths_reachable", "medium",
                    f"節点 {nid} に開始点から到達できない。辺を足すか削る。",
                    f"nodes:{nid}"))
        endings = {nid for nid, n in nodes.items() if n.kind == "ending"}
        can_finish: set[str] = set(endings)
        queue = deque(endings)
        reverse: dict[str, list[str]] = {nid: [] for nid in nodes}
        for edge in doc.edges:
            if edge.from_id in reverse and edge.to_id in reverse:
                reverse[edge.to_id].append(edge.from_id)
        while queue:
            here = queue.popleft()
            for prev in reverse.get(here, []):
                if prev not in can_finish:
                    can_finish.add(prev)
                    queue.append(prev)
        for nid in sorted(set(nodes) - can_finish):
            findings.append(_finding(
                "paths_reachable", "medium",
                f"節点 {nid} から結末に到達できない。罠（無限回遊）か、辺の不足。",
                f"nodes:{nid}"))

    # -- endings_terminated --------------------------------------------------------------
    for node in doc.nodes:
        ref = f"nodes:{node.id}"
        if node.kind == "ending":
            if outgoing.get(node.id):
                findings.append(_finding(
                    "endings_terminated", "medium",
                    f"結末 {node.id} から辺が出ている。結末で止める。",
                    ref))
            if not node.ending:
                findings.append(_finding(
                    "endings_terminated", "medium",
                    f"結末 {node.id} の内容（ending）が空欄。", ref))
        elif not outgoing.get(node.id):
            findings.append(_finding(
                "endings_terminated", "medium",
                f"{node.id} は行き止まり（結末でもない）。辺を足すか結末にする。",
                ref))

    # -- flags_declared -------------------------------------------------------
    for flag_id in doc.initial:
        if flag_id not in flags:
            findings.append(_finding(
                "flags_declared", "medium",
                f"初期の旗「{flag_id}」が旗の表にない。", "initial"))
    for flag in doc.flags:
        if not flag.meaning:
            findings.append(_finding(
                "flags_declared", "medium",
                f"旗 {flag.id} の意味（meaning）が空欄。", f"flags:{flag.id}"))

    def _flag_uses() -> list[tuple[str, str]]:
        uses = []
        for edge in doc.edges:
            for flag_id in edge.requires:
                uses.append((flag_id, f"edges[{edge.index}].requires"))
            for flag_id in edge.sets:
                uses.append((flag_id, f"edges[{edge.index}].sets"))
        for node in doc.nodes:
            for option in node.options:
                for flag_id in option.requires:
                    uses.append((flag_id,
                                 f"nodes:{node.id}.options:{option.id}"))
        return uses

    for flag_id, where in _flag_uses():
        if flag_id not in flags:
            findings.append(_finding(
                "flags_declared", "medium",
                f"旗「{flag_id}」が旗の表にない（{where}）。",
                "flags"))

    # -- conditions_sound ------------------------------------------------------
    settable = set(doc.initial)
    for edge in doc.edges:
        settable.update(edge.sets)
    for flag_id, where in _flag_uses():
        if flag_id in flags and flag_id not in settable and \
                ".requires" in where:
            findings.append(_finding(
                "conditions_sound", "medium",
                f"旗「{flag_id}」は必須にされるが、どこでも設定されない"
                f"（{where}）。", "flags"))
    if doc.start in nodes:
        traversed, capped = _product_search(doc, nodes, flags)
        if capped:
            findings.append(_finding(
                "conditions_sound", "low",
                f"状態空間が上限（{MAX_PRODUCT_STATES}）を超えたため、"
                "条件付き到達の検査を省略した。分岐を分割して再検査する。",
                "edges"))
        else:
            for edge in doc.edges:
                if edge.from_id in nodes and edge.to_id in nodes \
                        and edge.index not in traversed:
                    findings.append(_finding(
                        "conditions_sound", "medium",
                        f"辺 edges[{edge.index}]"
                        f"（{edge.from_id} → {edge.to_id}）は"
                        "どの状態でも辿れない。条件を緩めるか削る。",
                        f"edges[{edge.index}]"))

    # -- options_meaningful --------------------------------------------------------
    for node in doc.nodes:
        ref = f"nodes:{node.id}"
        if node.kind != "choice":
            if node.options:
                findings.append(_finding(
                    "options_meaningful", "medium",
                    "選択肢は choice の節点にだけ書く。", ref))
            continue
        if len(node.options) < 2:
            findings.append(_finding(
                "options_meaningful", "medium",
                f"選択肢が {len(node.options)} 件（2 件必要）。"
                "1 件の選択は選択ではない。", ref))
        labels = [o.label for o in node.options if o.label]
        if len(labels) != len(set(labels)):
            findings.append(_finding(
                "options_meaningful", "medium",
                "同じ表示の選択肢がある。区別できる表示にする。", ref))
        used = {e.via for e in outgoing.get(node.id, []) if e.via}
        for option in node.options:
            if not option.label:
                findings.append(_finding(
                    "options_meaningful", "medium",
                    f"選択肢 {option.id or '?'} の表示が空欄。", ref))
            if option.id and option.id not in used:
                findings.append(_finding(
                    "options_meaningful", "medium",
                    f"選択肢 {option.id} を使う辺がない。辺を足すか削る。",
                    ref))

    # -- merges_noted -----------------------------------------------------
    for node in doc.nodes:
        sources = {s for s in incoming.get(node.id, []) if s != node.id}
        if len(sources) >= 2 and not node.merge_note:
            findings.append(_finding(
                "merges_noted", "medium",
                f"{node.id} は {len(sources)} 方向からの合流点。"
                "知識・状態の扱いを merge_note に書く。",
                f"nodes:{node.id}"))

    checks = []
    for spec in CHECKS:
        count = sum(1 for f in findings if f["check"] == spec.id)
        checks.append({"id": spec.id, "acceptance_ja": spec.acceptance_ja,
                       "technique_ids": list(spec.technique_ids),
                       "status": "fail" if count else "pass", "findings": count})
    by_severity: dict[str, int] = {}
    for item in findings:
        by_severity[item["severity"]] = by_severity.get(item["severity"], 0) + 1
    return {
        "branches": str(doc.path),
        "findings": findings,
        "checks": checks,
        "summary": {
            "findings": len(findings),
            "by_severity": by_severity,
            "checks_failed": sum(1 for c in checks if c["status"] == "fail"),
            "checks_skipped": sum(1 for c in checks if c["status"] == "skipped"),
        },
    }


def _product_search(doc: BranchDoc, nodes: dict, flags: dict):
    """Bounded search over (node, flags) states.

    Returns the traversed edge indices and whether the state cap was hit.
    Undeclared flags are ignored here (reported by flags_declared).
    """
    options_by_node = {nid: {o.id: o for o in n.options}
                       for nid, n in nodes.items()}
    outgoing: dict[str, list] = {nid: [] for nid in nodes}
    for edge in doc.edges:
        if edge.from_id in outgoing and edge.to_id in nodes:
            outgoing[edge.from_id].append(edge)
    start_flags = frozenset(f for f in doc.initial if f in flags)
    seen = {(doc.start, start_flags)}
    queue = deque([(doc.start, start_flags)])
    traversed: set[int] = set()
    while queue:
        if len(seen) >= MAX_PRODUCT_STATES:
            return traversed, True
        here, held = queue.popleft()
        node = nodes[here]
        for edge in outgoing.get(here, []):
            needed = set(edge.requires)
            if node.kind == "choice" and edge.via:
                option = options_by_node[here].get(edge.via)
                if option is not None:
                    needed.update(option.requires)
            if not needed.issubset(held):
                continue
            traversed.add(edge.index)
            nxt = (edge.to_id, held | frozenset(
                f for f in edge.sets if f in flags))
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return traversed, False


def render_markdown(report: dict) -> str:
    lines = ["# 分岐構造の検査結果", "",
             f"対象: `{report['branches']}`",
             f"所見: {report['summary']['findings']} 件 "
             f"（{report['summary']['by_severity']}）", ""]
    if not report["findings"]:
        lines.append("構造上の所見はない。**選択の面白さは判定していない。**")
        return "\n".join(lines)
    lines.append("| 検査 | 重要度 | 所見 |")
    lines.append("| --- | --- | --- |")
    for item in report["findings"]:
        lines.append(f"| {item['check']} | {item['severity']} "
                     f"| {item['branch_ref']}: {item['message_ja']} |")
    return "\n".join(lines)
