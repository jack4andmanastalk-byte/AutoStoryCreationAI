#!/usr/bin/env python3
"""Read-only probes of the Stage A / Stage B checker contracts.

The ``docs/two_stage_slice.md`` tables state what each check guarantees. This
script tests a handful of those statements against **mutated copies** of the
committed ``t01`` bundle, in memory, and prints what the checkers actually
report. Nothing is written to the pipeline and no model is called: the point is
to see where a passing status is narrower than the prose contract, not to prove
that the contract is satisfied.

    python3 scripts/probe_gamelog_contracts.py
    python3 scripts/probe_gamelog_contracts.py --include-resume

``--include-resume`` additionally exercises ``--resume`` with a scratch
directory under ``experiments/_probe-contracts-<pid>/`` (removed afterwards).
Exit status is 0 even when a probe shows a gap: the output is evidence for the
gap list, not a regression test. See
``research/curation/two_stage_stage1_audit_2026-10-26.md`` §3.

The probes are deliberately small and named after the *claim* they test.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from asc.gamelog.check import check_game_log  # noqa: E402
from asc.gamelog.rewrite import check_rewrite, missing_must_include  # noqa: E402
from asc.gamelog.schema import load_game_log, parse_game_log  # noqa: E402
from asc.gamelog.world import derive_timeline  # noqa: E402
from asc.plot.schema import load_plot  # noqa: E402
from asc.scene.schema import load_scenes  # noqa: E402
from asc.story.canon import load_canon  # noqa: E402
from asc.style.schema import load_voice  # noqa: E402

DEFAULT_BUNDLE = "experiments/2026-10-trpg-slice-t01"

# Probes of Stage A (`check_game_log`). Each mutates the loaded JSON.
STAGE_A = (
    ("A1", "死者が action.summary の自由記述で現在時に動く",
     "presence_death は自由記述も走査するか。"),
    ("A2", "action.target に死者名が部分文字列で入る",
     "target は完全一致だけか（死者の所持品を対象にした行動）。"),
    ("A3", "現在時 action に subject=johan（死者）を付ける",
     "PRESENT_TENSE_TYPES の subject は検査されるか。"),
    ("A4", "死者を used_facts の主体にする",
     "死者の現在時の知識使用は high になるか。"),
    ("A5", "同一場面で F-05 を learn してから use する",
     "learn → use の順序を場面内で許容するか（canon の開示章も ch01）。"),
    ("A6", "場面の purpose/conflict/change を設計と無関係な文にする",
     "設計書の目的/対立/変化と本文相当の欄を照合するか。"),
    ("A7", "登場しない人物の移動だけを宣言する",
     "移動は人物の現在地・登場と結び付くか。"),
    ("A8", "キー名を誤記する（present_character / state_delta.learn）",
     "未知キーは拒否または報告されるか。"),
    ("A9", "章を canon と逆順に並べる",
     "章順は明示的に検査されるか。"),
    ("A10", "同じ章 ID の章を複製する",
     "章 ID の重複は名指しで報告されるか。"),
    ("A11", "場面の day / location を章と矛盾させる",
     "場面レベルの日付・場所は使われるか。"),
)


def _mutations():
    def a1(d):
        d["chapters"][0]["scenes"][0]["actions"][0]["summary"] = (
            "アリアは油栓を確かめる。ヨハンが戸口に立って笑った。")

    def a2(d):
        d["chapters"][0]["scenes"][0]["actions"][0]["target"] = "ヨハンの潮札"

    def a3(d):
        d["chapters"][0]["scenes"][0]["actions"][0]["subject"] = "johan"

    def a4(d):
        scene = d["chapters"][1]["scenes"][0]
        scene["state_delta"]["used_facts"] = [{"character": "johan", "fact": "F-04"}]
        scene["emitted_markers"].append("{{use: johan fact=F-04}}")

    def a5(d):
        scene = d["chapters"][0]["scenes"][0]
        scene["state_delta"]["learned_facts"] = [{"character": "aria", "fact": "F-05"}]
        scene["state_delta"]["used_facts"] = [{"character": "aria", "fact": "F-05"}]
        scene["emitted_markers"] = ["{{learn: aria fact=F-05}}", "{{use: aria fact=F-05}}",
                                    "{{foreshadow: fs-001 setup}}",
                                    "{{foreshadow: fs-002 setup}}"]

    def a6(d):
        scene = d["chapters"][0]["scenes"][0]
        scene["purpose"] = "まったく別の目的"
        scene["conflict"] = "無関係な対立"
        scene["change"] = "無関係な変化"

    def a7(d):
        scene = d["chapters"][0]["scenes"][0]
        scene["state_delta"]["location_moves"] = [
            {"character": "celia", "origin": "港", "destination": "王都",
             "depart_day": 1, "arrival_day": 4}]

    def a8(d):
        scene = d["chapters"][0]["scenes"][0]
        scene["present_character"] = ["boris"]
        scene["state_delta"]["learn"] = [{"character": "aria", "fact": "F-09"}]

    def a9(d):
        d["chapters"][0], d["chapters"][2] = d["chapters"][2], d["chapters"][0]

    def a10(d):
        d["chapters"].append(copy.deepcopy(d["chapters"][0]))

    def a11(d):
        scene = d["chapters"][1]["scenes"][0]
        scene["location"] = "港"
        scene["day"] = 99

    return {"A1": a1, "A2": a2, "A3": a3, "A4": a4, "A5": a5, "A6": a6,
            "A7": a7, "A8": a8, "A9": a9, "A10": a10, "A11": a11}


# Probes of Stage B (`check_rewrite`), applied to the scripted ch01 text.
STAGE_B = (
    ("B1", "死者が現在時に動く一文を足す（章には記録への言及がある）",
     "character_boundary は言及と現在時行動を区別できるか。"),
    ("B2", "canon にない人物を出す",
     "未知の人物は報告されるか。"),
    ("B3", "学習した事実を打ち消す",
     "マーカーがあっても事実の否定は検出できるか。"),
    ("B4", "マーカーは残したまま、その事実を本文から消す",
     "マーカー一致は事実の保持を含意するか。"),
    ("B5", "ログにない場所と船旅を書き足す",
     "本文中の新しい場所・移動は検出できるか。"),
    ("B6", "死者の短い別名（兄）だけを現在時の行動主にする",
     "短い別名の言及は人物境界に出るか。"),
    ("B7", "タスクの必須語（鍵）を全章から落とす",
     "must_include は作品全体でゲートされるか。"),
    ("B8", "ch03 の「六日ぶり」を「四日ぶり」に置き換える",
     "明示された日数の矛盾は検出できるか。抽象化は許容されるか。"),
)


def _text_mutations(base: str):
    return {
        "B1": base.replace("潮札を革袋に入れ、",
                           "ヨハンが戸口から入ってきてアリアの肩を叩いた。潮札を革袋に入れ、"),
        "B2": base.replace("アリアは潮札を裏返した。",
                           "マルタという女が戸口に立っていた。アリアは潮札を裏返した。"),
        "B3": base.replace("王都までは三日かかる、と隅に書いてある。",
                           "王都まで何日かかるかは、どこにも書かれていない。"),
        "B4": base.replace("王都までは三日かかる、と隅に書いてある。",
                           "アリアは頁をめくった。"),
        "B5": base.replace("風はまだ強かったが、灯りは揺れなかった。",
                           "風はまだ強かった。アリアは港の桟橋まで歩き、船で対岸へ渡った。"),
        "B6": base.replace("潮札を裏返した。",
                           "潮札を裏返した。兄が戸口に立って、アリアを見ていた。"),
        "B7": base.replace("鍵", "錠"),
    }


def _print_findings(report: dict, limit: int = 6) -> None:
    findings = report.get("findings", [])
    summary = report.get("summary", {})
    print(f"    status={summary.get('status')} findings={len(findings)} "
          f"by={summary.get('by_severity') or {}}")
    for item in findings[:limit]:
        print(f"      - [{item['severity']}] {item['check']}: {item['message_ja']}")


def run_stage_a(bundle: Path) -> int:
    raw = json.loads((bundle / "inputs" / "game_log.json").read_text(encoding="utf-8"))
    canon = load_canon(bundle / "inputs" / "canon")
    plot = load_plot(bundle / "inputs" / "design" / "plot.json")
    scenes = load_scenes(bundle / "inputs" / "design" / "scene.json")
    mutations = _mutations()
    print("## Stage A — check_game_log（変異コピー、実装は変更しない）")
    for probe_id, title, question in STAGE_A:
        print(f"\n{probe_id}: {title}")
        print(f"    契約の問い: {question}")
        data = copy.deepcopy(raw)
        mutations[probe_id](data)
        try:
            log = parse_game_log(data, "<probe>")
        except Exception as exc:  # noqa: BLE001 - a parse refusal is a result too
            print(f"    parse refused: {exc}")
            continue
        _print_findings(check_game_log(log, canon, plot, scenes))
    return 0


def run_stage_b(bundle: Path) -> int:
    log = load_game_log(bundle / "inputs" / "game_log.json")
    canon = load_canon(bundle / "inputs" / "canon")
    scenes = load_scenes(bundle / "inputs" / "design" / "scene.json")
    voice = load_voice(bundle / "inputs" / "design" / "voice.json")
    base = (bundle / "inputs" / "rewrite" / "ch01.md").read_text(encoding="utf-8")
    bodies = _text_mutations(base)
    chapters = {path.stem: path.read_text(encoding="utf-8")
                for path in sorted((bundle / "inputs" / "rewrite").glob("*.md"))}
    print("\n## Stage B — check_rewrite（ch01、変異コピー）")
    for probe_id, title, question in STAGE_B:
        print(f"\n{probe_id}: {title}")
        print(f"    契約の問い: {question}")
        if probe_id == "B7":
            # The required word is a property of the whole work, so the
            # mutation is applied to every chapter (B-06).
            mutated = {cid: text.replace("鍵", "錠") for cid, text in chapters.items()}
            joined = "\n\n".join(mutated[cid] for cid in sorted(mutated))
            per_chapter = [check_rewrite(text, cid, log, canon, voice, scenes,
                                         avoid=("古代の予言", "選ばれし者"),
                                         min_chars=200)["summary"]["status"]
                           for cid, text in sorted(mutated.items())]
            missing = missing_must_include(joined, ("灯台", "鍵", "嵐"))
            print(f"    章ごとの check_rewrite: {per_chapter}")
            print(f"    missing_must_include={missing} → 作品単位では "
                  f"{'unresolved' if missing else 'clean'}")
            continue
        if probe_id == "B8":
            # The scripted ch03 writes no day number at all, so the probe
            # injects one: the derived table says aria left 灯台 six days ago.
            timeline = derive_timeline(log, canon)
            anchor = "灯台に戻ると、"
            variants = (
                ("正しい「六日ぶり」", "六日ぶりの灯台だった。"),
                ("誤った「四日ぶり」", "四日ぶりの灯台だった。"),
                ("抽象化「しばらく」", "しばらくぶりの灯台だった。"),
            )
            for label, opening in variants:
                text = chapters["ch03"].replace(anchor, opening + anchor)
                kwargs = dict(avoid=("古代の予言", "選ばれし者"), min_chars=200,
                              timeline=timeline)
                warn = check_rewrite(text, "ch03", log, canon, voice, scenes,
                                     **kwargs)
                strict = check_rewrite(text, "ch03", log, canon, voice, scenes,
                                       strict_timeline=True, **kwargs)
                summary = warn["summary"]
                print(f"    {label}: warn status={summary['status']} "
                      f"blocking={summary['blocking_findings']} "
                      f"warning={summary['warning_findings']} "
                      f"checked={summary['timeline']['checked']} "
                      f"skipped={summary['timeline']['skipped']} / "
                      f"strict status={strict['summary']['status']} "
                      f"blocking={strict['summary']['blocking_findings']}")
                for item in warn["findings"]:
                    if item["check"] == "timeline_consistency":
                        print(f"      - [{item['severity']}] {item['message_ja']}")
            continue
        report = check_rewrite(bodies[probe_id], "ch01", log, canon, voice, scenes,
                              avoid=("古代の予言", "選ばれし者"), min_chars=200)
        _print_findings(report)
    print("\n    （B7 は章ごとの検査が clean のままでも、作品全体で必須語が"
          "欠けると runner が unresolved にする、という差の確認。）")
    print("    （B6 は canon の別名「兄」（1 文字）を現在時の行動主にしたもの。"
          "character_boundary は 2 文字未満の名前を走査しない。）")
    print("    （B8 は日数を数字で書いた場合だけを照合する。抽象化と、書かれていない""誤りは対象外。厳密判定は --strict-timeline のときだけ。）")
    return 0


def run_resume(bundle: Path) -> int:
    """Exercise --resume in a scratch bundle under experiments/."""
    scratch = REPO_ROOT / "experiments" / f"_probe-contracts-{os.getpid()}"
    python = sys.executable

    def command(out: Path, *, resume: bool = False, seed: str = "0",
                scripted: bool = True, run_id: str = "probe",
                provider_script: Path | None = None,
                allow_config_change: bool = False) -> list[str]:
        args = [python, str(REPO_ROOT / "scripts" / "run_twostage.py"),
                "--task", "t01",
                "--canon", str(bundle / "inputs" / "canon"),
                "--design-dir", str(bundle / "inputs" / "design"),
                "--out", str(out), "--run-id", run_id,
                "--report-only", "--quiet", "--seed", seed]
        if scripted:
            args += ["--provider", "scripted",
                     "--script", str(bundle / "scripted.json")]
        else:
            args += ["--provider", "command",
                     "--command", f"{python} {provider_script}"]
        if allow_config_change:
            args.append("--allow-config-change")
        if resume:
            args.append("--resume")
        return args

    def call(*args, **kwargs):
        return subprocess.run(command(*args, **kwargs), capture_output=True,
                              text=True, cwd=REPO_ROOT)

    try:
        print("\n## 再開・記録保全 — run_twostage.py --resume")
        # R1: the documented resume_command must run as printed.
        call(scratch)
        state = json.loads((scratch / "probe" / "state.json").read_text(encoding="utf-8"))
        print("\nR1: state.json の resume_command をそのまま実行する")
        print(f"    resume_command: {state['resume_command']}")
        printed = state["resume_command"].replace("python3", python).split()
        done = subprocess.run(printed, capture_output=True, text=True)
        print(f"    rc={done.returncode} stderr={done.stderr.strip()[:160]}")
        resumed_state = json.loads(
            (scratch / "probe" / "state.json").read_text(encoding="utf-8"))
        print(f"    resume_count={resumed_state['resume_count']}")

        # R2: an edited recorded response must be refused.
        path = scratch / "probe" / "responses.jsonl"
        entries = [json.loads(line) for line in
                   path.read_text(encoding="utf-8").splitlines() if line.strip()]
        entries[0]["response"]["text"] = entries[0]["response"]["text"].replace("嵐", "霧")
        path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n",
                        encoding="utf-8")
        done = call(scratch, resume=True)
        print("\nR2: 記録済み応答の本文を書き換えてから --resume")
        print(f"    rc={done.returncode} stderr={done.stderr.strip()[:200]}")
        print("    期待: rc=2（response_sha256 の不一致を拒否する）")

        # R3: a different --seed is accepted and silently replaces the record.
        done = call(scratch, resume=True, seed="7")
        seed = json.loads((scratch / "probe" / "state.json").read_text(
            encoding="utf-8"))["config"]["seed"]
        allowed = call(scratch, resume=True, seed="7", allow_config_change=True)
        state = json.loads((scratch / "probe" / "state.json").read_text(
            encoding="utf-8"))
        print("\nR3: --resume --seed 7（保存済み config の seed は 0）")
        print(f"    素の --resume: rc={done.returncode} "
              f"stderr={done.stderr.strip().splitlines()[:1]}")
        print(f"    --allow-config-change: rc={allowed.returncode} | "
              f"state.config.seed={state['config']['seed']} | "
              f"config_changes={sorted(state.get('config_changes', {}))}")

        # R4: a provider error leaves no state.json, so --resume refuses.
        failing = scratch.parent / f"_probe-fail-{os.getpid()}.py"
        failing.write_text(
            "import json, sys\n"
            "req = json.load(sys.stdin)\n"
            "if req['purpose'].startswith('stage_b:ch02'):\n"
            "    sys.stderr.write('boom\\n'); sys.exit(1)\n"
            "base = 'experiments/2026-10-trpg-slice-t01/inputs/'\n"
            "name = 'game_log.json' if not req['purpose'].startswith('stage_b') else \\\n"
            "    'rewrite/' + req['purpose'].split(':')[1] + '.md'\n"
            "print(json.dumps({'text': open(base + name, encoding='utf-8').read()}))\n",
            encoding="utf-8")
        shutil.rmtree(scratch, ignore_errors=True)
        call(scratch, scripted=False, provider_script=failing)
        run_dir = scratch / "probe"
        print("\nR4: Stage B の途中で provider が失敗した run")
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        print(f"    state.json=True status={state['status']} "
              f"error={str(state.get('error'))[:60]!r}")
        print(f"    responses.jsonl="
              f"{len((run_dir / 'responses.jsonl').read_text(encoding='utf-8').strip().splitlines())} 行")
        done = call(scratch, resume=True, scripted=False, provider_script=failing)
        kept = len((run_dir / "responses.jsonl").read_text(
            encoding="utf-8").strip().splitlines())
        print(f"    --resume rc={done.returncode}（同じ失敗を再現）| "
              f"記録は保持: {kept} 行 | resume_count="
              f"{json.loads((run_dir / 'state.json').read_text(encoding='utf-8'))['resume_count']}")
        failing.unlink(missing_ok=True)
        return 0
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bundle", default=str(REPO_ROOT / DEFAULT_BUNDLE))
    parser.add_argument("--include-resume", action="store_true",
                        help="also probe --resume in a scratch experiments/ directory")
    parser.add_argument("--only", choices=["a", "b", "resume"], default=None)
    args = parser.parse_args(argv)
    bundle = Path(args.bundle)
    if not bundle.is_absolute():
        bundle = REPO_ROOT / bundle
    print(f"bundle: {bundle.relative_to(REPO_ROOT)}")
    print("注: 出力は「契約文とコードの差」の証拠であり、意味的整合性の保証ではない。")
    if args.only in (None, "a"):
        run_stage_a(bundle)
    if args.only in (None, "b"):
        run_stage_b(bundle)
    if args.include_resume or args.only == "resume":
        run_resume(bundle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
