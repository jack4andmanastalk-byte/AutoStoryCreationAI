# ゲームナラティブ制作研究カタログ

**基準日：2026-10-23（Asia/Tokyo）／版1.0／日本語**

現代の米国を主要制作拠点とするゲーム開発の公開事例を中心に、ストーリー、キャラクター、世界観、作中史・カノン、実在史の調査、制作パイプライン、PDCA/PDSA、反復、評価、音声・翻訳を整理したスコーピング調査です。

## ファイル

| ファイル | 内容 |
|---|---|
| [report_ja.md](report_ja.md) | 要旨、方法、参照パイプライン、領域別解説、事例比較、評価・制作、42項目の実務索引、参考文献 |
| [sources.jsonl](sources.jsonl) | 資料候補61件の書誌・アクセス・確認範囲・根拠要約・限界 |
| [practices.jsonl](practices.jsonl) | P01〜P42。説明、対象、段階、artifact、根拠、分析上のPDCA、注意点 |
| [sources.schema.json](sources.schema.json) | 情報源JSONLの1レコードに対応するJSON Schema |
| [practices.schema.json](practices.schema.json) | 実務JSONLの1レコードに対応するJSON Schema |
| [research_log.md](research_log.md) | 探索・選定・日付・アクセスの処理、判断と限界 |
| [validate.py](validate.py) | オフラインの書式・ID・相互参照・引用・日付等の検証 |
| [validation_report.txt](validation_report.txt) | 検証結果。内容の真実性や全外部リンクの現時点の稼働を認証するものではない |
| [checksums.sha256](checksums.sha256) | 配布した主要ファイルのSHA-256 |

## 規模と注意

- 資料候補61件：**採用55、補助3、除外3**。
- 採用資料の確認範囲：ウェブ本文全体7、選択箇所47、要旨のみ1。PDFをダウンロードできたことと、その全頁・全図を精読したことは別です。
- 実務42項目。各PDCA対応は本報告の分析です。スタジオがPDCAという名称で運用しているとの主張ではありません。
- 55件は55社や55実験を意味しません。同じ作品・発表の関連資料があります。
- 英語公開資料中心の目的抽出的収集で、悉皆調査・PRISMA準拠レビュー・因果評価ではありません。
- ツール仕様、非米国事例、理論、開発者の実務、企業の方針、二次報道を区別しています。
- 参照資料の全文、PDF、キャッシュ、画像はZIPに含めません。引用先から閲覧してください。

## JSONLの読み方

UTF-8、BOMなし、1行につき1個のJSONオブジェクト、改行区切りです。大きな配列ではありません。

```python
import json
from pathlib import Path

sources = [json.loads(line) for line in Path('sources.jsonl').read_text(encoding='utf-8').splitlines()]
practices = [json.loads(line) for line in Path('practices.jsonl').read_text(encoding='utf-8').splitlines()]
by_id = {s['source_id']: s for s in sources}

# 米国制作事例として採用された資料
us_cases = [s for s in sources
            if s['inclusion_status'] == 'included'
            and s['geographic_applicability'] == 'us_case']

# 作中史関連の実務と、その根拠
for p in practices:
    if 'history' in p['domains']:
        print(p['practice_id'], p['title_ja'])
        for sid in p['source_ids']:
            s = by_id[sid]
            print(' ', sid, s['url'], s['verification']['review_extent'])
```

### 情報源の主なフィールド

