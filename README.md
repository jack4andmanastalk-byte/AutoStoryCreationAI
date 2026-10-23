# AutoStoryCreationAI

AI による自動創作活動（ストーリー・キャラクター・世界観・歴史など）を研究するためのリポジトリです。
本リポジトリは **研究素材のデータセットアップ** を主眼に置き、

1. 公開ドメインの日本語文学（青空文庫）
2. Web 小説（小説家になろう）

から、統一スキーマのメタデータ JSONL と閲覧用の PDF を生成するパイプラインと、
その実行結果を収録します。

> 現在のフェーズ: **Phase 0 — データセットアップ**。
> スキル／ハーネス／パイプラインはこのフェーズで実験し、逐年拡張します。

---

## 1.  提供物

| 成果物 | パス | 内容 |
| --- | --- | --- |
| 書誌メタデータ | `data/datasets/aozora_works.jsonl` | 青空文庫の作品（作品ID・タイトル・著者・NDC分類・初出・底本初版発行年・公開URLなど） |
| 著者メタデータ | `data/datasets/aozora_authors.jsonl` | 作家・翻訳者（人物ID・氏名・ヨミガナ・生没年など） |
| 書誌メタデータ | `data/datasets/narou_novels.jsonl` | 小説家になろうの作品（Nコード・ジャンル・R15要素・掲載日・話数・文字数・評価指標など） |
| 外部確認済・商業化200作品メタデータ | `samples/narou_commercialized_ranked.jsonl` (`top100` / `rank101_200` も同梱) | CiNii Books (ISBN)・Wikipedia により書籍・マンガ・アニメ・ゲームの実在を確認した上位 200 作品カタログ（R15 対象作品を含む） |
| 外部確認済・商業化ランキング表 | `docs/narou_commercialized_ranking.md` (`docs/narou_top100_ranking.md`, `docs/narou_rank101_200_ranking.md`) | 第1位〜第200位の順位・R15有無・外部確認メディア・ISBN/レーベル・全話数・総文字数・PDFサイズ一覧 |
| 整形済み本文 | `data/raw/{aozora,narou}/texts/*.txt` | ルビ・まえがき／あとがき・注記を除いたプレーンテキスト |
| PDF | `data/pdf/{aozora,narou}/*.pdf` | 表紙（書誌・外部メディア確認・ISBN・ランキング情報）+ 全話本文の A5 PDF（和文組版・禁則処理つき） |
| ビルド情報 | `data/datasets/manifest.json` | 各ステップの取得元・件数・総話数・総文字数・生成時刻 |

JSONL は 1 行 = 1 レコード（UTF-8 / `ensure_ascii=False` / キー順固定）です。
スキーマの詳細は [`docs/dataset_schema.md`](docs/dataset_schema.md) を参照してください。

## 2.  クイックスタート

```bash
# 1) 環境準備（Python 3.11 想定）
make setup

# 2) ユニットテスト
make test

# 3) データ取得（青空文庫 → 小説家になろう の順）
make data

# 4) 統計の確認
make report
```

個別に実行する場合:

```bash
.venv/bin/python scripts/setup_dataset.py aozora-metadata            # 書誌データのみ
.venv/bin/python scripts/setup_dataset.py aozora-texts --works 120 --pdf
.venv/bin/python scripts/fetch_narou_api.py --per-query 500 --order-pages 4
.venv/bin/python scripts/setup_dataset.py narou-metadata --cached-only
.venv/bin/python scripts/setup_dataset.py narou-rank --top 200 --strict-external   # 書籍・漫画・アニメ・ゲームの外部実在検証＋ランキング
.venv/bin/python scripts/setup_dataset.py narou-texts --works 200 --max-episodes 0 --pdf --rank-order
# さらに続き（例: 第201位〜第300位）をダウンロードする場合:
.venv/bin/python scripts/setup_dataset.py narou-texts --start-rank 201 --works 100 --max-episodes 0 --pdf --rank-order
```

事前ビルド済みの全 200 作品・全話（86,007 話 / 約 3.64 億文字 / 1.22 GiB、R15 対象作品を含む外部確認済・商業化作品）PDF セットを取得する場合:

```bash
# 方法 A: datasets ブランチから展開
make pull-datasets

# 方法 B: GitHub Release から PDF アーカイブ (第1〜100位 / 第101〜200位) を直接取得
gh release download datasets-narou-commercialized
```

## 3.  データソース

### 3.1 青空文庫（aozora.gr.jp）

