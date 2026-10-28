# AutoStoryCreationAI リポジトリ分析レポート

**作成日:** 2026-10-28
**対象ブランチ:** `arena/9195f0c3-autostorycreationai` (コミット `e5ef373`、P0/P1 U-C/U-D/U-E 実装済み)
**対象:** リポジトリ全体 (1,748 ファイル、コード・ドキュメント・研究資料・実験記録・サンプルデータ)

---

## 1. エグゼクティブサマリー

本リポジトリは「AIによる自動創作活動（ストーリー・キャラクター・世界観・歴史など）を支える研究用道具箱」であり、**データセット構築パイプライン**、**13種類の実行可能スキル**、**生成パイプライン (Plan→Design→Draft→改稿→文体適用)**、**創作プロジェクト管理**、**評価ハーネス (L1/L2/L3)** を一貫して備えています。

現状の構造は **「研究プロトタイプとしては整然とし、拡張の余地を残している」** 一方で、**「スケールアップ（大規模・長期運用・多人数協働）にそのまま耐える構造ではない」** と判断します。主な理由は以下の通りです。

| 評価観点 | 判定 | サマリー |
|---|---|---|
| スケールアップ適性 | △→○ 条件付き・改善中 | モジュール分割・バージョン管理・スキルレジストリ・インデックス/差分検査・研究カタログ↔スキル紐付けが実装済み。JSONファーストストアの限界と大量実験アーティストのコミット混在が残るボトルネック |
| データの有機的結合 | △→○ 部分的・改善中 | 作品メタデータ統一スキーマ・canonによる工程連結は良好。スキルレジストリと技法カタログのコードレベル紐付け（U-E）により研究資産と生成工程の接続が強化。データセットと生成工程の接続はドキュメントレベルのまま |
| 未使用/矛盾/放置データ・設計 | ⚠→○ ほぼ解消 | P0でPDF出力削除・R15文言整合・旧ドキュメント削除を完了。凍結L2/L3コードは方針で凍結維持。実験アーティストは検証段階として保持中 |
| 分割粒度の妥当性 | ○ 良好 | 変更なし |
| インターフェースの妥当性 | ○ 良好 | スキルレジストリと技法カタログ読み込みにより、研究カタログ↔スキル間もコード級インターフェースで接続 |

---

## 2. リポジトリの目的と制約条件

### 2.1 目的（README・docsより抽出）

1. **データセット構築**: 青空文庫（パブリックドメイン日本語文学）と小説家になろう（Web小説）から、統一スキーマの書誌メタデータJSONLとUTF-8プレーンテキストを生成。PDF出力は廃止済み。
2. **AI自動創作の基盤**: 13スキル（企画核、世界規則、歴史年表、人物核、人物関係、筋立て、場面情報、語り文体、整合性台帳、改稿ループ、分岐構造、翻案、評価ハーネス）を実行可能な形で実装。
3. **生成パイプライン**: Plan（canon生成）→ Design（8種設計書）→ Draft（3章本文）→ 監査 → 改稿 → 文体適用 (S0–S3)。
4. **創作プロジェクト管理**: 任意の前提から作品を作り、続き・改訂・分岐・入れ子・編纂・bundleによる保存/検証/復元。
5. **評価**: L1（決定論的検査）を対象。L2（モデル判定）・L3（人間評価）は2026-10-24に運用凍結。

### 2.2 制約条件（明示されたもの）

- 常駐ワーカーによる無人運用は当面範囲外（人間が開始・採用判断・読後のフィードバックを行う）。
- L2/L3の実証・較正・人間評定は凍結（再開には利用者の明示的な方針変更が必要）。
- Arenaのモデル版を固定できないため、G5（再現性）は主張せずL1値も探索的参考値。
- 生成物は `runs/`（git管理外）に置かれ、セッションを越えて残る保証がない。残すには `--root works` または `bundle export` が必要。
- 総合点は出さない（次元別プロファイル、根拠の無い判定は無効）。
- データ収集は各ソースの利用規約に従い、著作権存続作品の再配布は行わない。

---

## 3. 構造全体像