- `source_id`：S001〜S061の固定識別子。件数や採用順の順位ではありません。
- `title`, `authors`, `publisher`：確認できた題名・署名または発行主体・媒体。講演資料は登壇者、共同編集Wikiは共同著者集団を記録。著者未確認は空配列。
- `author_status`：署名／発行主体、登壇者、個別著者未確認の共同編集、未確認を区別。
- `publication_date`, `publication_date_precision`：確認できた初出日。`YYYY`・`YYYY-MM`・`YYYY-MM-DD`または`null`。年のみはその精度です。
- `date_modified`, `date_note`：更新日と日付の判断根拠。文書の更新メタデータ、講演開催日、再掲パス、原著の初出を混同しません。
- `url`, `resolved_url`, `doi`, `doi_url`：閲覧先・転送先・DOI。DOIで同定できても本文を読めたとは限りません。
- `bibliographic_details`：確認できた巻・号・頁・版等。未確認事項は補完しません。
- `version_url`, `version_identifier`：確認できた固定版。ink文書はパス別の最新commitを確認し、固定URLを併記。Wikiの固定版が分かった場合も併記。
- `source_type`, `source_relationship`：資料種別と、一次・当事者証言を含む二次・学術等の関係。品質点数や因果的な強さの順位ではありません。
- `geographic_applicability`：米国の制作事例、米国の概念・ガイド、非米国比較、国際研究、ツール仕様、方法参照等の関係。開催地・媒体所在地だけで米国採用を推定しません。
- `domains`：story／character／world／history／canon／productionの関心タグ。比較のための本調査のコードです。
- `inclusion_status`：`included`（採用）、`supplementary`（補助）、`excluded`（除外）。
- `verification.review_extent`：`full_text`、`selected_sections`、`abstract_only`、`index_only`、`unavailable`。講演告知のfull_textは講演本体の全確認ではありません。
- `verification.retrieval_scope`：取得できたものの範囲。確認範囲とは別です。
- `verification.reviewed_locators`：確認した節・頁・チャンク等。PDF頁は原則として表紙を1とするファイル内の順番。
- `verification.http_status`：通常の取得経路の状態。S026・S059は403でも別経路で一部確認できたため、これだけで可読性を判定しないでください。
- `verification.*sha256`, `hash_role`：何の応答を識別する値かを明記。ブロック／メンテナンス応答のハッシュは本文証拠のハッシュではありません。元全文は配布していません。
- `evidence`：箇所と和文の要約。原文の長文引用ではありません。
- `limitations_ja`：その資料から言えないこと。自己報告・年代・対象・未確認等。
- `practice_ids`：実務台帳への対応。
- `referenced_in_report`, `report_reference_role`：報告内の参照の有無と役割。除外理由を説明する引用は、実務の証拠として採用したという意味ではありません。

日付の既知の注意：S001はonlineと号の年月が異なります。S014とS015は公式SteamイベントJSONで公開時刻を確認しました。S040の2011-01-01は現行本文の正確な初出と断定せず別フィールドへ保存。S043は2012年第2稿を2021年パスで再掲した文書。S044は`ms.date`と更新日を初出日から区別。S054はCoG転載版を引用し、元ブログの正確な初出日は未確認です。

### 実務の主なフィールド

- `practice_id`, `title_ja`, `description_ja`：IDと実務説明。
- `domains`, `phase`：対象と制作上の位置。phaseは厳密な共通工程ではなく比較用の記述。
- `artifacts`：資料で確認されたもの、または明示した分析上のartifact名。
- `source_ids`：根拠資料。実施効果が証明されたという意味ではありません。
- `classification`：通常は実務観察＋分析テンプレート。P36・P42は統合的推奨。
- `pdca_mapping_is_analytical`：全件`true`。
- `pdca_ja`：Plan／Do／Check-Study／Actへの本報告の対応づけ。
- `limitations_ja`：移転・解釈上の注意。

## オフライン検証

Python 3.10以降と`jsonschema`を使用します。外部ネットワークは使いません。

```bash
python -m pip install 'jsonschema>=4,<5'
python validate.py
```

検証対象はUTF-8、JSON Schema、ID、件数、相互参照、脚注、基本的な日付・URL形状、重要な確認範囲の整合等です。研究者による再読・事実確認や第三者査読の代わりではありません。外部URLの将来の有効性も保証しません。

## 作業ディレクトリについて

会話のworkspace内の`research/`には収集・注釈・組版のスクリプトと作業用メタデータがあります。配布ZIPは主要成果物と検証用ファイルに限定します。`.cache/`の元資料は配布しません。将来再取得する場合は基準日を更新し、アクセスや内容が変わり得ることを前提に再審査してください。本版のメタデータを未来の取得結果で無断上書きする運用は想定していません。
