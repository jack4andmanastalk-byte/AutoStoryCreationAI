---
name: scene-information
description: 各場面の目的・対立・変化・緊張の型・知識の流れ・開示計画・伏線の仕掛けと回収を設計書として書く。説明過多・根拠のない驚き・置き忘れの伏線を防ぎたいときに使う。場面の面白さは判定しない。
license: MIT
compatibility: Python 3.11+; PyYAML 6+; ネットワーク不要
metadata:
  seed: seed-07-scene-information
  version: "0.1"
  catalog: research/catalog/techniques.jsonl
  executability: research/catalog/executability.jsonl
---

# 場面の目的・情報・開示の設計

場面を**起きたことではなく仕事**として書く。
このスキルの要点は、各場面が「誰が何を知り、読者に何を開示し、
何を伏せ、何を仕掛け、何を回収するか」を持つことにある。

## いつ使うか

* 場面が「起きたことの羅列」になり、目的が見えない。
* どんでん返しが根拠なし（ご都合）に堕しそうだ。
* 誰が何を知っているかが場面ごとに食い違う。
* 伏線の仕掛けと回収の対応を全章で持ちたい。

使わない場面: 幕・転換点の設計（[`plot-architecture`](../plot-architecture/SKILL.md)）。
本文中の伏線監査は [`continuity-ledger`](../continuity-ledger/SKILL.md)。

## 入力

| 入力 | 必須 | 形式 |
| --- | --- | --- |
| 章立て | 推奨 | 章 ID の一覧でよい |
| canon | 照合時に必須 | `check_scene --canon` に渡す |

## 手順

1. **各場面に仕事を書く。** 目的・対立・変化を 1 文ずつ。
2. **緊張の型を指定する。** 6 語彙（suspense / curiosity / surprise / irony / deadline / quiet）から選ぶ。
3. **知識の流れを追跡する。** 入場時の既知と、場面で得る事実。
4. **開示を計画する。** 開示と保留を分け、保留に理由を書く。得た事実は開示か保留のどちらかに置く。
5. **伏線を仕掛け、回収する。** 回収は実在の布石を指し、仕掛けより前に置かない。
6. **検査を実行する。**

   ```bash
   python3 scripts/check_scene.py --scenes scenes.yaml --canon canon/
   ```

書式は [`references/scene-schema.md`](references/scene-schema.md)。

## 出力

| 出力 | 内容 |
| --- | --- |
| `scenes.yaml` | 場面ごとの仕事・緊張・知識・開示・伏線 |
| 検査レポート | 構造上の所見（目的・緊張・知識・開示・伏線・章の被覆） |

## 合格条件（このスキル自体の検証）

| 条件 | 判定方法 |
| --- | --- |
| 形式の欠陥を検出できる | `harness/cases/scene-demo/scenes-bad.yaml` の 6 検査すべてを fail にする（`tests/test_scene_information.py`） |
| 良好な場面設計を通す | `scene-demo/scenes.yaml` が所見 0 件になる |
| canon が無くても落ちない | 章の被覆が `skipped` になり、理由がレポートに出る |
| 面白さを判定しない | 検査項目に質の判断が含まれない（`references/measurement.md` の非目標表） |
| CI で使える | `--fail-on medium` で終了コードが 1 になる |

**この 5 条件は本リポジトリが書いた編集上の基準であり、原典の主張ではない。**

## しないこと

* 緊張の型を「なんとなく面白い場面」で済ませない。
* 得た事実を開示計画に入れずに放置しない。
* 保留に理由を書かずに伏せない。
* 所見 0 件を「良い場面」と表現しない。

## うまくいかないとき

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| 目的が書けない | 場面の分割不足 | 変化が 2 つある場面は割る |
| 開示が追いつかない | 知識の整理不足 | `relationship-web` の知識表を先に作る |
| 回収が仕掛けより前になる | 章順の誤り | 年表の日付と場面の章を見直す |

## 参照

* [`references/scene-schema.md`](references/scene-schema.md) — `scenes.yaml` の書式
* [`references/measurement.md`](references/measurement.md) — 各検査の合格条件と、判定しないこと
* [`references/techniques.md`](references/techniques.md) — 依拠した技法と、本実装で補った条件
* `research/catalog/executability.jsonl` — 依拠した技法の実行可能度
