---
name: revision-loop
description: 決定論的な所見（継続性違反・文体所見）を批評ノートに変え、明示的なパッチで修正して再監査し、前後を比較する。改稿が別の矛盾を生んでいないか確かめたいとき、同じ指摘の繰り返しを検出したいときに使う。文章の書き直し自体は人間かモデルが行う。
license: MIT
compatibility: Python 3.11+; PyYAML 6+; ネットワーク不要
metadata:
  seed: seed-10-revision-loop
  version: "0.1"
  catalog: research/catalog/techniques.jsonl
  executability: research/catalog/executability.jsonl
---

# 批評・改稿・再検査のループ

所見を**修正可能な単位**に変え、直して、直ったことを確かめる。
このスキルの要点は文章を直すことではなく、**改稿の一周を検査可能にすること**にある。

## いつ使うか

* 監査・文体検査の所見が出て、どこから直すか決めたい。
* 改稿が別の矛盾を生んでいないか確かめたい。
* 同じ指摘が繰り返され、根本原因が疑わしい。
* S2（改稿ループ）の実行内容を、人間が追える形で残したい。

使わない場面: 所見のない原稿の推敲（直す対象がない）。
意味の批評（動機・主題）は L2 の判定を人間が読む。このスキルは決定論的な所見だけを扱う。

## 入力

| 入力 | 必須 | 形式 |
| --- | --- | --- |
| 監査レポート | 必須 | `audit_continuity.py` の JSON 出力 |
| 文体レポート | 任意 | `check_voice.py` の JSON 出力 |
| パッチ | 適用時に必須 | `patch.json`（章・行・anchor・replacement・理由） |

## 手順

1. **批評を作る。** 所見を位置と修正方針つきの批評ノートにする。

   ```bash
   python3 scripts/revise.py --mode plan --audit build/audit.json --out build/critique.json
   ```

2. **書き直す。** 人間かモデルが本文を直す。局所修正が詰まったら企画・台帳に戻る。
3. **パッチを当てる**（機械的に適用する場合）。

   ```bash
   python3 scripts/revise.py --mode apply --text manuscript/ \
       --patch build/patch.json --out revised/
   ```

4. **再監査する。** 改稿後の本文を監査し直す。
5. **比較する。** 解消・残存・新規を数える。

   ```bash
   python3 scripts/revise.py --mode compare \
       --before build/audit-before.json --after build/audit-after.json
   ```

6. **繰り返しを読む。** 同じ所見が残り続けたら、局所修正をやめて設計に戻る。

パッチの書式と批評の読み方は [`references/loop-schema.md`](references/loop-schema.md)。

## 出力

| 出力 | 内容 |
| --- | --- |
| 批評ノート | 所見ごとの位置・問題・修正方針（`CR-001`…） |
| 適用レポート | パッチごとの適用／失敗と理由 |
| 前後比較 | 解消・残存・新規の件数と一覧 |
| 繰り返し検出 | 複数ラウンド残存する所見（根本原因の疑い） |

## 合格条件（このスキル自体の検証）

| 条件 | 判定方法 |
| --- | --- |
| 所見を批評に変えられる | `revision-demo` の 2 件が CR-001/CR-002 になる（`tests/test_revision_loop.py`） |
| パッチを適用できる | `patch.json` の 2 件が適用され、再監査で違反 0 件になる |
| 曖昧なパッチを拒む | anchor の不一致・複数一致は失敗として報告し、推測で当てない |
| 前後を比較できる | 解消 2・残存 0・新規 0 を数え、終了コード 0 を返す |
| 繰り返しを検出できる | 同一所見の連続残存を根本原因の疑いとして報告する |

**この 5 条件は本リポジトリが書いた編集上の基準であり、原典の主張ではない。**

## しないこと

* 所見の解消を「質の向上」と表現しない（数えたのは所見だけ）。
* 改稿回数を質の根拠にしない（回数と品質は比例しない）。
* 失敗したパッチを黙って飛ばさない（失敗は理由つきで残す）。
* 同じ箇所の三度目の書き直しを続けない（設計に戻る合図）。

## うまくいかないとき

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| 新規が増え続ける | 修正が別の矛盾を生む | 一度に戻さず、1 件ずつ当てて再監査する |
| 同じ CR が残る | 根本原因が別にある | 企画核・canon・文体仕様に戻る |
| パッチが当たらない | 本文が変わった | anchor を直す。推測で当てない |

## 参照

* [`references/loop-schema.md`](references/loop-schema.md) — 批評・パッチ・比較の書式
* [`references/measurement.md`](references/measurement.md) — 各手順の合格条件と、判定しないこと
* [`references/techniques.md`](references/techniques.md) — 依拠した技法と、本実装で補った条件
* `research/catalog/executability.jsonl` — 依拠した技法の実行可能度