```
├── configs/dataset.yaml          # 取得対象・件数・フォント等の設定（型付きdataclassで読込）
├── data/                         # 生成物（大半は.gitignore対象。チェックアウト時はmanifest.jsonのみ）
├── docs/ (21ファイル)            # 設計・スキーマ・法務メモ・ロードマップ・運用モデル等
├── experiments/ (26実験+README)  # 実験ノート（results.json + note.md、raw run出力はコミットしない）
├── harness/                      # 評価ケース・ルーブリック・禁止パターン・fixture
├── prompts/ (21テンプレート)    # AIへの注文票（plan/design/draft/revise/stage等）
├── research/                     # 創作技法の研究コーパス（curated/catalog/program/inventory/curation）
├── samples/                      # 同梱サンプル（書誌抜粋・373作品カタログ・小規模本文サンプル）
├── scripts/ (41ファイル)         # CLIエントリポイント（setup_dataset, run_pipeline, story_project等）
├── skills/ (13スキル)            # SKILL.md + references/（スキーマ・測定・技法）
├── src/asc/                      # ライブラリ本体（config, http, jsonl, schema, sources, text, render,
│                                  story, evaluation, pipeline, project, 各スキル実装等）
└── tests/ (73ファイル)           # pytest（実装とほぼ1対1の対応）
```

---

## 4. 分析項目ごとの評価

### 4.1 スケールアップに適した構造になっているか

#### 良い点（スケールに寄与する設計）

1. **スキル単位のモジュール化**: `skills/<name>/` に `SKILL.md`（仕様）+` references/`（スキーマ/測定/技法）+` src/asc/<name>/`（実装）という同じレイアウトを13スキルで統一。新スキル追加のパターンが明確。
2. **パイプラインの段階分離**: Plan → Design（8種設計書）→ Draft → 改稿 → 文体適用。各段階が独立した責務を持ち、失敗時は `unresolved` 記録で続行（fail-open）または `failed` で停止（fail-closed）の使い分けが明確。
3. **バージョン化されたプロジェクトモデル**: `src/asc/project/schema.py` は全レコードに `record_type` と `schema_version` を持ち、コンテンツハッシュ (`spec_sha256`) で不整合検出。JSONファーストながら互換性を意識した設計。
4. **トレーサビリティ**: `RunLedger`（`src/asc/pipeline/run.py`）が `git_commit`、`prompt_hashes`、`model_version`、`responses_sha256` を記録。再現性の骨格。
5. **プロバイダ抽象化**: `scripted`（台本）/ `command`（外部コマンド）/ `arena`（relay）の切り替えにより、オフライン配線検証と実生成を分離。
6. **CI設計**: `research-check.yml` でカタログ整合・全テスト・固定デモを毎push/PR実行。`dataset-refresh.yml` は別ワークフローで同時実行数を絞り、CI枠を確保。

#### スケールアップにおける懸念点（実装済み・残存）

1. **JSONファーストストアの限界**: プロジェクトレコード・チェックポイント・アーティファクトをすべてJSONファイルで管理。作品数・章数・ノード数が増加するとファイル探索・整合性検査（`doctor`）のコストが線形以上に増大する恐れ。ロードマップも `R-05: index、incremental検査、依存queue` を「規模の実測が引き金に達していない」として後置しており、**現状では大規模運用を想定していない**。`doctor.py` にインデックスベース差分検査（P1 U-D）を導入し、変更ノードのみ詳細検査することで部分的に軽減。

2. **スキルレジストリの導入（完了 - P1 U-C）**: `configs/skills.yaml` に全13スキルを登録し、`src/asc/skills_registry.py` で `SkillEntry`/`SkillRegistry` による動的参照・チェッカースクリプト実行を実装。新スキル追加の手動配線を削減。

3. **インデックスと差分検査（完了 - P1 U-D）**: `src/asc/project/index.py` で `.index.json` データモデルとチェックサム記録・差分検知を実装。`src/asc/project/store.py` で保存時のインデックス更新を統合。`doctor.py` で変更ノードのみ詳細検査するインデックスベース差分検査を統合済み（26テスト通過）。

