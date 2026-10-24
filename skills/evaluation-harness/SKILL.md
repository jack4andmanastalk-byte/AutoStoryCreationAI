---
name: evaluation-harness
description: 生成した作品を、決定論的検査（L1）・モデル判定（L2）・人間評価（L3）に分けて測り、ベースラインとの差を欠陥密度と次元別プロファイルで報告する。改稿やプロンプト変更の前後を比べたいとき、品質を単一スコアに潰さずに判断したいときに使う。
license: MIT
compatibility: Python 3.11+; PyYAML 6+; ネットワーク不要（L2 は外部コマンドとして接続）
metadata:
  seed: seed-13-evaluation-harness
  version: "0.1"
  catalog: research/catalog/techniques.jsonl
  executability: research/catalog/executability.jsonl
---

# 評価ハーネス

> 現在のリポジトリ運用は L1-only。L2/L3 の実証・較正・追加開発は 2026-10-24 に凍結。
> この SKILL.md と関連 fixture は評価層の仕様を保存するものであり、新規の L2/L3 評定を
> 促すものではない。運用範囲と報告制約は
> [`docs/evaluation_scope.md`](../../docs/evaluation_scope.md) を参照する。

**単一の点数を出さない。** 品質は複数の独立した能力に分かれており、
1 つの数字にすると「何が悪くなったか」が消える。このスキルは 3 層を別々に走らせ、
失敗を類型化して、次の変更先（スキル）まで割り当てる。

## いつ使うか

* 改稿・プロンプト変更・モデル変更の前後を比べたい。
* 「良くなった気がする」を、再現可能な差に変えたい。
* 生成が画一化していないか（文体・構成の均質化）を点検したい。
* 失敗の種類を分類し、どのスキルを直すか決めたい。

使わない場面: 1 本の作品の出来を採点したいだけのとき。このスキルは**比較**のための道具。

## 3 層

| 層 | 何を測るか | 実装 | 停止条件 |
| --- | --- | --- | --- |
| **L1** 決定論的 | 整合性違反、禁止パターン、長さ・会話率・文長のばらつき | `src/asc/story`、`src/asc/evaluation/metrics.py` | high の整合性違反が 1 件でもあれば失敗 |
| **L2** モデル判定 | ルーブリック 6 次元の点数と根拠 | 外部コマンド（JSON プロトコル） | 根拠の無い判定は無効 |
| **L3** 人間評価 | ペア比較の選好 | ラベル JSON | — |

**L1 で落ちるものを L2 に渡さない。** L2 は L1 の代替ではなく、意味の評価に限る。

## 手順

1. **ルーブリックを選ぶ。** 既定は [`harness/rubrics/story-quality-v0.yaml`](../../harness/rubrics/story-quality-v0.yaml)。
   次元を増やすと比較可能性が落ちるので、まず 6 次元で運用する。
2. **L1 だけを回す**（ネットワーク不要）。

   ```bash
   python3 scripts/run_evaluation.py \
     --candidate manuscript/ --baseline draft/ \
     --canon canon/ --out build/eval/
   ```

3. **L2 を接続する。** 判定器は外部コマンド。標準入力に JSON、標準出力に JSON を返す。

   ```bash
   python3 scripts/run_evaluation.py ... \
     --judge-command "python3 judge_adapter.py"
   ```

   プロトコルは [`references/measurement.md`](references/measurement.md#判定器のプロトコル)。
4. **L3 のラベルを用意する。** ペア比較の結果を JSON で渡すと、L2 との一致率が出る。
5. **チケットを読む。** `report.md` の「改善チケット」が、担当スキルと次の一手を示す。
6. **前回の結果と比べる。** `evaluation.json` を保存し、次回のベースラインにする。

## 入力

| 入力 | 必須 | 備考 |
| --- | --- | --- |
| 候補の章 | 必須 | `*.md` / `*.txt` |
| ベースラインの章 | 比較するなら | 無い場合は単体のプロファイルのみ |
| canon | L1 を使うなら | 無い場合、整合性の層は `skipped` |
| ルーブリック | L2 を使うなら | YAML。次元・問い・アンカー |
| 禁止パターン | 任意 | [`harness/patterns.yaml`](../../harness/patterns.yaml) |
| 判定器 | L2 を使うなら | コマンド or 記録済み判定（fixture） |
| 人間ラベル | L3 を使うなら | JSON |

## 出力

| 出力 | 内容 |
| --- | --- |
| `evaluation.json` | L1 の数値、L2 の判定と根拠、L3 の一致率、比較、チケット、ゲート |
| `report.md` | 人が読む版。ゲート → L1 → L2 → L3 → 比較 → チケット |
| `continuity.json` | 整合性監査の生データ（canon を渡した場合） |

ゲートは 3 つ。

| ゲート | 条件 |
| --- | --- |
| `no_high_severity_continuity` | high の整合性違反が 0 件 |
| `all_verdicts_evidenced` | L2 の全判定に根拠（引用または位置）がある |
| `no_regression` | 欠陥密度と次元得点がベースラインより悪化していない |

## 合格条件（このスキル自体の検証）

| 条件 | 判定方法 |
| --- | --- |
| 3 層が独立に動く | 判定器なしでも L1 が完走する（`tests/test_evaluation.py`） |
| 根拠の無い判定を落とす | evidence 空の次元を `unevidenced` としてゲート失敗にする |
| 悪化だけを失敗にする | 会話率・段落長・文長の変化は「記述統計」で、失敗にしない |
| 長さバイアスを統制する | 文字数差 25% 超でペア比較を省略（`--allow-length-gap` で解除） |
| 順序バイアスを検出する | ペア比較を A/B・B/A の 2 回行い、不一致なら引き分け扱い |
| 較正できる | 人間ラベルがあれば一致率を出す。1 名なら「測れない」と明示 |
| 比較不能を比較しない | 監査カバレッジの差が 30 ポイント超なら CED 比較を無効化 |

## しないこと

* 総合点を出さない。次元ごとのプロファイルを出す。
* 判定器の名前・版・設定を記録せずに比較しない。
* ベンチマークのスコアを最適化しない。失敗の類型を見るために使う。
* 人間の代わりに L2 を最終判断にしない（一致率は 8 割程度が上限）。
* L3 が無いのに「妥当性を確認した」と言わない。

## うまくいかないとき

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| L2 が skipped | 判定器かルーブリックが未指定 | `--judge-command` か `--judge-fixture` を渡す |
| 全部 3 点になる | ルーブリックのアンカーが曖昧 | 5 と 1 のアンカーを具体的な本文の特徴で書き直す |
| 毎回 L2 が失敗 | 判定器が JSON を返していない | 標準出力を JSON のみにする（ログは stderr） |
| 比較で全部「悪化」 | 欠陥の定義が広すぎる | 欠陥は CED・禁止パターン・次元得点だけ。記述統計は失敗にしない |
| CED が比較されない | 監査カバレッジが違う | 両方にマーカーを入れる。無理なら CED を諦めて L2/L3 で見る |

## 参照

* [`references/measurement.md`](references/measurement.md) — 各指標の定義、バイアス統制、判定器プロトコル
* [`references/techniques.md`](references/techniques.md) — 依拠した技法と外部ベンチマークの使い方
* `research/curation/executability_report.md` — なぜ合格条件を明示するのか
