# AutoStoryCreationAI

**初めて読む方へ:** [一般向け現状レポート（2026-10-25）](docs/overview_report_ja.md) に、スキル・評価ハーネス・生成工程・データの「できること／できないこと」をまとめています。技法や既存資料の実装・接続状況は[資料の棚卸し](research/curation/materials_inventory_2026-10-25.md)を参照してください。

**保守状況:** Arena.ai の GitHub 接続から Issue を更新できない場合があるため、
未完の調査・旧ブランチの採否・削除条件は [保守状況](docs/maintenance_status.md) に記録します。
Issue の OPEN 表示だけで作業状況を判断せず、関連 PR と併せて確認してください。

**外部作品の本文について:** 本リポジトリは public です。無料公開されている本文でも
再配布の許可とは別です。`datasets` と Actions 成果物には本文が残っています。
なろう本文の Release 圧縮ファイル4件は非公開コピーの照合後に削除され、
`dataset-refresh` は GitHub 上で手動停止されていますが、再有効化すると再公開し得ます。
[保守状況](docs/maintenance_status.md) と[非公開研究資料の設計・注意書き](docs/private_research_design.md)
を参照し、権利と残存する公開経路を確認してください。

AI による自動創作活動（ストーリー・キャラクター・世界観・歴史など）のためのリポジトリです。
AIが作品を作り続けられるよう、その基盤として **研究素材のデータセットアップ** を含み、

1. 公開ドメインの日本語文学（青空文庫）
2. Web 小説（小説家になろう）

から、統一スキーマのメタデータ JSONL と AI 自動創作・評価に直接利用できる整形済みプレーンテキスト（UTF-8 `.txt`）を生成するパイプラインと、
その実行結果を収録します。

> 現在のフェーズ: **Phase 0 — データセットアップ**（完了）、
> **Phase 1 — 創作知識の運用可能化**（進行中）、
> **Phase 2 — スキルの実行可能化**（進行中: 13 スキル実装済み、S2/S3 配線済み）。
> **現在の実験範囲は Arena.ai × L1**。L2/L3 の実証・較正・追加開発は 2026-10-24 に凍結しました
> （[`docs/evaluation_scope.md`](docs/evaluation_scope.md)）。次は対照群の確定と L1 の探索的実験です。
> `research/` に、外部コーパスの選別・統一カタログ・スキル種を収録しています。
>
> **今後の開発方針（2026-10-29）**: AIによる自動創作そのものの実用改善を優先します。
> 厳密な検証より、作品を作り、読み、摩擦を直す循環を標準とし、研究用プロトコルと
> 過去の実験記録は基盤・履歴として保持します。タスク整理は
> [`docs/practical_roadmap.md`](docs/practical_roadmap.md) を参照してください。

---

## 1.  提供物

| 成果物 | パス | 内容 |
| --- | --- | --- |
| 書誌メタデータ | `data/datasets/aozora_works.jsonl` | 青空文庫の作品（作品ID・タイトル・著者・NDC分類・初出・底本初版発行年・公開URLなど） |
| 著者メタデータ | `data/datasets/aozora_authors.jsonl` | 作家・翻訳者（人物ID・氏名・ヨミガナ・生没年など） |
| 書誌メタデータ | `data/datasets/narou_novels.jsonl` | 小説家になろうの作品（Nコード・ジャンル・R15要素・掲載日・話数・文字数・評価指標など） |
| 外部確認済・商業化統合メタデータ（373作品） | `samples/narou_commercialized_all.jsonl` | 総合上位 300 作品＋5ジャンル追加 73 作品を重複なく統合した全 373 作品（139,656 話 / 約 5.84 億文字）カタログ |
| 外部確認済・商業化300作品メタデータ | `samples/narou_commercialized_ranked.jsonl` (`top100` / `rank101_200` / `rank201_300` も同梱) | CiNii Books (ISBN)・Wikipedia・Apple Books Japan により書籍・マンガ・アニメ・ゲームの実在を確認した上位 300 作品カタログ（R15 対象作品を含む） |
| 5ジャンル限定・商業化追加73作品メタデータ | `samples/narou_commercialized_genre_supplement.jsonl` | **歴史（15）・推理（15）・現代（15）・SF（15）・ホラー（13）** に限定して外部実在検証・全話テキスト化した計 73 作品（19,057 話 / 約 7,981 万文字、Top 300 と重複なし） |
| 外部確認済・商業化カタログ表 | `docs/narou_commercialized_ranking.md`, `docs/narou_genre_supplement_ranking.md` (`top100` / `rank101_200` / `rank201_300` も同梱) | 順位・区分・R15有無・外部確認メディア・ISBN/レーベル・全話数・総文字数・本文TXTサイズ一覧 |
| 整形済み本文（プレーンテキスト専用） | `data/raw/{aozora,narou}/texts/*.txt` | ルビ・まえがき／あとがき・注記を除いた UTF-8 プレーンテキスト（公開データはテキスト形式） |
| ビルド情報 | `data/datasets/manifest.json` | 各ステップの取得元・件数・総話数・総文字数・テキスト容量・生成時刻 |