4. **研究カタログとスキルのコードレベル接続（完了 - P1 U-E）**: `configs/skills.yaml` の全13スキルに `technique_categories` を追加。`src/asc/skills_registry.py` に `TechniqueEntry`、`techniques.jsonl` 読み込み、`techniques_by_category`/`techniques_for_skill`/`category_counts` を実装。研究カタログ（488件）とスキルがコードレベルで紐付き、スキル別・カテゴリ別の技法取得が可能。

5. **実験アーティストのリポジトリ混在**: `experiments/` 配下に大量のJSONアーティスト（canon/design/text/付録等）がコミット済み（ファイル数1,748の大半）。生成物をコミットすることはリポジトリ肥大化と差分ノイズの原因。`experiments/README.md` では「結果と限界だけをコミット」と規約化されているが、実際にはアーティストが残っているケースがある。

6. **データセット未同梱**: チェックアウト時の `data/datasets/` には `manifest.json` のみ。実際の書誌JSONL・本文は別途ダウンロード必要。オフライン/初回構築時の摩擦。

7. **レスポンス生ログの非永続性**: `runs/` はgit管理外でセッションを越えて残る保証がない。再実行や監査には元の応答実体が必要なケースがある。

### 4.2 全てのデータが有機的に結合されているか

#### 有機的に結合している部分

1. **作品メタデータの統一スキーマ**: `src/asc/schema.py` の `Work`/`Author` は青空文庫・小説家になろうの双方を `<source>:<native id>` のグローバルIDで統一し、JSONL（1行=1レコード、UTF-8, `ensure_ascii=False`, キー順固定）で出力。データセット内での有機的結合は確保。
2. **canon（設定台帳）による工程連結**: PlanのcanonがDesignの8種設計書の入力となり、Draftの本文生成・監査の照合基準となる。マーカー（`{{time:}}`/`{{location:}}`等）とcanonが双方向で参照され、工程間の変換がない（canonスキーマでそのまま受け取る）。
3. **プロジェクトモデルの関連付け**: project→node→revision→link→checkpoint→artifact が `id`/`sha256`/`content_version` で紐付き、分岐・入れ子・継承を構造化。

#### 結合が弱い・断絶している部分

1. **研究カタログとスキルの接続（完了 - P1 U-E）**: `configs/skills.yaml` の全13スキルに `technique_categories` を追加し、`src/asc/skills_registry.py` で `TechniqueEntry`/`techniques_for_skill`/`techniques_by_category`/`category_counts` を実装。研究カタログ（488件）とスキルがコードレベルで紐付き、スキル別・カテゴリ別の技法取得が可能。`skill_pipeline_mapping.md` は設計ドキュメントとして残存。
2. **データセットと生成工程の接続**: 収集した青空文庫/なろうの本文・メタデータは「研究素材」として位置づけられ、生成パイプライン（story creation）の入力として直接利用される流れは定義されていない。データセット構築と創作生成が二本の別柱として並列している。
3. **実験間の横断的索引**: 各実験ディレクトリは `results.json`+`note.md` で独立。実験間の条件差分・モデル版比較・プロンプト版比較を機械的に横断するインデックスや集計スキーマがない。

### 4.3 使用されていないデータ・矛盾したデータ・放置された設計はないか

#### 明確な矛盾（コードと文書の不一致）

| # | 矛盾箇所 | 内容 | 状態 |
|---|---|---|---|
| C1 | PDF出力 | READMEは「既存PDFは全てテキスト化の上で完全削除済」「テキスト中心・PDF削除」と記述。一方、`src/asc/render/pdf.py`/`fonts.py`、`configs/dataset.yaml` の `pdf` セクション、`PdfConfig` dataclass、`purge-pdfs` サブコマンドが現存。 | **解決済み（P0）**: `src/asc/render/pdf.py`/`fonts.py` を削除。`scripts/setup_dataset.py` から `--pdf`、`build_renderer`、`cmd_purge_pdfs`、PDF描画コードを削除。`tests/test_render_pdf.py`、`tests/test_media_verify.py` のPDF依存を削除。`requirements.txt` から `fpdf2`、`pypdf` を削除。 |
| C2 | R15 取り扱い | `docs/legal_and_ethics.md` は「R15は既定で除外」と記述。一方、`configs/dataset.yaml` は `include_r15: true`。 | **解決済み（P0）**: `docs/legal_and_ethics.md` の文言を「R15対象作品を含む」に修正し、設定と文書を整合。 |
| C3 | 旧ドキュメント | `docs/data_setup.md` はPDFを通常成果物のように記述する旧手順。現行 `make data` はテキスト中心・PDF削除。READMEで「設定と今の実行コードを優先して確認」と注意喚起されているが、旧文書が残存。 | **解決済み（P0）**: `docs/data_setup.md` を削除。 |

