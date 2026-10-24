---
name: voice-style
description: 誰が語るか・何を知るか・どの文体で語るかを分離して宣言し、視点の逸脱・自称の揺れ・禁止表現・サンプルからの乖離を根拠位置つきで報告する。章をまたぐ文体の揺れを抑えたいとき、S3 の文体適用の前後を比べたいときに使う。文章の良し悪しは判定しない。
license: MIT
compatibility: Python 3.11+; PyYAML 6+; ネットワーク不要
metadata:
  seed: seed-09-voice-style
  version: "0.1"
  catalog: research/catalog/techniques.jsonl
  executability: research/catalog/executability.jsonl
---

# 語り・視点・文体の統制

「誰が語るか」「何を知るか」「どう書くか」を**分けて宣言する**。
このスキルの要点は文体を均一にすることではなく、**揺れを見える形にすること**にある。

## いつ使うか

* 一人称／三人称限定で、視点の混入が心配な作品を書いている。
* 章ごとに文体が揺れ、どこが違うのか掴みたい。
* AI っぽい定型句・感情の直接命名を機械的に洗い出したい。
* S3（文体適用）の前後で、何が変わったか確かめたい。

使わない場面: 全知視点の作品（視点検査は対象外。禁止表現と乖離のみ使う）。
文体の質の判定は [`evaluation-harness`](../evaluation-harness/SKILL.md) の L2（`prose_control`）の担当。

## 入力

| 入力 | 必須 | 形式 |
| --- | --- | --- |
| 本文 | 必須 | `*.md` / `*.txt`。章ごとに連番 |
| 文体仕様 | 必須 | `voice.yaml`。視点・知識範囲・サンプル・禁止表現 |
| 比較対象 | 任意 | 改稿前の章（S3 の前後比較用） |

書式は [`references/voice-schema.md`](references/voice-schema.md)。

## 手順

1. **視点人物と人称を決める。** 逸脱の条件（何が出たら疑うか）を書く。
2. **語り手の知識範囲を書く。** 知らないことを地の文で断定しないルールにする。
3. **文体サンプルを 300 字程度で固定する。** 以後の照合基準。巧い文である必要はない。
4. **禁止表現を宣言する。** 定型句・感情の直接命名・在庫の比喩を正規表現で書く。
5. **検査を実行する。**

   ```bash
   python3 scripts/check_voice.py --voice voice.yaml --text manuscript/
   ```

6. **medium から読む。** すべて「見るべき箇所」であり、断定ではない。誤検出なら仕様を直す。

## 出力

| 出力 | 内容 |
| --- | --- |
| 文体レポート | 所見の一覧（種別・重要度・章・行・一致箇所） |
| 文体プロファイル | 章ごとの平均文長・文長 CV・会話率（記述のみ） |
| 検査の実行状況 | 各検査が pass / fail / skipped のどれか、skipped の理由 |

## 合格条件（このスキル自体の検証）

| 条件 | 判定方法 |
| --- | --- |
| 仕込んだ逸脱を検出できる | `harness/cases/voice-demo` の 4 件を medium で検出する（`tests/test_voice_style.py`） |
| 良好な章を通す | `voice-demo/text/ch01.md` 単体で所見 0 件になる |
| 仕様が欠けたら落ちない | 該当検査が `skipped` になり、理由がレポートに出る |
| 断定しない | パターン所見は medium 上限、乖離は low（情報提供）。high を出さない |
| CI で使える | `--fail-on medium` で終了コードが 1 になる |

**この 5 条件は本リポジトリが書いた編集上の基準であり、原典の主張ではない。**

## しないこと

* 所見を「誤り」として報告しない（すべて疑い・注意喚起）。
* 文長・会話率の数値を質の点数にしない（均質化は個性を失わせる）。
* 日本語の文体を英語の基準で評価しない（指標は日本語の代理指標に限る）。
* 検出 0 件を「文体が良い」と表現しない。

## うまくいかないとき

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| 同じ行が毎回引っかかる | 誤検出のパターン | 仕様の例外に書くか、パターンを狭める |
| 三人称で内面が全部引っかかる | 視点人物の指定漏れ | `viewpoint.character` と `aliases` を確認 |
| 乖離が毎章出る | サンプルが章と別物 | サンプルを作品の本文から採り直す |

## 参照

* [`references/voice-schema.md`](references/voice-schema.md) — `voice.yaml` の書式
* [`references/measurement.md`](references/measurement.md) — 各検査の合格条件・測定方法・限界
* [`references/techniques.md`](references/techniques.md) — 依拠した技法と、本実装で補った条件
* `research/catalog/executability.jsonl` — 依拠した技法の実行可能度