JSONL は 1 行 = 1 レコード（UTF-8 / `ensure_ascii=False` / キー順固定）です。
スキーマの詳細は [`docs/dataset_schema.md`](docs/dataset_schema.md) を参照してください。

## 2.  クイックスタート

```bash
# 1) 環境準備（Python 3.11 想定）
make setup

# 2) ユニットテスト
make test

# 3) データ取得（青空文庫 → 小説家になろう の順、プレーンテキストのみ）
make data

# 4) 統計の確認
make report
```

### 2.1 AIに作品を作らせる（標準フロー）

題材と条件から**3章の原稿**までを、Arena のセッション内で進める標準手順です。

- 手順: [`docs/quickstart.md`](docs/quickstart.md)
- 決定（入口・provider・状態の置き場所・検査の位置づけ）: [`docs/standard_flow.md`](docs/standard_flow.md)

```bash
.venv/bin/python scripts/story_project.py --root works init \
  --project-id prj-seaside --title "潮の記録者" \
  --premise "港町で失われた潮位記録を追う。" --chapters 3 --target-chars 1200
.venv/bin/python scripts/story_project.py --root works run prj-seaside      # 応答待ちで exit 3
.venv/bin/python scripts/story_project.py --root works relay status prj-seaside
# 示されたタグに生成した本文を answers.txt で答える（捏造しない）
.venv/bin/python scripts/story_project.py --root works relay submit prj-seaside --file answers.txt
#   exit 3 = 次の1件 / 0 = 完成 / 2 = 失敗。待機中は submit を繰り返す（3章で12回）
.venv/bin/python scripts/story_project.py --root works render prj-seaside \
  --out works/prj-seaside/manuscript.md
.venv/bin/python scripts/story_project.py --root works render prj-seaside --reader \
  --out works/prj-seaside/manuscript.reader.md
.venv/bin/python scripts/story_project.py --root works summary prj-seaside \
  --out works/prj-seaside/summary.md
```

`relay submit` は取り込みと再開を1コマンドにまとめた1ラウンドの単位です。完成・失敗・
未回答のどれも同じ書式で報告し、終了コードがその状態になります（`0` / `3` / `2`）。
回答済みの要求は再生成せず、完成済みの作品には取り込みません。
`render --reader` は章見出しを付け監査マーカーを除いた読書用原稿を、`summary` は JSON を
開かずに作品情報・設定台帳（canon）・8設計書・検査要約（Blocker / Warning / Observation と
次に直すコマンド）を Markdown で出力します。章の目安字数は単一指定でも ±5% の許容幅
（`1200` → `1140〜1260` 字）として扱い、幅の外にだけ警告を出します。一部だけ作り直すときは
`revise --chapter ch02 --note "何を直すか"` のように意図を渡せます（依頼文と `summary` に残ります）。

`run_pipeline.py` と `run_twostage.py` は、凍結した実験条件を再実行するための
固定経路で、標準フローではありません（[`docs/standard_flow.md`](docs/standard_flow.md) §1）。
導線は `make quickstart-check`（`tests/test_standard_flow.py` と `tests/test_relay_round.py`）で回帰対象にしています。

個別に実行する場合:

```bash
.venv/bin/python scripts/setup_dataset.py aozora-metadata            # 書誌データのみ
.venv/bin/python scripts/setup_dataset.py aozora-texts --works 120   # プレーンテキストのみ取得
.venv/bin/python scripts/fetch_narou_api.py --per-query 500 --order-pages 4
.venv/bin/python scripts/setup_dataset.py narou-metadata --cached-only
.venv/bin/python scripts/setup_dataset.py narou-rank --top 300 --strict-external   # 書籍・漫画・アニメ・ゲームの外部実在検証＋ランキング
.venv/bin/python scripts/setup_dataset.py narou-texts --works 300 --max-episodes 0 --rank-order
# 5ジャンル限定（歴史・推理・現代・SF・ホラー）の商業化作品を各 10〜15 作品（計 50〜75 作品）追加する場合:
.venv/bin/python scripts/setup_dataset.py narou-genre-supplement --per-genre 15 --min-per-genre 10
# 残存 PDF がある場合にプレーンテキストへ変換して完全削除する:
.venv/bin/python scripts/setup_dataset.py purge-pdfs
```

事前ビルド済みの全 373 作品・全話（総合 Top 300 作品＋歴史・推理・現代・SF・ホラー 73 作品＝139,656 話 / 約 5.84 億文字 / 圧縮アーカイブ合計 0.54 GB、PDF 完全削除済）プレーンテキストセットを取得する場合:

```bash
# 方法 A: datasets ブランチから展開（プレーンテキスト＋JSONL のみ、PDF ゼロ）
make pull-datasets

# 方法 B: GitHub Release から圧縮テキストアーカイブ (*_texts.tar.gz) を直接取得
gh release download datasets-narou-commercialized
```