#### 未使用・放置気味のデータ/設計

1. **凍結L2/L3コードの保持**: `scripts/judge_adapter.py`/`judge_pairs.py`/`calibrate_judge.py`/`make_blind_pairs.py`、`harness/rubrics/`、`harness/fixtures/` は「凍結資産として保存」と明記され、新規評定・較正は行われない。コードとしては動くが、運用上は死にコードに近い。保持の意義（回帰防止・デモ再生）は理解できるが、メンテナンスコストを伴う。
2. **類似実験ディレクトリの重複**: `2026-10-realrun-a-t01` / `-b-t01` / `-b2-t01`、`2026-10-surface-checks-t01` / `-t02` など、似た目的の実験が複数存在。各 `note.md` で限界・次に試すことは記載されているが、どれが「最新の正」かがパッと分からない。
3. **未使用のmanifest系**: `benchmarks/protocol-v1/controls.json` / `controls.approved.json` / `controls.proposed.json` / `controls.proposed.md` は対照群30作品の承認記録。L2/L3凍結により実質的に使用されていない（L1比較対象としては選定済みだが測定なし）。
4. **`harness/` の一部**: 評価ケース・fixtureはL1デモで使用されるが、L2/L3凍結により一部はデモ専用。

#### 放置された設計（意図的な後置を含む）

- `R-04` スキルレジストリ、**実装済み（P1 U-C）**: `configs/skills.yaml` と `src/asc/skills_registry.py` でスキルレジストリを導入。
- `R-05` インデックス/差分検査、**実装済み（P1 U-D）**: `src/asc/project/index.py`、`store.py`、`doctor.py` でインデックスベース差分検査を実装（26テスト通過）。
- `WorldEvent`/`KnowledgeState`/`CharacterState` はロードマップで明示的に後置。これは「放置」ではなく「意図的な先送り」だが、実現のトリガー（実測の閾値超過）が定義されていない。

### 4.4 適切な粒度で分割されているか

| 対象 | 粒度評価 | 根拠 |
|---|---|---|
| スキル（13種） | ○ 適切 | 各スキルが単一責任。SKILL.mdで「いつ使うか/入力/手順/出力/合格条件/しないこと」を明確。 |
| パイプライン段階 | ○ 適切 | Plan/Design/Draft/改稿/文体適用が独立。Design内も8種設計書に依存順で分割。 |
| プロジェクトモデル | ○ 適切 | project/node/revision/link/checkpoint/artifact を別レコード型とし、各々バリデーション。 |
| ソースコードモジュール | ○ 〜 △ | `src/asc/` 配下は機能別によく分割。ただし `design.py` は571行とやや大型。`pipeline/run.py` の `RunLedger` は192行で適切。 |
| テスト | ○ 適切 | 73テストファイルが実装とほぼ1対1。各スキル・パイプライン・プロジェクト機能をカバー。 |
| ドキュメント | △ やや分散 | `docs/` (21ファイル) + `research/curation/` (27ファイル) + 実験 `note.md` で同等情報が重複するケースあり（例: `spec_changes_2026-10.md` 系4ファイル、`two_stage_stage1_audit` など）。 |

### 4.5 適切なインターフェイスで接続されているか

