#!/usr/bin/env python3
"""Create, run, and inspect persistent creative projects.

Examples::

    python3 scripts/story_project.py init \
        --title "潮の記録者" --premise "港町で失われた潮位記録を追う。"
    python3 scripts/story_project.py status PROJECT_ID --json

This is the standard entry point for AI automatic authorship: a premise and its
constraints go in, three inspected chapters come out, and the same project can
then be continued, revised, branched, and compiled.  The contract with the rest
of the repository is [`docs/standard_flow.md`](../docs/standard_flow.md), and the
step-by-step procedure is [`docs/quickstart.md`](../docs/quickstart.md).

By default, projects live below ``runs/projects/``.  Use ``--root`` before the
subcommand to select another store; committed works use ``--root works``.
``run`` executes the single-work S1 vertical slice, and ``resume`` continues an
interrupted revision without regenerating its completed response prefix.

Generation defaults to ``--provider arena``: ``scripts/chat_operator.py`` keeps
each prompt in ``<project>/relay/requests`` and reads the answer back from
``<project>/relay/responses``, so an Arena session can stop at the exact prompt
that has no text yet and continue in a later turn.  ``relay export`` writes the
paste-ready ``PROMPTS.md`` and ``relay ingest`` reads the answers back.
``continue`` creates a new revision for a completed work, and
``bundle export|verify|restore`` moves its replay materials to an external
directory.  ``add-child`` creates an independent
child below any node; ``run-tree`` uses parent-first dependency order;
``render`` and ``compose`` provide single-work and recursive pinned outputs.
``world`` persists multiple timeframes, regions, culture states, revision-pinned
work bindings, and explicitly adopted scoped canon.  It also selects those
records for generation and compiles chronicle/gazetteer/culture/collection views.
``doctor`` inspects project, revision, world, and artifact integrity together
with pending/stale references, and ``context show`` prints the current or a
recorded ContextPacket.  Both are read-only: they never generate, resume, or
adopt.  ``revise`` makes a new revision of a finished work and ``branch`` makes
a new node from it; both regenerate only the chapters and design documents
named on the command line and copy the rest byte-for-byte.
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
# The relay file format (tags, PROMPTS.md, ingest rules) lives in the sibling
# script `relay_prompts.py`; reusing it keeps one definition of the handoff.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import relay_prompts  # noqa: E402

from asc.pipeline import (  # noqa: E402
    CommandProvider, ProviderError, ScriptedProvider, load_scripted_responses,
)
from asc.project import (  # noqa: E402
    DEFAULT_STAGES,
    CanonScope,
    ProjectComposer,
    ProjectError,
    ReplayBundle,
    ProjectRunError,
    ProjectRunPending,
    ProjectRunner,
    ProjectStore,
    ProjectValidationError,
    WorkSpec,
    WorldCompiler,
    WorldStore,
    build_context_view,
    build_diff,
    inspect_project,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--root", default=str(REPO_ROOT / "runs" / "projects"),
        help="project store root (default: runs/projects)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="create a project and its first revision")
    init.add_argument("--project-id", help="optional stable id; lowercase letters, digits, ._-")
    init.add_argument("--title", required=True)
    premise = init.add_mutually_exclusive_group(required=True)
    premise.add_argument("--premise", help="premise text")
    premise.add_argument("--premise-file", help="read UTF-8 premise text from a file")
    init.add_argument("--language", default="ja")
    init.add_argument("--chapters", type=int, default=3)
    init.add_argument("--target-chars", type=int, default=1600)
    init.add_argument("--form", default="novel")
    init.add_argument(
        "--knowledge-character",
        help="filter ancestor facts to this character ID's canon knows list",
    )
    init.add_argument("--json", dest="json_output", action="store_true")

    def _provider_arguments(parser) -> None:
        """The provider options shared by every generation entry point.

        ``arena`` is the standard flow: prompts and answers stay in the
        project's ``relay/`` directory (``scripts/chat_operator.py``), so the
        work resumes across Arena sessions.  It is also the default when
        neither ``--provider`` nor a provider option is given.
        """
        parser.add_argument(
            "--provider", choices=sorted(PROVIDERS), default=None,
            help="model provider (default: arena = the project's relay directory)",
        )
        parser.add_argument("--script", help="scripted response JSON (with --provider scripted)")
        parser.add_argument("--command", dest="provider_command", help="external provider command")
        parser.add_argument(
            "--relay-dir",
            help="operator directory for --provider arena (default: <project>/relay)",
        )
        parser.add_argument("--model")

    def _generation_arguments(parser) -> None:
        _provider_arguments(parser)
        parser.add_argument("--seed", type=int, default=0)
        parser.add_argument("--temperature", type=float)

    run = subparsers.add_parser("run", help="run plan, design, and draft for a new revision")
    run.add_argument("project_id")
    run.add_argument("--node", dest="node_id", help="descendant node ID (default: root)")
    _generation_arguments(run)
    run.add_argument("--json", dest="json_output", action="store_true")

    tree = subparsers.add_parser(
        "run-tree", help="run a node and its descendants in parent-first order",
    )
    tree.add_argument("project_id")
    tree.add_argument("--node", dest="node_id", help="subtree root (default: project root)")
    _generation_arguments(tree)
    tree.add_argument("--json", dest="json_output", action="store_true")

    continuation = subparsers.add_parser(
        "continue", help="create a new revision with additional chapters",
    )
    continuation.add_argument("project_id")
    continuation.add_argument("--node", dest="node_id", help="descendant node ID (default: root)")
    chapter_change = continuation.add_mutually_exclusive_group()
    chapter_change.add_argument("--add-chapters", type=int)
    chapter_change.add_argument("--chapters", type=int, help="new total chapter count")
    continuation.add_argument("--title")
    continuation.add_argument("--premise")
    continuation.add_argument(
        "--world-binding",
        help="explicitly reuse this parent-revision world binding for the new revision",
    )
    _generation_arguments(continuation)
    continuation.add_argument("--json", dest="json_output", action="store_true")

    def _derived_arguments(parser) -> None:
        parser.add_argument(
            "--chapter", dest="chapters", action="append", default=[],
            metavar="ID", help="chapter to regenerate (repeatable)",
        )
        parser.add_argument(
            "--design", dest="design", action="append", default=[],
            metavar="DOC", help="design document to regenerate (repeatable)",
        )
        parser.add_argument("--title")
        parser.add_argument("--premise")
        parser.add_argument("--target-chars", type=int)
        parser.add_argument(
            "--world-binding",
            help="explicitly copy this source-revision world binding to the new revision",
        )
        _generation_arguments(parser)
        parser.add_argument("--json", dest="json_output", action="store_true")

    revise = subparsers.add_parser(
        "revise",
        help="create a new revision and regenerate only the selected chapters/design",
    )
    revise.add_argument("project_id")
    revise.add_argument("--node", dest="node_id", help="descendant node ID (default: root)")
    revise.add_argument(
        "--revision", dest="source_revision", help="source revision (default: current)",
    )
    _derived_arguments(revise)

    branch = subparsers.add_parser(
        "branch", help="create a new node from a revision, regenerating only the selected parts",
    )
    branch.add_argument("project_id")
    branch.add_argument(
        "--from-node", dest="from_node", help="source node ID (default: root)",
    )
    branch.add_argument(
        "--from-revision", dest="source_revision",
        help="source revision (default: the source node's current revision)",
    )
    branch.add_argument(
        "--parent-node", dest="parent_node_id",
        help="parent of the new node (default: the source node's parent)",
    )
    branch.add_argument("--node-id", dest="child_node_id", help="stable new node ID")
    branch.add_argument("--link-id", help="stable new link ID")
    branch.add_argument("--order", type=int, help="positive output order; default: append")
    _derived_arguments(branch)

    resume = subparsers.add_parser("resume", help="resume an interrupted project revision")
    resume.add_argument("project_id")
    resume.add_argument("--node", dest="node_id", help="descendant node ID (default: root)")
    _provider_arguments(resume)
    resume.add_argument(
        "--retry-failed",
        action="store_true",
        help="start a failed stage again as a fresh run instead of refusing",
    )
    resume.add_argument("--json", dest="json_output", action="store_true")

    child = subparsers.add_parser("add-child", help="add an independent child below any node")
    child.add_argument("project_id")
    child.add_argument("--parent-node", dest="parent_node_id", help="parent node (default: root)")
    child.add_argument("--node-id", dest="child_node_id", help="optional stable child node ID")
    child.add_argument("--link-id", help="optional stable link ID")
    child.add_argument("--order", type=int, help="positive output order; default: append")
    child.add_argument("--title", required=True)
    child_premise = child.add_mutually_exclusive_group(required=True)
    child_premise.add_argument("--premise")
    child_premise.add_argument("--premise-file")
    child.add_argument("--language", default="ja")
    child.add_argument("--chapters", type=int, default=3)
    child.add_argument("--target-chars", type=int, default=1600)
    child.add_argument("--form", default="novel")
    child.add_argument(
        "--knowledge-character",
        help="filter ancestor facts to this character ID's canon knows list",
    )
    child.add_argument("--json", dest="json_output", action="store_true")

    adopt = subparsers.add_parser(
        "adopt-child", help="explicitly adopt a child's current completed revision",
    )
    adopt.add_argument("project_id")
    adopt.add_argument("link_id")
    adopt.add_argument("--json", dest="json_output", action="store_true")

    render = subparsers.add_parser("render", help="render one node's current completed draft")
    render.add_argument("project_id")
    render.add_argument("--node", dest="node_id", help="descendant node ID (default: root)")
    render.add_argument("--out", help="optional external UTF-8 markdown output")
    render.add_argument("--json", dest="json_output", action="store_true")

    compose = subparsers.add_parser(
        "compose", help="recursively compile a node and its pinned descendants",
    )
    compose.add_argument("project_id")
    compose.add_argument("--node", dest="node_id", help="subtree root (default: project root)")
    compose.add_argument("--out", help="optional additional external UTF-8 markdown output")
    compose.add_argument(
        "--partial", action="store_true",
        help="keep compiling when a child has no pinned draft (omitted explicitly)",
    )
    compose.add_argument("--json", dest="json_output", action="store_true")

    pending = subparsers.add_parser("pending", help="list operator responses still needed")
    pending.add_argument("project_id")
    pending.add_argument("--node", dest="node_id", help="subtree root (default: root and all descendants)")
    pending.add_argument("--json", dest="json_output", action="store_true")

    relay = subparsers.add_parser(
        "relay", help="hand prompts to a chat session and take the answers back",
    )
    relay_commands = relay.add_subparsers(dest="relay_command", required=True)
    relay_export = relay_commands.add_parser(
        "export", help="write PROMPTS.md and one file per unanswered request",
    )
    relay_export.add_argument("project_id")
    relay_export.add_argument(
        "--out", help="default: the project's relay directory itself (PROMPTS.md, index.json)",
    )
    relay_export.add_argument("--json", dest="json_output", action="store_true")
    relay_status = relay_commands.add_parser(
        "status", help="show how many prompts are answered and which are pending",
    )
    relay_status.add_argument("project_id")
    relay_status.add_argument("--json", dest="json_output", action="store_true")
    relay_ingest = relay_commands.add_parser(
        "ingest", help="read pasted <<<ANSWER tag>>> blocks into responses/",
    )
    relay_ingest.add_argument("project_id")
    relay_ingest.add_argument("--file", required=True, help="UTF-8 text file with the answers")
    relay_ingest.add_argument("--model", default="arena-agent-mode")
    relay_ingest.add_argument("--model-version", help="default: unversioned-<today>")
    relay_ingest.add_argument(
        "--map", action="append", default=[], metavar="FROM=TO",
        help="accept a mistyped tag explicitly, e.g. --map ch02=1F3A9C2D",
    )
    relay_ingest.add_argument("--json", dest="json_output", action="store_true")
    relay_submit = relay_commands.add_parser(
        "submit",
        help="ingest an answer file and continue the work in one step",
    )
    relay_submit.add_argument("project_id")
    relay_submit.add_argument("--file", required=True, help="UTF-8 text file with the answers")
    relay_submit.add_argument("--node", dest="node_id", help="descendant node ID (default: root)")
    relay_submit.add_argument("--model-version", help="default: unversioned-<today>")
    relay_submit.add_argument(
        "--map", action="append", default=[], metavar="FROM=TO",
        help="accept a mistyped tag explicitly, e.g. --map ch02=1F3A9C2D",
    )
    relay_submit.add_argument(
        "--retry-failed", action="store_true",
        help="retry a failed stage as a fresh run instead of refusing",
    )
    _generation_arguments(relay_submit)
    relay_submit.add_argument("--json", dest="json_output", action="store_true")

    bundle = subparsers.add_parser("bundle", help="export, verify, or restore replay sources")
    bundle_commands = bundle.add_subparsers(dest="bundle_command", required=True)
    bundle_export = bundle_commands.add_parser("export", help="export a project replay bundle")
    bundle_export.add_argument("project_id")
    bundle_export.add_argument("--out", required=True, help="new external bundle directory")
    bundle_export.add_argument("--json", dest="json_output", action="store_true")
    bundle_verify = bundle_commands.add_parser("verify", help="verify bundle hashes and records")
    bundle_verify.add_argument("bundle_dir")
    bundle_verify.add_argument("--json", dest="json_output", action="store_true")
    bundle_restore = bundle_commands.add_parser("restore", help="restore a bundle below --root")
    bundle_restore.add_argument("bundle_dir")
    bundle_restore.add_argument("--json", dest="json_output", action="store_true")

    world = subparsers.add_parser(
        "world", help="persist time, space, culture, bindings, and explicit canon",
    )
    world_commands = world.add_subparsers(dest="world_command", required=True)
    world_add = world_commands.add_parser("add", help="add one immutable world record")
    world_add.add_argument("project_id")
    world_add.add_argument("kind", choices=[
        "timeframe", "time-span", "time-conversion", "region", "spatial-relation",
        "culture", "culture-state", "culture-relation", "canon", "binding",
    ])
    world_add.add_argument("--file", required=True, help="UTF-8 JSON record; metadata is filled in")
    world_add.add_argument("--json", dest="json_output", action="store_true")
    world_status = world_commands.add_parser("status", help="inspect world records and stale canon")
    world_status.add_argument("project_id")
    world_status.add_argument("--node", dest="node_id", help="binding node (default: root)")
    world_status.add_argument("--json", dest="json_output", action="store_true")
    world_bind = world_commands.add_parser("bind", help="bind a node revision to explicit world IDs")
    world_bind.add_argument("project_id")
    world_bind.add_argument("--node", dest="node_id", help="node ID (default: root)")
    world_bind.add_argument("--time-span", action="append", default=[], dest="time_span_ids")
    world_bind.add_argument("--region", action="append", default=[], dest="region_ids")
    world_bind.add_argument("--culture-state", action="append", default=[], dest="culture_state_ids")
    world_bind.add_argument("--binding-id")
    world_bind.add_argument("--json", dest="json_output", action="store_true")
    world_adopt = world_commands.add_parser(
        "adopt-canon", help="adopt a value from a completed node's pinned plan JSON",
    )
    world_adopt.add_argument("project_id")
    world_adopt.add_argument("--node", dest="node_id", help="source node (default: root)")
    world_adopt.add_argument("--artifact", required=True, help="project-relative pinned plan JSON path")
    world_adopt.add_argument("--pointer", default="", help="RFC 6901 JSON pointer (default: whole document)")
    world_adopt.add_argument("--scope", required=True, choices=[
        "global", "timeframe", "region", "culture", "work", "node",
    ])
    world_adopt.add_argument("--scope-id", help="required except for global scope")
    world_adopt.add_argument("--subject", required=True)
    world_adopt.add_argument("--valid-span")
    world_adopt.add_argument("--supersedes")
    world_adopt.add_argument("--entry-id")
    world_adopt.add_argument("--json", dest="json_output", action="store_true")
    world_profile = world_commands.add_parser(
        "add-profile", help="add a chronicle, gazetteer, culture, or collection profile",
    )
    world_profile.add_argument("project_id")
    world_profile.add_argument("--file", required=True, help="UTF-8 compilation profile JSON")
    world_profile.add_argument("--json", dest="json_output", action="store_true")
    world_profiles = world_commands.add_parser("profiles", help="list compilation profiles")
    world_profiles.add_argument("project_id")
    world_profiles.add_argument("--json", dest="json_output", action="store_true")
    world_compile = world_commands.add_parser(
        "compile", help="compile a deterministic world or work-collection view",
    )
    world_compile.add_argument("project_id")
    world_compile.add_argument("profile_id")
    world_compile.add_argument("--out", help="optional additional external UTF-8 markdown output")
    world_compile.add_argument("--json", dest="json_output", action="store_true")

    doctor = subparsers.add_parser(
        "doctor",
        help="inspect project/world/artifact integrity plus pending and stale references",
    )
    doctor.add_argument("project_id")
    doctor.add_argument("--json", dest="json_output", action="store_true")

    context = subparsers.add_parser(
        "context", help="inspect a node's ContextPacket without generating anything",
    )
    context_commands = context.add_subparsers(dest="context_command", required=True)
    context_show = context_commands.add_parser(
        "show", help="show the current or a recorded ContextPacket",
    )
    context_show.add_argument("project_id")
    context_show.add_argument("--node", dest="node_id", help="node ID (default: root)")
    context_show.add_argument(
        "--run", dest="run_id", help="read the packet recorded in this run's project-input",
    )
    context_show.add_argument(
        "--stage", choices=list(DEFAULT_STAGES),
        help="read the packet recorded by this stage of the current revision",
    )
    context_show.add_argument(
        "--out", help="optional external UTF-8 JSON file for the packet document",
    )
    context_show.add_argument("--json", dest="json_output", action="store_true")

    diff = subparsers.add_parser(
        "diff",
        help="compare two ContextPackets or two compilations record by record",
    )
    diff.add_argument("project_id")
    diff.add_argument(
        "--left", required=True,
        help="current | stage:<stage> | run:<run_id> | "
             "compile:<profile_id>[@<content_version>]",
    )
    diff.add_argument("--right", required=True, help="same forms as --left")
    diff.add_argument("--node", dest="node_id", help="node for current/stage sides")
    diff.add_argument("--json", dest="json_output", action="store_true")

    status = subparsers.add_parser("status", help="load and summarize an existing project")
    status.add_argument("project_id")
    status.add_argument("--node", dest="node_id", help="descendant node ID (default: root)")
    status.add_argument("--json", dest="json_output", action="store_true")
    return parser.parse_args(argv)


def _work_options(args: argparse.Namespace) -> dict:
    if not args.knowledge_character:
        return {}
    return {"context_knowledge": {"character_id": args.knowledge_character}}


class _UnusedProvider:
    """A provider for operations that regenerate nothing at all."""

    name = "none"
    model = None
    model_version = None

    def generate(self, request):  # pragma: no cover - guarded by the CLI
        raise ProviderError(
            "this operation needs a model: name a chapter or design document "
            "and pass --provider"
        )


PROVIDERS = ("arena", "command", "scripted")

#: Directory below a project that holds the Arena relay (requests/responses).
RELAY_SUBDIR = "relay"


class _ArenaRelayProvider(CommandProvider):
    """``chat_operator.py`` bound to one project's relay directory.

    The provider name is recorded in each run manifest, so a later reader can
    tell a relayed response from a scripted fixture or an external model.
    """

    name = "arena-relay"


def _relay_directory(store: ProjectStore, project_id: str, args) -> Path:
    override = getattr(args, "relay_dir", None)
    if override:
        return Path(override).expanduser()
    return store.project_dir(project_id) / RELAY_SUBDIR


def _inferred_provider(args: argparse.Namespace) -> str | None:
    """The provider an omitted ``--provider`` means.

    ``--script`` and ``--command`` still select their provider on their own, so
    a command line written before the relay existed keeps working.  Otherwise
    the standard flow applies: the project's relay directory.
    """
    if getattr(args, "provider", None):
        return args.provider
    if getattr(args, "script", None):
        return "scripted"
    if getattr(args, "provider_command", None):
        return "command"
    return None


def _make_provider(
    args: argparse.Namespace, store: ProjectStore | None = None, *,
    allow_none: bool = False,
):
    name = _inferred_provider(args)
    if allow_none and name is None:
        return _UnusedProvider()
    name = name or "arena"
    if name == "scripted":
        if not args.script:
            raise ProviderError("--provider scripted requires --script")
        return ScriptedProvider(
            load_scripted_responses(args.script), model=args.model or "scripted-fixture",
        )
    if name == "arena":
        if store is None:
            raise ProviderError("--provider arena needs the project store")
        directory = _relay_directory(store, args.project_id, args)
        command = shlex.join([
            sys.executable, str(REPO_ROOT / "scripts" / "chat_operator.py"),
            "--dir", str(directory),
        ])
        return _ArenaRelayProvider(command, model=args.model or "arena-agent-mode")
    if not args.provider_command:
        raise ProviderError("--provider command requires --command")
    return CommandProvider(args.provider_command, model=args.model or "external")


def _export_relay(project_id: str, directory: Path, out: Path | None = None) -> dict:
    """Write PROMPTS.md for the unanswered requests of one project."""
    summary = relay_prompts.export(directory, out or directory)
    summary["project_id"] = project_id
    summary["directory"] = str(directory)
    return summary


#: A stage can fail because the interpreter that runs this script lacks an
#: optional dependency (PyYAML is needed once the design checks run).  Retrying
#: the stage cannot fix that, so say what can.
MISSING_DEPENDENCY_HINT = (
    "This is a missing Python dependency, not a problem with the answer. "
    "Run the same command with the project interpreter "
    "(`.venv/bin/python scripts/story_project.py ...`) after `make setup`."
)

#: What a retry actually does: the failed run is kept, the stage starts again,
#: and prompts that are byte-identical reuse the answers stored in the relay
#: (the relay is keyed by prompt, not by attempt).  A changed prompt asks again.
RETRY_NOTE = (
    "A retry makes a new attempt and keeps the failed run. Prompts that are "
    "unchanged reuse the answers already stored in the relay; a changed prompt "
    "is asked again."
)

#: One relay round is: answer the request that is waiting, ingest it, resume.
#: The report below is the single place that says where the round stands.
RELAY_ROUND_SCHEMA = "asc-relay-round-v1"

#: Pipeline order of the purposes a request can carry.
_PURPOSE_STAGE = {"plan": 0, "design": 1, "draft": 2}


def _cli_base(store: ProjectStore) -> str:
    base = "python3 scripts/story_project.py"
    default_root = (REPO_ROOT / "runs" / "projects").resolve()
    if store.root.resolve() != default_root:
        base += f" --root {store.root}"
    return base


def _purpose_stage(purpose: str | None) -> str:
    name = str(purpose or "").split(":", 1)[0]
    return name or "unknown"


def _stage_rank(purpose: str | None) -> tuple[int, str]:
    stage = _purpose_stage(purpose)
    return (_PURPOSE_STAGE.get(stage, 9), str(purpose or ""))


def _relay_round(
    store: ProjectStore, project_id: str, directory: Path, *,
    node_id: str | None = None,
) -> dict:
    """Where one relay round stands, and the one next thing to do.

    The report is deliberately small: state, how many answers are stored, the
    request that is waiting (if any), and the command to run next.  It never
    regenerates an answered request and never invents a prompt: the next
    request only exists once the previous stage has accepted its answer.
    """
    requests_dir = directory / "requests"
    responses_dir = directory / "responses"
    status = store.status(project_id, node_id)
    pending = relay_prompts.pending(directory) if requests_dir.is_dir() else []
    pending = sorted(pending, key=lambda row: _stage_rank(row["purpose"]))
    requests = relay_prompts.all_requests(directory) if requests_dir.is_dir() else []
    answered = len(list(responses_dir.glob("*.json"))) if responses_dir.is_dir() else 0
    base = _cli_base(store)
    node_option = (
        f" --node {status['node_id']}"
        if status.get("node_id") != status.get("root_node_id") else ""
    )

    next_request = None
    if pending:
        row = pending[0]
        response_path = responses_dir / f"{row['key']}.json"
        request_path = requests_dir / f"{row['key']}.json"
        next_request = {
            "tag": row["tag"],
            "key": row["key"],
            "purpose": row["purpose"],
            "stage": _purpose_stage(row["purpose"]),
            "request_path": str(request_path),
            "response_path": str(response_path),
            "response_ready": response_path.is_file(),
        }

    manuscript = _manuscript_hint(status)
    work_state = status.get("work", {}).get("state")
    if work_state == "failed":
        next_command = f"{base} resume {project_id}{node_option} --retry-failed"
    elif next_request is not None:
        next_command = (
            f"{base} relay submit {project_id}{node_option} --file <answers.txt>"
        )
    elif work_state == "waiting_response":
        # The prompt was recorded but the response file is gone or was renamed:
        # resume finds out, it never makes up an answer.
        next_command = f"{base} resume {project_id}{node_option}"
    elif manuscript is not None:
        next_command = manuscript[0]
    else:
        next_command = f"{base} status {project_id}{node_option}"

    return {
        "schema": RELAY_ROUND_SCHEMA,
        "project_id": project_id,
        "node_id": status.get("node_id"),
        "directory": str(directory),
        "state": status.get("work", {}).get("state", status.get("state")),
        "stages": status.get("work", {}).get("stages"),
        "requests": len(requests),
        "answered": answered,
        "pending_count": len(pending),
        "next": next_request,
        "next_command": next_command,
        "manuscript": (
            {"path": manuscript[1], "command": manuscript[0],
             "written": Path(manuscript[1]).is_file()}
            if manuscript is not None else None
        ),
        "actions": list(status.get("next_actions") or ()),
    }


def _print_round(report: dict) -> None:
    stages = report.get("stages") or {}
    detail = ", ".join(f"{name}={value}" for name, value in stages.items()) or "unknown"
    print(f"Project: {report['project_id']} ({report['state']})")
    print(f"Stages: {detail}")
    print(
        f"Relay: {report['answered']} answered / {report['pending_count']} pending "
        f"/ {report['requests']} request(s) recorded"
    )
    print(f"Relay directory: {report['directory']}")
    if report["next"] is not None:
        row = report["next"]
        # ``purpose`` already carries its stage (``draft:ch02``); repeating the
        # stage here printed "draft: draft:ch02" during the U-03 dogfood run.
        print(f"Next request: tag {row['tag']} ({row['purpose']})")
        print(f"  request:  {row['request_path']}")
        print(f"  response: {row['response_path']}")
        if row["response_ready"]:
            print("  the response file already exists; submit it to continue")
    manuscript = report.get("manuscript")
    if manuscript is not None:
        label = "" if manuscript["written"] else " (not written yet)"
        print(f"Manuscript: {manuscript['path']}{label}")
    print(f"Next: {report['next_command']}")


def _relay_line(status: dict) -> str | None:
    """One line about the relay, or None when the standard flow was not used."""
    directory = Path(status["project_dir"]) / RELAY_SUBDIR
    requests = directory / "requests"
    if not requests.is_dir():
        return None
    total = len(list(requests.glob("*.json")))
    responses = directory / "responses"
    answered = len(list(responses.glob("*.json"))) if responses.is_dir() else 0
    pending = total - answered
    if pending:
        return (
            f"Relay: {answered} answered / {pending} pending "
            f"(next: relay submit {status['project_id']} --file <answers.txt>)"
        )
    return f"Relay: {answered} answered / 0 pending ({directory})"


def _manuscript_hint(status: dict) -> tuple[str, str] | None:
    """The rendered-manuscript path and the command that writes it."""
    draft = (status.get("checkpoints") or {}).get("draft")
    if not draft or draft.get("status") != "done":
        return None
    directory = Path(status["project_dir"])
    path = directory / "manuscript.md"
    node_option = ""
    if status.get("node_id") != status.get("root_node_id"):
        node_option = f" --node {status['node_id']}"
    command = (
        f"python3 scripts/story_project.py --root {directory.parent} "
        f"render {status['project_id']}{node_option} --out {path}"
    )
    return command, str(path)


def _print_human(status: dict, *, created: bool) -> None:
    heading = "Created project" if created else "Project"
    print(f"{heading}: {status['project_id']}")
    print(f"Title: {status['title']}")
    print(f"State: {status['state']}")
    print(f"Root node: {status['root_node_id']}")
    print(f"Selected node: {status.get('node_id', status['root_node_id'])}")
    print(f"Current revision: {status['current_revision_id']}")
    print(f"Spec SHA-256: {status['spec_sha256']}")
    print(
        f"Artifact refs: {len(status.get('artifact_refs', []))}; "
        f"runs: {len(status['runs'])}"
    )
    if status.get("attempt_id"):
        print(f"Attempt: {status['attempt_id']}")
    work = status.get("work") or {}
    failed = list(work.get("failed_stages") or ())
    if failed:
        print(
            f"Failed stages: {', '.join(failed)} "
            "(resume --retry-failed starts them again)"
        )
    retried = [
        f"{name}<-{row['retry_of']}"
        for name, row in status.get("checkpoints", {}).items() if row.get("retry_of")
    ]
    if retried:
        print(f"Retried stages: {', '.join(retried)}")
    if work:
        _print_work(work)
    else:
        print(f"Pending responses: {len(status.get('pending', []))}")
    relay = _relay_line(status)
    if relay is not None:
        print(relay)
    _print_actions(list(status.get("next_actions") or ()))
    hint = _manuscript_hint(status)
    if hint is not None:
        command, path = hint
        if Path(path).is_file():
            print(f"Manuscript: {path}")
        else:
            print("Manuscript: not written yet")
        print(f"  write it: {command}")
    if status.get("links"):
        print(f"Child links: {len(status['links'])}")
    print(f"Directory: {status['project_dir']}")


def _print_pending(status: dict) -> None:
    rows = status.get("pending", [])
    if not rows:
        print(f"No pending responses for {status['project_id']}")
        return
    for row in rows:
        print(
            f"{row['key']}: project={row['project_id']} node={row['node_id']} "
            f"stage={row['stage']} ready={row['response_ready']}"
        )
        print(f"  response: {row['response_path']}")
        if row.get("request_path"):
            print(f"  request: {row['request_path']}")
    print(
        "  export the prompts: python3 scripts/story_project.py "
        f"relay export {status['project_id']}"
    )


def _print_bundle(report: dict) -> None:
    print(f"Project: {report['project_id']}")
    print(f"Files: {report['file_count']}")
    print(f"Manifest SHA-256: {report['manifest_sha256']}")
    if report.get("bundle_dir"):
        print(f"Bundle: {report['bundle_dir']}")
    if report.get("project_dir"):
        print(f"Restored: {report['project_dir']}")
    print("Verified: yes")


def _print_actions(actions: list[dict]) -> None:
    if not actions:
        return
    print("Next:")
    for action in actions:
        print(f"  {action['command']}")
        print(f"    {action['reason']}")


def _print_work(work: dict) -> None:
    def count(value) -> str:
        return "not inspected" if value is None else str(value)

    stages = work.get("stages")
    label = "node" if work.get("scope") == "node" else "project"
    scope = f"{label} {work['node_id']}" if work.get("node_id") else label
    detail = ", ".join(
        f"{name}={value}" for name, value in (stages or {}).items()
    ) or "stages unknown"
    pending = work["pending"]
    stale = work["stale"]
    runs = work["runs"]
    print(f"Work ({scope}): state={work['state']}; {detail}")
    print(
        f"  pending: {pending['count']} "
        f"(ready {pending['ready']}, awaiting reply {pending['waiting_for_reply']}); "
        f"runs: {count(runs['count'])} (interrupted {count(runs['interrupted'])})"
    )
    print(
        f"  stale: links={count(stale['links'])}, canon={count(stale['canon'])}, "
        f"bindings={count(stale['bindings'])}"
    )
    print(f"  inspected: {', '.join(work['inspected'])}")


def _print_doctor(report: dict) -> None:
    summary = report["summary"]
    state = "ok" if report["ok"] else "errors found"
    print(f"Project: {report['project_id']} ({state})")
    print(
        f"Nodes: {summary['nodes']}; findings: {summary['findings']} "
        f"(errors={summary['errors']}, warnings={summary['warnings']}, "
        f"info={summary['info']})"
    )
    checks = ", ".join(
        f"{check['name']}={check['status']}" for check in report["checks"]
    )
    print(f"Checks: {checks}")
    pending = report["pending"]
    if pending:
        print(f"Pending responses: {len(pending)}")
    for row in pending:
        print(
            f"  {row['node_id']} stage={row['stage']} ready={row['response_ready']} "
            f"key={row['key']}"
        )
        if row.get("response_path"):
            print(f"    response: {row['response_path']}")
    stale = report["stale"]
    if stale.get("total"):
        print(
            f"Stale items: links={len(stale['links'])}, canon={len(stale['canon'])}, "
            f"bindings={len(stale['bindings'])}"
        )
    for row in stale["links"]:
        print(
            f"  link {row['link_id']} ({row['child_node_id']}) pinned="
            f"{row['pinned_revision_id']} current={row['current_child_revision_id']}"
        )
    for row in stale["canon"]:
        print(
            f"  canon {row['entry_id']} ({row['subject']}) source="
            f"{row['source_revision_id']} current={row['current_source_revision_id']}"
        )
    for row in stale["bindings"]:
        print(
            f"  binding {row['binding_id']} ({row['node_id']}) revision="
            f"{row['revision_id']} current={row['current_revision_id']}"
        )
    for finding in report["findings"]:
        node = f" node={finding['node_id']}" if finding.get("node_id") else ""
        path = f" path={finding['path']}" if finding.get("path") else ""
        print(
            f"  [{finding['severity']}] {finding['code']}{node}{path}: "
            f"{finding['message']}"
        )
    if report.get("work"):
        _print_work(report["work"])
    _print_actions(list(report.get("next_actions") or ()))
    print(f"Directory: {report['project_dir']}")


def _print_context(view: dict) -> None:
    summary = view["summary"]
    print(f"Project: {view['project_id']}")
    print(f"Node: {view['node_id']}")
    print(f"Revision: {view['revision_id']}")
    if not view.get("same_revision", True):
        print(
            f"Current revision: {view['current_revision_id']} "
            "(the selected packet belongs to an older revision)"
        )
    print(f"Mode: {view['mode']}")
    if view.get("run_id"):
        print(f"Run: {view['run_id']} (stage={view.get('stage')})")
    if summary.get("kind") is None:
        print("Packet: none (no ancestors and no world binding)")
    else:
        print(
            f"Packet: {summary['kind']}; {summary['packet_bytes']} bytes; "
            f"sha256={summary['packet_sha256']}"
        )
        print(f"Ancestors: {len(summary['ancestors'])}")
        for ancestor in summary["ancestors"]:
            print(
                f"  {ancestor['node_id']} rev={ancestor['revision_id']} "
                f"state={ancestor['state']} canon_bytes={ancestor['canon_bytes']} "
                f"chapters={ancestor['chapter_count']}"
            )
        world = summary.get("world")
        if world is None:
            print("World: none")
        else:
            print(
                f"World: binding={world['binding_id']} "
                f"revision={world['binding_revision_id']}"
            )
            print("  overlay: " + " -> ".join(world["overlay_order"]))
            print(
                f"  canon={world['canon_entries']} omitted="
                f"{world['omitted_canon_count']} references={world['reference_count']}"
            )
            for reference in world["references"]:
                print(
                    f"  {reference['record_type']} {reference['id']} "
                    f"{reference['content_version']}"
                )
        if summary.get("knowledge"):
            print(f"Knowledge: {json.dumps(summary['knowledge'], ensure_ascii=False)}")
    if view["recorded_packets"]:
        print(
            f"Recorded packets for revision {view['revision_id']}: "
            f"{len(view['recorded_packets'])}"
        )
        for row in view["recorded_packets"]:
            print(
                f"  {row['run_id']} stage={row['stage']} "
                f"sha256={row['packet_sha256']} bytes={row['packet_bytes']}"
            )
    drift = view.get("drift")
    if drift is not None:
        print(
            "Recorded vs current: "
            + ("differs" if drift["differs"] else "identical")
        )
        if drift["differs"]:
            print("  " + json.dumps(drift["differences"], ensure_ascii=False))
    elif view["mode"] == "recorded" and not view.get("same_revision", True):
        print("Recorded vs current: skipped (different revisions)")
    if view.get("external_out"):
        print(f"Packet written: {view['external_out']}")


def _print_diff(report: dict) -> None:
    def side(row: dict) -> str:
        identity = row["identity"]
        where = identity.get("run_id") or identity.get("stage")
        if row["source"] == "compilation":
            where = (
                f"profile={identity.get('profile_id')} "
                f"version={identity.get('content_version')}"
            )
        elif where is None:
            where = identity.get("revision_id")
        return (
            f"{row['spec']} ({row['source']}; {where}; "
            f"records={row['record_count']} sha256={row['document_sha256'][:16]})"
        )

    print(f"Project: {report['project_id']}")
    print(f"Left:  {side(report['left'])}")
    print(f"Right: {side(report['right'])}")
    print("Identical: " + ("yes" if report["identical"] else "no"))
    counts = report["counts"]
    print(
        f"Records: added={counts['added']} removed={counts['removed']} "
        f"changed={counts['changed']} unchanged={counts['unchanged']}"
    )
    for row in report["records"]["added"]:
        print(
            f"  + {row['scope']} {row['record_type']} {row['id']} "
            f"{row['content_version']}"
        )
    for row in report["records"]["removed"]:
        print(
            f"  - {row['scope']} {row['record_type']} {row['id']} "
            f"{row['content_version']}"
        )
    for row in report["records"]["changed"]:
        print(
            f"  ~ {row['scope']} {row['record_type']} {row['id']} "
            f"{row['left_content_version']} -> {row['right_content_version']}"
        )
    for key, change in sorted(report["attributes"].items()):
        print(f"  ! {key}: {change['left']} -> {change['right']}")
    for node, change in sorted(report["ancestors"].items()):
        print(f"  ! ancestor {node}: {change['left'] or 'none'} -> {change['right'] or 'none'}")


def _print_world(status: dict) -> None:
    print(f"Project: {status['project_id']}")
    print(f"Selected node: {status['selected_node_id']}")
    print(f"Selected revision: {status['selected_revision_id']}")
    print("World records: " + ", ".join(
        f"{kind}={count}" for kind, count in status["counts"].items()
    ))
    print(f"Current node binding: {'yes' if status['selected_binding'] else 'no'}")
    current = [row for row in status["canon_entries"] if row["current"]]
    stale = sum(1 for row in current if row["stale"])
    print(f"Current canon: {len(current)}; stale: {stale}")


def _parse_tag_map(entries: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for entry in entries:
        if "=" not in entry:
            raise ProjectError(f"--map expects FROM=TO, got {entry!r}")
        source, target = entry.split("=", 1)
        mapping[source.strip()] = target.strip()
    return mapping


def _ingest_answers(args, directory: Path) -> dict:
    path = Path(args.file).expanduser()
    if not path.is_file():
        raise ProjectError(f"no such answer file: {path}")
    version = args.model_version or datetime.now(timezone.utc).strftime(
        "unversioned-%Y-%m-%d"
    )
    summary = relay_prompts.ingest(
        directory, path.read_text(encoding="utf-8"),
        model=getattr(args, "model", None) or "arena-agent-mode",
        model_version=version, tag_map=_parse_tag_map(args.map),
    )
    return summary


def _print_ingest(summary: dict) -> None:
    print(f"Answers written: {len(summary['written'])}")
    for key in summary["written"]:
        print(f"  {key}")
    for row in summary["errors"]:
        print(f"error block (tag {row['tag']}): {row['reason']}")
    for row in summary["rejected"]:
        print(f"rejected (tag {row['tag']}): {row['reason']}")
    print(f"Still pending: {summary['still_pending']}")


def _run_or_resume(store: ProjectStore, args, *, retry_failed: bool = False):
    """Start a new revision, or continue the interrupted one.

    A run that has not started a stage yet is started; anything else resumes,
    so a submitted answer is never the reason a finished stage runs again.
    """
    node_id = getattr(args, "node_id", None)
    state = store.status(args.project_id, node_id)["work"]["state"]
    provider = _make_provider(args, store)
    runner = ProjectRunner(store)
    if state == "not_started":
        return runner.run(
            args.project_id, provider,
            seed=getattr(args, "seed", 0),
            temperature=getattr(args, "temperature", None),
            node_id=node_id,
        )
    return runner.resume(
        args.project_id, provider, node_id=node_id,
        retry_failed=retry_failed,
    )


def _relay_command(args: argparse.Namespace, store: ProjectStore) -> int:
    """``relay export|status|ingest|submit``: one round, one report.

    ``submit`` is the whole round after the answers are written: ingest them and
    continue the work.  It refuses to touch a complete work and points at
    ``resume --retry-failed`` instead of collecting answers for a failed stage,
    so an answered request is never re-asked or overwritten by habit.
    """
    directory = _relay_directory(store, args.project_id, args)
    node_id = getattr(args, "node_id", None)
    command = args.relay_command
    payload: dict = {}

    def current() -> dict:
        return _relay_round(store, args.project_id, directory, node_id=node_id)

    def finish(
        *, ingest: bool = False, pending: BaseException | None = None,
        failure: BaseException | None = None, code: int | None = None,
    ) -> int:
        report = current()
        payload["round"] = report
        if code is None:
            if report["state"] == "failed":
                code = 2
            else:
                code = 3 if report["pending_count"] else 0
        _emit_round(
            args, payload, ingest=ingest, store=store,
            pending=pending, failure=failure,
        )
        return code

    if command == "status":
        report = current()
        if getattr(args, "json_output", False):
            print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        else:
            _print_round(report)
        if report["state"] == "failed":
            return 2
        return 3 if report["pending_count"] else 0

    if command == "export":
        out = Path(args.out).expanduser() if getattr(args, "out", None) else None
        payload["export"] = _export_relay(args.project_id, directory, out)
        return finish(code=0)

    before = current()
    retry_failed = bool(getattr(args, "retry_failed", False))
    if command == "submit" and before["state"] == "complete":
        payload["skipped"] = (
            "the work is already complete; nothing was ingested. "
            "Use continue or revise to make a new revision."
        )
        return finish(code=0)
    if command == "submit" and before["state"] == "failed" and not retry_failed:
        payload["skipped"] = (
            "a stage is failed; retrying it makes a new attempt that reuses the "
            "answers already stored for unchanged prompts, so new answers would "
            "be ignored. Rerun with --retry-failed instead."
        )
        return finish(code=2)

    if (directory / "requests").is_dir():
        payload["ingest"] = _ingest_answers(args, directory)
    else:
        payload["ingest"] = {
            "written": [], "errors": [], "rejected": [], "remapped": [],
            "still_pending": 0,
            "note": "no request has been recorded yet; run the project first",
        }
    rejected = payload["ingest"]["rejected"] or payload["ingest"]["errors"]
    if rejected:
        # Nothing was generated: the paste has to be fixed first.
        return finish(ingest=True, code=1)
    if command == "ingest":
        return finish(ingest=True)

    if not payload["ingest"]["written"] and before["state"] != "failed":
        ready = (before.get("next") or {}).get("response_ready")
        payload["skipped"] = (
            "the response file for the waiting request already exists; "
            "nothing was ingested"
            if ready else "the answer file had no block for a waiting request"
        )
        return finish(ingest=True, code=3)
    try:
        result = _run_or_resume(store, args, retry_failed=retry_failed)
        payload["result"] = {
            "state": result.status["work"]["state"],
            "attempt_id": result.attempt_id,
            "stages": result.status["work"]["stages"],
        }
    except ProjectRunPending as exc:
        payload["pending"] = {
            "key": exc.pending.get("key"), "purpose": exc.pending.get("purpose"),
        }
        # Keep the paste-ready prompts in step with the next request.
        _export_relay(args.project_id, directory)
        return finish(ingest=True, pending=exc, code=3)
    except ProjectRunError as exc:
        payload["error"] = str(exc)
        return finish(ingest=True, failure=exc, code=2)
    if payload["result"]["state"] != "complete":
        _export_relay(args.project_id, directory)
    return finish(ingest=True)


def _emit_round(
    args: argparse.Namespace, payload: dict, *, ingest: bool,
    store: ProjectStore,
    pending: BaseException | None = None, failure: BaseException | None = None,
) -> None:
    if getattr(args, "json_output", False):
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return
    if payload.get("skipped"):
        print(f"Skipped: {payload['skipped']}")
        if ingest:
            print("")
    if ingest:
        _print_ingest(payload["ingest"])
        print("")
    _print_round(payload["round"])
    if pending is not None:
        print(f"Waiting: {pending}")
    if failure is not None:
        print(f"Failed: {failure}")
        if "No module named" in str(failure):
            print(MISSING_DEPENDENCY_HINT)
        else:
            print(RETRY_NOTE)
    if payload["round"]["state"] == "complete":
        manuscript = payload["round"].get("manuscript")
        if manuscript is not None:
            print("Complete. Read the manuscript with the Next command above.")
    elif any(
        row.get("action") == "resume --retry-failed"
        for row in payload["round"].get("actions") or ()
    ):
        for row in payload["round"]["actions"]:
            if row.get("action") == "resume --retry-failed":
                print(f"Retry: {row['command']}")
                break


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    store = ProjectStore(args.root)
    try:
        if args.command == "init":
            premise = args.premise
            if args.premise_file:
                premise = Path(args.premise_file).read_text(encoding="utf-8")
            spec = WorkSpec(
                title=args.title,
                premise=premise,
                language=args.language,
                chapter_count=args.chapters,
                target_chars_per_chapter=args.target_chars,
                form=args.form,
                options=_work_options(args),
            )
            snapshot = store.create_project(spec, project_id=args.project_id)
            status = store.status(snapshot.project.id)
            if args.json_output:
                print(json.dumps(status, ensure_ascii=False, sort_keys=True))
            else:
                _print_human(status, created=True)
            return 0

        if args.command == "add-child":
            premise = args.premise
            if args.premise_file:
                premise = Path(args.premise_file).read_text(encoding="utf-8")
            link = store.create_child(
                args.project_id,
                WorkSpec(
                    title=args.title, premise=premise, language=args.language,
                    chapter_count=args.chapters,
                    target_chars_per_chapter=args.target_chars, form=args.form,
                    options=_work_options(args),
                ),
                parent_node_id=args.parent_node_id, order=args.order,
                child_node_id=args.child_node_id, link_id=args.link_id,
            )
            report = {
                "project_id": args.project_id,
                "link": link.to_dict(),
                "child": store.status(args.project_id, link.child_node_id),
                "parent": store.status(args.project_id),
            }
            if args.json_output:
                print(json.dumps(report, ensure_ascii=False, sort_keys=True))
            else:
                print(f"Child node: {link.child_node_id}")
                print(f"Link: {link.id}; order: {link.order}")
                print(f"Pinned revision: {link.child_revision_id}")
            return 0

        if args.command == "adopt-child":
            link = store.adopt_child(args.project_id, args.link_id)
            report = {
                "project_id": args.project_id,
                "link": link.to_dict(),
                "parent": store.status(args.project_id),
            }
            if args.json_output:
                print(json.dumps(report, ensure_ascii=False, sort_keys=True))
            else:
                print(f"Adopted {link.child_revision_id} for {link.child_node_id}")
            return 0

        if args.command in {"render", "compose"}:
            composer = ProjectComposer(store)
            result = (
                composer.render(args.project_id, args.node_id)
                if args.command == "render"
                else composer.compose(
                    args.project_id, args.node_id,
                    partial=getattr(args, "partial", False),
                )
            )
            if args.out:
                output = Path(args.out).expanduser()
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(result.text, encoding="utf-8")
            if args.json_output:
                report = result.to_dict()
                report["text"] = result.text
                print(json.dumps(report, ensure_ascii=False, sort_keys=True))
            elif args.out:
                print(f"Output: {Path(args.out).expanduser()}")
                print(f"SHA-256: {result.sha256}")
                for row in result.omitted:
                    print(f"Omitted: {row['link_id']} ({row['node_id']}) {row['reason']}")
            else:
                print(result.text, end="")
            return 0

        if args.command == "world":
            world = WorldStore(store)
            if args.world_command == "add":
                payload = json.loads(Path(args.file).expanduser().read_text(encoding="utf-8"))
                record = world.add_record(args.project_id, args.kind, payload)
                report = {
                    "project_id": args.project_id,
                    "record": record.to_dict(),
                    "counts": world.status(args.project_id)["counts"],
                }
            elif args.world_command == "bind":
                root = store.load_project(args.project_id).root_node_id
                record = world.bind_work(
                    args.project_id, args.node_id or root,
                    time_span_ids=tuple(args.time_span_ids),
                    region_ids=tuple(args.region_ids),
                    culture_state_ids=tuple(args.culture_state_ids),
                    binding_id=args.binding_id,
                )
                report = {
                    "project_id": args.project_id,
                    "record": record.to_dict(),
                    "counts": world.status(args.project_id)["counts"],
                }
            elif args.world_command == "adopt-canon":
                root = store.load_project(args.project_id).root_node_id
                record = world.adopt_world_canon(
                    args.project_id, args.node_id or root,
                    source_artifact_path=args.artifact, json_pointer=args.pointer,
                    scope=CanonScope.from_dict({
                        "kind": args.scope, "reference_id": args.scope_id,
                    }),
                    subject=args.subject, valid_span_id=args.valid_span,
                    supersedes_id=args.supersedes, entry_id=args.entry_id,
                )
                report = {
                    "project_id": args.project_id,
                    "record": record.to_dict(),
                    "counts": world.status(args.project_id)["counts"],
                }
            elif args.world_command == "add-profile":
                payload = json.loads(Path(args.file).expanduser().read_text(encoding="utf-8"))
                profile = WorldCompiler(store).add_profile(args.project_id, payload)
                report = {"project_id": args.project_id, "record": profile.to_dict()}
            elif args.world_command == "profiles":
                report = {
                    "project_id": args.project_id,
                    "profiles": [
                        profile.to_dict()
                        for profile in WorldCompiler(store).list_profiles(args.project_id)
                    ],
                }
            elif args.world_command == "compile":
                result = WorldCompiler(store).compile(args.project_id, args.profile_id)
                report = result.to_dict()
                if args.out:
                    output = Path(args.out).expanduser()
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_text(result.text, encoding="utf-8")
                    report["external_out"] = str(output)
            else:
                report = world.status(args.project_id, args.node_id)
            if args.json_output:
                if args.world_command == "compile":
                    report["text"] = result.text
                print(json.dumps(report, ensure_ascii=False, sort_keys=True))
            elif args.world_command == "status":
                _print_world(report)
            elif args.world_command == "profiles":
                for profile in report["profiles"]:
                    print(f"{profile['id']}: {profile['kind']} {profile['content_version']}")
            elif args.world_command == "compile":
                if args.out:
                    print(f"Output: {Path(args.out).expanduser()}")
                    print(f"SHA-256: {result.sha256}")
                else:
                    print(result.text, end="")
            else:
                print(f"World record: {report['record']['id']}")
                print(f"Type: {report['record']['record_type']}")
            return 0

        if args.command == "run-tree":
            provider = _make_provider(args, store)
            result = ProjectRunner(store).run_tree(
                args.project_id, provider, node_id=args.node_id,
                seed=args.seed, temperature=args.temperature,
            )
            status = dict(result.status)
            status["order"] = list(result.order)
            status["tree_runs"] = [
                {
                    "node_id": item.status["node_id"],
                    "attempt_id": item.attempt_id,
                    "stage_runs": item.stage_runs,
                    "state": item.status["state"],
                }
                for item in result.results
            ]
            if args.json_output:
                print(json.dumps(status, ensure_ascii=False, sort_keys=True))
            else:
                _print_human(status, created=False)
                print("Topological order: " + " -> ".join(result.order))
                print(f"Nodes run: {len(result.results)}")
            return 0

        if args.command in {"run", "resume", "continue"}:
            provider = _make_provider(args, store)
            runner = ProjectRunner(store)
            if args.command == "run":
                result = runner.run(
                    args.project_id, provider,
                    seed=args.seed, temperature=args.temperature, node_id=args.node_id,
                )
            elif args.command == "resume":
                result = runner.resume(
                    args.project_id, provider, node_id=args.node_id,
                    retry_failed=args.retry_failed,
                )
            else:
                result = runner.continue_project(
                    args.project_id, provider,
                    additional_chapters=args.add_chapters,
                    total_chapters=args.chapters,
                    seed=args.seed, temperature=args.temperature,
                    title=args.title, premise=args.premise, node_id=args.node_id,
                    world_binding_id=args.world_binding,
                )
            status = dict(result.status)
            status["attempt_id"] = result.attempt_id
            if args.json_output:
                print(json.dumps(status, ensure_ascii=False, sort_keys=True))
            else:
                _print_human(status, created=False)
            return 0

        if args.command in {"revise", "branch"}:
            regenerate = bool(args.chapters or args.design)
            if regenerate and args.provider is None:
                raise ProviderError(
                    f"{args.command} regenerates {', '.join(args.chapters + args.design)}; "
                    "pass --provider scripted --script ... or --provider command --command ..."
                )
            provider = _make_provider(args, store, allow_none=True)
            runner = ProjectRunner(store)
            if args.command == "revise":
                result = runner.revise(
                    args.project_id, provider,
                    node_id=args.node_id,
                    source_revision_id=args.source_revision,
                    chapters=tuple(args.chapters),
                    design=tuple(args.design),
                    title=args.title, premise=args.premise,
                    target_chars_per_chapter=args.target_chars,
                    world_binding_id=args.world_binding,
                    seed=args.seed, temperature=args.temperature,
                )
            else:
                source_node = store.load_node_snapshot(
                    args.project_id, args.from_node,
                ).root_node
                parent = args.parent_node_id
                if parent is None:
                    parent = source_node.parent_id
                result = runner.branch(
                    args.project_id, provider,
                    child_node_id=args.child_node_id, link_id=args.link_id,
                    source_node_id=args.from_node,
                    source_revision_id=args.source_revision,
                    parent_node_id=parent, order=args.order,
                    chapters=tuple(args.chapters),
                    design=tuple(args.design),
                    title=args.title, premise=args.premise,
                    target_chars_per_chapter=args.target_chars,
                    world_binding_id=args.world_binding,
                    seed=args.seed, temperature=args.temperature,
                )
            status = dict(result.status)
            status["attempt_id"] = result.attempt_id
            if args.json_output:
                print(json.dumps(status, ensure_ascii=False, sort_keys=True))
            else:
                _print_human(status, created=False)
                derived = status.get("derived") or {}
                if derived:
                    print(
                        f"{derived['kind']} of {derived['source_revision_id']}"
                        f" (node {derived['source_node_id']})"
                    )
                    print(
                        "Regenerated chapters: "
                        + (", ".join(derived.get("chapters") or []) or "none")
                    )
                    print(
                        "Regenerated design: "
                        + (", ".join(derived.get("design") or []) or "none")
                    )
                    if not regenerate:
                        print("Provider calls: none (the revision was copied in full)")
            return 0

        if args.command == "diff":
            report = build_diff(
                store, args.project_id, args.left, args.right, node_id=args.node_id,
            ).to_dict()
            if args.json_output:
                print(json.dumps(report, ensure_ascii=False, sort_keys=True))
            else:
                _print_diff(report)
            return 0

        if args.command == "doctor":
            report = inspect_project(store, args.project_id)
            data = report.to_dict()
            if args.json_output:
                print(json.dumps(data, ensure_ascii=False, sort_keys=True))
            else:
                _print_doctor(data)
            return 0 if report.ok else 1

        if args.command == "context":
            view = build_context_view(
                store, args.project_id, args.node_id,
                run_id=args.run_id, stage=args.stage,
            )
            if args.out and view.packet is None:
                raise ProjectError(
                    "no ContextPacket to write: no ancestors and no world binding"
                )
            data = view.to_dict(include_packet=args.out is None)
            if args.out:
                output = Path(args.out).expanduser()
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(
                    json.dumps(view.packet, ensure_ascii=False, sort_keys=True, indent=2)
                    + "\n",
                    encoding="utf-8",
                )
                data["external_out"] = str(output)
            if args.json_output:
                print(json.dumps(data, ensure_ascii=False, sort_keys=True))
            else:
                _print_context(data)
            return 0

        if args.command == "bundle":
            if args.bundle_command == "export":
                report = ReplayBundle(store).export(args.project_id, args.out)
            elif args.bundle_command == "verify":
                report = ReplayBundle.verify(args.bundle_dir)
            else:
                report = ReplayBundle.restore(args.bundle_dir, store.root)
            if args.json_output:
                print(json.dumps(report, ensure_ascii=False, sort_keys=True))
            else:
                _print_bundle(report)
            return 0

        if args.command == "relay":
            return _relay_command(args, store)

        status = store.status(args.project_id, args.node_id)
        if args.command == "pending":
            report = {
                "project_id": status["project_id"],
                "node_id": status["node_id"],
                "state": status["state"],
                "pending": status["pending"],
            }
            if args.json_output:
                print(json.dumps(report, ensure_ascii=False, sort_keys=True))
            else:
                _print_pending(status)
            return 0
        if args.json_output:
            print(json.dumps(status, ensure_ascii=False, sort_keys=True))
        else:
            _print_human(status, created=False)
        return 0
    except ProjectRunPending as exc:
        # One waiting state, one place to look: refresh the paste-ready prompts
        # and name the single next command (ingest + resume in one step).
        round_report = None
        try:
            directory = _relay_directory(store, exc.project_id, args)
            if (directory / "requests").is_dir():
                _export_relay(exc.project_id, directory)
                round_report = _relay_round(
                    store, exc.project_id, directory,
                    node_id=exc.status.get("node_id"),
                )
        except (OSError, ProjectError, ProviderError):
            round_report = None
        if getattr(args, "json_output", False):
            print(json.dumps(exc.status, ensure_ascii=False, sort_keys=True))
        else:
            print(f"pending: {exc}", file=sys.stderr)
            print(f"response: {exc.pending.get('response_path')}", file=sys.stderr)
            if round_report is not None:
                print(
                    f"prompts: {round_report['pending_count']} pending / "
                    f"{round_report['answered']} answered",
                    file=sys.stderr,
                )
                print(
                    f"  {Path(round_report['directory']) / 'PROMPTS.md'}",
                    file=sys.stderr,
                )
                print(f"next: {round_report['next_command']}", file=sys.stderr)
            else:
                node_option = ""
                if exc.status.get("node_id") != exc.status.get("root_node_id"):
                    node_option = f" --node {exc.status['node_id']}"
                print(
                    "resume after writing the response: "
                    f"story_project.py resume {exc.project_id}{node_option}",
                    file=sys.stderr,
                )
        return 3
    except ProjectRunError as exc:
        print(f"error: {exc}", file=sys.stderr)
        if "No module named" in str(exc):
            print(MISSING_DEPENDENCY_HINT, file=sys.stderr)
        if exc.run_dir is not None:
            print(f"run: {exc.run_dir}", file=sys.stderr)
        return 2
    except (
        ProjectError, ProjectValidationError, ProviderError,
        OSError, UnicodeError, json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