**PDF と既存ファイルへの注意:** 通常の `make data` / `dataset-refresh` はテキスト形式を
使いますが、CLI の `--pdf` と旧 PDF の `purge-pdfs` は互換機能として残っています。
`make data` は最後に `purge-pdfs` を実行し、対応するテキストを確認・抽出した後、
設定の PDF ディレクトリ内の対象 PDF を削除します。実行前に必要なファイルをバックアップし、
[`docs/data_setup.md`](docs/data_setup.md) の注意事項を確認してください。

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
生成した JSONL・本文テキストを `datasets` ブランチおよび artifact として公開します
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
├── skills/                     # 実行可能なスキル（SKILL.md + references/、下記 4.2）
├── harness/                    # 評価ケース・ルーブリック・判定器（下記 4.2）
├── research/                   # 創作技法・制作実務の研究コーパス（下記 4.1）
│   ├── curated/                # 選別済みの元成果物（出典・限界つき）
│   ├── catalog/                # 統一カタログ（技法 488・分類 10・ツール 96・書誌 529）
│   ├── program/                # スキル／ハーネス種（13）と実装設計
│   ├── inventory/              # 34 成果物の採否台帳
│   └── curation/               # 選別報告・ギャップ分析・追加調査
├── samples/                    # リポジトリに同梱する小さなサンプル
├── scripts/
│   ├── story_project.py        # AI自動創作の標準エントリポイント（創作project・relay・要約・編纂）
│   ├── setup_dataset.py        # データセットアップ CLI
│   ├── fetch_narou_api.py      # 公式API生JSONの保存
│   └── dataset_report.py       # 統計・欠損チェック
├── src/asc/                    # ライブラリ本体
│   ├── config.py http.py jsonl.py schema.py report.py
│   ├── sources/aozora.py sources/narou.py
│   ├── text/aozora_format.py text/narou_html.py
│   ├── render/pdf.py fonts.py
│   ├── story/                  # canon・台帳・継続性監査（continuity-ledger）
│   ├── evaluation/             # 指標・ルーブリック・判定器・ハーネス
│   ├── pipeline/               # 生成パイプライン（Plan / Design 8種 / Draft / Replay）
│   └── project/                # 永続創作プロジェクト（再開・continuation・改訂・分岐・入れ子・共有world・要約）
└── tests/                      # pytest
```

### 4.1 研究コーパス（`research/`）

外部で収集した創作研究資料（25 成果物）を、実用性 6 軸で判定して取捨選択したものです。
**採用 9・参照 21・除外 4**。保存したのは書誌・要約・分析であり、第三者の本文は含みません。

| パス | 内容 |
| --- | --- |
| [`research/README.md`](research/README.md) | 全体像と読み方 |
| [`research/curation/selection_report.md`](research/curation/selection_report.md) | 実用性判定・採否理由・重複分析 |
| [`research/curation/gap_analysis_and_added_sources.md`](research/curation/gap_analysis_and_added_sources.md) | 空白領域の追加調査（24 件、2025–2026 のベンチマーク等） |
| [`research/catalog/README.md`](research/catalog/README.md) | 統一カタログのスキーマと限界 |
| [`research/curation/executability_report.md`](research/curation/executability_report.md) | 実務化できるかの仕分け（488 件：executable 115 / partial 290 / reference_only 83） |
| [`research/program/skill_pipeline_mapping.md`](research/program/skill_pipeline_mapping.md) | 技法 → `SKILL.md`／評価ハーネスへの変換設計 |

| [`research/curation/spec_changes_2026-10.md`](research/curation/spec_changes_2026-10.md) | 実装時に補った合格条件と設計変更の記録 |
| [`docs/protocol.md`](docs/protocol.md) | **評価プロトコル v1（凍結）**。タスク 10 題・系 S0–S3・指標・合格閾値 G1–G5 |
| [`docs/evaluation_scope.md`](docs/evaluation_scope.md) | **現在の運用範囲**。Arena × L1 を継続し、L2/L3 を凍結する決定と報告制約 |
| [`docs/arena_operation.md`](docs/arena_operation.md) | **実行前提の運用モデル**。Arena Agent Mode × GitHub で完結する実行・生成・永続化・再検証の役割分担（分析・検証・再設計） |
| [`docs/practical_roadmap.md`](docs/practical_roadmap.md) | **実用改善ロードマップ**。AI自動創作を前提に、作品を作って直す循環と今後の優先タスク |
| [`docs/replay.md`](docs/replay.md) | 記録済み応答を外部providerなしで再実行し、prompt・response・成果物の一致を監査する方法 |
| [`docs/continuous_creation_roadmap.md`](docs/continuous_creation_roadmap.md) | 単一作品の再開から、続編・入れ子作品・世界スケール親作品までの設計と実装順序 |
| [`docs/project.md`](docs/project.md) | 任意premiseの創作projectを作成し、S1のplan/design/draftを実行・中断再開・continuation・多段入れ子作品の依存順実行とpinned再帰編纂・複数時間軸/地域/文化状態/世界canonの保存と選択ContextPacket・年代記/地誌/文化圏/作品集の編纂・外部replay bundleのexport/verify/restoreを行う方法 |
| [`docs/ci.md`](docs/ci.md) | CI の実行枠設計（なぜ CI が待たされていたか、どう直したか） |

```bash
make research         # research/curated/ から統一カタログを再生成
make research-check   # コミット済みカタログとの差分検査（CI 用）
```

### 4.2 実行可能なスキル（`skills/`・`harness/`）

知識を読むだけの資料ではなく、**実行して判定できる形**にした 13 スキルです。
いずれも「決定論的に検査できる部分」と「意味の評価」を分離しています。

| スキル | 何をするか | 実装 |
| --- | --- | --- |
| [`skills/premise-brief/SKILL.md`](skills/premise-brief/SKILL.md) | 企画核（一文ログライン・主題・差分・禁止条件）が検証可能な形か検査する | `src/asc/brief/`、`scripts/check_brief.py` |
| [`skills/world-rules/SKILL.md`](skills/world-rules/SKILL.md) | 世界の公理・規則とコスト・例外の条件・地理の対応を検査する | `src/asc/world/`、`scripts/check_world.py` |
| [`skills/history-timeline/SKILL.md`](skills/history-timeline/SKILL.md) | 年表の年代順・因果参照・痕跡・正史と異説の分離を検査する | `src/asc/history/`、`scripts/check_history.py` |
| [`skills/character-core/SKILL.md`](skills/character-core/SKILL.md) | 人物の WANT/NEED・視点の分離・選択の予測・口調・アークが設計書としてあるか検査する | `src/asc/character/`、`scripts/check_character.py` |
| [`skills/relationship-web/SKILL.md`](skills/relationship-web/SKILL.md) | 関係の表向きと利害・両立しない目的・知識表・変化・沈黙を検査する | `src/asc/relation/`、`scripts/check_relation.py` |
| [`skills/plot-architecture/SKILL.md`](skills/plot-architecture/SKILL.md) | 幕割り・転換点・副筋の合流・結末・未回収の棚卸しを検査する | `src/asc/plot/`、`scripts/check_plot.py` |
| [`skills/scene-information/SKILL.md`](skills/scene-information/SKILL.md) | 場面の目的・緊張の型・知識の流れ・開示計画・伏線の対応を検査する | `src/asc/scene/`、`scripts/check_scene.py` |
| [`skills/interactive-branch/SKILL.md`](skills/interactive-branch/SKILL.md) | 分岐の到達不能・行き止まり・罠・辿れない条件・合流の覚え書きを検査する | `src/asc/branch/`、`scripts/check_branch.py` |
| [`skills/adaptation/SKILL.md`](skills/adaptation/SKILL.md) | 機能の翻訳・削除の理由と代替・両者への対応・権利の記録を検査する | `src/asc/adapt/`、`scripts/check_adaptation.py` |
| [`skills/continuity-ledger/SKILL.md`](skills/continuity-ledger/SKILL.md) | canon（設定台帳）と本文マーカーから、死亡・知識・伏線・移動日数・年齢の矛盾を検出する | `src/asc/story/`、`scripts/audit_continuity.py` |
| [`skills/voice-style/SKILL.md`](skills/voice-style/SKILL.md) | 視点の逸脱・自称の揺れ・禁止表現・サンプルからの乖離を報告する | `src/asc/style/`、`scripts/check_voice.py` |
| [`skills/revision-loop/SKILL.md`](skills/revision-loop/SKILL.md) | 所見を批評に変え、パッチを当てて再監査し、前後を比較する | `src/asc/revision/`、`scripts/revise.py` |
| [`skills/evaluation-harness/SKILL.md`](skills/evaluation-harness/SKILL.md) | 作品を L1（決定論）・L2（モデル判定）・L3（人間）に分けて測り、改稿前後を比較する | `src/asc/evaluation/`、`scripts/run_evaluation.py` |

```bash
make audit      # デモ作品（矛盾を 7 件仕込んだ 5 章）を監査して、検出結果を表示
make evaluate   # デモ作品と初稿を比較（L2 は記録済み判定を再生／ネットワーク不要）
make brief      # 企画核の検査デモ（良好 0 件／不良 6 検査 fail）
make world      # 世界規則の検査デモ（canon 照合つき）
make history    # 年表の検査デモ（canon 照合つき）
make character  # 人物核の検査デモ（canon 照合つき）
make relation   # 関係網の検査デモ（canon 照合つき）
make plot       # 筋立ての検査デモ（canon 照合つき）
make scene      # 場面設計の検査デモ（canon 照合つき）
make voice      # 文体の検査デモ（4 件の仕込みを検出）
make revise     # 改稿ループのデモ（批評→パッチ→再監査→比較）
make branch     # 分岐構造の検査デモ（7 検査）
make adaptation # 翻案設計の検査デモ（4 検査）
make calibrate  # 凍結資産の固定デモ（κ=0.5 fixture。新規較正ではない）
make skills-check   # SKILL.md の仕様検査＋全スキルのテスト
make protocol-check # 凍結した評価プロトコル（タスクセット・閾値）の検査
make plan           # 固定タスク t01 から canon だけを生成
make design         # 設計書 8 種の生成・検証デモ（canon 照合つき）
make story          # S1: 企画 → canon → 設計 → 3 章 → 監査を一括実行
make story-s2       # S2: S1 ＋ 改稿ループ（台本での配線検証）
make story-s3       # S3: S2 ＋ 文体適用（台本での配線検証）
make baseline       # S0: canon を使わない単発プロンプト（比較の下限）
make experiment     # S0/S1 × seed の行列を回し、実験ノートの雛形を出す
make blind-pairs    # 凍結資産: 既存 runs/ から A/B ペアを作る（新規評定は実施しない）
```

> **運用上の注意（2026-10-24）**: 新しい研究実験は L1 のみです。以下の L2/L3 の手順と
> `make calibrate` / `make blind-pairs` は凍結資産の仕様・固定デモであり、新規の評定や
> 較正を再開するものではありません。G3/G4 は未測定、Arena の版を固定できない run は
> G5 を主張せず、L1 の値も探索的な参考値として扱います。

判定器は外部コマンドとして接続します（このリポジトリは鍵を持ちません）。

```bash
# どのモデル CLI でも、stdin にプロンプト / stdout に応答を返すものであれば使えます
python3 scripts/run_evaluation.py --candidate build/runs/<id>/text \
  --rubric harness/rubrics/story-quality-v0.yaml \
  --judge-command "python3 scripts/judge_adapter.py --llm-command 'my-model --json'"
