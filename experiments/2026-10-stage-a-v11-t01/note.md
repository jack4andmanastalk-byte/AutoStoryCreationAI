# 場面フレーム（schema 1.1）の実応答実走 — t01 / Stage A → Stage B

- 日付: 2026-10-28
- 種類: **実応答**での Stage A（`schema_version: "1.1"`）→ Stage B の一気通貫
  （`--stage both --gamelog-schema 1.1`）。台本（`scripted`）ではない。
- 位置づけ: [`docs/two_stage_slice.md`](../../docs/two_stage_slice.md) §27 の
  「**実モデルでの 1.1 の応答は未実施**」に対する最初の走り。手順は [`runbook.md`](runbook.md)。
- 決定論的要約: [`artifacts/results.json`](artifacts/results.json)（`schema: trpg-slice-wiring-v1`）。
  run バンドルの正本は `out/run1/` だが、この環境（Arena）は `out/` をスナップショットから
  除外するため、完了後に [`artifacts/run1/`](artifacts/run1/) へ複写してコミットした。

## 目的

1. 1.1 で足した 4 欄（`phase` / `outcome_kind` / `rescue` / `carry_forward`）を持つ Stage A の応答が、
   9 件目の検査 `scene_frame` を通るか。
2. 1.1 のログを Stage B が小説化できるか（3 章・マーカー列・知識境界・死者参照・時系列）。

**質・面白さの判定ではない。** L2/L3 は `frozen_not_measured`、G3/G4 は未測定、G5 は未達。

## 入力と条件

```text
inputs/canon/    t01 の canon（2026-10-trpg-slice-t01 と同一の複製。sha256 は results.json の inputs に記録）
inputs/design/   plot.json / scene.json / voice.json（同複製。game_log.json と rewrite/ は使っていない）
relay/run1/      4 要求（stage_a・ch01・ch02・ch03）と 4 応答
```

- `--task t01 --stage both --gamelog-schema 1.1 --observe-surface --seed 0`、`temperature 0.8`。
- provider は `command` → `scripts/chat_operator.py --dir relay/run1`。
- `prompt_hashes`: `stage-a-gamelog c051eacd8b244187` / `stage-a-repair 2177a6fbddf7e1de` /
  `stage-b-rewrite b6dab12394b7085c` / `stage-b-repair e8bf637756ab4724`。
  1.1 の Stage A 依頼文の `prompt_hash` は `ac3075465acb2e35`
  （[`prompts/stage-a.attempt-1.prompt.md`](prompts/stage-a.attempt-1.prompt.md) とバイト一致）。
- model: `arena-agent-mode` / `unversioned-2026-10-28`。4 応答とも `provenance.origin: fresh`。

## 応答者と独立性

- 依頼文はエージェントが `relay/run1/requests/<key>.json` の `"prompt"` を**逐語で提示**し、
  利用者が別の回答用チャットに貼って応答を得た（[`ARENA_PROMPTS.md`](ARENA_PROMPTS.md) の運用）。
  応答は利用者が貼り戻し、エージェントが封筒（`text` / `model` / `model_version` / `provenance`）に
  逐語で保存した。**依頼本文・応答本文をエージェントが作文していない。**
- ラウンド: 4 要求 / 4 応答（Stage A 1、Stage B 3）。**修復 0 回**
  （`stage_a:repair` も `stage_b:repair` も発生しなかった）。
- 応答者（どのチャットか、毎回新規チャットだったか）: **【人が記入】**

## 手順（実際に起きたこと）

```bash
# 0. 前提
make setup
.venv/bin/python -m pytest tests/test_gamelog_scene_frame.py -q   # 16 passed

# 1. 1 回目（--resume を付けない）→ exit 3
B=experiments/2026-10-stage-a-v11-t01
R=$PWD/$B/relay/run1
CMD="$PWD/.venv/bin/python scripts/chat_operator.py --dir $R"
.venv/bin/python scripts/run_twostage.py --task t01 --stage both --gamelog-schema 1.1 \
  --canon $B/inputs/canon --design-dir $B/inputs/design \
  --provider command --command "$CMD" --observe-surface --seed 0 \
  --out $B/out --run-id run1 --results $B/out/results.json

# 3. 応答を relay/run1/responses/<key>.json に書くたびに、同じ command に --resume を付けて再開
#    （--gamelog-schema 1.1 は毎回付ける）
```

