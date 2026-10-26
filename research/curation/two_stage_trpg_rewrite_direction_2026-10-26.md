# 今後の設計思想と開発方針：パイプラインによる整合性担保と「擬似 TRPG ログ → 小説化リライト」二段階方式

- 日付: 2026-10-26
- 基準コミット: `eefb3a4`（[PR #44](https://github.com/jack4andmanastalk-byte/AutoStoryCreationAI/pull/44) マージ時点）
- 前提資料:
  - [`research/curation/plot_to_draft_2026-10-25.md`](plot_to_draft_2026-10-25.md)（Plot → Draft 縦割り接続と `t01-s1-seed0` ペア実験記録）
  - [`experiments/2026-10-plot-ablation-t01/paired/results.json`](../../experiments/2026-10-plot-ablation-t01/paired/results.json) / [`note.md`](../../experiments/2026-10-plot-ablation-t01/paired/note.md)
  - [`research/curation/materials_inventory_2026-10-25.md`](materials_inventory_2026-10-25.md)（既存 13 スキルと採録資料の棚卸し）
  - [`research/curated/narrative/japan_trpg/report.md`](../curated/narrative/japan_trpg/report.md)（日本の TRPG シナリオ技法カタログ）
  - [`docs/continuous_creation_roadmap.md`](../../docs/continuous_creation_roadmap.md)・[`docs/evaluation_scope.md`](../../docs/evaluation_scope.md)・[`docs/protocol.md`](../../docs/protocol.md)

---

## 1. 今回の実験から得られた結論と設計思想

### 1.1 モデル単体のテキスト生成だけでは継続的な整合性は維持できない

`t01-s1-seed0` における Plot → Draft（`narrative/us_2026:T004`）のペア比較実験、および先行する S0〜S3 パイロット実験を通じて確認された第一の結論は、**「AI/モデル単体のテキスト生成能力だけに頼って、整合性のあるストーリーを継続的に創作することは困難であり、スキル・ツール・データセット・ハーネス・パイプラインによるモデル外の作り込みが不可欠である」**という点である。

今回の実験プロセス自体が、以下の 4 つの層でモデル外の仕組みがなぜ必要かを具体的に示している。

1. **設計段階（Design）ですら一発では台帳と整合しない（検査器と修復ループの必要性）**
   - `t01-s1-seed0` の共有準備（`shared_prep`）でも、8 種の設計書を生成する過程で `history.json`（通史・因果設計、タグ `8BDA`）の初回出力が構造検査で不合格となり、具体的な違反内容をフィードバックする修復ステップ（`design:history:repair`、タグ `3B86`）を経て初めて `status: clean` に到達した。
   - 本文を書く前の構造化設計の段階でさえ、決定論的なチェッカーと修復ループがなければ、設定台帳（`canon`）の人物・事実・時系列との矛盾が残る。
2. **設計書をそのまま全文渡すことはできず、章単位の厳密な情報スライスが要る**
   - 設計書（`plot.json` や `scene.json`）を全文そのまま本文生成プロンプトへ投入すると、コンテキストが肥大化するだけでなく、**後の章で明かされるべき真相や結末を前の章で先取りして書いてしまう（知識境界・開示順序の崩壊）**。
   - そのため PR #40〜#44 の実装では、`plot.report.json` が `clean` かつ現行 `canon` で `check_plot` を通る場合に限り、**その章に属する幕の問いと転換点の選択（2 行のみ）**を切り出して Draft プロンプトに渡す制御が必要となった。
3. **「小説を書く負荷」と「状態・マーカーを厳密に管理する負荷」の同時発生**
   - 現行の Draft 工程では、モデルは 1 回の生成で「三人称限定視点・文体制約を守った自然な散文を書くこと」と、「日付・場所・事実の獲得（`learn`）・伏線の設置と回収（`foreshadow setup/payoff`）・死者の扱いを正確にマーカー付きで管理すること」を同時に要求される。
   - 実際のペア比較（`t01-s1-seed0`）でも、`no_plot` 条件の ch02 では本文中で父の沈黙の理由に触れながら `{{foreshadow: fs-004 payoff}}` マーカーが 1 箇所欠落したことで `unresolved_foreshadow` 1 件が計上された。また、物語開始前に死亡している人物（`johan`）に関する記録や会話中の言及が、文字列ベースの監査器では `dead_character_reappears`（`name_mention` による `medium` 報告）として `no_plot` で 7 件・`with_plot` で 5 件検出された。
4. **章をまたぐ媒介効果と、永続的な状態管理の必要性**
   - 第 1 章のプロンプト差を 2 行だけに統制できても、第 2 章以降は「前章の本文末尾」を入力に含むため、前章のわずかな出力差が後続章へ伝播する。また、マルチターン実行において一時ディレクトリ（`runs/` や `build/`）に状態を置くとセッション境界で失われるため、入力・試行・リレー応答・ハッシュを単一バンドル（`experiments/<id>/`）に閉じ込める基盤整備が不可欠であった。

---

## 2. 次期アーキテクチャ方針：「擬似 TRPG 風システムによるゲームログ生成 → 【読める物語】へのリライト」二段階方式

### 2.1 核心となる設計思想：シミュレータ（GM）と語り手（小説家）の責務分離

現行の S1 パイプライン（`Plan → Design → Draft`）が Draft 段階でモデルに課している「状態管理（何が起きたか）」と「散文表現（どう語るか）」の二重負荷を解消するため、本文生成を以下の **二段階方式（Two-Stage Simulation-to-Rewrite）** へ分割する方針を採る。

```text
[前提・設定層]
  Plan (canon) + Design (brief / world / history / character / relation / plot / scene / voice)
        │
        ▼
[Stage A: 擬似 TRPG 進行・ゲームログ生成層（状態と因果の確定）]
  ・ツール（ルール＆状態機械）が日次・場所・移動日数・所持品・生死・既知集合(knows)・伏線状態を保持
  ・各シーンで「状況提示(Situation) → 人物の行動/選択(Action/Choice) → 判定と状態更新(Outcome/State Delta)」を進行
  ・状態整合性とマーカー（time / location / learn / use / foreshadow）が 100% 検証された【構造化ゲームログ】を出力
        │
        ▼
[Stage B: 小説化リライト層（【読める物語】への変換）]
  ・確定した【構造化ゲームログ】を事実の骨格（変更禁止のイベント・マーカー列）として入力
  ・voice-style（視点・文体・禁止表現）と adaptation（ログ→散文の機能対応）に従い、章本文へノベライズ
        │
        ▼
[監査・修復層]
  ・continuity-ledger（L1 監査）＋ ゲームログ対比チェック（ログにない事実漏洩やマーカー欠落の検出）
  ・必要に応じ revision-loop（S2）で局所修正
```

### 2.2 なぜ二段階方式の方が安定しやすいのか

1. **ハード制約（時間・移動・生死・知識境界・伏線回収）を前段で確定できる**
   - 移動日数（`locations.json` の `travel_days`）、残り日数やリソース（例：`t01` の 9 日目の油の期限）、誰がどの事実（`F-01`〜`F-11`）を知っているか、どの伏線（`fs-001`〜`fs-006`）を設置・回収したかを、散文を書く前に **Stage A の構造化ログと決定論的チェッカーで完全に確定** できる。
   - マーカー（`{{time}}`, `{{location}}`, `{{learn}}`, `{{foreshadow}}`）も、散文生成中にモデルに思い出させて埋め込ませるのではなく、Stage A の状態遷移から機械的に確定させ、Stage B では「確定済みマーカーを保持したまま散文化する（またはイベント単位で結合する）」形にできるため、マーカー欠落による `unresolved_foreshadow` 等を防ぎやすい。
2. **「死者の現在時行動」と「死者の記録・遺物・回想への言及」を型として区別できる**
   - 今回の実験で課題となった `dead_character_reappears`（`name_mention` による `medium` 警告）についても、Stage A のゲームログ上で「現在その場にいるアクターの行動（`actor_action`）」と「記録文書・遺物・回想の中の言及（`record_reference` / `memory_mention`）」をイベント型として分離すれば、死者本人が動く違反（`high`）を厳格に防ぎつつ、物語上必要な兄の手形や潮札への言及を誤検出なしに扱える。
3. **後段（Stage B）のモデルが「視点統制と文章表現」だけに集中できる**
   - Stage B のモデルは「次に何を起こしてどう辻褄を合わせるか」を考える必要がなく、確定したシーンログを `voice.json` の三人称限定視点・感覚描写・会話の間へと翻訳することだけに集中できる。

### 2.3 本リポジトリの既存資産との対応付け

この二段階方式は、ゼロから別システムを作るのではなく、**本リポジトリがすでに持つ 13 スキル・台帳・採録資料をそのまま接続して構築できる**。

| 二段階方式の要素 | 活用する既存スキル・コード・資料 | 役割 |
| --- | --- | --- |
| **初期状態・ルール定義** | `canon/`（[`src/asc/story/canon.py`](../../src/asc/story/canon.py)）、`world-rules`、`history-timeline`、`character-core`、`relationship-web` | PC/NPC の初期配置・生死・初期知識（ハンドアウト）、場所間の移動日数、世界規則と代償の定義。 |
| **シーン進行・課題設計（Stage A）** | `plot-architecture`（幕の問い・転換点の選択）、`scene-information`（目的・対立・変化・情報開示・伏線）、`interactive-branch`（状態変数 `narrative/japan_2026:T094` 等）、[`research/curated/narrative/japan_trpg/report.md`](../curated/narrative/japan_trpg/report.md)（B2 フェイズ/シーン制、B5 状況→行動→結果ループ、C1/C4 ハンドアウトと秘密開示、D1 手がかり配置） | 各シーンの開始条件・登場人物・行動選択・情報開示（`fact` 獲得）・伏線処理・終了条件を構造化ゲームログとして進行・検証する。 |
| **小説化リライト（Stage B）** | `voice-style`（視点・文体・禁止表現）、`adaptation`（媒体変換時の機能対応・省略理由）、`draft`（章生成） | 構造化ゲームログを、指定された視点・文体で【読める物語】の章本文へリライトする。 |
| **整合性監査・修復・評価** | `continuity-ledger`（[`src/asc/story/continuity.py`](../../src/asc/story/continuity.py)）、`revision-loop`（S2）、`evaluation-harness`、[`scripts/run_plot_ablation.py`](../../scripts/run_plot_ablation.py) | ゲームログとリライト後本文の整合性検査、マーカー保持確認、直接生成（S1）との L1 ペア比較。 |

### 2.4 想定されるトレードオフと設計上の対策

1. **「ゲームログの棒読み（クエスト消化感）」になるリスク**
   - **問題**: 単に「移動した→調べた→アイテムを得た」というログを直訳すると、平板な行動記録になりやすい。
   - **対策**: Stage A の各シーンログに、`scene-information` の **目的（`purpose`）・対立（`conflict`）・変化（`change`）・緊張種別（`tension`）** と `plot-architecture` の **転換点での選択（`choice`）** を必須項目として組み込み、「何が起きたか」だけでなく「何の対立の末に何を捨てて何を選んだか」までをログに記録してから Stage B へ渡す。
2. **Stage B（リライト時）の描写ハルシネーション**
   - **問題**: ログを小説化する際に、モデルが良かれと思って未開示の事実やその場にいない人物の行動を描写に足してしまう。
   - **対策**: Stage B プロンプトで「ゲームログに記録されたイベント・登場人物・開示事実・確定マーカー以外の新事実や人物行動を追加しない」契約を明示し、生成後に「ゲームログの確定マーカー列と本文中のマーカー列の一致検査」および `continuity-ledger` を通す。

---

## 3. 今後の段階的な開発ステップ（Vertical Slice 計画）

『[継続創作基盤ロードマップ](../../docs/continuous_creation_roadmap.md)』および『[評価運用範囲](../../docs/evaluation_scope.md)』の原則に従い、最初から巨大な汎用 TRPG エンジンを作るのではなく、**検証可能な最小の縦割りスライス**で段階的に実装・検証する。

1. **Phase 1: 構造化ゲームログ（`game_log`）スキーマと決定論的検査器の実装**
   - 章・シーン単位で `day`, `location`, `present_characters`, `situation`, `actions`（行為者・対象・種別：`action` / `dialogue` / `record_reference`）, `outcome`, `state_delta`（`learned_facts`, `foreshadow_events`, `location_moves`）, `emitted_markers` を持つ最小 JSON スキーマを定義する。
   - `canon` および `design`（`plot.json`, `scene.json`）と照合し、移動日数・知識境界・死者の現在時行動禁止・伏線の設置/回収順序を検証する決定論的チェッカー（`src/asc/gamelog/check.py` 等）と単体テストを作る。
2. **Phase 2: Stage A（ゲームログ生成）→ Stage B（小説化リライト）パイプラインの接続**
   - 既存の共有 `canon` + `design`（`t01-s1-seed0` の確定入力等をそのまま再利用可能）から、Stage A で `game_log.json` を生成・検証（不一致時は `repair`）し、Stage B で `game_log.json` + `voice.json` から章本文へリライトする工程を実装する。
   - 固定台本（`scripted`）での配線確認と回帰テストを追加し、`make ci` が通ることを確認する。
3. **Phase 3: 直接生成（S1）と二段階方式（TRPG ログ → リライト）の L1 ペア比較**
   - `experiments/2026-10-plot-ablation-t01/paired/` で確立した自己完結型バンドルと `--ingest` / `--resume` ワークフローを用い、同一の共有 `canon` / `design`（`t01-s1-seed0`）の上で、直接生成と二段階方式の L1 各指標（必須語、禁止表現、マーカー保持、継続性違反、CED、文字数・記述統計）を比較する。
   - 引き続き L1 を物語の面白さ・質の証拠とは扱わず、L2/L3 は `frozen_not_measured` を維持する。

---

## 4. 新しいチャット用の開始プロンプト

次のチャットセッションで具体的な開発を始める際は、以下のブロックをそのままコピー＆ペーストして使用してください。

```text
`jack4andmanastalk-byte/AutoStoryCreationAI` の最新 `main` を確認し、作業ブランチ上で「擬似 TRPG 風システムによる構造化ゲームログ生成（Stage A）→【読める物語】への小説化リライト（Stage B）」の二段階方式の最初の縦割りスライス（Phase 1〜2）を設計・実装してください。

まず以下のファイルを読んで、現在の到達点・設計思想・評価制約を把握してください。
1. `research/curation/two_stage_trpg_rewrite_direction_2026-10-26.md`（今回の設計思想と Phase 1〜3 の計画）
2. `research/curation/plot_to_draft_2026-10-25.md` および `experiments/2026-10-plot-ablation-t01/paired/note.md`（直近の Plot→Draft L1 ペア比較結果とマルチターン永続バンドルの仕組み）
3. `research/curated/narrative/japan_trpg/report.md`（日本の TRPG シナリオ技法：フェイズ/シーン制、状況→行動→結果ループ、ハンドアウト・情報開示設計）
4. `src/asc/pipeline/design.py`, `src/asc/pipeline/draft.py`, `src/asc/story/canon.py`, `src/asc/story/continuity.py`（現行の台帳・設計書・章生成・継続性監査の実装）
5. `docs/protocol.md`, `docs/evaluation_scope.md`, `docs/replay.md`（評価規約・Arena×L1 スコープ・リプレイ境界）

守るべき方針・制約：
- 最初から巨大な汎用ゲームエンジンを作らず、`research/curation/two_stage_trpg_rewrite_direction_2026-10-26.md` の §3 に従い、小さく検証可能な縦割りスライスとして実装してください。
- Stage A（構造化ゲームログ `game_log.json` のスキーマと決定論的チェッカー）では、`canon`（人物の生死・現在地・既知集合 `knows`・移動日数 `travel_days`・伏線 `foreshadowing`）および `design`（`plot.json` の幕・転換点、`scene.json` の目的・対立・変化・情報開示）との整合性を機械的に検査できるようにしてください。特に「死者の現在時行動（禁止）」と「死者の記録・遺物・回想への言及（許容）」をイベント型として区別できるようにし、また確定マーカー列（`time`, `location`, `learn`, `foreshadow`）をゲームログ側から導出・検証できるようにしてください。
- Stage B（小説化リライト）では、検証済みの `game_log.json` と `voice.json`（視点・文体・禁止表現）を入力として章本文を生成し、ゲームログで確定したマーカー・事実・知識境界からの逸脱がないかを検査できるようにしてください。
- 固定台本（`scripted`）による決定論的な配線・回帰テストを追加し、`make ci` がすべて通ることを確認してください。
- マルチターン実験や Arena リレーを行う場合は、Git 管理外の `runs/` や `build/` に依存せず、`experiments/<id>/` 配下の自己完結バンドルとして保存してください。実モデルの応答がない段階で応答や効果を捏造しないでください。
- L1 は構造・衛生チェックであり物語の質や面白さの証拠とは扱わず、L2/L3 は `frozen_not_measured` のまま維持してください。
- 作業ブランチはセッションで用意されたものを使用し、PR を作成した場合は私が指示するまでマージしないでください。
```
