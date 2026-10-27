---
name: continuity-ledger
description: 長編・連載の本文と設定台帳（canon）を照合し、人物の生死・所在・知識・時系列・伏線の矛盾を根拠位置つきで報告する。章を追加した後や、改稿で前の章と食い違っていないか確かめたいときに使う。LLM の記憶に頼らず、決定論的に検査する。
license: MIT
compatibility: Python 3.11+; PyYAML 6+; ネットワーク不要
metadata:
  seed: seed-08-continuity-ledger
  version: "0.1"
  catalog: research/catalog/techniques.jsonl
  executability: research/catalog/executability.jsonl
---

# 継続性台帳と矛盾検出

本文を読む前に、**照合先**を用意する。このスキルの要点は「矛盾を探す」ことではなく、
**矛盾を判定できる形で状態を外に出す**ことにある。

## いつ使うか

* 章を書き足した／改稿したあと、以前の章と食い違っていないか確かめたい。
* 人物の生死・所在・知識が増え、記憶で追えなくなった。
* 伏線の設置と回収の位置を一覧したい。
* 分岐・連載など、同じ設定を長く使う作品を書いている。

使わない場面: 一章だけの短編で、設定が本文内で完結している場合。
意味の破綻（動機の飛躍、主題の不一致）の判定は [`evaluation-harness`](../evaluation-harness/SKILL.md) の担当。

## 入力

| 入力 | 必須 | 形式 |
| --- | --- | --- |
| 本文 | 必須 | `*.md` / `*.txt`。`ch01.md` のように連番で並ぶ |
| canon | 必須 | `characters` / `facts` / `locations` / `timeline` / `foreshadowing` / `suppressions`（YAML または JSON） |
| 意図的な矛盾 | 任意 | `suppressions.yaml`。理由を必ず書く |

canon の書式とマーカーの一覧は [`references/canon-schema.md`](references/canon-schema.md)。

## 手順

1. **canon を用意する。** 人物の生死・所在・既知の事実、場所間の移動日数、章ごとの日付、
   伏線の設置・回収を書く。分からない項目は空けてよい（空欄は「未検査」として報告される）。
2. **本文にマーカーを置く。** 状態が変わった箇所に `{{death: boris}}`、`{{learn: aria fact=F-07}}`
   などを書く。マーカーは地の文に混ざってよい（描画時は除去する）。
3. **監査を実行する。**

   ```bash
   python3 scripts/audit_continuity.py \
     --canon canon/ --text manuscript/ \
     --out build/audit/report.json --ledger build/audit/ledger.json \
     --markdown build/audit/report.md
   ```

4. **high から読む。** high はマーカーか発話に裏づけられた違反。medium は
   分類できない名前の言及・時間のずれなど、誤検出の余地があるもの。low は情報提供。
   死者への言及のうち、引用・参照語彙・助詞から参照文脈と分類できたものは
   `observations` に残し、違反には数えない。
5. **意図した矛盾は除外する。** 分類できない回想・夢・遺体・代役などは
   `suppressions.yaml` に理由つきで登録する。除外した件数もレポートに残る。
6. **台帳を次の章へ渡す。** `--ledger` の出力（人物の状態・既知の事実・伏線の状態）を
   次の執筆に渡す。本文ではなく、この JSON を入力にする。

## 出力

| 出力 | 内容 |
| --- | --- |
| 矛盾レポート | 違反の一覧（種別・重要度・章・根拠位置・canon 参照・根拠の種類） |
| 状態台帳 | 人物ごとの生死・所在・既知の事実・最終登場章 |
| 伏線台帳 | 設置章・回収章・未回収かどうか |
| 検査の実行状況 | 各検査が pass / fail / skipped のどれか、skipped の理由 |
| 密度 | 1 万文字あたりの違反数（長さの違う作品を比べるため） |

## 合格条件（このスキル自体の検証）

| 条件 | 判定方法 |
| --- | --- |
| 仕込んだ矛盾を検出できる | `harness/cases/demo` の 7 件を再現する（`tests/test_continuity.py`） |
| 意図的な矛盾を除外できる | `suppressions.yaml` の 1 件が `suppressed` に入り、`violations` に入らない |
| canon が欠けたら落ちない | 該当検査が `skipped` になり、理由がレポートに出る |
| 誤検出を重要度で分ける | 参照文脈の名前は `observations`、分類できない言及は medium、マーカー/発話裏づけは high |
| CI で使える | `--fail-on high` で終了コードが 1 になる |

**この 5 条件は本リポジトリが書いた編集上の基準であり、原典の主張ではない。**

## しないこと

* 意味の破綻を「矛盾」として報告しない（L1 では判定できない）。
* 名前が出ただけで「生きている」と断定しない（回想・遺体・手紙がある）。
* canon を勝手に書き換えない。変更は `revision` として記録し、影響範囲を人が承認する。
* 検出 0 件を「矛盾がない」と表現しない。**検査していない項目がある**（`skipped`）。

## うまくいかないとき

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| 違反が 0 件で、検査も 0 件 | canon が空 | `characters` と `timeline` を最低限書く |
| 同じ人物の違反が大量に出る | 死亡章の指定漏れ | `{{death}}` か `status_since` を確認 |
| 回想が毎回引っかかる | 意図的な矛盾が未登録 | `suppressions.yaml` に章を限って登録 |
| 移動時間が誤検出される | 移動日数表が不完全 | `locations.travel_days` を埋める。未定義の組は判定しない |

## 参照

* [`references/canon-schema.md`](references/canon-schema.md) — canon とマーカーの書式
* [`references/measurement.md`](references/measurement.md) — 各検査の合格条件・測定方法・失敗類型
* [`references/techniques.md`](references/techniques.md) — 依拠した技法と、本実装で補った条件
* `research/catalog/executability.jsonl` — 依拠した技法の実行可能度