* 書誌リスト: `https://www.aozora.gr.jp/index_pages/list_person_all_extended_utf8.zip`
  （毎夜更新される CSV。作品名・ヨミガナ・初出・分類番号（NDC）・文字遣い種別・
  作品著作権フラグ・公開日・最終更新日・図書カードURL・底本情報など）
* 本文: 作品ごとの ZIP（`/cards/<人物ID>/files/<作品ID>_<形式>_<ハッシュ>.zip`）
* 権利: 「青空文庫収録ファイルの取り扱い規準」に従います。**作品著作権フラグが「あり」の作品
  （著作権存続作品）は再配布できません**。本パイプラインはフラグを `rights.copyright_flag`
  に記録し、フラグ「なし」の作品のみ本文・PDF を生成します。

### 3.2 小説家になろう（syosetu.com）

* 書誌 API: `https://api.syosetu.com/novelapi/api/`（公式 API。非商用・教育・研究用途での
  利用が認められています）
* 本文: 公式のデータダウンロード（`https://ncode.syosetu.com/txtdownload/<Nコード>/`）と
  各話のページ（`https://ncode.syosetu.com/<Nコード>/<話数>/`）
* 作品の著作権は作者に帰属します。**商業化されている作品の印刷版・電子書籍は本リポジトリでは
  再配布しません**。購入先は公式ストアの URL を `rights` に記録しています。
  詳細は [`docs/legal_and_ethics.md`](docs/legal_and_ethics.md) を参照してください。

### 3.3 ミラーとオフライン再現

公式ホストに到達できない環境（社内ネットワーク、オフライン研究室など）向けに、
ミラーとキャッシュを用意しています。

* `configs/dataset.yaml` の `aozora.card_list_mirrors` / `aozora.text_mirror_tarball`
* `narou.api_response_files` … `scripts/fetch_narou_api.py` が保存した公式 API の生 JSON を再利用
  （ネットワーク無効でもメタデータ構築が可能）
* `narou.local_text_dir` … 事前取得済みの本文（`<Nコード>/<話数>.txt`）を再利用

`.github/workflows/dataset-refresh.yml` は同じパイプラインを GitHub Actions 上で実行し、
生成した JSONL・本文・PDF を `datasets` ブランチおよび artifact として公開します
（`make data` のネットワーク制約がある環境では `make pull-datasets` で即座に展開可能）。

## 4.  ディレクトリ構成

```
.
├── configs/dataset.yaml        # 取得対象・件数・フォント等の設定
├── data/                       # 生成物（大半は .gitignore 対象）
│   ├── cache/                  # ダウンロードキャッシュ（tarball・ZIP・フォント・API生JSON）
│   ├── datasets/               # メタデータ JSONL と manifest
│   ├── raw/                    # 整形済み本文テキスト
│   └── pdf/                    # レンダリングした PDF
├── docs/                       # 設計・スキーマ・法務メモ
├── samples/                    # リポジトリに同梱する小さなサンプル
├── scripts/
│   ├── setup_dataset.py        # データセットアップ CLI（主要エントリポイント）
│   ├── fetch_narou_api.py      # 公式API生JSONの保存
│   └── dataset_report.py       # 統計・欠損チェック
├── src/asc/                    # ライブラリ本体
│   ├── config.py http.py jsonl.py schema.py report.py
│   ├── sources/aozora.py sources/narou.py
│   ├── text/aozora_format.py text/narou_html.py
│   ├── render/pdf.py fonts.py
└── tests/                      # pytest
```

## 5.  品質保証

* `make test` — パーサ（青空文庫ルビ記法／小説家になろう HTML）、NUXT ペイロード、PDF 描画、
  JSONL ラウンドトリップのユニットテスト
* `make report` — レコード数・ジャンル分布・出版年分布・文字数合計・必須フィールド欠損の集計
* CI: `.github/workflows/dataset-refresh.yml` が公式取得からレポートまでを実行します

## 6.  次フェーズ候補

* スキルの定義（`skills/`）と評価ハーネスの雛形
* 文字種・文構造・会話率などの言語統計に基づく feature 抽出
* キャラクターシート・世界観ノートの生成と、その評価軸の設計
* 縦組み PDF / EPUB 出力（現在は横組み A5）

## 7.  ライセンスと引用

* 本リポジトリのコード: MIT（`LICENSE` を参照）
* 取得データ: 各ソースの規約に従います
  （青空文庫 = 「青空文庫収録ファイルの取り扱い規準」、
   小説家になろう = 「なろうデベロッパー利用ガイドライン」と作品ごとの著作権）
* データセットを論文・学習に用いる際は、**出典 URL と取得日を明記**してください。
