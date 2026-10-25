#!/usr/bin/env python3
"""Create, run, and inspect persistent creative projects.

Examples::

    python3 scripts/story_project.py init \
        --title "潮の記録者" --premise "港町で失われた潮位記録を追う。"
    python3 scripts/story_project.py status PROJECT_ID --json

By default, projects live below ``runs/projects/``.  Use ``--root`` before the
subcommand to select another store.  ``run`` executes the single-work S1
vertical slice, and ``resume`` continues an interrupted revision without
regenerating its completed response prefix.  ``continue`` creates a new
revision for a completed work, and ``bundle export|verify|restore`` moves its
replay materials to an external directory.  ``add-child`` creates an independent
child below any node; ``run-tree`` uses parent-first dependency order;
``render`` and ``compose`` provide single-work and recursive pinned outputs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.pipeline import (  # noqa: E402
    CommandProvider, ProviderError, ScriptedProvider, load_scripted_responses,
)
from asc.project import (  # noqa: E402
    ProjectComposer,
    ProjectError,
    ReplayBundle,
    ProjectRunError,
    ProjectRunPending,
    ProjectRunner,
    ProjectStore,
    ProjectValidationError,
    WorkSpec,
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
    init.add_argument("--json", dest="json_output", action="store_true")

    run = subparsers.add_parser("run", help="run plan, design, and draft for a new revision")
    run.add_argument("project_id")
    run.add_argument("--node", dest="node_id", help="descendant node ID (default: root)")
    run.add_argument("--provider", choices=["scripted", "command"], default="command")
    run.add_argument("--script", help="scripted response JSON (with --provider scripted)")
    run.add_argument("--command", dest="provider_command", help="external provider command")
    run.add_argument("--model")
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--temperature", type=float)
    run.add_argument("--json", dest="json_output", action="store_true")

    tree = subparsers.add_parser(
        "run-tree", help="run a node and its descendants in parent-first order",
    )
    tree.add_argument("project_id")
    tree.add_argument("--node", dest="node_id", help="subtree root (default: project root)")
    tree.add_argument("--provider", choices=["scripted", "command"], default="command")
    tree.add_argument("--script", help="scripted response JSON (with --provider scripted)")
    tree.add_argument("--command", dest="provider_command", help="external provider command")
    tree.add_argument("--model")
    tree.add_argument("--seed", type=int, default=0)
    tree.add_argument("--temperature", type=float)
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
    continuation.add_argument("--provider", choices=["scripted", "command"], default="command")
    continuation.add_argument("--script", help="scripted response JSON (with --provider scripted)")
    continuation.add_argument("--command", dest="provider_command", help="external provider command")
    continuation.add_argument("--model")
    continuation.add_argument("--seed", type=int, default=0)
    continuation.add_argument("--temperature", type=float)
    continuation.add_argument("--json", dest="json_output", action="store_true")

    resume = subparsers.add_parser("resume", help="resume an interrupted project revision")
    resume.add_argument("project_id")
    resume.add_argument("--node", dest="node_id", help="descendant node ID (default: root)")
    resume.add_argument("--provider", choices=["scripted", "command"], default="command")
    resume.add_argument("--script", help="scripted response JSON (with --provider scripted)")
    resume.add_argument("--command", dest="provider_command", help="external provider command")
    resume.add_argument("--model")
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
    compose.add_argument("--json", dest="json_output", action="store_true")

    pending = subparsers.add_parser("pending", help="list operator responses still needed")
    pending.add_argument("project_id")
    pending.add_argument("--node", dest="node_id", help="subtree root (default: root and all descendants)")
    pending.add_argument("--json", dest="json_output", action="store_true")

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

    status = subparsers.add_parser("status", help="load and summarize an existing project")
    status.add_argument("project_id")
    status.add_argument("--node", dest="node_id", help="descendant node ID (default: root)")
    status.add_argument("--json", dest="json_output", action="store_true")
    return parser.parse_args(argv)


def _make_provider(args: argparse.Namespace):
    if args.provider == "scripted":
        if not args.script:
            raise ProviderError("--provider scripted requires --script")
        return ScriptedProvider(
            load_scripted_responses(args.script), model=args.model or "scripted-fixture",
        )
    if not args.provider_command:
        raise ProviderError("--provider command requires --command")
    return CommandProvider(args.provider_command, model=args.model or "external")


def _print_human(status: dict, *, created: bool) -> None:
    heading = "Created project" if created else "Project"
    print(f"{heading}: {status['project_id']}")
    print(f"Title: {status['title']}")
    print(f"State: {status['state']}")
    print(f"Root node: {status['root_node_id']}")
    print(f"Selected node: {status.get('node_id', status['root_node_id'])}")
    print(f"Current revision: {status['current_revision_id']}")
    print(f"Spec SHA-256: {status['spec_sha256']}")
    stages = ", ".join(f"{name}={value}" for name, value in status["stages"].items())
    print(f"Stages: {stages}")
    print(
        f"Artifact refs: {len(status.get('artifact_refs', []))}; "
        f"runs: {len(status['runs'])}"
    )
    if status.get("attempt_id"):
        print(f"Attempt: {status['attempt_id']}")
    print(f"Pending responses: {len(status.get('pending', []))}")
    if status.get("links"):
        stale = sum(1 for link in status["links"] if link["stale"])
        print(f"Child links: {len(status['links'])}; stale: {stale}")
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


def _print_bundle(report: dict) -> None:
    print(f"Project: {report['project_id']}")
    print(f"Files: {report['file_count']}")
    print(f"Manifest SHA-256: {report['manifest_sha256']}")
    if report.get("bundle_dir"):
        print(f"Bundle: {report['bundle_dir']}")
    if report.get("project_dir"):
        print(f"Restored: {report['project_dir']}")
    print("Verified: yes")


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
                else composer.compose(args.project_id, args.node_id)
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
            else:
                print(result.text, end="")
            return 0

        if args.command == "run-tree":
            provider = _make_provider(args)
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
            provider = _make_provider(args)
            runner = ProjectRunner(store)
            if args.command == "run":
                result = runner.run(
                    args.project_id, provider,
                    seed=args.seed, temperature=args.temperature, node_id=args.node_id,
                )
            elif args.command == "resume":
                result = runner.resume(
                    args.project_id, provider, node_id=args.node_id,
                )
            else:
                result = runner.continue_project(
                    args.project_id, provider,
                    additional_chapters=args.add_chapters,
                    total_chapters=args.chapters,
                    seed=args.seed, temperature=args.temperature,
                    title=args.title, premise=args.premise, node_id=args.node_id,
                )
            status = dict(result.status)
            status["attempt_id"] = result.attempt_id
            if args.json_output:
                print(json.dumps(status, ensure_ascii=False, sort_keys=True))
            else:
                _print_human(status, created=False)
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
        if getattr(args, "json_output", False):
            print(json.dumps(exc.status, ensure_ascii=False, sort_keys=True))
        else:
            print(f"pending: {exc}", file=sys.stderr)
            print(f"response: {exc.pending.get('response_path')}", file=sys.stderr)
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
