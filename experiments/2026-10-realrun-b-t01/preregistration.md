# バッチ B の事前登録（走らせる前に固定した判定規則）

- 日付: 2026-10-27（**標本を走らせる前に記録**）
- 機械可読な実体: [`preregistration.json`](preregistration.json)。計測スクリプトは閾値と
  プロンプト digest をこのファイルから読む（結果を見てから規則を書き換えないため）。
- 位置づけ: [`docs/two_stage_slice.md`](../../docs/two_stage_slice.md) §23。
- 前段: バッチ A の結果は同文書 §21.1、プロンプト v1.2 は §22。

## 何を決めたいのか

まだ実応答で通していないのは、固定した canon・設計を使う段ではなく、**S1 全体**
（plan → 8 設計 → draft）である。このバッチでは 1 標本だけを通し、どの段で
初回不適合・修復／再試行・未解決が起きるかと、最終本文の L1 ゲート・長さを記録する。

決める／記録するのは次である。

1. 登録した条件どおりの S1 全体だったか（B0）。
2. 完走し、設計の fail-open やゲート不合格が隠れていないか（B1）。
3. **初回所見を、修復で消えたものも含めて数える**と、どこで落ちたか（B2）。
4. 章・合計の長さが目安に入るか（B3）。
5. 最終本文の継続性監査が全検査実行・high なしで終わるか（B4）。

## 「同一 canon」の解釈（元々の設計思想による）

このバッチの「同一 canon」は、**この run の plan が一度だけ作った単一の canon を、
8 設計と draft が読む**という意味である。バッチ A の `inputs/canon` は再利用しない。

根拠:

- [`docs/project.md`](../../docs/project.md) は「plan は canon を作り、design は
  plan run の canon を読み、draft は plan の canon と design の設計書を読む」とする。
- [`docs/two_stage_slice.md`](../../docs/two_stage_slice.md) §15.2 は、固定 canon と
  固定設計で draft 段だけを比べたものを「S1 全体ではない」と明記している。

したがって実行コマンドには `--canon` を付けない。生成された canon は run 内に残り、
計測時に 6 つの JSON の sha256 を記録する。`run-summary.json` に `plan.attempts` が
無い走りは、外部 canon を再利用した別条件として条件違反にする。

## 条件（固定）

- タスク `t01`、system `s1`、`--stage all`、設計段あり。設計書は
  `brief, world, history, character, relation, plot, scene, voice` の 8 種。
- プロンプトは現在の S1 セットを使う。S1 経路で **v1.2 なのは `draft-chapter`** であり、
  他のテンプレートも版と digest を `preregistration.json` に固定する。
  プロンプト本文はこの登録には含めない。
- seed `0`、temperature `0.8`。試行上限はパイプライン既定（plan 2、各設計書 2、各章 2）。
- 標本は 1 つ（`sample-1`）。回答待ちのたびに未完成 run を消して再実行しても、
  relay に残る同一標本の応答を再生するだけであり、新しい標本にはしない。
- 生成は `chat_operator.py` のリレー。実応答をこちらで作文しない。

## 判定規則（結果を見る前に固定）

### B0: 条件

task/system/stage/seed/temperature、plan による canon 生成、8 設計の集合、
プロンプト digest を照合する。不一致なら `condition_violation` とし、
他の verdict を主張に使わない（数値は参考として残す）。

### B1: 完走とゲート

| 結果 | 判定 |
| --- | --- |
| `status=pass` かつ 8 設計すべて clean | `complete_pass` |
| 完走したが `status=fail`、8 設計すべて clean | `complete_but_gate_fail` |
| 完走したが設計に unresolved / missing がある | `complete_with_unresolved_design` |
| `run-summary.json` が無い | `incomplete` |

設計段は fail-open（未解決でも次へ進む）ため、完走だけでは合格と呼ばない。

### B2: 初回所見（修復で消えたものも数える）

**主数え方は初回である。最終報告で消えていても数える。** バッチ A の R3 が
曖昧だった点は、ここで明示して解消する。最終所見は別欄に併記する。

- **plan**: `attempts > 1`、または `plan/attempt-1.error.txt` があれば初回失敗。
- **設計**: 各 `design/<doc>.report.json` の `first_attempt.findings` を数える。
  最終 `findings` とは分ける。完全一致したまま最終から消えた件数は補助値として出す。
- **draft**: `draft/<chapter>-attempt-1.issues.txt` がある、または attempt 2 の
  応答がある章を、初回受理条件に落ちた章として数える。
- **監査**: S1 には改稿段がないので、continuity 監査は最終本文への所見として
  B4 で数え、B2 には混ぜない。

判定は `first_attempt_clean` / `first_attempt_findings_repaired` /
`first_attempt_findings_remain_nonblocking`（修復対象でない所見が残る）/
`first_attempt_findings_unresolved` とする。N=1 なので「繰り返す失敗」とは呼ばない。
落ちた段・設計書・check 名を列挙するに留める。

### B3: 長さ

章 1,000〜1,400 字が 3 章中 2 章以上、かつ合計 3,000〜4,200 字なら `length_ok`。
片方だけなら `length_mixed`、両方外れれば `length_outside`。

### B4: 最終本文の監査（L1）

high 違反 0 かつ `checks_skipped=0` なら `audit_no_high_all_checks_ran`。
high があれば `audit_high_present`、未実行検査があれば
`audit_incomplete_coverage`。これは意味的整合の保証ではない。

## 測る量

主: plan attempts／初回失敗、canon 件数・被覆・sha256、設計書ごとの
status/attempts/repairs と初回・最終 findings（check 別・severity 別）、
章ごとの字数・試行・初回 issues・補完マーカー、必須語率、gates/status、
監査の違反内訳と未実行検査、応答数と provenance 内訳。

副: CED は監査の参考値として記録するが判定には使わない。バッチ A とは canon が
異なるため、本文同士の対比較として扱わない。

## 主張しないこと

- L2/L3（意味の整合・質）は `frozen_not_measured` のまま。G3/G4 は未測定、
  G5 は operator 方式では到達しない。
- 面白さ・読みやすさは測らない。N=1 で率や再発率は主張しない。
- 応答の独立性は保証されない。`provenance` が `unspecified` の応答を「新規」と
  読み替えない。台本走行は配線確認であり実応答ではない。

## 打ち切り

`sample-1` が完走するか、回答待ちでない失敗で止まった時点で測る。
**途中で結果を見て条件を変えない。** 標本を足す場合は、走らせる前に B2 として登録する。
