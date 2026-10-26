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
| `prompts/` | 3 章ぶんの Stage B プロンプト（`ch0N.prompt.md`、まとめた `ALL.md`、`index.json` に `prompt_hash`）。パイプラインと同じ関数で描画し、実際の要求とバイト一致を確認済み |
| `results.json` | 計測スクリプトの空の出力（`not_run` / `not_enough_data`） |
| `sample-1…3/`, `relay/sample-1…3/` | **まだ無い**（走行時に作られる） |

プロンプトは 3 標本で共通（seed はプロンプトに入らない）。標本の違いは回答だけなので、
`sample-2`・`sample-3` は前の標本の回答を見せずに書く。

## 走行の記録（進行中）

応答は利用者がこのセッションで提示した本文を、そのまま（逐語で）記録している。作文・修正はしていない。

### sample-1 / ch01（2026-10-26、1 試行・修復 0）

| 項目 | 値 |
| --- | --- |
| status | **clean** |
| 字数 | **1,096 字**（目安 1,000〜1,400 の**内側**） |
| マーカー | 6/6（`marker_sequence` 12 件評価・所見 0） |
| 所見 | 0（`character_boundary` 4・`fact_boundary` 5・`voice_contract` 2 を評価） |
| 時系列 | checked 1 / skipped 1（strict ではない） |
| 観測（地名） | **0 件** |

**時系列の読み方（記録しておく）**: 本文は「往復六日」と 4 回書いている。これは `DAY_PATTERNS`
（`N日ぶり`・`N日目`・`N日後`・`N日かけて/歩/の道のり`）のどれにも当たらないため、**照合されていない**
（`skipped` の 1 件は「数日分」の抽象表現）。人手で確かめると、灯台 1 日目 → 王都 4 日目 →
灯台 7 日目なので往復 6 日で、本文はログと**合っている**。つまり「合っていたが、検査は見ていない」。
数字の書き方（「往復六日」）が検査の語彙の外にあるという、既知の限界の実例である。

### sample-1 / ch02（2026-10-26、1 試行目は **不合格** → 修復を要求）

| 項目 | 値 |
| --- | --- |
| 1 試行目の status | **unresolved**（blocking 1） |
| 字数 | 1,025 字（目安の内側） |
| マーカー | 7/7 |
| 所見 | `fact_boundary` **medium・blocking** 1 件: 未開示の事実 F-04 の語「三年前」が本文にある |
| 時系列 | checked 1 / skipped 0（「三日歩いた末」が `travel` として照合され、許容 3 日と一致） |
| 観測（地名） | 0 件 |
| 次 | 修復要求 `ch02-repair-a2`（`prompt_hash` `f3568158a359895e`）を発行して停止（exit 3） |

**予測どおりの失敗である。** ch01 の結果を受けて「この章で『三年前』を書くと `fact_boundary` で止まる」
と先に伝えていた。v1.1 の走りでも同じ語で 1 回止まっている（`2026-10-stageb-v11-t01` の ch02）。
ただし今回は、**ログの前提文そのものに「三年前に死んだ人物」と書かれている**点が効いている。
前提を読んだ書き手が「三年前」を使うのは自然で、語彙境界のねじれが実モデル本文でも再現した。

**検査が見ていない数字**: 末尾の「道のりは三日」は `DAY_PATTERNS` の語順（`三日の道のり`）と逆なので
照合されていない。値としては正しい（王都 → 灯台は 3 日）が、ch01 の「往復六日」と同じく**検査の外**。

## 走行後にここへ書くこと

- 標本ごとの `status`、章ごとの字数・マーカー・修復回数、所見の検査名。
- `observations` の目的地と枝。
- `results.json` の verdict（読み替えずに引用する）。
- operator が誰で、`provenance.origin` が何だったか（独立性の限界）。

## 限界

- 3 標本は分布ではない。率（偽陽性率・合格率）は主張しない。
- 同じ canon・同じタスク・同じプロンプトの 1 条件だけを見る。条件間の比較はしない。
- L1 の量（字数・マーカー・所見）だけで、読んで面白いかは判定しない。
