---
name: history-timeline
description: 現在の世界状態を説明する歴史を因果と証拠の連鎖として組み立て、年代順・原因参照・痕跡・正史と異説の分離・人物の知識地図を検査する。年表を飾りではなく利害の源にしたいとき、実在史料と創作の混交を防ぎたいときに使う。歴史の説得力は判定しない。
license: MIT
compatibility: Python 3.11+; PyYAML 6+; ネットワーク不要
metadata:
  seed: seed-03-history-timeline
  version: "0.1"
  catalog: research/catalog/techniques.jsonl
  executability: research/catalog/executability.jsonl
---

# 架空史・年表・カノンの構築

歴史を**飾りではなく因果と証拠の連鎖**として書く。
このスキルの要点は年表を長くすることではなく、**現在の状態を説明できること**にある。

## いつ使うか

* 世界の現在を生んだ過去の決定を 3〜5 個に絞りたい。
* 出来事に原因・結果・痕跡を対応させたい。
* 誰が記録し、誰が消されたかを決めたい。
* 人物が知っている歴史と知らない歴史を分けたい。

使わない場面: 歴史を持たない一話完結の小品。
歴史の意味的な破綻は L2 の担当。実在史の考証はこのスキルの範囲外。

## 入力

| 入力 | 必須 | 形式 |
| --- | --- | --- |
| 世界の現在の状態 | 任意 | 一言でよい |
| 実在史の参照資料 | 任意 | 書誌情報つき。創作とは別欄に書く |
| canon | 照合時に必須 | `check_history --canon` に渡す |

## 手順

1. **現在から逆算する。** 現在の状態を生んだ過去の決定を 3〜5 個書く。
2. **原因・結果・痕跡を対応させる。** 痕跡のない出来事は物語に効かない。
3. **記録者と消された者を決める。** 正史と異説を分ける。
4. **実在史料と創作を分ける。** 引用には書誌情報を付け、創作に権威を借りない。
5. **検査を実行する。**

   ```bash
   python3 scripts/check_history.py --history history.yaml --canon canon/
   ```

書式は [`references/history-schema.md`](references/history-schema.md)。

## 出力

| 出力 | 内容 |
| --- | --- |
| `history.yaml` | 時代区分・年表・史料・正史と異説・知識地図 |
| 検査レポート | 構造上の所見（年代・因果・痕跡・分離・知識） |

## 合格条件（このスキル自体の検証）

| 条件 | 判定方法 |
| --- | --- |
| 形式の欠陥を検出できる | `harness/cases/history-demo/history-bad.yaml` の 5 検査すべてを fail にする（`tests/test_history_timeline.py`） |
| 良好な年表を通す | `history-demo/history.yaml` が所見 0 件になる |
| canon が無くても落ちない | 人物の照合を省き、年表内の参照だけを検査する |
| 説得力を判定しない | 検査項目に質の判断が含まれない（`references/measurement.md` の非目標表） |
| CI で使える | `--fail-on medium` で終了コードが 1 になる |

**この 5 条件は本リポジトリが書いた編集上の基準であり、原典の主張ではない。**

## しないこと

* 年表の長さを質と混同しない。
* 実在史の証拠として『太古の神話』を扱わない。
* 神話・歴史の比較の地域的な偏りを無視しない（出典の文化圏を記録する）。
* 所見 0 件を「良い歴史」と表現しない。

## うまくいかないとき

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| 因果が循環する | 原因と結果の取り違え | 現在から逆算し直す |
| 知識地図が引っかかる | 人物 ID の不一致 | canon の人物 ID と完全一致させる |
| 引用が引っかかる | 書誌情報の欠落 | citation を書くか、origin を adapted にする |

## 参照

* [`references/history-schema.md`](references/history-schema.md) — `history.yaml` の書式
* [`references/measurement.md`](references/measurement.md) — 各検査の合格条件と、判定しないこと
* [`references/techniques.md`](references/techniques.md) — 依拠した技法と、本実装で補った条件
* `research/catalog/executability.jsonl` — 依拠した技法の実行可能度
