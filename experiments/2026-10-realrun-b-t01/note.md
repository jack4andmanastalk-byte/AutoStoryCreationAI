# バッチ B: S1 全体（plan → 8 設計 → draft）の実走り準備 — t01

- 日付: 2026-10-27
- 種類: **実走り前のバンドル準備（事前登録）**。実モデル応答はまだ無い。
- 状態: **未走行**（`results.json` は `not_run`）
- 事前登録: [`preregistration.md`](preregistration.md) / [`preregistration.json`](preregistration.json)
- 手順: [`runbook.md`](runbook.md)（Arena Agent Mode 内でエージェントが実行）
- 運用モデル: [`docs/arena_operation.md`](../../docs/arena_operation.md)
- 計測: [`results.json`](results.json)（`schema: realrun-b-v1`、事前登録の `sha256` を記録）
- 位置づけ: [`docs/two_stage_slice.md`](../../docs/two_stage_slice.md) §23

## なぜこのバンドルがあるか

これまでの比較は、固定した canon・設計書を使う draft 段だけか
（[`docs/two_stage_slice.md`](../../docs/two_stage_slice.md) §15）、固定した
canon・設計・検証済みログを使う二段階方式の Stage B だけ（バッチ A）だった。

まだ実応答で通していないのは **S1 全体**、すなわち plan が canon を作り、
その canon を 8 種の設計が読み、最後に draft が同じ canon と設計から本文を書く
一続きの経路である。このバッチではコードを足す前に、その 1 標本を
先に規則を決めて走らせるための自己完結バンドルを用意した。

## 何を固定したか（走らせる前）

1. **条件**: t01、S1、`--stage all`、seed 0、temperature 0.8、1 標本。
   設計書は `brief, world, history, character, relation, plot, scene, voice` の 8 種。
2. **同一 canon の解釈**: この run の plan が一度だけ作った単一の canon を、
   8 設計と draft が読む。バッチ A の `inputs/canon` は再利用しない。
   これは、plan が canon を作るという [`docs/project.md`](../../docs/project.md) の
   設計と、固定 canon の draft 段だけを S1 全体と呼ばない
   [`docs/two_stage_slice.md`](../../docs/two_stage_slice.md) §15.2 に従う。
3. **プロンプト**: 現在の S1 セットを版と digest で登録に固定した。
   S1 経路で v1.2 なのは `draft-chapter` である。他のテンプレートの版も
   併せて記録し、走行後に manifest と照合する。プロンプト本文はこのバンドルに置かない。
4. **判定規則**（[`preregistration.md`](preregistration.md)）:
   - B0: 条件どおりか（plan による canon 生成、プロンプト digest）。
   - B1: 完走とゲート。ただし設計の unresolved / missing を隠さない。
   - B2: 初回所見。**修復で消えた所見も数える**。最終所見は別欄に残す。
   - B3: 章長 1,000〜1,400 字が 2 章以上で、合計 3,000〜4,200 字か。
   - B4: 最終本文監査で high 違反がなく、全検査が実行されるか。
5. **主張しないこと**: L2/L3 は `frozen_not_measured`。面白さや品質は判定せず、
   N=1 から率も主張しない。G5 は operator 方式では到達しない。

## 現在の中身

| パス | 内容 |
| --- | --- |
| `preregistration.json` / `preregistration.md` | 走らせる前に固定した判定規則と prompt digest |
| `runbook.md` | Arena 内でエージェントが relay を使って回す 1 標本の手順、再実行方法、つまずき |
| `results.json` | 計測スクリプトの空の出力（`not_run`） |
| `relay/sample-1/.gitkeep` | 実行時に要求・応答が入る場所。現時点では空 |

実応答、本文、プロンプト本文は含まれない。プロンプトは実行時に pipeline が
relay 配下へ要求として書き出す。応答待ちのたびに未完成 run だけを消して再実行しても、
relay にある同じ標本の応答が再生されるだけであり、新しい標本にはならない。

## 運用モデルの明確化（2026-10-27、走行前の追記）

初版の runbook が「利用者がローカルでコマンドを実行する」前提に読める形だったため、
[`docs/arena_operation.md`](../../docs/arena_operation.md) の分析・再設計に基づき、
**Arena Agent Mode 内でエージェントが実行し、GitHub を永続化・再検証の層とする**
運用に書き改めた。これは実行者と実行場所の明確化であり、事前登録の条件
（タスク・プロンプト固定・seed・temperature・canon 方針）も判定規則（B0〜B4）も
**変更していない**。標本はいまだ未走行である。

## 結果（走行後にここへ書く）

まだ無い。走行したら、次を `results.json` の verdict を読み替えずに引用して書く。

- B0〜B4 の verdict、run の status と gates。
- plan attempts／初回失敗、生成された canon の件数・被覆・sha256。
- 8 設計の status、attempts、初回 findings、最終 findings、修復で消えた件数。
- 章ごとの字数、attempts、初回 issues、補完マーカー、必須語率。
- 監査の violations、severity/type の内訳、未実行検査、CED（参考値）。
- 応答件数と `provenance.origin` の内訳、operator の独立性に関する限界。

## 限界

- **N=1** である。率、再発率、一般的な遵守率は主張しない。
- バッチ A と canon が異なるため、バッチ A 本文との対比較にはならない。
  比べられるのは、段ごとの所見・修復・L1 指標の出方までである。
- 設計段は未解決でも次へ進む fail-open である。完走は設計合格を意味しないため、
  B1 は unresolved / missing を分けて判定する。
- 継続性監査は主に機械可読マーカーと語彙照合による L1 検査である。
  通過は意味的整合や本文の良さの保証ではない。
- operator 応答では同一 seed の再現性（G5）を示せない。応答の独立性も保証されない。

## 次にすること

1. 利用者の開始指示を受けて、Arena Agent Mode 内で [`runbook.md`](runbook.md) の手順で `sample-1` を回す（ローカル実行は前提にしない）。
2. 完了または終端失敗後に、エージェントが `scripts/measure_realrun_b.py` で測る。
3. verdict をこのノートへ引用し、初回所見の出た段を次の修正候補として記録する。
4. 標本を増やす場合は、この結果を見た後に足すのではなく、B2 として走らせる前に登録する。
