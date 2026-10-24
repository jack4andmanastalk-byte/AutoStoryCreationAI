---
name: world-rules
description: 世界観を雰囲気ではなく人物の選択を拘束する規則系として設計し、公理・コスト・例外の条件・地理の対応・開示順序を検査する。設定が物語の帰結に効いているか確かめたいとき、都合のよい追加・撤回を防ぎたいときに使う。世界の面白さは判定しない。
license: MIT
compatibility: Python 3.11+; PyYAML 6+; ネットワーク不要
metadata:
  seed: seed-02-world-rules
  version: "0.1"
  catalog: research/catalog/techniques.jsonl
  executability: research/catalog/executability.jsonl
---

# 世界の規則・制度・制約の設計

世界観を**雰囲気の記述ではなく規則系**として書く。
このスキルの要点は設定を増やすことではなく、**設定が物語を拘束すること**にある。

## いつ使うか

* 世界の「大きな嘘」を一つに絞り、派生する規則を列挙したい。
* 力・制度・移動にコストを付け、抜け道を塞ぎたい。
* 地理が場面の制約として機能しているか確かめたい。
* 説明の開示順序を計画し、前出し・後出しを防ぎたい。

使わない場面: 現実世界そのままの日常物（規則の宣言が要らない）。
規則の意味的な破綻は L2（`world_rule_consistency`）の担当。

## 入力

| 入力 | 必須 | 形式 |
| --- | --- | --- |
| ジャンルとトーン | 任意 | 一言でよい |
| 参照資料 | 任意 | 現実世界の制度・地理のメモ |
| canon | 照合時に必須 | `check_world --canon` に渡す |

## 手順

1. **大きな嘘を一つ決める。** そこから派生する規則を列挙する。
2. **各規則にコストを付ける。** 代償・制約・例外の条件を書く。
3. **誰の生活を変えるか書く。** 規則が職業・政治・日常に及ぶ先を制度にする。
4. **開示順序を作る。** 必要な情報だけを、必要になる章に割り当てる。
5. **検査を実行する。**

   ```bash
   python3 scripts/check_world.py --world world.yaml --canon canon/
   ```

書式は [`references/world-schema.md`](references/world-schema.md)。

## 出力

| 出力 | 内容 |
| --- | --- |
| `world.yaml` | 公理・規則とコスト・制度・地理・開示順序 |
| 検査レポート | 構造上の所見（公理・コスト・例外・地理・開示） |

## 合格条件（このスキル自体の検証）

| 条件 | 判定方法 |
| --- | --- |
| 形式の欠陥を検出できる | `harness/cases/world-demo/world-bad.yaml` の 5 検査すべてを fail にする（`tests/test_world_rules.py`） |
| 良好な世界を通す | `world-demo/world.yaml` が所見 0 件になる |
| canon が無くても落ちない | 地理の照合が `skipped` になり、理由がレポートに出る |
| 面白さを判定しない | 検査項目に質の判断が含まれない（`references/measurement.md` の非目標表） |
| CI で使える | `--fail-on medium` で終了コードが 1 になる |

**この 5 条件は本リポジトリが書いた編集上の基準であり、原典の主張ではない。**

## しないこと

* 設定の量を質と混同しない（量と質は比例しない）。
* 現実の文化・宗教を流用したままにしない（文脈と権利への配慮を `notes` に残す）。
* 規則を都合よく追加・撤回しない（変更は版として記録する）。
* 所見 0 件を「良い世界」と表現しない。

## うまくいかないとき

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| コストが書けない | 規則が願望になっている | 規則を破った場合の帰結から逆算する |
| 地理が引っかかる | 表記揺れ | canon の場所 ID と完全一致させる |
| 開示先が引っかかる | 章の指定間違い | canon の年表にある章 ID を使う |

## 参照

* [`references/world-schema.md`](references/world-schema.md) — `world.yaml` の書式
* [`references/measurement.md`](references/measurement.md) — 各検査の合格条件と、判定しないこと
* [`references/techniques.md`](references/techniques.md) — 依拠した技法と、本実装で補った条件
* `research/catalog/executability.jsonl` — 依拠した技法の実行可能度
