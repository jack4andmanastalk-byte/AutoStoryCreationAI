# バッチ B2 の事前登録（history プロンプト v1.1 の介入、1 標本）

- 登録日: 2026-10-27。**sample-2 を走らせる前に固定する。**
- 機械可読な正本: [`preregistration.json`](preregistration.json)
  （条件・プロンプト digest・閾値・判定はすべてこちら。計測はこのファイルの sha256 を結果に記録する）
- 位置づけ: [`docs/two_stage_slice.md`](../../docs/two_stage_slice.md) §24
- 先行バッチ: [`experiments/2026-10-realrun-b-t01/`](../2026-10-realrun-b-t01/note.md)（判定 B0〜B4 の定義は継承）

## 問い

history プロンプト v1.1（history 検査だけが知っていた制約を明記した版）で S1 全体
（plan→8 設計→draft）を 1 標本通したとき、介入対象の `canon_separated` 初回所見は出るか。
バッチ B では同所見が初回に 3 件あり、すべて修復で消えた。

## バッチ B から変えたこと／変えないこと

- **変えたのは 1 点だけ**: `design-history` プロンプトを 1.0 から 1.1 に上げ、
  history 検査（`canon_separated` / `trace_exists` / `knowledge_consistent`）だけが
  知っていた未記載の制約を、検査と同じ意味になるようプロンプトに明記した。
- 変えない: タスク t01、`--system s1 --stage all`、seed 0、temperature 0.8、設計 8 種、
  canon 方針（同一 run の plan が作った単一 canon を 8 設計と draft が読む）、
  他の全プロンプトの版・digest、判定 B0〜B4 の定義と閾値、初回所見の数え方。
- 全テンプレートの name/version/digest と `tasks.yaml` の sha256 は
  `preregistration.json` に固定する（プロンプト本文は登録に含めない）。

## 標本と打ち切り

- 標本は **1 つ**（`sample-2`。全体では 2 番目の S1 実走りだが、条件が一部違うため
  バッチ B と合算して率を出さない）。
- sample-2 が完走するか、回答待ちでない失敗で停止した時点で測る。
  途中で条件・プロンプト・閾値を変えない。足す場合は B3 として事前に登録する。

## 判定

バッチ B の B0〜B4 をそのまま使う。加えて介入判定 H を置く。

| 判定 | 問い | 主な区分 |
| --- | --- | --- |
| B0 | 登録条件どおりか（plan 生成 canon、digest 一致。design-history は v1.1 を要求） | `condition_ok` / `condition_violation` |
| B1 | 完走とゲート（設計 unresolved/missing を隠さない） | `complete_pass` / `complete_but_gate_fail` / `complete_with_unresolved_design` / `incomplete` |
| B2 | 初回不適合はどこで起きたか | `first_attempt_clean` / `first_attempt_findings_repaired` / `first_attempt_findings_remain_nonblocking` / `first_attempt_findings_unresolved` / `incomplete` |
| B3 | 長さ（章 1,000〜1,400 字が 2 章以上、合計 3,000〜4,200 字） | `length_ok` / `length_mixed` / `length_outside` |
| B4 | 最終本文監査（high 0 件かつ checks_skipped=0） | `audit_no_high_all_checks_ran` / `audit_high_present` / `audit_incomplete_coverage` / `not_measured` |
| H | history の `canon_separated` 初回所見が出たか | `target_findings_absent` / `target_findings_present` / `incomplete` |

**数え方（B2 と同じ）**: 設計所見は修復で消えても `first_attempt.findings` を数える。
plan は attempts>1 または初回エラー、draft は初回不受理の章を数える。監査所見は B4 で別に数える。

## 交絡と主張しないこと

- 生成担い手（同一の Arena エージェント）はバッチ B で同じ指摘を経験済みである。
  したがって所見の増減を **プロンプト変更だけに帰因できない**。H は因果の判定ではなく、
  対象所見が出たかどうかの記録である。
- N=1。率・再発率・効果量は主張しない。バッチ B との比較は記述的対照に留める
  （canon は新規生成され、本文同士の対比較にもならない）。
- L2/L3 は `frozen_not_measured` のまま。面白さ・品質は測らない。G5 は operator 方式では到達しない。
- 応答の独立性は保証されない。provenance が記録されていない応答を新規生成だったとみなさない。
- scripted の配線確認を実モデル応答として扱わない。