- exit code の推移: **3**（Stage A 待ち）→ **3**（ch01 待ち）→ **3**（ch02 待ち）→ **0**（完了）。
- **環境由来の中断（2 回）**: Arena の作業環境は `out/` と `.venv` という名前のディレクトリを
  スナップショットから除外するため、run バンドル（`state.json`）と venv が消えた。
  そのときは `--resume` が exit 2（`--resume needs state.json`）になったので、§1 を
  `--resume` なしで再実行し、`relay/run1/responses/` の記録済み応答をリプレイしてバンドルを
  再構築した（`replay.report.json` が `response_sha256` の一致を記録）。**応答は `relay/` に
  残るので走りそのものは失われていない。** 3 回目は環境が保持され、`--resume`
  （`resume_count: 1`、replayed 3 件＋ch03 は新規取得）で完了した。

## 結果

### Stage A（[`artifacts/run1/game_log.report.json`](artifacts/run1/game_log.report.json)）

| 項目 | 値 |
| --- | --- |
| `summary.status` | **`clean`** |
| 検査 | `checks_run: 9` / `checks_skipped: 0` / `findings: 0` / `blocking_findings: 0` |
| 9 検査 | `schema_shape` `canon_refs` `design_alignment` `timeline_travel` `presence_death` `knowledge_boundary` `foreshadow_order` `emitted_markers` **`scene_frame`** → すべて `pass` |
| **`scene_frame`** | `pass`・`evaluated: 3`・**所見 0 件** |
| 試行 / 修復 | `attempts: 1` / `repairs: 0` / `first_attempt_findings: 0` |
| 章 / 場面 / マーカー | 3 / 3 / 25（`time 3`・`location 3`・`learn 4`・`use 9`・`foreshadow 6`） |
| 受理ログ | [`artifacts/run1/game_log.json`](artifacts/run1/game_log.json) = `schema_version: "1.1"` |

### 場面フレームの実測値（3 場面）

| 場面 | `phase` | `outcome_kind` | `rescue` | `carry_forward` |
| --- | --- | --- | --- | --- |
| g01（s01 / setup / t1） | `opening` | `success` | `""` | 2 件（潮札、王都への出発） |
| g02（s02 / investigation / t2） | `development` | `success` | `""` | 2 件（予備の鍵、書き換えられた記録の写し） |
| g03（s03 / resolution / t3） | `ending` | `success` | `""` | 0 件（最後の場面） |

→ `fail_forward` と `rescue` は**一度も使われなかった**。`scene_frame` が実際に判定したのは
phase の並び（`opening` → `development` → `ending`、戻りなし）・`outcome_kind` の列挙値・
最後の場面以外の `carry_forward` 1〜3 件である（`rescue` の枝は `fail_forward` が無いので通らない）。

### Stage B（[`artifacts/run1/rewrite.report.json`](artifacts/run1/rewrite.report.json)）

| 章 | 状態 | 検査 | 所見 | 字数（マーカー除く） | マーカー | 試行 / 修復 | 時系列 checked / skipped | 宣言済みの死者参照 |
| --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |
| ch01 | `clean` | 5 `pass` | 0 | 1,067 | 6 / 6 | 1 / 0 | 1 / 0 | `record_reference`・媒体「潮札」（`johan`） |
| ch02 | `clean` | 5 `pass` | 0 | 1,057 | 10 / 10 | 1 / 0 | 0 / 0 | `record_reference`・媒体「帳面」（`johan`） |
| ch03 | `clean` | 5 `pass` | 0 | 1,059 | 9 / 9 | 1 / 0 | 1 / 1 | `memory_mention`・媒体「回想」（`johan`） |

- 合計 **3,183 字**、必須語率 **1.0**（灯台・鍵・嵐）、題材の禁止語 **0**
  （`選ばれし者` 0・`古代の予言` 0）、`missing_must_include: []`、章ごとの `observations: 0`。
- 既存監査（[`artifacts/run1/audit.json`](artifacts/run1/audit.json)）: 6 検査すべて `pass`、
  **違反 0**、`observations: 2`（いずれも ch03 の `dead_character_reference`。
  「兄の最後の記録に、そうあった。」「その夜に兄が選んだことを、最後の記録は残している。」を
  参照文脈と分類。`reasons: cue:記録` / `cue:記録, cue:その夜`）、CED **0.0** / 1 万字、`suppressed: 0`。
- 導出時系列（[`artifacts/run1/timeline.json`](artifacts/run1/timeline.json)）:
  1 日目 灯台 → 4 日目 王都（経過 3 日）→ 7 日目 灯台（経過 3 日、アリアは灯台を離れて 6 日）。
  ch03 本文の「六日ぶり」は `timeline_consistency` が照合し（`checked 1`・不一致 0）通した。