| インターフェース | 評価 | 根拠 |
|---|---|---|
| 設定読み込み (`config.py`) | ○ | YAMLを型付きdataclassに変換。未知キーを無視する前方互換設計。 |
| データセットスキーマ (`schema.py`) | ○ | `Work`/`Author`/`AuthorRecord` に `to_json`/`from_json`。統一JSONLスキーマ。 |
| パイプライン (`run.py`, `design.py`, `draft.py`) | ○ | `RunLedger` がmanifest・プロンプトハッシュ・応答ハッシュを記録。プロバイダ抽象化。 |
| プロジェクトモデル (`project/schema.py`) | ○ | `record_type`/`schema_version`/`spec_sha256`/`canonical_json` でレコード整合性を機械検証。 |
| スキル↔実装 | ○ | `skills/<name>/SKILL.md` と `src/asc/<name>/`、`scripts/check_*.py` の対応が明確。 |
| **研究カタログ↔スキル** | ○ | `configs/skills.yaml` の `technique_categories` と `src/asc/skills_registry.py` の `techniques_for_skill`/`techniques_by_category`/`category_counts` でコード級紐付けを実装（P1 U-E）。488件の技法とスキルがコードレベルで接続。 |
| **データセット↔生成工程** | △ | データセット構築CLIと創作パイプラインが別経路。統一された受け渡しインターフェースなし。 |
| 評価ハーネス | ○ | L1/L2/L3を層分離。`patterns.yaml`、`rubrics/`、`fixtures/` で判定器を外部コマンド接続。 |
| CLI | ○ | `story_project.py`/`run_pipeline.py`等でサブコマンド統一。`--json`で機械可読出力。 |

---

## 5. 改善提案（優先度付き）

### P0: すぐに手をつけるべき（正当性・一貫性の担保）

**U-A. 矛盾の解消（C1–C3）** ✅ 完了
- `src/asc/render/pdf.py`、`src/asc/fonts.py` を削除。`scripts/setup_dataset.py` から `--pdf`、`build_renderer`、`cmd_purge_pdfs`、PDF描画コードを削除。`tests/test_render_pdf.py`、`tests/test_media_verify.py` のPDF依存を削除。`requirements.txt` から `fpdf2`、`pypdf` を削除。
- `docs/legal_and_ethics.md` の「R15既定除外」文言を「R15対象作品を含む」に修正し、`include_r15: true` と整合。
- `docs/data_setup.md` を削除。

**U-B. 大規模アーティストのリポジトリ外出し** △ 保留
- `experiments/` 配下の生成JSONアーティスト（canon/design/text等）は、現時点では検証段階・成果物ではない。確認終了後に削除。続き物検証データは保持。運用複雑化ならリポジトリ外出し（Git LFS/Release）を採用。
- 現状では `experiments/` に 1,216 ファイルが存在。リポジトリ肥大化と差分ノイズが懸念される。

### P1: 次の改善サイクル（運用摩擦の削減）

**U-C. スキルレジストリの導入（R-04）** ✅ 完了
- `configs/skills.yaml` に全13スキルを登録し、`src/asc/skills_registry.py` で `SkillEntry`/`SkillRegistry` による動的参照・チェッカースクリプト実行を実装。

**U-D. インデックスと差分検査（R-05）** ✅ 完了
- `src/asc/project/index.py`、`store.py`、`doctor.py` でインデックスベース差分検査を実装（26テスト通過）。変更ノードのみ詳細検査。

**U-E. 研究カタログとスキルのコードレベル接続** ✅ 完了
- `configs/skills.yaml` の全13スキルに `technique_categories` を追加。`src/asc/skills_registry.py` に `TechniqueEntry`、`techniques.jsonl` 読み込み、`techniques_by_category`/`techniques_for_skill`/`category_counts` を実装。488件の技法とスキルがコードレベルで紐付き。

**U-F. データセットと生成工程の接続** △ 未着手
- 収集済み本文・メタデータを創作パイプラインの「参照素材」として取り込めるインターフェース（`--source-dataset` 等）を検討。現状の「データ構築」と「創作生成」が完全に分離している状態を緩和。

**U-G. 実験の横断索引と正体明確化** △ 未着手
- `experiments/README.md` に「最新の正」を示す実験一覧（インデックス）を追加。類似実験（realrun a/b/b2、surface-checks t01/t02）を統合または非推奨標記。