```

L3（選好・識別）は、**どちらがどちらの系かを隠した**ペアでなければ意味を持ちません。
`scripts/make_blind_pairs.py` が `runs/` から判定用の束を作ります。

```bash
python3 scripts/make_blind_pairs.py --runs-root runs \
  --baseline s0 --candidate s1 --out build/pairs/2026-10-pilot
#   pairs/pair-001.json  {"pair_id","a","b"}   ← 評定者に渡すのはこれだけ
#   key.json                                    ← どちらが s1 か。評定者に見せない
#   judge_prompt.md / manifest.json             ← 判定手順と、除外したペアの理由
```

* 本文から**マーカー（`{{time: …}}` 等）と見出し**を除きます（S1 にしか無い手がかりを消す）
* 文字数の差が `--max-length-diff`（既定 25%）を超えるペアは、理由つきで除外します（§4）
* `a` が常に S1 にならないよう、**半分ずつ入れ替えてからシャッフル**します
* 同じ `--seed` なら同じ束ができます

### 4.3 生成パイプライン（Phase 2-A: Plan / Design / Draft）

固定タスク（`benchmarks/protocol-v1/tasks.yaml`）から **canon を生成し、設計書を検証し、3 章の本文を書き、監査まで通す**段階です。

```bash
python3 scripts/run_pipeline.py --task t01 --out runs            # 台本で配線を確認
python3 scripts/run_pipeline.py --task t01 --provider command \
    --command "python3 my_model_adapter.py" --out runs           # 実モデルを接続