- gates: `stage_a_clean: true` / `stage_b_clean: true`、run の `status: clean`。
- 本文: [`artifacts/run1/text/ch01.md`](artifacts/run1/text/ch01.md)・
  [`ch02.md`](artifacts/run1/text/ch02.md)・[`ch03.md`](artifacts/run1/text/ch03.md)。

## 観測できたこと

1. **1.1 の Stage A は修復なしで 1 回で `clean` になった。** 4 欄すべてが契約どおりで、
   `scene_frame` の所見は 0 件。ただし N=1・単一タスク・依頼文は 1 種類である。
2. **救済（`rescue`）と `fail_forward` は空のままだった。** 1.1 で足した 4 欄のうち実際に非空だったのは
   `phase` と `carry_forward` だけ。判定の枝の一部（`fail_forward` → `rescue` 必須）は
   今回の走りでは**通っていない**。
3. **持ち越しは記録されただけ**で、次の場面の検査には使われていない（§27「持ち越しの扱い（未実装）」）。
   本文に反映されたかは検査していない（下の「人が確認すること」参照）。
4. **run バンドルはコミットするか複写しないと消える。** Arena 環境が `out/` をスナップショットから
   除外するため、`state.json` を失って `--resume` が exit 2 になった。走りの正本として残ったのは
   `relay/run1/`（依頼 4・応答 4・`served.jsonl`）だけで、そこから同じ run を再構成できた。

## 人が確認すること（未記入）

- [ ] `scene_frame` の所見 0 件は、人が見て妥当か（3 場面の `phase` / `outcome_kind` /
      `carry_forward` の中身が物語として意味を持つか。検査は並びと列挙値と件数しか見ていない）。
- [ ] 持ち越し（`潮札`・`王都への出発` / `予備の鍵`・`書き換えられた記録の写し`）が
      次の章の本文に実際に反映されたか（`artifacts/run1/text/ch0*.md` を読んで確認。検査はしていない）。
- [ ] `rescue` が空だったことをどう扱うか（`fail_forward` が出る題材で回し直すか）。
- [ ] 応答者と回答用チャットの記録（独立性の限界）。
- [ ] 1.0 の凍結実験（[`2026-10-trpg-slice-t01`](../2026-10-trpg-slice-t01/note.md)、
      [`2026-10-full-t01`](../2026-10-full-t01/)）との比較を載せるか。
      **今回は比較していない**（載せるなら runbook §4 のとおり件数の参考値にとどめる）。

## 限界

[`runbook.md`](runbook.md) §4 の記載（人が書いた文言）を転記する:

- L1 は構造・衛生の検査であり、物語の質の証拠ではない。G5（同条件での再現）は主張しない。
  L2/L3 は凍結中。`clean` は意味的な整合性を保証しない。

自動記録された範囲（`results.json`）:

- `claim`: relay run ＝ 本文は外部オペレータが書いたため再現可能なモデルではなく **G5 は主張しない**。
  L1 の構造・衛生のみで、物語の質の証拠ではない。
- `scope`: `Arena.ai x L1; L2/L3 frozen_not_measured`。
- `evaluation_scope.gate_status`: G1 / G2 `reference_only`、G3 / G4 `frozen_not_measured`、
  G5 `unmet_with_unversioned_arena`。

**【人が追記】** この走りに固有の限界（N=1・単一タスク・同一応答者、`rescue` の枝が未通過、
環境リセットによるバンドル再構築の影響 など）。

## 次に試すこと

**【人が追記】**

## 再現

- `relay/run1/` から同じ run を再構成できる。応答 `text` の sha256（先頭 16 桁）:
  Stage A `d4f72370b910448c`、ch01 `ec3ce276c5fc35f7`、ch02 `5b9e4c4d3d18d0de`、ch03 `5193509e5d94d4ef`
  （フル値とリプレイの一致は [`artifacts/run1/replay.report.json`](artifacts/run1/replay.report.json)）。
- 見る場所の対応（runbook §4 は `out/run1/` を指す。コミット済みは `artifacts/`）:

| runbook §4 | このリポジトリでの場所 |
| --- | --- |
| `$B/out/run1/game_log.report.json` | [`artifacts/run1/game_log.report.json`](artifacts/run1/game_log.report.json) |
| `$B/out/run1/game_log.json` | [`artifacts/run1/game_log.json`](artifacts/run1/game_log.json) |
| `$B/out/run1/text/ch0*.md`・`rewrite.report.json` | [`artifacts/run1/text/`](artifacts/run1/text/)・[`artifacts/run1/rewrite.report.json`](artifacts/run1/rewrite.report.json) |
| `$B/results.json`（判定の要約） | [`artifacts/results.json`](artifacts/results.json) |