### P2: 長期・大規模運用（必要になったら）

**U-H. ストレージ層の見直し** △ 見送り（ユーザー方針）
- 成果物蓄積段階になってから再検討。今回は見送り。`project/schema.py` のバリデーション層はそのまま流用可能。

**U-I. 応答ログの永続化方針** ✅ 採用（ユーザー方針）
- `runs/` がセッションを越えて残らない問題に対し、重要実験の応答実体を `experiments/<id>/responses/` に明示的に保存する運用をルール化（`dogfood-01` が先行事例）。

### 保守（並行して可）

**M-1. ドキュメントの整理と旧文書の非推奨化** ✅ 部分完了
- `docs/data_setup.md` を削除済み（P0）。残存する旧手順文書を現行の `README.md`/`docs/quickstart.md`/`docs/standard_flow.md` に一本化。

**M-2. 凍結L2/L3コードの扱い方針** ✅ 方針確定
- 凍結維持（ユーザー方針）。変更しない。凍結資産として保持し、メンテナンスコストを最小化。

---

## 6. 付録：主要指標とファイル構成サマリ

| 項目 | 値 |
|---|---|
| 総ファイル数 | 1,751 |
| テストファイル | 71 |
| スキル数 | 13 |
| プロンプトテンプレート | 21 |
| ドキュメント (`docs/`) | 20 |
| 研究資料 (`research/`) | 多数（curated/catalog/program/inventory/curation） |
| 実験ディレクトリ | 26 |
| サンプルデータ | 373作品カタログ含む |
| スケールアップへの明示的な後置項目 | WorldEvent/KnowledgeState/CharacterState（skill registry、index/incremental検査は実装済み） |
| 凍結済み評価層 | L2/L3（2026-10-24より、凍結維持） |

### 主要ディレクトリの役割

| パス | 役割 | スケールへの影響 |
|---|---|---|
| `src/asc/` | ライブラリ本体 | モジュール分割は良好。大型ファイル（`design.py` 571行）の分割検討。 |
| `scripts/` | CLIエントリポイント | 41ファイル。標準入口は `story_project.py`（U-01決定）。 |
| `skills/` | 13スキルの仕様+実装 | 粒度適切。新スキル追加パターンが定型化。 |
| `tests/` | pytest | 実装と1対1。CIで毎回実行。 |
| `experiments/` | 実験ノート | 生成アーティストのコミット混在がリポジトリ肥大化の要因。1,216ファイル。検証段階・成果物ではない。 |
| `research/catalog/` | 技法488・ツール96・書誌529 | ドキュメント資産。コードとの有機的接続なし。 |
| `data/` | 生成物 | `.gitignore` 対象。チェックアウト時はmanifestのみ。 |

---

## 7. 総評

本リポジトリは**研究プロトタイプとしては非常に考え抜かれた構造**を持っています。スキル単位のモジュール化、バージョン化されたプロジェクトモデル、トレーサビリティ（commit/prompt_hash/レスポンスハッシュ記録）、プロバイダ抽象化、CI設計など、スケールアップを見据えた骨格は既に備わっています。

ただし、**「そのまま大規模システムとして運用する」には至っていない**点が複数あります。特に JSONファーストストアの限界、スキルレジストリ未実装、大量実験アーティストのコミット混在、データセットと生成工程の断絶、PDF/R15などの文書・コード矛盾は、改善すればすぐに効果が現れる項目です。

ロードマップ（`practical_roadmap.md`）は「作品を作って直す循環」を北極星とし、規模対応は「実測が引き金になってから」としており、この方針自体は妥当です。ただし、**引き金となる実測指標（作品数、チェック時間、ファイル数、CI所要時間など）を定義し、超過時に自動的に後置項目（R-04/R-05等）へ着地する仕組み**を持つと、より計画的なスケールアップが可能になります。

---

**以上、分析レポートを終了します。** 改善提案の優先順位や、具体的な実装方針（例: スキルレジストリのYAML設計、Git LFS移行の範囲等）についてさらに詳細が必要な場合はお知らせください。