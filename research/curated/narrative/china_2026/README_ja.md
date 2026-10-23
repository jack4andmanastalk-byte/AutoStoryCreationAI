# 配布物の案内

**現代中国のストーリーテリング技法カタログ v1.0**  
基準日：2026-10-22／日本語／2000年以降／大陸中心＋香港・台湾・華人ディアスポラ比較。

## 最初に開くファイル

- `china_storytelling_report_ja.md`：サマリー、方法、12領域のサーベイ、84項目、地域比較、限界、全76件の参考文献。
- `sources.jsonl`：使用情報源のURL等を保存した1行1レコードのメタデータ（76件）。
- `catalog.jsonl`：カタログ本体の機械可読データ（84件）。
- `catalog_index.csv`：Excel等で並べ替え可能な索引。

## 数の読み方

84項目の内訳は**T＝語りの技法64、P＝制作・参加実践15、R＝関連概念5**。84種類の独自・実証済みの技法という意味ではない。

根拠の粒度は**A=59、B=24、C=1**。Aは関連本文・一次資料の具体例を確認、Bは主に抄録・書評・紹介、Cは追加照合が必要な操作的整理。Aも効果の因果証明や全編精読を意味しない。

本成果物はスコーピング型サーベイで、完全網羅・事前登録された体系的レビュー・査読論文ではない。引用する際は原資料を開き、確認範囲と版、頁を確かめること。

## JSONL

UTF-8で1行に1つのJSONオブジェクトを収録する。S番号は固定IDのため欠番がある。`source_id`と`source_ids`で出典と項目を対応させる。年・著者など未確定の値を空想で埋めない。

Python例：

```python
import json
with open('sources.jsonl', encoding='utf-8') as f:
    sources = {x['source_id']: x for line in f if (x := json.loads(line))}
with open('catalog.jsonl', encoding='utf-8') as f:
    entries = [json.loads(line) for line in f]
techniques = [e for e in entries if e['entry_type'] == 'T']
assert len(techniques) == 64
```

`all_content_close_read`は全件falseであり、取得した全資料を全編精読したという過大な宣言を避けている。`selected_full_text`は実際の関連箇所を確認したことを示す。

## 日付と版の重要事項

- S029は2025年先行オンライン公開として引用し、基準日後の2026年11月号を既刊扱いしない。
- S025は公開査読を伴うプレプリント。S027はCHI2026刊行を照合し、確認本文はarXiv版。
- S066は掲載ページ・CrossrefのDOI `10.22599/wcj.74`を採用。PDF内の`wcj.86`とは不一致。
- S073の著者はChris Gayomali、S048はShaoyu Tang。候補段階の誤記は納品データで訂正済み。

## 検証・権利

`validation_report.json`は機械的整合性の検証、各`.schema.json`はJSON構造、`manifest.json`はサイズとSHA-256を示す。機械的検証は学術的真偽・完全性の保証ではない。

取得したPDFや原資料の全文は配布しない。各サイトへリンクし、本調査による日本語の要約・操作的分類とメタデータのみを収録する。

作成支援：Arena.ai Agent Mode。
