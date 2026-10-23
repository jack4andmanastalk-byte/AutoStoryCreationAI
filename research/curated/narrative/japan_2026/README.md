# 日本における物語創作技法：データと報告書

**版1.0／作成・参照日2026-10-22（Asia/Tokyo）**

戦後〜現代の漫画、アニメ、映画、TVドラマ、ゲーム、ライトノベルを対象とする、文献ベースの探索的カタログです。116項目・12分類・使用文書59件（学術系25、実務・出版・報道系34）を収録します。AI支援による調査・編集であり、査読論文や技法の悉皆調査ではありません。

## ファイル

|ファイル|内容|
|---|---|
|[japan_narrative_techniques_report.md](japan_narrative_techniques_report.md)|要約、範囲・方法、116項目の解説、考察、限界、59件の書誌・確認範囲。|
|[sources.jsonl](sources.jsonl)|使用文書のURL、書誌、日付、資料種別、根拠箇所、確認範囲、対応する技法ID。1行1文書、59行。|
|[techniques.jsonl](techniques.jsonl)|技法の操作、狙い、留意点、根拠資料IDと頁／節。1行1項目、116行。|
|[technique_index.csv](technique_index.csv)|表計算向け索引。ヘッダーを除き116行。|
|[screening_log.jsonl](screening_log.jsonl)|候補URL87件の採否・統合・不採用理由。検索結果全体の記録ではない。|
|[schema.json](schema.json)|JSONL内のオブジェクトのJSON Schema（`$defs.source`、`$defs.technique`、`$defs.screening_record`）。|
|[manifest.json](manifest.json)|件数と分類別・資料種別の内訳。タグの件数には重複がある。|
|[validation.json](validation.json)|構造・参照・件数・日付の機械検査結果。内容の学術的妥当性の認証ではない。|
|[SHA256SUMS.txt](SHA256SUMS.txt)|配布ファイルのハッシュ。ZIP自体と本ハッシュ表を除く。|

すべてUTF-8です。JSONLはJSON配列ではなく、各行が独立したJSONオブジェクトです。`null`は未確認・不明を示し、公開日不明を著作権年やURLから補完していません。

## 1. sources.jsonl の主なフィールド

|フィールド|意味|
|---|---|
|`source_id`|S001形式の安定した収集ID。採否履歴を残すため欠番がある。|
|`title`, `authors`, `contributors`|文書の題名、著者／責任団体、講師・取材回答者等。団体名による責任表示と個人の発言者を混同しない。|
|`container_title`, `publisher`|誌名・掲載サイトと発行主体。|
|`source_family`, `source_type`, `source_type_label`|学術系／実務・出版等の大分類と、論文・予稿・概要・インタビュー・解説等の区分。|
|`peer_review_status`|全件`not_independently_verified`。査読の有無を独立に調べて確定したデータではない。|
|`publication_date`, `publication_date_precision`|刊行日／記事公開日と精度（年・月・日）。不明ならnull。|
|`platform_online_date`|J-STAGE等へのオンライン公開日。冊子の刊行日と別。|
|`modified_date`|確認できた記事更新・改訂日。初回公開日とは別。|
|`event_date`, `interview_date`|講演・イベント日と取材日を別フィールドで保存。確認できない場合はnull。|
|`date_basis`, `date_anomalies`, `raw_reported_dates`|日付の根拠、異常・不一致、取得時の未正規化の値。JSON-LD候補値はページ内の関連・別記事を含みうるため、それだけで当該記事の刊行日としない。|
|`volume`, `issue`, `first_page`, `last_page`|巻・号・誌面頁。PDFのファイル内頁番号と区別する。|
|`doi`, `isbn`|確認できた識別子。今回は引用対象が論文・公開記事なのでISBNは全件null。紹介された本のISBNを記事に付与しない。|
|`url`, `resolved_url`, `pdf_url`|収集対象URL、転送先、PDF URL（あれば）。|
|`bibliographic_witness_urls`|同一文書の書誌を別途確認したURL。S080・S081の記録はここへ統合。|
|`accessed_on`, `access_timezone`|参照日2026-10-22とAsia/Tokyo。|
|`verification`|本文・抜粋・要旨・概要のどこまで確認したか、節・頁、技法側の根拠箇所。|
|`limitations`|当該文書から何を一般化してはいけないか。|
|`original_theory_attribution`|紹介記事が解説する理論の提唱者等。これを未読原著への直接引用としない。|
|`retrieval`|HTTP状態、取得ファイル／確認用テキストのSHA-256、PDF頁数等。全文の正確性や理論の妥当性の認証ではない。|
|`technique_ids`, `report_only_use`|対応する技法の逆引き。S022のみ技法項目ではなく概念整理に用いる。|

