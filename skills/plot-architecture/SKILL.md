---
name: plot-architecture
description: 幕割り・転換点・副筋・結末・未回収を設計書として書く。型をなぞるのではなく各転換点を主人公の選択に結び付け、副筋を本筋に合流させる。中だるみ・投げっぱなしの伏線・都合のよい結末を防ぎたいときに使う。筋の面白さは判定しない。
license: MIT
compatibility: Python 3.11+; PyYAML 6+; ネットワーク不要
metadata:
  seed: seed-06-plot-architecture
  version: "0.1"
  catalog: research/catalog/techniques.jsonl
  executability: research/catalog/executability.jsonl
---

# 筋立て・転換・結末の設計

筋を**出来事の並びではなく選択の連鎖**として書く。
このスキルの要点は、各転換点が主人公（または担い手）の選択であり、
副筋が本筋に合流し、結末が逆算されていることにある。

## いつ使うか

* 中だるみ（第 2 幕の失速）を構造で防ぎたい。
* 伏線の置き忘れ・投げっぱなしを棚卸ししたい。
* 副筋が本筋と交わらないまま終わりそうだ。
* 「起きたことの羅列」になった筋を選択の連鎖に戻したい。

使わない場面: 場面単位の設計（[`scene-information`](../scene-information/SKILL.md)）。
最終稿の伏線監査は [`continuity-ledger`](../continuity-ledger/SKILL.md)。

## 入力

| 入力 | 必須 | 形式 |
| --- | --- | --- |
| ログライン | 推奨 | 1 文 |
| canon | 照合時に必須 | `check_plot --canon` に渡す |

## 手順

1. **結末から逆算する。** 型・要約・余韻を先に決める。
2. **幕に割り、各幕に問いを立てる。** 章の束に意味を持たせる。
3. **転換点を 3～5 件置く。** 各転換点は出来事ではなく選択で書く。
4. **副筋に節目と合流を書く。** 交わらない副筋は削るか合流させる。
5. **未回収を棚卸しする。** 布石に結び付けるか、意図的と宣言する。
6. **検査を実行する。**

   ```bash
   python3 scripts/check_plot.py --plot plot.yaml --canon canon/
   ```

書式は [`references/plot-schema.md`](references/plot-schema.md)。

## 出力

| 出力 | 内容 |
| --- | --- |
| `plot.yaml` | 幕・転換点・副筋・結末・未回収 |
| 検査レポート | 構造上の所見（幕・転換点・副筋・結末・未回収の照合） |

## 合格条件（このスキル自体の検証）

| 条件 | 判定方法 |
| --- | --- |
| 形式の欠陥を検出できる | `harness/cases/plot-demo/plot-bad.yaml` の 5 検査すべてを fail にする（`tests/test_plot_architecture.py`） |
| 良好な筋立てを通す | `plot-demo/plot.yaml` が所見 0 件になる |
| canon が無くても落ちない | 章・伏線の照合が弱くなり、残りは検査する |
| 面白さを判定しない | 検査項目に質の判断が含まれない（`references/measurement.md` の非目標表） |
| CI で使える | `--fail-on medium` で終了コードが 1 になる |

**この 5 条件は本リポジトリが書いた編集上の基準であり、原典の主張ではない。**

## しないこと

* 型（beat sheet 等）を逆算なしになぞらない。
* 転換点を「出来事が起きた」で書かない（選択で書く）。
* 未回収を黙って残さない（布石か意図的宣言のどちらか）。
* 所見 0 件を「良い筋」と表現しない。

## うまくいかないとき

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| 幕の問いが立たない | ログライン不足 | 主人公の選択を 1 文で書いてから戻る |
| 転換点が出来事になる | 主体不足 | 「誰が何を選び、何を捨てたか」に書き換える |
| 副筋が合流しない | 設計不足 | 節目を削るか、合流の章を決める |

## 参照

* [`references/plot-schema.md`](references/plot-schema.md) — `plot.yaml` の書式
* [`references/measurement.md`](references/measurement.md) — 各検査の合格条件と、判定しないこと
* [`references/techniques.md`](references/techniques.md) — 依拠した技法と、本実装で補った条件
* `research/catalog/executability.jsonl` — 依拠した技法の実行可能度
