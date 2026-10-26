# バッチ A: 実モデルの本文で、地名観測・長さ・繰り返す失敗を見る — t01

- 日付: 2026-10-26
- 種類: **実走りの準備（事前登録と計測手順）**。本文はまだ 1 章も無い。
- 状態: **未走行（`samples_present: 0`）**
- 事前登録: [`preregistration.md`](preregistration.md) / [`preregistration.json`](preregistration.json)
- 手順: [`runbook.md`](runbook.md)
- 計測（空の記録）: [`results.json`](results.json)（`schema: realrun-a-v1`）
- 位置づけ: [`docs/two_stage_slice.md`](../../docs/two_stage_slice.md) §21

## なぜこのバンドルがあるか

地名検査の根拠は clean 9 章（3 走り・同一 canon）で、事例表 18 件はこちらが書いた文だった。
二段構成の価値も n=1〜3 でしか測っていない。**コードを足すより先に、実本文を 3 標本増やす**のが
次の一手だと判断し、走らせる前に判定規則を固定して、そのための自己完結バンドルを用意した。

## 何を固定したか（走らせる前）

1. **条件**: Stage B のみ・プロンプト v1.1・`--observe-surface`・canon/design/log は
   [`inputs/`](inputs/)（ログは走行前に `check_gamelog.py` で clean を再確認済み）。
2. **標本数**: 3。結果を見てから足すなら A2 として別途、走らせる前に登録する。
3. **判定規則**（`results.json` の `verdicts` がそのまま答える）:
   - R1: 観測の枝（`off_log` / `undeclared`）→ `no_examples` / `drop_undeclared_branch` /
     `narrow_branch_only` / `inspect_both`。**採否（blocking 化）はこのバッチでは決めない。**
   - R2: 章の長さ（1,000〜1,400 字、3 章中 2 章以上）→ `length_ok` / `fix_prompt_target` / `mixed`。
   - R3: 2 標本以上で落ちた検査 → `recurring` / `no_recurring_failure`。
4. **主張しないこと**: L2/L3 は `frozen_not_measured`、G5 は operator 方式では到達しない、
   面白さは測らない、観測は率ではない、独立性は保証されない。

登録の `sha256` は計測時に `results.json` へ記録される（結果を見て規則を書き換えたかどうかが残る）。

## 現在の中身

| パス | 内容 |
| --- | --- |
| `inputs/canon/` `inputs/design/` `inputs/game_log.json` | v1.1 と同一（sha256 一致を確認） |
| `preregistration.json` / `preregistration.md` | 走らせる前の判定規則 |
| `runbook.md` | 3 標本のコマンドとつまずき |
| `results.json` | 計測スクリプトの空の出力（`not_run` / `not_enough_data`） |
| `sample-1…3/`, `relay/sample-1…3/` | **まだ無い**（走行時に作られる） |

## 走行後にここへ書くこと

- 標本ごとの `status`、章ごとの字数・マーカー・修復回数、所見の検査名。
- `observations` の目的地と枝。
- `results.json` の verdict（読み替えずに引用する）。
- operator が誰で、`provenance.origin` が何だったか（独立性の限界）。

## 限界

- 3 標本は分布ではない。率（偽陽性率・合格率）は主張しない。
- 同じ canon・同じタスク・同じプロンプトの 1 条件だけを見る。条件間の比較はしない。
- L1 の量（字数・マーカー・所見）だけで、読んで面白いかは判定しない。