### 確認範囲コード

- `substantive_full_text`：当該論文の抽出テキスト全体を確認したもの（S009）。全画像を詳細に視認したという意味ではない。
- `substantive_body`：公開された記事本文・講義抜粋の単位で本文を確認したもの。講義全体・連載全回とは異なる。
- `selected_passages`：関連部分のみ。原資料全体の通読ではない。
- `abstract_and_bibliography`：要旨を主な根拠とし、本文詳細に踏み込まない（S004・S005）。
- `official_abstract_only`：CEDEC公式概要のみ。講演動画やスライド未確認（S045・S046・S047・S049）。

## 2. techniques.jsonl の主なフィールド

- `technique_id`：T001〜T116。
- `category_code`, `category`, `title`：12分類と編集上の技法名。
- `documented_context`：資料で確認できた媒体・領域。他媒体への効果を認定する欄ではない。
- `japan_relation`：`実践`、`分析`、`受容`、`提案`、`実験`、`実装指南`の配列。意味は報告書1.4節を参照。
- `procedure`：資料から作業手順へ変換した要約・総合。逐語引用ではない。
- `intended_function`：狙い・機能。統計的に確定した効能の保証ではない。
- `limitations`：成立条件、解釈上の注意、資料の限界。
- `term_status`, `operationalization`：名称と手順が編集上の操作化であることを明示。
- `cross_media_effectiveness`：全件`not_evaluated`。別媒体に転用できないと断定する値ではない。
- `evidence[]`：`source_id`、頁／節を記した`pinpoint`、資料の主張種別`source_assertion_kind`、`verification_extent`、根拠の範囲`support_scope`。

一項目の複数の根拠は、同じ種類・同じ強さとは限りません。資料IDでsources.jsonlへ結合し、種別と確認範囲を確認してください。116項目が互いに独立した変数であるとも仮定しないでください。

## 3. 読込みと照合の例

```python
import json
from pathlib import Path

def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]

sources = {x['source_id']: x for x in read_jsonl('sources.jsonl')}
techniques = read_jsonl('techniques.jsonl')
item = next(t for t in techniques if t['technique_id'] == 'T042')
print(item['title'])
for evidence in item['evidence']:
    source = sources[evidence['source_id']]
    print(source['authors'], source['title'], evidence['pinpoint'])
    print(source['verification']['extent_label'])
```

## 4. 引用・再利用上の注意

1. 理論・実践の存在を論証する際は、原資料と該当頁を確認して直接引用してください。本報告の編集上の分類を使う場合は、報告書名、版1.0、作成日、T番号を明記してください。
2. 公開日のない紹介記事を、紹介された書籍の発売年で引用しないでください。S051の2025-08-04は更新日です。S007の誌面年2017をプラットフォーム公開年2021で置換しないでください。
3. 制作者の助言、作品論の解釈、実装マニュアル、心理実験は互いに代用できません。面白さ・売上・読解・注意の効果を同一視しないでください。
4. 日付既知の採用文書は2007〜2025年に偏ります。1945年以後の全歴史を均等に網羅したデータではありません。
5. 原資料の権利は各権利者に帰属します。本ZIPには原資料のHTML・PDF・書籍本文を再配布していません。`retrieval.inspection_text_relative_path`は作業領域内の確認用キャッシュの所在であり、ZIP内のファイルを指すものではありません。
6. リンクは将来変更・削除されることがあります。収集時のHTTP成功やハッシュは、現在・将来の可用性や本文・理論の正しさを保証しません。

構造検査の結果はvalidation.json、方法・偏り・具体的な引用上の注意はMarkdown報告書に記載しています。
