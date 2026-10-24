#!/usr/bin/env python3
"""Create, run, and inspect persistent creative projects.

Examples::

    python3 scripts/story_project.py init \
        --title "潮の記録者" --premise "港町で失われた潮位記録を追う。"
    python3 scripts/story_project.py status PROJECT_ID --json

By default, projects live below ``runs/projects/``.  Use ``--root`` before the
subcommand to select another store.  ``run`` executes the single-work S1
vertical slice; resume, continuation, and nested works are later increments.
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
    ProjectError,
    ProjectRunError,
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
    run.add_argument("--provider", choices=["scripted", "command"], default="command")
    run.add_argument("--script", help="scripted response JSON (with --provider scripted)")
    run.add_argument("--command", dest="provider_command", help="external provider command")
    run.add_argument("--model")
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--temperature", type=float)
    run.add_argument("--json", dest="json_output", action="store_true")

    status = subparsers.add_parser("status", help="load and summarize an existing project")
    status.add_argument("project_id")
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
    print(f"Directory: {status['project_dir']}")


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

        if args.command == "run":
            provider = _make_provider(args)
            result = ProjectRunner(store).run(
                args.project_id, provider,
                seed=args.seed, temperature=args.temperature,
            )
            status = dict(result.status)
            status["attempt_id"] = result.attempt_id
            if args.json_output:
                print(json.dumps(status, ensure_ascii=False, sort_keys=True))
            else:
                _print_human(status, created=False)
            return 0

        status = store.status(args.project_id)
        if args.json_output:
            print(json.dumps(status, ensure_ascii=False, sort_keys=True))
        else:
            _print_human(status, created=False)
        return 0
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
