---
name: adaptation
description: 原作の再現ではなく機能（情報・感情・関係・緩急）の翻訳として翻案を設計する。各機能に媒体固有の手段と両者（初見・原作読者）への対応を割り当て、削除は理由と代替を記録し、権利を残す。翻案・メディアミックスの設計監査に使う。翻案の出来は判定しない。
license: MIT
compatibility: Python 3.11+; PyYAML 6+; ネットワーク不要
metadata:
  seed: seed-12-adaptation
  version: "0.1"
  catalog: research/catalog/techniques.jsonl
  executability: research/catalog/executability.jsonl
---

# 翻案・機能翻訳の設計

翻案を**再現の努力ではなく機能の翻訳**として書く。
このスキルの要点は、原作の各機能が「別媒体の固有手段でどう担われるか」を
決め、削る機能の働きの行き先を残すことにある。

## いつ使うか

* 原作の「エッセンス」を別媒体に移したい。
* 初見にも原作読者にも届く設計にしたい。
* 削る要素の働きが消えていないか確かめたい。
* 権利の確認漏れを防ぎたい。

使わない場面: 一次創作の設計（`premise-brief` ほか各スキル）。
翻案の質の評価は L2/L3。

## 入力

| 入力 | 必須 | 形式 |
| --- | --- | --- |
| 原作の指定 | 必須 | 題名でよい |
| 翻訳先の媒体 | 必須 | 舞台・漫画・ゲーム等 |

翻案は自己完結。canon は要らない。

## 手順

1. **機能を列挙する。** 情報・感情・関係・緩急の 4 種類で。
2. **各機能を翻訳する。** 媒体固有の手段と、初見・原作読者への対応を書く。
3. **削る機能を記録する。** 理由と、働きを担う代替を書く。
4. **権利を残す。** 原作・範囲・状態（cleared / pending / na）。
5. **検査を実行する。**

   ```bash
   python3 scripts/check_adaptation.py --adaptation adaptation.yaml
   ```

書式は [`references/adaptation-schema.md`](references/adaptation-schema.md)。

## 出力

| 出力 | 内容 |
| --- | --- |
| `adaptation.yaml` | 機能・翻訳・削除・権利 |
| 検査レポート | 構造上の所見（機能・翻訳・削除・権利） |

## 合格条件（このスキル自体の検証）

| 条件 | 判定方法 |
| --- | --- |
| 形式の欠陥を検出できる | `harness/cases/adaptation-demo/adaptation-bad.yaml` の 4 検査すべてを fail にする（`tests/test_adaptation.py`） |
| 良好な翻案設計を通す | `adaptation-demo/adaptation.yaml` が所見 0 件になる |
| 確認中の権利を区別する | `pending` は low の所見になり、`--fail-on medium` では落ちない |
| 出来を判定しない | 検査項目に質の判断が含まれない（`references/measurement.md` の非目標表） |
| CI で使える | `--fail-on medium` で終了コードが 1 になる |

**この 5 条件は本リポジトリが書いた編集上の基準であり、原典の主張ではない。**

## しないこと

* 忠実度（再現の量）を翻案の質と呼ばない。
* 媒体固有の寄与なしに「同じ話の別媒体」で済ませない。
* 削る機能の働きの行き先を書かずに削らない。
* 所見 0 件を「良い翻案」と表現しない。

## うまくいかないとき

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| 機能が列挙できない | 原作の分析不足 | 場面ごとに「何の働きか」を抜く |
| 手段が原作の模写になる | 媒体の理解不足 | 媒体固有の手段を先に棚卸しする |
| 初見への対応が書けない | 前提の置き忘れ | 原作既読を前提にしていないか見直す |

## 参照

* [`references/adaptation-schema.md`](references/adaptation-schema.md) — `adaptation.yaml` の書式
* [`references/measurement.md`](references/measurement.md) — 各検査の合格条件と、判定しないこと
* [`references/techniques.md`](references/techniques.md) — 依拠した技法と、本実装で補った条件
* `research/catalog/executability.jsonl` — 依拠した技法の実行可能度