python3 scripts/run_pipeline.py --task t01 --provider command \
    --command "python3 scripts/chat_operator.py --dir runs/operator/pilot"  # 鍵なし
OPENAI_API_KEY=... python3 scripts/run_pipeline.py --task t01 --provider command \
    --command "python3 scripts/model_adapter.py --model gpt-4.1" \
    --model gpt-4.1 --model-version 2025-04-14 --out runs       # 版を固定した実モデル
```

* 出力 `runs/<run_id>/`: `manifest.json`（モデル・温度・seed・**プロンプトのハッシュ**・git commit・プロトコル版）、
  `responses.jsonl`、`brief.md`、`canon/`（6 チャネル）、`plan.json`
* 生成物は**既存の canon スキーマ**で受け取ります。企画の成果物がそのまま監査の入力になるため、
  工程間の変換がありません。canon が監査の要求を満たさない場合は**生成段階で失敗**します
  （`--max_attempts` 回まで修復プロンプトで再試行し、それでも駄目なら `status: failed`）
* `runs/` は git 管理外。研究ノートには `manifest.json` の `git_commit` と `prompt_hashes` を引きます
* `--provider scripted` は**配線検証用の台本**（`benchmarks/protocol-v1/fixtures/*.json`）で、
  モデル出力ではありません
* `scripts/model_adapter.py` は、**版を固定した実モデル**を繋ぐ経路です（OpenAI 互換の
  `/chat/completions`。ローカルのゲートウェイも `--base-url` で使えます）。鍵は環境変数から読み、
  標準出力には本文だけを返します。`--dry-run` で送信内容を確認でき、`--model-version` を渡すと
  `manifest.json` の `model_version` が固定されます（これが §5 G5 を判定できる唯一の経路）。
  `--json-mode`（既定 `auto`）は plan のときだけ `response_format=json_object` を付けます
* `--dir` は **`build/` の下に置かないでください**。`build/` はセッションを越えて残らず、
  `responses/` を失うと**同じ本文をチャットに書き直してもらう**ことになります。
  `runs/operator/<名前>` は git 管理外ですが残ります
* `scripts/chat_operator.py` は、**鍵を持たない環境で実テキストを通す**ための経路です。
  プロンプトを `requests/` に書き出し、応答を `responses/` に置くと、次回からはそれを返します。
  応答が無ければ **exit 3**、プロンプトが変わった応答は **exit 4** で止まります。
  応答JSONには `provenance: {"origin": "fresh"}`、再利用なら
  `provenance: {"origin": "reused", "source_run_id": "..."}` を記録できます。
  未指定は `unspecified` であり、新規応答とは見なしません。`run_experiment.py` は
  request数、design attempts / repairs、初回findings、応答来歴を集計します。
  チャットに貼って返してもらう場合の受け渡しは `scripts/relay_prompts.py` が担当します
  （`export` でタグ付きの貼り付け用ファイル、`ingest` で返答案の取り込み）
  モデル版を固定できないため **G5 は満たさず**、値は参考値です
  （例: [`experiments/2026-10-pilot-t01-s0s1/`](experiments/2026-10-pilot-t01-s0s1/note.md)）
* `--system s0` は canon を渡さない単発プロンプト（比較の下限）。`--system s1` が canon＋設計書を使う系です
* design ステージは 8 種の設計書（brief / world / history / character / relation / plot / scene / voice）を
  生成し、各スキルの検査器で検証します。検査落ちは修復プロンプトで再試行し、それでも落ちたら
  `unresolved` として記録して続行します（fail-open。ゲートには入れない）。S3 の文体適用は設計の
  `voice.json` を既定に使います。`--no-design` は ablation・デバッグ専用で、本実験では使いません
* 各章には `{{time: day=3}}{{location: 王都}}` などのマーカーが入り、監査の根拠になります。
  モデルがマーカーを落とした場合は canon から補い、**補ったことを `warnings_ja` に残します**（黙って直さない）
* 実行の最後にゲート（`must_include` / `length` / `no_high_severity` / `all_checks_ran`）を評価し、
  未達なら終了コード 1 を返します（デモは `--report-only` で 0）

* デモ: [`harness/README.md`](harness/README.md)、期待値: `harness/cases/demo/EXPECTED.md`
* 設計方針: **総合点を出さない**（次元別プロファイル）、**根拠の無い判定は無効**、
  **文字数・会話率・段落長は良し悪しとして扱わない**、**監査カバレッジが違う CED は比較しない**
* 仕様変更の記録: [`research/curation/spec_changes_2026-10.md`](research/curation/spec_changes_2026-10.md)

### 4.4 二段階方式の最初の縦割り（Stage A → Stage B）

**構造化ゲームログを先に確定し、検証済みのログだけを小説化する**経路です。
[`docs/two_stage_slice.md`](docs/two_stage_slice.md) がスキーマ・検査器・限界の仕様です。

```bash
make gamelog-check   # Stage A の game_log.json を canon/plot/scene に対して検査
make two-stage       # 固定台本で Stage A → Stage B → 既存 continuity 監査までを配線確認
```

* Stage A は `game_log.json`（章・場面・`situation → actions → outcome`・`state_delta`）を生成し、
  `src/asc/gamelog/check.py` が **8 検査**を機械的にかけます（生死・現在地・`knows`・
  `travel_days`・伏線順序・`plot.json` の幕/転換点・`scene.json` の目的/対立/変化/開示・マーカー列）。
  死者は `record_reference` / `memory_mention` の `subject` + `medium` としてのみ現れます。
* 確定マーカー（`{{time:}}` / `{{location:}}` / `{{learn:}}` / `{{use:}}` / `{{foreshadow:}}`）は
  **`state_delta` から導出**され、Stage B 本文はその列を順序まで保持しなければなりません。
  Stage A が `clean` にならない場合、Stage B は実行しません（fail-closed）。
* 固定台本バンドルは [`experiments/2026-10-trpg-slice-t01/`](experiments/2026-10-trpg-slice-t01/note.md)。
  `--out` は `experiments/<id>/` 配下のみ（`build/` / `runs/` は拒否）。回答待ちの Arena リレーは
  同じバンドルへ `PROMPTS.md` を書き、`--resume` で記録済み応答を再生して続行します。
* 全工程の実応答試走は [`experiments/2026-10-full-t01/`](experiments/2026-10-full-t01/note.md)
  （Stage A 1 回で clean・Stage B 3 章 clean・計 3,047 字。人手照合で検出漏れ 4 件、`clean` は事実の整合を意味しません）。
* 日数の確定表（`$timeline`）を入れた Stage B v1.1 での再生成は
  [`experiments/2026-10-stageb-v11-t01/`](experiments/2026-10-stageb-v11-t01/note.md)。同じ検証済みログから
  3 章を作り直して `clean`（修復 1 回）。誤っていた「四日ぶり」は「六日ぶり」になり、時系列検査が
  照合して不一致 0 でした。ただし `clean` は目標長の達成も意味的整合も意味しません。
* **検査の検出力**は [`experiments/2026-10-detect-power-t01/`](experiments/2026-10-detect-power-t01/note.md)。
  既知の誤りを 5 種注入すると、日数・死者の現在時行動・保留事実の語彙は両腕で発火し、
  ログにない場所・移動と宣言のない数量は**どちらでも検出できません**（`scripts/probe_detection_power.py`）。
  ログを見ずに書いた本文は、ログ契約を当てると既に 3 件の `medium` 所見を持ちます。
* その穴への候補検査が [`experiments/2026-10-surface-checks-t01/`](experiments/2026-10-surface-checks-t01/note.md)
  と [`2026-10-surface-checks-t02`](experiments/2026-10-surface-checks-t02/note.md)。
  地名は「場所＋へ／に＋移動動詞」に絞れば clean 6 章で偽陽性 0・注入 1 件を検出しました（`advisory`、
  契約には未接続）。数量は**検査にできません** — 数詞は単独で指示対象を持たず、clean な本文でも
  1 章 2〜4 個が「ログに無い表記」として並ぶため、報告一覧に留めています（`src/asc/gamelog/surface.py`）。
  言い換え耐性の測定（clean 9 章で所見 0・言い換え 6/6・紛らわしい文 12/12）の途中で、実本文の
  「三日かけて王都へ着いた」から目的地の抽出欠陥が見つかり、修正しました。ただし「canon にあるが
  この章で宣言されていない」枝は章の外の移動を偽陽性にするため、契約には入れていません。
  事例を集めるため、`run_twostage.py --observe-surface` で結果を `observations` として走りに
  残せるようにしました（既定は無効。所見にも状態にも影響せず、修復は起きません —
  [`2026-10-surface-observe-t01`](experiments/2026-10-surface-observe-t01/note.md)）。
* 次の一手は**実モデル 3 標本**で、走らせる前に判定規則を固定しています:
  [`experiments/2026-10-realrun-a-t01/`](experiments/2026-10-realrun-a-t01/note.md)
  （`preregistration.json`・`runbook.md`・`scripts/measure_realrun_a.py`）。判定は地名の枝・
  章の長さ・繰り返す失敗の 3 つだけで、採否（blocking 化）はこのバッチでは決めません。
* バッチ A は 3 標本走り終え、**9 章すべて `clean`**（修復 4 回）でした。地名の観測は 0 件
  — ただし発火機会が 0 だったので精度の証拠にはならず、検査は advisory のまま据え置きです。
  その代わり、**検査だけが知っていてプロンプトに書かれていなかった規則**（未開示の語、死者の名を
  含む文の媒体）が見つかり、検査と同じデータから規則文を生成して Stage B プロンプト v1.2 に載せました
  （`docs/two_stage_slice.md` §22。効果は未測定）。
  長さは 1/3・3/3・3/3 で `mixed`（外れたのは修復後の 2 章だけ）。繰り返す失敗は、最終報告で
  数えると 0 ですが、**修復前**には「三年前」（3 標本すべての ch02）と死者の媒体不足（2 標本）が
  出ており、登録文がその数え方を決めていませんでした（両方の読みを記録）。
* **S1 全体（plan → 8 設計 → draft → 監査）の事前登録 1 標本実走り**は
  [`experiments/2026-10-realrun-b-t01/`](experiments/2026-10-realrun-b-t01/note.md)（バッチ B）と
  [`experiments/2026-10-realrun-b2-t01/`](experiments/2026-10-realrun-b2-t01/note.md)（バッチ B2、
  `design-history` v1.1）です（`docs/two_stage_slice.md` §23・§24）。また継続性監査の
  `dead_character_reappears` は、死者の行為・発話（`high`）と、参照文脈（引用内・記録/回想の手掛かり・
  非主語形）の言及を分け、参照言及を `observations`（`dead_character_reference`）に残すようにしています
  （同 §25）。任意 premise の標準創作フロー（単体・部分改訂・continuation・入れ子・共有 world）の
  実応答 dogfood は [`experiments/2026-10-dogfood-01/`](experiments/2026-10-dogfood-01/note.md) に記録しています。
* `--strict-timeline` は誤った日数を**修復対象**にします（既定は警告のみ。v1.1 の試走で
  「四日ぶり」→ 修復 1 回を確認）。
* 二段階方式と**直接生成**（同じ canon・同じ設計で draft 段のみ）の L1 参考比較は
  [`experiments/2026-10-l1-pair-t01/`](experiments/2026-10-l1-pair-t01/note.md)。必須語 1.0・禁止 0 は
  両方で同じで、**L1 のパターン集合は 2 条件を識別しません**。差は指標ではなく「ログという照合先が
  あるか」にあります（`make` の対象外、`scripts/compare_l1_arms.py` で再計算できます）。
* Stage B 単独の実応答試走は [`experiments/2026-10-stageb-solo-t01/`](experiments/2026-10-stageb-solo-t01/note.md)
  （3 章 `clean`・修復 1 回。ただし `clean` は事実の整合を意味しません）。
* Stage A の検査は、未知キーの報告、同一場面の `learn`→`use`、現在時 `subject`、死者の `used_facts`、章 ID の重複と章順、人物の現在地の連続性まで見ます。Stage B は題材の必須語を**作品単位**でゲートします。
* **日数・場所・時系列は決定論側が決めます**（`src/asc/gamelog/world.py`）。canon の `travel_days` を
  無向グラフとして最短経路を解き、ログを畳んで `timeline.json`（`trpg-timeline-v1`、派生成果物）を
  作って Stage B のプロンプトへ渡します。モデルには計算させません。本文側は、**明示された日数だけ**を
  表と照合し（`timeline_consistency`）、既定は警告・`--strict-timeline` で修復対象です。
  抽象表現（しばらく・明け方）と、書かれていない誤りは対象外です。
* **Stage B だけを試す**ときは `--stage b --game-log <verified game_log.json>` を使います。Stage A は
  実行せず、与えたログをその場で再検査し、`clean` のときだけ本文化します（不合格は fail-closed。
  `--allow-unverified-log` を明示した場合だけ続行し、`unverified: true` を残します）。
* **再開の契約**: `state.json` の `resume_command` はそのまま実行でき、失敗時も `state.json` を書きます。
  `--resume` は記録を切り詰めず、条件（seed・温度・試行回数・provider・プロンプト・入力ハッシュ）が
  変わっていれば拒否します（意図的な変更は `--allow-config-change`、差分は `config_changes` に記録）。
  改変された記録（`response_sha256` 不一致）は再生しません。
* **これは配線確認であり、実モデルの応答でも効果の観測でもありません。** L1 は構造・衛生の検査で
  あり、質・面白さ・選好の証拠にはなりません。L2/L3 は `frozen_not_measured` のままです。
  S1 直接生成との L1 ペア比較は Phase 3 の未実施課題です。
* 契約文と実装の差（現在地の連続性、死者言及の章スコープ、マーカーと本文事実の乖離、`--resume` の記録保全）は
  [`research/curation/two_stage_stage1_audit_2026-10-26.md`](research/curation/two_stage_stage1_audit_2026-10-26.md) に
  再現例つきでまとめています。**検査が `clean` を返すことは意味的整合性の保証ではありません。**
  `make probe-gamelog` で同じ変異を再実行できます。

## 5.  品質保証

* `make test` — パーサ（青空文庫ルビ記法／小説家になろう HTML）、NUXT ペイロード、PDF 描画、
  JSONL ラウンドトリップのユニットテスト
* `make report` — レコード数・ジャンル分布・出版年分布・文字数合計・必須フィールド欠損の集計
* `make skills-check` — `SKILL.md` の frontmatter・リンク・500 行制限、継続性監査の期待値、
  評価ハーネスのゲート（根拠必須・回帰判定・カバレッジ警告）を検査
* 場面フレーム（schema 1.1、[`docs/two_stage_slice.md`](docs/two_stage_slice.md) §27）は `--gamelog-schema 1.1` で
  有効化します（既定は 1.0）。フェイズ（導入・本編・クライマックス・結末）、結果の種別、救済、次場面への持ち越しを
  記録し、検査 `scene_frame` で確かめます。実モデルでの 1.1 の確認は未実施です。
* `make gamelog-check` / `make two-stage` — 二段階方式の Stage A ログ検査と Stage A→B の
  固定台本配線。決定論的な回帰テスト（`tests/test_gamelog_*.py`、
  `tests/test_twostage_pipeline.py`）が `make ci` で毎回走ります
* CI: `.github/workflows/research-check.yml` が**全 push / 全 PR** でカタログ整合・全テスト・
  デモの監査と評価を実行します（ローカル 30〜60 秒）。実行枠の設計は
  [`docs/ci.md`](docs/ci.md) を参照してください
* `dataset-refresh`（データ取得とテキスト公開）は別ワークフローで、**同時実行数を絞って**
  CI の枠を空けます

## 6.  次フェーズ候補

対照群 30 作品は選定承認・凍結済みです（[`controls.proposed.md`](benchmarks/protocol-v1/controls.proposed.md)、
[`controls.approved.json`](benchmarks/protocol-v1/controls.approved.json)、
[`controls.json`](benchmarks/protocol-v1/controls.json)）。この承認は L1 の比較対象を
決めるもので、G3/G4 の再開や人間による品質評定ではありません。

* Arena の chat operator / relay による S0〜S3 の L1 パイロット（まず t01、その後 10 題×3 seed）。版を固定できないため、結果は探索的な参考値として記録する
* 二段階方式の Phase 3: 共有 `canon` / `design`（`t01-s1-seed0`）の上で、直接生成 S1 と
  Stage A→B の **L1 のみ**をペア比較する。自己完結バンドルと入力差（前章本文の有無）の明示が必要。
  [`docs/two_stage_slice.md`](docs/two_stage_slice.md) §10 を参照
* L1 の失敗類型を根拠に、スキル／プロンプト／パイプラインを一つずつ変更し、同じ条件で再測定する
* 設計書を canon 生成に使う順序（design-first）の検討（現行は plan → design。`plan-canon` の作り替えを伴うため別件）
* 文字種・文構造・会話率などの言語統計に基づく feature 抽出
* **凍結**: L2/L3 の実証・較正・人間評定・それらの追加開発（再開には利用者の明示的な方針変更が必要）
* 縦組み PDF / EPUB 出力（現在は横組み A5）

## 7.  ライセンスと引用

* 本リポジトリのコード: MIT（`LICENSE` を参照）
* 取得データ: 各ソースの規約に従います
  （青空文庫 = 「青空文庫収録ファイルの取り扱い規準」、
   小説家になろう = 「なろうデベロッパー利用ガイドライン」と作品ごとの著作権）
* データセットを論文・学習に用いる際は、**出典 URL と取得日を明記**してください。
