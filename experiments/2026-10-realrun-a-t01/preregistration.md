# バッチ A の事前登録（走らせる前に固定した判定規則）

- 日付: 2026-10-26（**標本を 1 つも走らせる前に記録**）
- 機械可読な実体: [`preregistration.json`](preregistration.json)。計測スクリプトはこのファイルの
  閾値だけを使う（結果を見てから規則を書き換えないため）。
- 位置づけ: [`docs/two_stage_slice.md`](../../docs/two_stage_slice.md) §21。

## 何を決めたいのか

いま詰まっているのは実本文の量である。地名検査は clean 9 章で偽陽性 0 だが、その 9 章は
3 走り・同一 canon のもので、事例表 18 件はこちらが書いた文だ。二段構成の価値も n=1〜3 でしか
測っていない。ここで**小さく、先に規則を決めた実走り**を 1 巡して、次の判断材料にする。

このバッチで決めるのは 3 つだけである。

1. 地名の観測は、どの枝に出るか（`off_log` / `undeclared`）。
2. 章の長さは目安 1,000〜1,400 字に入るか（P1-8 の再発）。
3. 同じ検査が繰り返し落ちるか（次の修正対象の特定）。

## 条件（固定）

- Stage B のみ。プロンプトは v1.1（`stage-b-rewrite`）。
- 入力は [`inputs/`](inputs/)（canon・design・`game_log.json`）。ログは走らせる前に
  `check_gamelog.py` で clean を再確認する。
- `--observe-surface` を付ける。付け忘れた標本は「観測なし」として記録し、判定に使わない。
- 標本は 3 つ（`sample-1`〜`sample-3`）。同じ条件で、回答だけを毎回新しく書く。
- temperature 0.8、`--max-attempts 2`。

## 判定規則（結果を見る前に固定）

### R1: 地名の枝

目的地を 2 つに分ける。`off_log` = canon の locations に無い。`undeclared` = canon にあるが、
その章の移動として宣言されていない。

| 観測 | 判定 | その後の行動 |
| --- | --- | --- |
| 0 件 | `no_examples` | advisory のまま据え置き、採否は決めない |
| `off_log` 0・`undeclared` > 0 | `drop_undeclared_branch` | 「未宣言」の枝を削除し、残る枝だけで再測定 |
| `off_log` > 0・`undeclared` 0 | `narrow_branch_only` | 狭い枝の候補として保持（**まだ blocking にしない**） |
| 両方 > 0 | `inspect_both` | 人が読む。自動の採否はしない |

**このバッチでは blocking 化を決めない。** 採否はより大きな標本での別バッチ。

### R2: 章の長さ（目安 1,000〜1,400 字、3 章中 2 章以上）

| 結果 | 判定 | その後の行動 |
| --- | --- | --- |
| すべての標本で 2/3 以上 | `length_ok` | 目標値もプロンプトも動かさない |
| どの標本でも 2/3 未満 | `fix_prompt_target` | **目標値ではなくプロンプト側**を直す |
| 標本によって違う | `mixed` | 目標値は動かさず、A2（別バッチ・別登録）で再測 |

### R3: 繰り返す失敗

2 標本以上で所見を出した検査を `recurring` として列挙する。あればそれを次の修正対象にする。
どの検査も 2 標本以上では落ちないなら `no_recurring_failure`（検査は律速ではない）。

## 測る量

主: 章ごとの chars、`expected_markers` と `found_markers`、`status`、`blocking_findings`、
`attempts`（修復回数）、`observations` の目的地と枝、所見の check 別・severity 別。

副: CED（`scripts/compare_l1_arms.py` で別途）。**判定には使わない。**

## 主張しないこと

- L2/L3（意味の整合・質）は `frozen_not_measured` のまま。G3/G4 は未測定、G5 は operator 方式では
  到達しない（同一 seed で同一出力を作れない）。
- 面白さ・読みやすさの比較はしない。
- 観測は**事例**であって率ではない。このバッチで偽陽性率は主張しない。
- 応答の独立性は保証されない（operator が同じエージェントである可能性がある）。`provenance` に
  `origin` を記録し、`unspecified` を「新規」とみなさない。

## 打ち切り

3 標本が揃うか、修復上限で停止した時点で測る。**途中で結果を見て条件を変えない。**
足りないと分かった場合は、走らせる前に A2 として別途登録する。
