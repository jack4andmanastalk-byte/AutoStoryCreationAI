# データセットアップ手順

本ドキュメントは `scripts/setup_dataset.py` が一括で実行する処理を、段階ごとに説明します。
実行環境の前提は Python 3.11 以上、標準ライブラリ + `fpdf2` / `PyYAML` のみです。

## 0. 準備

```bash
make setup      # .venv を作成して requirements.txt をインストール
make test       # ユニットテスト（ネットワーク不要）
```

設定は `configs/dataset.yaml` に集約しています。取得対象・件数・フォント・接続先は
すべてこのファイルを編集して変更します（CLI オプションで上書き実行できます）。

## 1. 青空文庫の書誌データ

```bash
.venv/bin/python scripts/setup_dataset.py aozora-metadata
```

処理順:

1. 公式 CSV (`list_person_all_extended_utf8.zip`) を取得
2. 取得できない場合は `aozora.card_list_mirrors` のミラーを試す
   （静的サイトの JSON ペイロード / 旧 CSV スナップショット）
3. `data/datasets/aozora_works.jsonl` と `aozora_authors.jsonl` を出力

CSV の列は日本語見出しで取得するため、列名が存在しない場合は該当項目だけをスキップします
（前方互換のため、未知の列は無視されます）。

NDC 分類の名称は `ndc_class_all.json` があればラベルに付与し、無い場合は `code` のみ残します。

## 2. 青空文庫の本文と PDF

```bash
.venv/bin/python scripts/setup_dataset.py aozora-texts --works 120 --pdf
```

* サンプリングは `--seed`（既定 `aozora.sample_seed`）で再現可能。
  著者と出版年に分散するよう Acquiring 選定します（太少な作家に偏ることを避けるため）。
* 本文は青空文庫記法（`｜漢字《かんじ》` のルビ、`［＃...］` の注記）を解析して
  ルビ・注記を除去したプレーンテキストとして `data/raw/aozora/texts/<作品ID>.txt` に保存します。
* `--pdf` を付けると `data/pdf/aozora/<作品ID>.pdf` に A5 PDF を出力します
  （表紙に書誌情報、本文は和文改行・禁則処理、PDF メタデータにタイトル/作者を設定）。
* 作品著作権フラグが「あり」の作品は、本文を生成せず `rights.copyright_flag` に記録します。

## 3. 小説家になろうの書誌データ

```bash
# 公式APIの生JSONを保存（オフライン再利用・再現性のため）
.venv/bin/python scripts/fetch_narou_api.py --per-query 200

# JSONLへ変換
.venv/bin/python scripts/setup_dataset.py narou-metadata
```

`fetch_narou_api.py` は次の情報を API から取得して `data/cache/narou_api/*.json` に保存します。

* タイトル・Nコード・作者・あらすじ
* 大ジャンル／ジャンル／キーワード
* 初回掲載日・最終掲載日・更新日
* 話数・文字数・読了時間・会話率・挿絵数
* R15・残酷な描写などの要素フラグ、ブックマーク数・評価ポイント

`setup_dataset.py narou-metadata` は保存済みの生 JSON（`narou.api_response_files`）を
取り込みつつ、API へ直接クエリも実行します（`order` と `genre` を変えて重複排除）。

## 4. 小説家になろうの本文と PDF

```bash
.venv/bin/python scripts/setup_dataset.py narou-texts --works 20 --pdf
```

取得の優先順位:

1. `narou.local_text_dir` に `<Nコード>/<話数>.txt` があればそれを使用
   （1 行目が `# 話名` なら章タイトルとして扱います）
2. 公式のデータダウンロード `https://ncode.syosetu.com/txtdownload/<Nコード>/`
3. 各話のページ `https://ncode.syosetu.com/<Nコード>/<話数>/`

## 5. 統計と検証

```bash
.venv/bin/python scripts/dataset_report.py          # テキストで出力
.venv/bin/python scripts/dataset_report.py --json   # 機械可読形式
```

表示内容:

* レコード数、テキスト/PDF 保有数、文字数合計
* 出版年の分布（10 年単位のヒストグラム）
* ジャンル・メディア別の分布
* 必須フィールドの欠損件数

## 6. CI での再現

`.github/workflows/dataset-refresh.yml` は同じコマンドを GitHub Actions 上で実行し、
`data/datasets/*.jsonl` を artifact として保存します。取得例:

```bash
gh run download --name datasets
```

## 7. トラブルシューティング

| 事象 | 対処 |
| --- | --- |
| `official card list unavailable` | 公式ホストへの接続が遮断されています。ミラーの利用を許可するか、`aozora.card_list_urls` を差し替えてください。 |
| `no text for aozora:XXXXXX` | テキスト形式（ruby/plain）の違いでミラーに存在しない可能性があります。公式 ZIP の取得に切替わります。 |
| `NUXT payload` のパース失敗 | ミラー側の構造変更です。`asc/sources/aozora.py::parse_nuxt_payload` の更新が必要です。 |
| PDF の文字化け | `pdf.body_font` / `pdf.heading_font` が CJK フォントであるか確認してください。 |
| `FontError` | Google Fonts からの取得に失敗しています。ローカルフォントのパスを直接指定できます。 |
