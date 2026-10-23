# 創作活動（ストーリー・キャラクター・世界観・歴史）の構築に使える AIスキル／ハーネス 実用カタログ

- **調査日**：2026-10-23（スター数・更新日などの数値はこの日の取得値）
- **対象**：GitHub と Hugging Face で公開されている Agent Skills（SKILL.md）、Claude Code/Codex プラグイン、MCP サーバー、執筆ハーネス、ジェネレータ、データセット・モデル
- **同梱データ**：`data/catalog.jsonl`（選定79件の詳細と評価）、`data/sources.jsonl`（使った情報源231件のURL・メタデータ）、`data/candidates_screened.jsonl`（スクリーニングした候補1,741件）

---

## 0. サマリー

### 0.1 結論（要点）

1. **主流は「Agent Skills＋ファイルで持つ設定資料」**：2026年の実用的なツールの多くは、`SKILL.md` 形式のスキルに、Markdown＋YAML frontmatter の設定資料（ストーリーバイブル、canon、truth files）を組み合わせています。Claude Code・Codex・Gemini CLI・OpenCode など、エージェントを替えても使い回せます。
2. **実用性を分けるのは「生成力」ではなく「一貫性の外部化と機械的な検証」**：上位に入ったツールは、設定・伏線・人物の状態をファイルや台帳に出し、決定論的なチェックをかけて矛盾を見つけます。例として、継続性コンパイラ（`story-skills`）、truth files と章ごとの監査→書き戻し（`inkos`）、伏線の約束台帳と360ルールのlint（`neuro-book`）があります。
3. **作り方は「作者主導型」と「自律生成型」の二つに分かれる**：作者主導型は質問を重ねて提案だけを出すもので、`fiction-skills`、`Calliope writing-skills`、`novel-harness` が該当します。自律生成型は評価ループで一冊を書き上げるもので、`autonovel` や `inkos` が該当します。成果物の質と著作者性を保ちたいなら、前者に後者の検証の仕組みを取り込むのが現実的です。
4. **世界観は「設定DB＋MCP」と「専用ジェネレータ」の組み合わせが最も実用的**：設定DBにあたるのは Obsidian の `hivemind`、`Loreum`、`Kanka`、`WorldAnvil MCP` です。専用ジェネレータは、地図が `Azgaar FMG` と `Nortantis`、言語が `ConlangCrafter`、暦が `Fantasy-Calendar` と `Calendarium` です。
5. **「歴史構築」は空白に近い領域**：LLMだけで架空の歴史を体系的に作るツールは少数です（`bragi` の時空二重ツリー、`StoryCraftr` の history サブコマンド程度）。現時点では、年表ツール（`Timelines Studio`）、社会・王朝シミュレーション（`Neighborly`・`Minerva`・`Viv`・`OpenStory`）、LLMによる叙述化の三つを組み合わせるのが有効です。
6. **日本語での利用**：日本語ネイティブの資源は少数です（`claude-novel-workflow` は日本のラノベ作家による実例、`screenwriting-skills` と `inkos` には日本語READMEがあり、日本語データセット・モデルもあります）。ただしスキルの多くは言語に依存しないので、日本語での執筆・質問に問題なく使えます。開発が最も活発なのは中国語圏の網文（Web小説）系で、そこで使われている一貫性管理の手法は日本語作品にもそのまま応用できます。

### 0.2 数値の概要

| 項目 | 値 |
|---|---|
| 実行した検索クエリ | GitHub 60本 / Hugging Face 64本 / Web検索 2本 ＋ 二次カタログ4種 |
| スクリーニングした候補 | 1,741件（GitHub 862 / HF 879） |
| 中身を確認したリポジトリ | 66件（ファイルツリー・README・SKILL.md を確認） |
| 選定（カタログ掲載） | **79件**（GitHub 64 / HF 15） |
| ランク内訳 | S 12 / A 36 / B 23 / C 5 / 参考 3 |

### 0.3 目的別おすすめ（最初に試すべき10件）

| # | 目的 | おすすめ | 理由 |
|---|---|---|---|
| 1 | 小説の設定資料一式をAIと作り、矛盾を自動検出したい | [danjdewhurst/story-skills](https://github.com/danjdewhurst/story-skills) | 24スキルで構想から入稿まで扱え、継続性コンパイラCLIが付く。総合点が最も高い（24/25） |
| 2 | 日本語でWeb小説・ラノベを書きたい | [MintoTsukino/claude-novel-workflow](https://github.com/MintoTsukino/claude-novel-workflow) | 日本のプロ作家が公開した canon 7ファイル構成と JET 設計フレームワーク。AI草稿と人手推敲版を並べて比較できる |
| 3 | 長編・脚本・インタラクティブ作品を一つの基盤で扱いたい | [Narcooo/inkos](https://github.com/Narcooo/inkos) | truth files と章ごとの監査→修訂→状態書き戻し。日本語READMEあり |
| 4 | プロットと連続ものの構造を理論的に詰めたい | [jtydhr88/screenwriting-skills](https://github.com/jtydhr88/screenwriting-skills) | 技術書47冊から蒸留した26スキル（Truby、シリーズバイブル、日本の脚本術、小津スタイル） |
| 5 | キャラクターの「声」や関係性を対話で掘り下げたい | [haowjy/creative-writing-skills](https://github.com/haowjy/creative-writing-skills) | character-sim（人物本人との対話）と reader-sim（初読者の反応）を含む11エージェント |
| 6 | キャラクターシートを質問形式で作りたい／原稿から逆算したい | [Calliope-Editor/writing-skills](https://github.com/Calliope-Editor/writing-skills) | character-card-builder と reverse-character-cards。本文は一切書かない |
| 7 | 世界地図（国家・文化・宗教の分布つき）を作りたい | [Azgaar/Fantasy-Map-Generator](https://github.com/Azgaar/Fantasy-Map-Generator) | ブラウザで開くだけで使え、政治・文化・宗教レイヤーまで生成できる |
| 8 | 架空の歴史年表を作りたい | [sreegjl/timelines](https://github.com/sreegjl/timelines) | 分岐・合流する期間、時代帯、地図と時間スライダー。ローカルのJSONとMarkdownで保存 |
| 9 | 既存の設定ノートをAIに守らせたい（幻覚防止） | [hiveforge-sh/hivemind](https://github.com/hiveforge-sh/hivemind) | Obsidian の設定ノートをMCPで「真実のアンカー」にし、カノンの承認フローも持つ |
| 10 | 世界を自律的に「育てる」仕組みを試したい（注目株） | [benabhi/skills-world-building](https://github.com/benabhi/skills-world-building) | 未解決リンク駆動の拡張エンジン、28種のエンティティ型、git ブランチで試し書き。スペイン語・スター少 |

---

## 1. 調査方法

### 1.1 手順

1. **候補の発見**
   - GitHub REST API（`/search/repositories`、スター順）で日英の60クエリを実行しました（例：worldbuilding skill claude／novel writing agent skills／character creation llm／story bible ai／lorebook／worldbuilding timeline／procedural civilization history／小説 claude）。
   - Hugging Face Hub API でデータセット・モデル・Spaceの3種類を21語ずつ、さらに補完語で検索しました。
   - Web検索で Agent Skills のまとめ記事・キュレーションリストを確認しました。
2. **二次カタログとの突合**：`UnderleveledBuilder/awesome-story-skills` の `catalog.json`（819件、12の方法タグ）から「設定・世界観」「人物」「シミュレーション」タグの付いた329件を抽出し、取りこぼしを補いました。
3. **一次確認**：有力な66リポジトリを `git clone --depth 1 --filter=blob:none` で取得し、ファイルツリー・README・`SKILL.md` の数と構成・プラグインマニフェスト・MCP関連ファイルの有無を確認しました。主要なスキルは SKILL.md の本文も読んでいます。Hugging Face の項目は API とカード（README）で、ライセンス・説明・更新日を確認しました。
4. **評価と選定**：次の5つの軸で点数を付けました。

### 1.2 評価軸（各1〜5点、合計25点）

| 軸 | 記号 | 何を見たか |
|---|---|---|
| 成果物の具体性 | D | 設定ファイル、テンプレート、地図、年表、カードなど、手元に残る成果物がはっきり定義されているか |
| 導入容易性 | E | 1〜2コマンドで入るか、ブラウザで使えるか、追加のインフラ（DB・Docker・APIキー）が要るか |
| 一貫性・品質管理 | C | 台帳、状態管理、決定論的チェック、レビューループ、カノンの承認フローがあるか |
| 保守・コミュニティ | M | 更新の新しさ、スター・いいね数、アーカイブされていないか |
| 言語・ジャンル適応性 | L | 日本語での利用しやすさ、ジャンルや媒体を限定しないか |

**ランク**：S＝21点以上（最初に試すべき）、A＝17〜20点（目的が合えば有力）、B＝13〜16点（特定用途・参照実装）、C＝12点以下（学習・研究用の素材）、参考＝キュレーションリスト（評価対象外）

### 1.3 除外基準

- 画像・動画生成だけのツール（キャラシート生成など、創作設定に直結するものは例外として収録）
- NSFW特化のデータ・モデル、名前が一致しただけの無関係なリポジトリ
- 長期間更新がなく、より良い代替があるもの（研究上の代表実装は例外）
- アフィリエイト目的が主に見えるもの

### 1.4 限界

- **執筆品質の実測はしていません**。README・構成・コードからの評価です。
- スター数は人気の目安であり、品質を保証するものではありません。公開間もない良質なプロジェクトはスターが少なく出ます（例：fiction-skills、skills-world-building）。
- ライセンスは GitHub API の判定値です。「なし/不明」「要確認」の項目は、利用前に必ずリポジトリ本体を確認してください。

---

## 2. 解説：成果物を作るための技術パターン

カタログに並べたツールは、いくつかの共通する設計パターンの組み合わせとして理解できます。自分の創作フローにどれを取り入れるかを決めるために、主なパターンを解説します。

### 2.1 Agent Skills（SKILL.md）と段階的開示

スキルは `SKILL.md`（YAML frontmatter の `name` と `description`、本文の手順）と、任意の `references/`・`scripts/`・`assets/` からなるフォルダです。エージェントは普段 `description` だけを読み込み、依頼が合ったときに本文を、必要になったときに参照資料を読みます（段階的開示）。このため、**大量の創作理論（構造論、ジャンル論、暦・経済・魔法コストの考え方）を持たせても文脈を圧迫しません**。`npx skills add <repo>` や Claude Code の `/plugin marketplace add` で導入でき、複数のエージェントで共有できます。

### 2.2 ストーリーバイブル／カノンの外部化（ファイルが記憶になる）

上位ツールに共通するのは、**会話の記憶に頼らず、設定をファイルとして持つ**ことです。典型的な構成は次のとおりです（`story-skills` と `claude-novel-workflow` を合成した例）。

```
my-story/
├── story.md / canon.md        # 物語の物理法則：ジャンル・トーン・約束・禁止事項
├── style_guide.md             # 文体、forbidden_patterns.md（書かないこと）
├── characters/                # 1人物1ファイル（目的・傷・アーク・声・関係・知識状態）
├── worldbuilding/
│   ├── locations/  systems/  factions/  artifacts/
│   └── glossary/              # 造語・固有名詞の固定
├── plot/arcs/ + timeline.md   # 年表＋伏線台帳（設置→回収）
├── scenes/ + continuity/state.md
└── chapters/
```

YAML frontmatter に「生死」「所在」「誰が何を知っているか」「移動にかかる時間」などを構造化して持たせると、2.3の機械的な検証ができるようになります。

### 2.3 決定論的検証（LLMに頼らない矛盾検出）

- **継続性コンパイラ**（`story-skills`）：死んだはずの人物の再登場、伏線の設置前の回収、2地点間の移動時間との矛盾を、CLIが型エラーのように報告します。
- **台帳方式**：`neuro-book` の約束台帳、`webnovel-writer` の状態DB、`Novel-OS` のローカル継続性エンジン、`inkos` の truth files があります。
- **lint**：AIっぽい文型・禁止パターンの検出です（`neuro-book` 360ルール、`oh-story` のフック、`novel-harness` の決定論的lint）。

LLMによるレビューは見落としやばらつきがあるため、**「機械で確実に拾えるもの」は機械に任せる**のが上位ツールの共通点です。

### 2.4 階層的計画（トップダウンの物語設計）

- **ログライン→人物→プロットポイント→場所→台詞**（`Dramatron`）
- **スノーフレーク法：アイデア→世界→巻→アーク→シーン→章計画**（`AI_NovelGenerator`）
- **仕様駆動（SDD）：constitution→specify→clarify→plan→tasks→write→analyze**（`novel-writer`）
- **異種再帰計画**（`WriteHERE`）、**前提のモジュール合成**（`MoPS`：テーマ×背景×人物像）
- **構造テンプレート**：三幕構成、英雄の旅、Save the Cat、起承転結、Story Circle、Story Spine、Pixar 22ルール、Truby（`fiction-skills`・`writers-room-story-engine`・`screenwriting-skills`）

### 2.5 キャラクター構築の手法

| 手法 | 内容 | 代表 |
|---|---|---|
| カード化 | 目的・傷（wound）・アーク・声・関係を標準項目化。SillyTavern の Character Card V2 は持ち運べる事実上の標準 | Calliope、SillyTavern、cha1latte |
| インタビュー型 | 一問ずつ質問し、半端なアイデアを人物に仕上げる。提案には出自タグを付ける | Calliope character-card-builder、fiction-skills |
| 逆生成 | 書いた原稿だけを根拠に人物カードを作り直し、「意図した人物」と「書かれた人物」のずれを見る | Calliope reverse-character-cards |
| 人物シミュレーション | 人物本人と対話して声を見つける。人物を独立エージェントにして、知るべきことだけを知らせて行動させる | haowjy character-sim、nest-drama、OpenStory |
| 思考OSの蒸留 | 人物ごとに考え方・判断規則を SKILL.md 化し、キャラ崩壊（OOC）を防ぐ | novel-distiller |
| アーキタイプ診断 | Vogler/Campbell の8機能と Jung 派の12型で配役の偏りを点検 | author-toolkit |
| ビジュアル | キャラクターシート（設定画）、3D化、IPとしての展開設計 | Qwen-Image CharacterSheet、CharacterGen、character-ip-design |

### 2.6 世界観構築の手法

- **エンティティ型と相互リンク**：場所・勢力・体系（魔法・政治・技術・宗教・経済）・物品・種族・文化・言語・暦・時代・事件を型として定義し、双方向に参照させます（`worldbuilder` 11種、`skills-world-building` 28種）。
- **未解決リンク駆動の拡張**：ノート内で名前だけ出てまだ存在しないものを「保留リンク」として記録し、次のサイクルで優先的に肉付けします。乱数表で素材を振り、偶然性と整合性を両立させます（`skills-world-building`）。
- **三重記述**：同じ項目を「機械可読データ／文体付きの散文／画像生成プロンプト」の3つで持ちます（`worldbuilder`）。
- **ロアブック（World Info）**：キーワードが出たときだけ設定を文脈に入れます。トリガー語の設計が品質を左右します（`lorebook-creator`、SillyTavern）。設定ではなく「指示」を発火させる能動的な使い方もあります（sphiratrioth666）。
- **専用ジェネレータ**：地図（プレートテクトニクスや政治・文化・宗教レイヤー）、人工言語（音韻→文法→語彙→翻訳の多段パイプライン）、独自暦（複数の月、閏、紀年）。
- **MCPによる設定DB連携**：Obsidian、Loreum、WorldAnvil、Kanka の設定をAIに「読ませる／書かせる」ことで、設定と執筆を分けたまま整合させられます。

### 2.7 歴史構築の手法

| アプローチ | 内容 | 代表 |
|---|---|---|
| 時空の二重ツリー | 歴史段階と地点の階層を数字パスで管理し、現在地は詳細、周辺は要約、必要時に展開 | bragi |
| 要素別の生成 | 地理→歴史→文化→魔法体系→技術を順番に生成 | StoryCraftr |
| 年表の可視化 | 事件（点）・期間（分岐・合流）・時代帯を地図・時間軸と連動させる | Timelines Studio、Loreum、Hivemind、Calendarium |
| エージェントシミュレーション | 住民・家系・王朝を数世代シミュレートし、出来事のログを歴史の素材にする | Neighborly、Minerva、OpenStory、StoryBox |
| ストーリー・シフティング | シミュレーションのログから「物語になる出来事の連なり」を抽出 | Viv |
| 年代記の更新 | セッションやプレイの記録から、正確さを保ったまま年代記を追記 | loremaester chronik |

**実践的な流れ**：(1) 地図と勢力分布を作る（Azgaar）→ (2) 王朝・集落シミュレーションで出来事ログを生成する（Minerva・Neighborly）→ (3) LLMで主要事件を選び叙述化し、時代区分を決める → (4) Timelines Studio に年表化する → (5) 設定DBやストーリーバイブルの timeline.md に反映し、継続性チェックの対象にする。

### 2.8 品質向上：批評・読者シミュレーション・De-AI・評価ループ

- **役割を分けた多エージェント批評**：開発編集・ライン編集・継続性・テーマ・AI臭の検出を別々のエージェントに担当させます。鉄則は**「批評者は編集しない、採否は作者が決める」**（`novel-harness`）です。
- **読者シミュレーション**：初読者・ベータ読者パネルの逐次反応を見ます（`haowjy reader-sim`、`Calliope beta-reader-panel`、`autonovel` reader panel）。
- **構造レベルのDe-AI**：語彙を直す前に、主題の明示しすぎ、因果の単調さ、開示のタイミングといった物語構造を直します（`sepia`。StoryScope 研究に基づく）。
- **評価駆動ループ**：修正→評価→保持／破棄を、閾値を超えるまで繰り返します（`autonovel`）。
- **評価資源**：プロットホール検出（FlawedFictions）、創作ベンチ（EQ-Bench）、報酬モデル（LitBench RM）、ロールプレイ評価（MiniMax）。自作のチェッカーやモデル選びの物差しになります。
- **技法の蒸留**：参考作品から「再現性・生成力・排他性」を満たす規則だけを抽出してスキル化します（`wenfeng-skill`）。

### 2.9 作者主導型と自律生成型の使い分け

| 観点 | 作者主導型 | 自律生成型 |
|---|---|---|
| 代表 | fiction-skills、Calliope、novel-harness、claude-novel-workflow | autonovel、inkos（自動モード）、chinese-novelist-skill |
| 成果物 | 精度の高い設計資料＋作者の原稿 | 一冊分の草稿（PDF、ePub、音声まで） |
| 長所 | 著作者性、文体の一貫性、権利面の明確さ | 速度と量、試作・探索に強い |
| 短所 | 時間がかかる | 平均的な文体になりやすい、トークン費用が大きい |
| 推奨 | 本番の作品づくり | プロトタイピング、設定の妥当性検証 |

---

## 3. カテゴリ別カタログ（一覧）

表の見方：**評価**＝D/E/C/M/L（各5点）、**ランク**＝S/A/B/C、★＝GitHubスター、♥＝HFいいね（2026-10-23時点）、📦＝アーカイブ済み


### A. 統合型スキル／プラグイン（ストーリー・キャラ・世界観を一括管理）（7件）

| 名称 | 形式 | 主な成果物 | 評価(D/E/C/M/L) | ランク | 人気 | 更新 | ライセンス |
|---|---|---|---|---|---|---|---|
| [danjdewhurst/story-skills](https://github.com/danjdewhurst/story-skills) | Agent Skills（24個）+ Claude Code/Code… | story.md（ストーリーバイブル）、style-sheet.md、characters/、worldbuilding/{locati… | 5/5/5/5/4 (24) | **S** | ★341 | 2026-10-20 | MIT |
| [haowjy/creative-writing-skills](https://github.com/haowjy/creative-writing-skills) | Claude Code/Coworkプラグイン（11エージェント＋スキ… | スタイル参照ファイル、アーク/章/ビート単位のアウトライン、知識ベース（ナレッジレイヤー）、批評ノート、読者反応ログ | 4/4/4/5/4 (21) | **S** | ★530 | 2026-10-18 | Apache-2.0 |
| [MintoTsukino/claude-novel-workflow](https://github.com/MintoTsukino/claude-novel-workflow) | Claude Codeワークフロー（テンプレート＋実例プロジェクト＋ド… | canon.md、character_bible.md、world_bible.md、glossary.md、timeline.md（伏… | 5/3/5/3/5 (21) | **S** | ★10 | 2026-06-16 | 要確認 |
| [narrastory/story-architect-skill](https://github.com/narrastory/story-architect-skill) | 単一Agent Skill（references/・scripts/・… | 世界観、人物、プロット概要、草稿、年表、プロットスレッド、カノン、人物の知識状態、レビュー記録、最終稿をそれぞれ専用の場所に配置したプロ… | 5/4/4/2/4 (19) | **A** | ★5 | 2026-07-31 | MIT |
| [robskidmore/fiction-skills](https://github.com/robskidmore/fiction-skills) | Claude Code Skills（17個） | 00_contract.md（Story Contract）、01_world/（トピック別ファイル）、02_characters/、0… | 4/4/4/2/4 (18) | **A** | ★0 | 2026-10-11 | MIT |
| [howells/fiction](https://github.com/howells/fiction) | Claude Code / Codex プラグイン（20スキル） | 物語アーキテクチャ設計書、キャラクター文書、章アウトライン、批評・編集ノート、あらすじ、表紙・挿絵、タイトル候補 | 4/5/3/3/3 (18) | **A** | ★22 | 2026-10-17 | なし/不明 |
| [rhavekost/author-toolkit](https://github.com/rhavekost/author-toolkit) | Claude Code プラグイン（6スキル） | ブループリント／Story Bible、セッションノート（sessions/YYYY-MM-DD_*.md）、アーキタイプ監査 | 3/5/3/2/3 (16) | **B** | ★18 | 2026-07-22 | 要確認 |

### B. ストーリー構造・プロット設計（6件）

| 名称 | 形式 | 主な成果物 | 評価(D/E/C/M/L) | ランク | 人気 | 更新 | ライセンス |
|---|---|---|---|---|---|---|---|
| [jtydhr88/screenwriting-skills](https://github.com/jtydhr88/screenwriting-skills) | Agent Skills（26個）Claude Code / Code… | 構成表、テーマ・前提、人物葛藤表、シリーズ・エンジン／シリーズバイブル、シーン設計、台詞診断、脚色計画 | 4/5/3/5/5 (22) | **S** | ★1758 | 2026-10-03 | MIT |
| [jackterror/writers-room-story-engine](https://github.com/jackterror/writers-room-story-engine) | Agent Skill（SKILL.md＋単一ファイル版MEGA-SK… | 前提（premise）、物語の核、主人公エンジン、Story Spine、因果ビート、世界からの圧力、シーン、改稿プラン | 3/5/3/3/4 (18) | **A** | ★44 | 2026-07-07 | MIT |
| [wordflowlab/novel-writer](https://github.com/wordflowlab/novel-writer) | npm CLI＋スラッシュコマンド（13種のAIツール対応） | constitution（創作憲法）、spec（仕様）、plan、tasks、章原稿、分析レポート、プロット追跡・年表・人物一貫性検証 | 4/4/4/2/3 (17) | **A** | ★959 | 2025-10-26 | MIT |
| [IsaiahN/Serendipity-Engine](https://github.com/IsaiahN/Serendipity-Engine) | PWA／Chrome拡張（StoryWeaver） | 人物・関係・物語構造・分解（Decomposition）・原稿を含む8フェーズの作品一式 | 4/4/3/3/3 (17) | **A** | ★15 | 2026-06-29 | 要確認 |
| [google-deepmind/dramatron](https://github.com/google-deepmind/dramatron) | Colabノートブック（研究） | タイトル、登場人物、プロットポイント、場所描写、シーン毎の台詞（脚本） | 4/2/3/1/3 (13) | **B** | ★1135 | 2024-07-16 | Apache-2.0 |
| [GAIR-NLP/MoPS](https://github.com/GAIR-NLP/MoPS) | 研究コード（ACL 2024） | 多様な物語前提（premise） | 4/2/2/1/3 (12) | **C** | ★47 | 2024-07-19 | なし/不明 |

### C. キャラクター構築（6件）

| 名称 | 形式 | 主な成果物 | 評価(D/E/C/M/L) | ランク | 人気 | 更新 | ライセンス |
|---|---|---|---|---|---|---|---|
| [SillyTavern/SillyTavern](https://github.com/SillyTavern/SillyTavern) | LLMフロントエンド（Webアプリ） | Character Card（V2/V3仕様）、World Info（ロアブック）、グループチャット、ビジュアルノベルモード | 4/4/3/5/5 (21) | **S** | ★34828 | 2026-10-02 | AGPL-3.0 |
| [Calliope-Editor/writing-skills](https://github.com/Calliope-Editor/writing-skills) | Claude Agent Skills（13個、本文は書かない拡張専用） | 標準キャラクターカード（目的・傷・アーク・声・関係）、原稿からの逆生成キャラカード、編集レポート、ベータ読者パネルの反応 | 4/5/4/2/3 (18) | **A** | ★5 | 2026-07-16 | MIT |
| [63435212cwu-ops/nest-drama](https://github.com/63435212cwu-ops/nest-drama) | ローカルWebアプリ（Python標準ライブラリのみ） | 世界観、プロット背骨（必達ビート／可変ビート）、人物ごとの3枚のカード（核・声・心理）、ユニットストーリー／巻プロット | 4/4/4/3/3 (18) | **A** | ★57 | 2026-09-13 | AGPL-3.0 |
| [jacky-0218-lung/character-ip-design](https://github.com/jacky-0218-lung/character-ip-design) | Agent Skill／Claude Codeプラグイン | 競合IPポジショニング表、世界観、キャラ深層分析（価値観・渇望・禁忌・ギャップ）、3コンセプト案、同一キャラの3画風比較、スーパーシンボ… | 5/4/3/2/4 (18) | **A** | ★2 | 2026-08-10 | Apache-2.0 |
| [FutureFuzzy/novel-distiller](https://github.com/FutureFuzzy/novel-distiller) | Python CLI＋Claude Codeスキル（/ws） | 創世ブループリント、人物ごとの『思考OS』SKILL.md、作者文体DNA、シーン推演ログ、章原稿、プラットフォーム規約チェック結果 | 5/3/4/3/2 (17) | **A** | ★51 | 2026-05-11 | MIT |
| [cha1latte/sillytavern-character-generator](https://github.com/cha1latte/sillytavern-character-generator) | プロンプトファイル（標準版／小型モデル版） | SillyTavern Character Card V2 JSON（説明・性格・シナリオ・例示台詞・複数の挨拶文） | 4/5/2/1/4 (16) | **B** | ★60 | 2026-03-16 📦 | MIT |

### D. 世界観構築（設定DB・地図・言語・暦・ロアブック）（15件）

| 名称 | 形式 | 主な成果物 | 評価(D/E/C/M/L) | ランク | 人気 | 更新 | ライセンス |
|---|---|---|---|---|---|---|---|
| [Azgaar/Fantasy-Map-Generator](https://github.com/Azgaar/Fantasy-Map-Generator) | Webアプリ（ブラウザ／Electron） | 編集可能なファンタジー世界地図：国家・州・文化・宗教・都市・道路・軍事・マーカー・ノート、各種エクスポート | 5/5/3/5/5 (23) | **S** | ★6128 | 2026-10-22 | 要確認 |
| [hiveforge-sh/hivemind](https://github.com/hiveforge-sh/hivemind) | MCPサーバー＋Obsidianプラグイン | Vault上のタイムラインビュー、関係グラフビュー、カノン状態（approved/review/draft）管理 | 4/4/5/3/4 (20) | **A** | ★10 | 2026-10-21 | MIT |
| [owlchester/kanka](https://github.com/owlchester/kanka) | ソース公開型Webアプリ（kanka.ioでホスト版提供） | 人物・場所・組織・家系・暦・年表・地図・クエスト等を相互リンクしたキャンペーン/世界Wiki | 4/4/3/5/4 (20) | **A** | ★361 | 2026-10-22 | 要確認 |
| [virgilianshailer/lorebook-creator](https://github.com/virgilianshailer/lorebook-creator) | SillyTavern拡張 | SillyTavern World Info / LoreBook JSON（世界概要、ロア、人物・勢力・場所・物品・事件・魔法/技術・… | 5/4/4/3/4 (20) | **A** | ★16 | 2026-08-07 | MIT |
| [jeheydorn/nortantis](https://github.com/jeheydorn/nortantis) | デスクトップアプリ（Java） | 大陸・島・湖・森・川・山・都市を含むファンタジー地図、政治区画・道路・テキスト・独自テクスチャ | 5/4/2/4/5 (20) | **A** | ★230 | 2026-10-22 | AGPL-3.0 |
| [fantasycalendar/Fantasy-Calendar](https://github.com/fantasycalendar/Fantasy-Calendar) | Webアプリ（fantasy-calendar.com） | 独自の暦（複数の月・季節・紀年・閏ルール）と事件トラッキング | 4/5/3/4/4 (20) | **A** | ★146 | 2026-10-22 | なし/不明 |
| [gofastercloud/worldbuilder](https://github.com/gofastercloud/worldbuilder) | CLI（22コマンド）＋Flask Web UI＋MCPサーバー＋Cl… | 11種エンティティ（人物・場所・勢力・魔法体系・言語・血統など）のMarkdown＋YAML、関係グラフ可視化、執筆用プロンプト | 5/3/5/2/4 (19) | **A** | ★7 | 2026-06-23 | Apache-2.0 |
| [morrisalp/ConlangCrafter](https://github.com/morrisalp/ConlangCrafter) | Python研究コード（ACL 2026 Oral）＋HFデータセット | 人工言語スケッチ：音韻論（子音・母音・音素配列）、文法、語彙、翻訳例 | 5/3/4/3/4 (19) | **A** | ★49 | 2026-07-25 | MIT |
| [javalent/calendarium](https://github.com/javalent/calendarium) | Obsidianプラグイン | Obsidian内のファンタジー/SF暦と、ノートから拾ったイベント表示 | 4/5/3/3/4 (19) | **A** | ★154 | 2025-09-27 | MIT |
| [benabhi/skills-world-building](https://github.com/benabhi/skills-world-building) | Claude Code Skills（9個）＋Pythonスクリプト、… | Obsidian Vault：世界票（Ficha del Mundo）、CLAUDE.md（世界ルール）、28種のエンティティノート（人… | 5/3/5/2/3 (18) | **A** | ★0 | 2026-10-14 | なし/不明 |
| [loreum-app/loreum](https://github.com/loreum-app/loreum) | OSS Webプラットフォーム（MCP接続） | カスタムスキーマのエンティティ、知識グラフ、カスタム暦対応のガントチャート型年表、Lore Wiki、ストーリーボード、スタイルガイド | 4/3/4/3/4 (18) | **A** | ★3 | 2026-09-24 | AGPL-3.0 |
| [jasnonaz/vibe-worldbuilding-mcp](https://github.com/jasnonaz/vibe-worldbuilding-mcp) | MCPサーバー（Claude Desktop等） | 世界コンセプト、カスタム分類体系、相互リンクされた項目、参照先の自動スタブ、AI画像（FAL）、ナビゲーション付き静的Webサイト（As… | 5/3/3/2/4 (17) | **A** | ★10 | 2025-10-04 | なし/不明 |
| [mm-weber/loremaester](https://github.com/mm-weber/loremaester) | Claude Code設定（4スキル）＋MCPサーバー群（14ツール） | TTRPGキャンペーンVault内のNPC・場所・セッション案・キャンペーン年代記（Campaign_Chronicle.md） | 4/2/4/3/3 (16) | **B** | ★19 | 2026-10-21 | MIT |
| [wlcarden/worldanvil-mcp](https://github.com/wlcarden/worldanvil-mcp) | MCPサーバー（90+ツール）／Claude Codeプラグイン | WorldAnvil上の記事（人物・場所・アイテム）、地図とマーカー、タイムラインと事件、GM専用シークレット | 3/4/3/3/3 (16) | **B** | ★11 | 2026-06-01 | MIT |
| [bmen25124/lorecard](https://github.com/bmen25124/lorecard) | Webアプリ（Docker） | URL（Fandomのカテゴリページ等）からロアブック／キャラクターカード | 4/3/2/3/4 (16) | **B** | ★99 | 2026-06-30 | GPL-3.0 |

### E. 歴史・年表・社会シミュレーション（8件）

| 名称 | 形式 | 主な成果物 | 評価(D/E/C/M/L) | ランク | 人気 | 更新 | ライセンス |
|---|---|---|---|---|---|---|---|
| [sreegjl/timelines](https://github.com/sreegjl/timelines) | デスクトップアプリ（Electron）／Webビューア | .timeline（JSON）＋Markdownノート：事件（点）、期間（分岐・合流可能なスパン）、時代帯（Era）、タグ・グループ、地… | 5/5/3/4/4 (21) | **S** | ★222 | 2026-10-21 | GPL-3.0 |
| [wailers9/bragi](https://github.com/wailers9/bragi) | Python CLI＋ローカルWeb UI | 世界概要・基底ルール・歴史の流れ・空間構造、人物ネットワーク、公開／個人事件ログ、物語断片 | 5/3/4/2/3 (17) | **A** | ★32 | 2026-05-17 | なし/不明 |
| [ZJU-LLMs/OpenStory](https://github.com/ZJU-LLMs/OpenStory) | 多エージェント推演フレームワーク＋ランチャー | 人物・地点・経路・ルールを持つ対話可能な物語世界、分岐する推演ログ | 4/3/3/4/3 (17) | **A** | ★433 | 2026-08-19 | Apache-2.0 |
| [atisharma/chasm](https://github.com/atisharma/chasm) | 生成型テキストアドベンチャー（piハーネス上） | Markdownファイル群のディレクトリ＝世界（場所・人物・会話・事件が永続化）、gitで配布可能 | 4/3/4/3/3 (17) | **A** | ★15 | 2026-09-06 | MIT |
| [siftystudio/viv](https://github.com/siftystudio/viv) | 創発的物語エンジン（DSL・コンパイラ・ランタイム）＋Claude C… | キャラクター行動定義、ストーリーワールド設計、シミュレーション内の物語線（story sifting結果） | 4/2/4/3/3 (16) | **B** | ★39 | 2026-09-05 | 要確認 |
| [ShiJbey/neighborly](https://github.com/ShiJbey/neighborly) | Pythonライブラリ（エージェントベース・シミュレーション） | 数世代にわたる集落の住民史：特性・地位・関係・職業・ライフイベントのログ（データ分析可能） | 4/3/3/1/4 (15) | **B** | ★80 | 2026-04-07 📦 | MIT |
| [ShiJbey/minerva](https://github.com/ShiJbey/minerva) | Pythonライブラリ（王朝シミュレーター） | 地図上で勢力を争う家系・王朝の年代記（SQLで照会可能） | 4/3/3/1/4 (15) | **B** | ★8 | 2026-04-07 📦 | 要確認 |
| [amcghm/StoryBox](https://github.com/amcghm/StoryBox) | 研究コード（AAAI 2026） | 長編物語（ボトムアップ型） | 3/3/3/2/3 (14) | **B** | ★19 | 2026-03-27 | MIT |

### F. 長編生成ハーネス／パイプライン（15件）

| 名称 | 形式 | 主な成果物 | 評価(D/E/C/M/L) | ランク | 人気 | 更新 | ライセンス |
|---|---|---|---|---|---|---|---|
| [zenstory-ai/oh-story-claudecode](https://github.com/zenstory-ai/oh-story-claudecode) | Agent Skills（13個）＋サブエージェント、7種のコーディン… | 設定・大綱・細綱・本文・追跡ファイル（伏線・未完の約束）、状態カード、拆文（作品分解）レポート、表紙 | 5/5/5/5/3 (23) | **S** | ★7905 | 2026-10-18 | MIT |
| [Narcooo/inkos](https://github.com/Narcooo/inkos) | Agentシステム（Studio / TUI / CLI）＋20スキル | truth files（設定・伏線・人物状態）、章原稿、審稿・修訂記録、短編、脚本、互動影游（インタラクティブ映像ゲーム）、開放世界、翻… | 5/4/5/5/4 (23) | **S** | ★10432 | 2026-10-18 | AGPL-3.0 |
| [lingfengQAQ/webnovel-writer](https://github.com/lingfengQAQ/webnovel-writer) | Claude Code プラグイン（8スキル＋context/data… | 初期設定・総綱、巻綱・章綱、章原稿、多次元レビュー、状態DB＋RAGへの事実コミット、読み取り専用ダッシュボード | 5/4/5/5/3 (22) | **S** | ★7617 | 2026-10-22 | GPL-3.0 |
| [YILING0013/AI_NovelGenerator](https://github.com/YILING0013/AI_NovelGenerator) | ローカル実行の執筆ワークスペース（Web UI） | 物語方向、世界、勢力・人物・関係グラフ、巻→アーク→シーン→章計画、原稿 | 5/4/4/5/3 (21) | **S** | ★6325 | 2026-10-16 | AGPL-3.0 |
| [notnotype/neuro-book](https://github.com/notnotype/neuro-book) | 長編執筆IDE（デスクトップ）＋スキル群 | Markdown＋SQLiteのワークスペース：設定・プロット・本文・世界状態、伏線『約束台帳』、llmlintレポート | 5/3/5/4/3 (20) | **A** | ★751 | 2026-10-14 | AGPL-3.0 |
| [ExplosiveCoderflome/AI-Novel-Writing-Assistant](https://github.com/ExplosiveCoderflome/AI-Novel-Writing-Assistant) | Web/デスクトップアプリ | 世界サンプル庫・人物庫、世界地図、人物関係図、章計画・場面・本文、短編（3千〜3万字） | 5/4/4/5/2 (20) | **A** | ★3275 | 2026-10-21 | 要確認 |
| [PenglongHuang/chinese-novelist-skill](https://github.com/PenglongHuang/chinese-novelist-skill) | 単一Agent Skill | 10〜50章の完結した中国語小説、創作記憶（嗜好プロファイル） | 4/5/3/5/2 (19) | **A** | ★4123 | 2026-10-20 | MIT |
| [NousResearch/autonovel](https://github.com/NousResearch/autonovel) | Pythonパイプライン（自律型） | 世界・人物・アウトライン・文体・canon、章原稿、印刷用PDF、ePub、オーディオブック、LP | 5/3/4/3/3 (18) | **A** | ★1638 | 2026-03-20 | なし/不明 |
| [raestrada/storycraftr](https://github.com/raestrada/storycraftr) | Python CLI（pipx）＋VS Code拡張 | 世界設定（歴史・地理・文化・魔法体系・技術）、アウトライン（全体プロット・章構成・人物要約）、章原稿 | 4/4/3/3/4 (18) | **A** | ★175 | 2026-03-06 | MIT |
| [mrigankad/Novel-OS](https://github.com/mrigankad/Novel-OS) | 多エージェント執筆スタジオ（API＋Web） | 中央状態ファイル（人物・場所・プロットスレッド・伏線・品質スコア）、章原稿 | 4/3/5/3/3 (18) | **A** | ★54 | 2026-08-09 | MIT |
| [xindoo/sumeru](https://github.com/xindoo/sumeru) | Agent Skills（7個） | 選題分析、世界観・人物・プロット大綱、章原稿、整合性レビュー、各プラットフォーム形式への書き出し | 4/5/3/3/2 (17) | **A** | ★215 | 2026-08-23 | なし/不明 |
| [Lanerra/saga](https://github.com/Lanerra/saga) | ローカルPython CLI（Neo4j＋LangGraph） | アウトライン、人物/世界ファイル、シーン単位草稿、要約、Markdown原稿 | 4/2/5/3/3 (17) | **A** | ★114 | 2026-09-15 | Apache-2.0 |
| [jblemee/bmad-book-builder](https://github.com/jblemee/bmad-book-builder) | BMADメソッドのモジュール（8エージェント・17ワークフロー） | Story Bible、人物監査、テーマ・リズム分析、章原稿 | 4/3/4/2/3 (16) | **B** | ★33 | 2026-01-25 | WTFPL |
| [principia-ai/WriteHERE](https://github.com/principia-ai/WriteHERE) | OSSフレームワーク（バックエンド＋フロント） | 長編フィクション、技術レポート | 3/3/3/3/3 (15) | **B** | ★976 | 2026-09-03 | なし/不明 |
| [aiwaves-cn/RecurrentGPT](https://github.com/aiwaves-cn/RecurrentGPT) | 研究コード＋Gradioデモ | 任意長の小説・インタラクティブフィクション | 3/3/3/1/3 (13) | **B** | ★999 | 2024-05-15 | GPL-3.0 |

### G. 推敲・品質評価（De-AI・批評・ベンチマーク）（4件）

| 名称 | 形式 | 主な成果物 | 評価(D/E/C/M/L) | ランク | 人気 | 更新 | ライセンス |
|---|---|---|---|---|---|---|---|
| [Nanako0129/sepia](https://github.com/Nanako0129/sepia) | Agent Skill（77+エージェント対応）＋ネイティブプラグイン | 診断レポート（review）、最小修正版（refactor）、全面書き直し版（recreate） | 3/5/4/5/4 (21) | **S** | ★3429 | 2026-10-15 | MIT |
| [XTmingyue/wenfeng-skill](https://github.com/XTmingyue/wenfeng-skill) | Agent Skill（スキル蒸留器） | 作品から抽出した執筆用SKILL.md（叙事モデル・言語指紋・モチーフ・人物造形・プロット技法・創作境界） | 4/5/3/2/3 (17) | **A** | ★21 | 2026-05-26 | MIT |
| [jmcnestrie/novel-harness](https://github.com/jmcnestrie/novel-harness) | Claude Codeハーネス（drafter＋レビュアー群） | ボイス固定の章草稿、reviews/配下の批評ノート | 3/4/4/2/3 (16) | **B** | ★4 | 2026-07-07 | MIT |
| [EQ-bench/creative-writing-bench](https://github.com/EQ-bench/creative-writing-bench) | ベンチマークコード（EQ-Bench Creative Writing… | モデル別の創作評価（ルーブリック点＋Elo/Glicko） | 3/3/4/3/2 (15) | **B** | ★147 | 2026-06-24 | なし/不明 |

### H. Hugging Face データセット・モデル・Space（15件）

| 名称 | 形式 | 主な成果物 | 評価(D/E/C/M/L) | ランク | 人気 | 更新 | ライセンス |
|---|---|---|---|---|---|---|---|
| [tori29umai/Qwen-Image-2509-CharacterSheet](https://huggingface.co/spaces/tori29umai/Qwen-Image-2509-CharacterSheet) | Space（Gradioデモ） | キャラクターシート画像（設定画） | 4/5/3/2/4 (18) | **A** | ♥240 | 2025-11-11 | apache-2.0 |
| [sphiratrioth666/Character_Generation_Templates](https://huggingface.co/sphiratrioth666/Character_Generation_Templates) | プロンプトテンプレート集（モデルリポジトリ形式） | キャラクター生成用テンプレート | 4/5/2/2/4 (17) | **A** | ♥62 | 2025-08-12 | cc-by-nc-4.0 |
| [malper/ConlangCrafter](https://huggingface.co/datasets/malper/ConlangCrafter) | データセット | 生成済み人工言語64件（音韻・文法・語彙など） | 4/4/3/3/3 (17) | **A** | ♥2 | 2026-01-25 | cc-by-4.0 |
| [sphiratrioth666/Lorebooks_as_ACTIVE_scenario_and_character_guidance_tool](https://huggingface.co/sphiratrioth666/Lorebooks_as_ACTIVE_scenario_and_character_guidance_tool) | 手法解説＋ロアブック例 | 指示を注入する『能動的』ロアブック | 3/4/3/2/4 (16) | **B** | ♥37 | 2025-01-24 | cc-by-nc-4.0 |
| [VAST-AI/CharacterGen](https://huggingface.co/spaces/VAST-AI/CharacterGen) | Space＋研究コード（SIGGRAPH'24） | 単一画像からの3Dキャラクター（マルチビュー→3D） | 4/4/2/2/4 (16) | **B** | ♥230 | 2026-02-14 | apache-2.0 |
| [Aratako/Japanese-Creative-Writing-39.6k](https://huggingface.co/datasets/Aratako/Japanese-Creative-Writing-39.6k) | データセット（日本語） | 日本語の小説執筆タスク約39,600件（2ターン対話） | 3/3/2/3/5 (16) | **B** | ♥9 | 2025-07-04 | mit |
| [kahuja/flawed-fictions](https://huggingface.co/datasets/kahuja/flawed-fictions) | データセット（FlawedFictions） | 矛盾（プロットホール）入り物語と正解ラベル：414件＋長編200件＋陰性例 | 3/4/4/2/2 (15) | **B** | ♥4 | 2025-04-15 | mit |
| [lars1234/story_writing_benchmark](https://huggingface.co/datasets/lars1234/story_writing_benchmark) | データセット | 多言語で生成された短編と品質評価 | 2/4/3/2/3 (14) | **B** | ♥6 | 2025-03-01 | mit |
| [NousResearch/CharacterCodex](https://huggingface.co/datasets/NousResearch/CharacterCodex) | データセット | 多様なメディアの人気キャラクターの詳細情報と、各キャラ固有のシナリオ | 3/4/2/2/3 (14) | **B** | ♥256 | 2024-06-17 | apache-2.0 |
| [Local-Novel-LLM-project/Vecteus-v1](https://huggingface.co/Local-Novel-LLM-project/Vecteus-v1) | モデル（日本語ローカルLLM） | 日本語小説の生成 | 2/3/1/2/5 (13) | **B** | ♥36 | 2026-02-16 | apache-2.0 |
| [MiniMaxAI/role-play-bench](https://huggingface.co/datasets/MiniMaxAI/role-play-bench) | ベンチマーク | ロールプレイエージェント評価（中・英） | 2/3/3/3/2 (13) | **B** | ♥157 | 2026-01-28 | apache-2.0 |
| [ConicCat/Litbench-Creative-Writing-RM-3B](https://huggingface.co/ConicCat/Litbench-Creative-Writing-RM-3B) | 報酬モデル（Bradley-Terry） | 草稿の好ましさスコア | 2/3/3/2/2 (12) | **C** | ♥4 | 2025-09-15 | llama3.2 |
| [jondurbin/gutenberg-dpo-v0.1](https://huggingface.co/datasets/jondurbin/gutenberg-dpo-v0.1) | データセット（DPO） | Project Gutenberg章原文（選好）とLLM生成文（非選好）のペア | 2/3/2/2/2 (11) | **C** | ♥173 | 2024-01-12 | cc-by-4.0 |
| [VatsaDev/worldbuild](https://huggingface.co/datasets/VatsaDev/worldbuild) | データセット | Worldbuilding StackExchangeの質問約18,000件＋ロールプレイデータ | 3/3/1/1/2 (10) | **C** | ♥13 | 2024-01-09 | mit |
| [jukofyork/creative-writing-control-vectors-v3.0](https://huggingface.co/jukofyork/creative-writing-control-vectors-v3.0) | コントロールベクトル（GGUF, llama.cpp用） | 文体・語り・トーン傾向を操作したローカルモデル出力 | 2/2/2/2/2 (10) | **C** | ♥63 | 2025-03-17 | apache-2.0 |

### I. メタ情報源（キュレーションリスト）（3件）

| 名称 | 形式 | 主な成果物 | 評価(D/E/C/M/L) | ランク | 人気 | 更新 | ライセンス |
|---|---|---|---|---|---|---|---|
| [UnderleveledBuilder/awesome-story-skills](https://github.com/UnderleveledBuilder/awesome-story-skills) | キュレーションリスト（819件）＋catalog.json＋METHO… | 方法別・ジャンル別の索引、機械可読カタログ、手法ガイド | 3/5/2/4/3 (17) | **REF** | ★3 | 2026-10-19 | CC0-1.0 |
| [Picrew/awesome-llm-story-generation](https://github.com/Picrew/awesome-llm-story-generation) | 論文・OSSリスト（302件） | 計画・エージェント協調・サンドボックス/世界シミュレーション・記憶・一貫性・評価等10分類の索引 | 2/5/1/4/3 (15) | **REF** | ★117 | 2026-10-07 | なし/不明 |
| [yingpengma/Awesome-Story-Generation](https://github.com/yingpengma/Awesome-Story-Generation) | 論文リスト（199本） | 必読マーク・一行要約付きの論文索引（長編・脚本・ゲーム・物語世界モデル・評価・共創） | 2/5/1/4/3 (15) | **REF** | ★668 | 2026-10-19 | CC-BY-4.0 |

---

## 4. 詳細解説（全エントリ）

各エントリについて「何が作れるか（成果物）」「どんな技術・方法を使うか」「導入方法」「向いている人」「注意点」をまとめました。


### A. 統合型スキル／プラグイン（ストーリー・キャラ・世界観を一括管理）

#### danjdewhurst/story-skills　〔ランク S｜24/25〕

- **リンク／基本情報**：https://github.com/danjdewhurst/story-skills　｜　Agent Skills（24個）+ Claude Code/Codexプラグイン + npm CLI　｜　★341　｜　更新 2026-10-20　｜　ライセンス MIT　｜　ドキュメント言語：英語
- **成果物**：story.md（ストーリーバイブル）、style-sheet.md、characters/、worldbuilding/{locations,systems,factions,artifacts}、glossary/、plot/arcs・timeline.md、scenes/レジストリ、continuity/state.md、章原稿
- **技術・方法**：全要素をYAML frontmatter付きMarkdownで管理し、CLIが『継続性コンパイラ』として死亡キャラの再登場・伏線回収の順序逆転・移動時間（routes.hours）の矛盾を型エラーのように検出。`story knowledge`で章時点の人物の知識状態を照会、`story context --budget`でトークン予算内に執筆文脈をパック。三幕・英雄の旅・Save the Cat等の構造、暦・命名言語・経済・魔法コストの参照資料、命名衝突チェック付き
- **導入**：/plugin marketplace add danjdewhurst/story-skills → /plugin install story-skills@story-skills（または npx skills add danjdewhurst/story-skills）
- **向いている人・用途**：長編・シリーズ物を『検証可能な設定資料』として運用したい作者
- **注意点**：CLIはNode.js必須。英語の参照資料が中心（執筆言語は任意）

#### haowjy/creative-writing-skills　〔ランク S｜21/25〕

- **リンク／基本情報**：https://github.com/haowjy/creative-writing-skills　｜　Claude Code/Coworkプラグイン（11エージェント＋スキル群）　｜　★530　｜　更新 2026-10-18　｜　ライセンス Apache-2.0　｜　ドキュメント言語：英語
- **成果物**：スタイル参照ファイル、アーク/章/ビート単位のアウトライン、知識ベース（ナレッジレイヤー）、批評ノート、読者反応ログ
- **技術・方法**：muse（作者窓口）が brainstormer / outliner / writer / critic / editor / reader-sim / character-sim / continuity-checker / style-creator を振り分け。character-simで『キャラ本人と対話』して声や関係性を発見、reader-simで初読者の体験を逐次シミュレート、既存原稿から文体ファイルを蒸留
- **導入**：Claude Code プラグインとして導入（README参照）、または meridian mars add haowjy/creative-writing-skills
- **向いている人・用途**：キャラクターの声・関係性を対話で掘り下げたい人、批評ループを回したい人
- **注意点**：エージェント数が多くトークン消費は大きめ

#### MintoTsukino/claude-novel-workflow　〔ランク S｜21/25〕

- **リンク／基本情報**：https://github.com/MintoTsukino/claude-novel-workflow　｜　Claude Codeワークフロー（テンプレート＋実例プロジェクト＋ドキュメント）　｜　★10　｜　更新 2026-06-16　｜　ライセンス 要確認　｜　ドキュメント言語：英語/日本語（実例）
- **成果物**：canon.md、character_bible.md、world_bible.md、glossary.md、timeline.md（伏線台帳）、style_guide.md、forbidden_patterns.md、話数別ブリーフ・プロット・シーンカード、三層レビュー記録
- **技術・方法**：書籍化実績15冊超の日本のライトノベル作家による公開スナップショット。『AIは小説を書かない、作者が作ったカノンに従って大量に下書きする』思想。読者感情7変数・11ルール・4種OSクラスからなるJETストーリー設計フレームワーク（章ごとにAI採点可能）。AI草稿と人手推敲版（カクヨム掲載）の対照あり。96分で20話・137,806字の実績
- **導入**：templates/ をコピーして自作プロジェクトを開始（UNIVERSAL_PROMPT.md / GPTs・Gems用プロンプトもあり）
- **向いている人・用途**：日本語のWeb小説・ライトノベル作者
- **注意点**：ライセンスNOASSERTION（利用条件を要確認）。数日のカノン構築が前提

#### narrastory/story-architect-skill　〔ランク A｜19/25〕

- **リンク／基本情報**：https://github.com/narrastory/story-architect-skill　｜　単一Agent Skill（references/・scripts/・agents/同梱）　｜　★5　｜　更新 2026-07-31　｜　ライセンス MIT　｜　ドキュメント言語：英語/中国語
- **成果物**：世界観、人物、プロット概要、草稿、年表、プロットスレッド、カノン、人物の知識状態、レビュー記録、最終稿をそれぞれ専用の場所に配置したプロジェクト
- **技術・方法**：創作セッション毎に台帳（ledger）を同期。時間・設定・POV・人物の知識・スレッド整合性を検査。既存原稿を構造化プロジェクトへ安全に移行する手順を持つ。『最終決定権は作者』原則
- **導入**：SKILL.md を Claude Code の skills ディレクトリへ配置
- **向いている人・用途**：曖昧なアイデアから短編〜長編を組み立てたい人、既存原稿の移行
- **注意点**：小規模プロジェクト（スター少）

#### robskidmore/fiction-skills　〔ランク A｜18/25〕

- **リンク／基本情報**：https://github.com/robskidmore/fiction-skills　｜　Claude Code Skills（17個）　｜　★0　｜　更新 2026-10-11　｜　ライセンス MIT　｜　ドキュメント言語：英語
- **成果物**：00_contract.md（Story Contract）、01_world/（トピック別ファイル）、02_characters/、03_outline.md、04_relationships.md
- **技術・方法**：『インタビュー型』で作者に質問してから提案。生成要素に[notes]/[implied]/[new]の出自タグを付与し、採用時に外す。ジャンル・トーン・思弁的ルール・禁止事項・構造をStory Contractで一度合意し逸脱を警告。起承転結・Story Circle・Save the Cat等を選択可。world（世界設定の内部整合性チェック）、relationships（二者関係の力学）、plausibility（動機・因果・時系列の穴）、pressure（予測可能性・低ステークスの診断）
- **導入**：リポジトリを ~/.claude/skills/ に配置（プラグイン定義あり）
- **向いている人・用途**：AIに書かせず『設計を詰める』用途。設定の出自を明確にしたい作者
- **注意点**：公開直後でスター数は少ない（実績未知数）

#### howells/fiction　〔ランク A｜18/25〕

- **リンク／基本情報**：https://github.com/howells/fiction　｜　Claude Code / Codex プラグイン（20スキル）　｜　★22　｜　更新 2026-10-17　｜　ライセンス なし/不明　｜　ドキュメント言語：英語
- **成果物**：物語アーキテクチャ設計書、キャラクター文書、章アウトライン、批評・編集ノート、あらすじ、表紙・挿絵、タイトル候補
- **技術・方法**：/fiction:plan→character→outline→章執筆の順で進行。reconcile（設定と原稿の突合）、critique/edit、naming（タイトル案生成と既存書籍との重複確認）、language（非英語フレーズの文法・時代考証チェック）
- **導入**：claude plugins:add howells/fiction
- **向いている人・用途**：Claude Codeで長編を一気通貫で書きたい人
- **注意点**：LICENSEファイル無し（再利用条件は要確認）

#### rhavekost/author-toolkit　〔ランク B｜16/25〕

- **リンク／基本情報**：https://github.com/rhavekost/author-toolkit　｜　Claude Code プラグイン（6スキル）　｜　★18　｜　更新 2026-07-22　｜　ライセンス 要確認　｜　ドキュメント言語：英語
- **成果物**：ブループリント／Story Bible、セッションノート（sessions/YYYY-MM-DD_*.md）、アーキタイプ監査
- **技術・方法**：fiction-workshop（開発編集・ライン編集・キャラ相談・継続性トラッカー・ブレスト役の5ペルソナ）、character-archetypes（Vogler/Campbellの8機能＋Jung派12アーキタイプで診断）、story-structure、avoid-ai-writing。セッション終了時に状態を書き戻す
- **導入**：/plugin でマーケットプレイス追加（README参照）
- **向いている人・用途**：アーキタイプ理論でキャラ配置を点検したい人
- **注意点**：ライセンスがNOASSERTION（要確認）


### B. ストーリー構造・プロット設計

#### jtydhr88/screenwriting-skills　〔ランク S｜22/25〕

- **リンク／基本情報**：https://github.com/jtydhr88/screenwriting-skills　｜　Agent Skills（26個）Claude Code / Codex 両対応　｜　★1758　｜　更新 2026-10-03　｜　ライセンス MIT　｜　ドキュメント言語：中国語（README日本語版あり）
- **成果物**：構成表、テーマ・前提、人物葛藤表、シリーズ・エンジン／シリーズバイブル、シーン設計、台詞診断、脚色計画
- **技術・方法**：編集技術書47冊＋脚本・戯曲23巻から蒸留。Trubyの解剖学、三幕・シーン技法、ライターズルーム運営、日本の脚本術（sw-japanese-screenwriting）、小津安二郎スタイル、チェーホフ劇作法、中国戯曲の板腔・曲牌まで
- **導入**：/plugin marketplace add jtydhr88/screenwriting-skills → /plugin install screenwriting@screenwriting-skills
- **向いている人・用途**：脚本・ドラマ・連続ものの構造設計（小説にも転用可）
- **注意点**：スキル本文は中国語（日本語で質問すれば日本語で回答）。README_JAあり

#### jackterror/writers-room-story-engine　〔ランク A｜18/25〕

- **リンク／基本情報**：https://github.com/jackterror/writers-room-story-engine　｜　Agent Skill（SKILL.md＋単一ファイル版MEGA-SKILL.md）　｜　★44　｜　更新 2026-07-07　｜　ライセンス MIT　｜　ドキュメント言語：英語
- **成果物**：前提（premise）、物語の核、主人公エンジン、Story Spine、因果ビート、世界からの圧力、シーン、改稿プラン
- **技術・方法**：Pixarの22ルール、Story Spine、英雄の旅、South Park式『but/therefore』因果律、キャラアーク設計を順序立てて適用。世界観を『葛藤に奉仕させる』設計
- **導入**：SKILL.md を配置、またはMEGA-SKILL.mdをチャットAIに貼付
- **向いている人・用途**：短編・脚本・企画の骨格づくり
- **注意点**：プロンプト主体で検証機構は弱い

#### wordflowlab/novel-writer　〔ランク A｜17/25〕

- **リンク／基本情報**：https://github.com/wordflowlab/novel-writer　｜　npm CLI＋スラッシュコマンド（13種のAIツール対応）　｜　★959　｜　更新 2025-10-26　｜　ライセンス MIT　｜　ドキュメント言語：中国語
- **成果物**：constitution（創作憲法）、spec（仕様）、plan、tasks、章原稿、分析レポート、プロット追跡・年表・人物一貫性検証
- **技術・方法**：GitHub Spec Kit流の『仕様駆動開発（SDD）』を小説に適用した7ステップ：/constitution→/specify→/clarify→/plan→/tasks→/write→/analyze。プラグイン（文体模倣・翻訳等）
- **導入**：npm install -g novel-writer-cn → novel init my-novel --ai claude
- **向いている人・用途**：ソフトウェア開発の手順で小説を管理したい人
- **注意点**：中国語向け最適化。最終更新2025-10

#### IsaiahN/Serendipity-Engine　〔ランク A｜17/25〕

- **リンク／基本情報**：https://github.com/IsaiahN/Serendipity-Engine　｜　PWA／Chrome拡張（StoryWeaver）　｜　★15　｜　更新 2026-06-29　｜　ライセンス 要確認　｜　ドキュメント言語：英語
- **成果物**：人物・関係・物語構造・分解（Decomposition）・原稿を含む8フェーズの作品一式
- **技術・方法**：ブレスト→構造分析→散文生成→継続性チェック→編集フィードバックを8段階で誘導。小説・脚本・戯曲・グラフィックノベル・ゲームシナリオに媒体非依存。BYOK、データはローカル
- **導入**：npm install && npm run dev（またはChrome拡張）
- **向いている人・用途**：非エンジニアがGUIで設計したい場合
- **注意点**：ライセンスNOASSERTION

#### google-deepmind/dramatron　〔ランク B｜13/25〕

- **リンク／基本情報**：https://github.com/google-deepmind/dramatron　｜　Colabノートブック（研究）　｜　★1135　｜　更新 2024-07-16　｜　ライセンス Apache-2.0　｜　ドキュメント言語：英語
- **成果物**：タイトル、登場人物、プロットポイント、場所描写、シーン毎の台詞（脚本）
- **技術・方法**：ログラインから階層的に展開する『階層的物語生成』。各層で作者が編集・再生成でき、劇作家15名とのユーザースタディで検証
- **導入**：colab/dramatron.ipynb を開き、自前のLLM呼び出し（sample関数）を実装
- **向いている人・用途**：階層展開の設計を学びたい人・自作ツールの雛形
- **注意点**：LLM接続は自前実装。2024年以降更新なし

#### GAIR-NLP/MoPS　〔ランク C｜12/25〕

- **リンク／基本情報**：https://github.com/GAIR-NLP/MoPS　｜　研究コード（ACL 2024）　｜　★47　｜　更新 2024-07-19　｜　ライセンス なし/不明　｜　ドキュメント言語：英語
- **成果物**：多様な物語前提（premise）
- **技術・方法**：前提をテーマ・背景・人物像などのモジュールに分解し、候補をネスト辞書に事前収集→キーパスを抽出→LLMで統合して前提化。前提の多様性と品質を両立
- **導入**：poetry install → notebooks参照
- **向いている人・用途**：アイデア出しを体系化したい人・ツール開発者
- **注意点**：研究コードで保守停止。LICENSE無し


### C. キャラクター構築

#### SillyTavern/SillyTavern　〔ランク S｜21/25〕

- **リンク／基本情報**：https://github.com/SillyTavern/SillyTavern　｜　LLMフロントエンド（Webアプリ）　｜　★34828　｜　更新 2026-10-02　｜　ライセンス AGPL-3.0　｜　ドキュメント言語：英語（多言語UI）
- **成果物**：Character Card（V2/V3仕様）、World Info（ロアブック）、グループチャット、ビジュアルノベルモード
- **技術・方法**：キーワードトリガーで設定を文脈注入するWorld Infoと、人物定義を可搬化したキャラクターカードの事実上の標準。多数のツール（カード生成器・ロアブック作成器）がこの形式に準拠
- **導入**：git clone → Start.bat / start.sh
- **向いている人・用途**：キャラの『声』を対話で検証、設定の文脈注入の仕組みを学ぶ
- **注意点**：AGPL-3.0。NSFW用途のコミュニティ資源も多い点に注意

#### Calliope-Editor/writing-skills　〔ランク A｜18/25〕

- **リンク／基本情報**：https://github.com/Calliope-Editor/writing-skills　｜　Claude Agent Skills（13個、本文は書かない拡張専用）　｜　★5　｜　更新 2026-07-16　｜　ライセンス MIT　｜　ドキュメント言語：英語
- **成果物**：標準キャラクターカード（目的・傷・アーク・声・関係）、原稿からの逆生成キャラカード、編集レポート、ベータ読者パネルの反応
- **技術・方法**：character-card-builder（一問ずつ質問して半端なアイデアを人物に仕上げる）、reverse-character-cards（書かれた原稿だけを根拠に主要人物のカードを逆算）、dialogue-gym、psychic-distance、scene-architecture、continuity-editor 等。散文は一切生成しない設計原則
- **導入**：skills/ 以下を Claude の skills ディレクトリへ配置
- **向いている人・用途**：自分で書きたい作者のキャラ設計・診断
- **注意点**：Calliope MCP連携は任意

#### 63435212cwu-ops/nest-drama　〔ランク A｜18/25〕

- **リンク／基本情報**：https://github.com/63435212cwu-ops/nest-drama　｜　ローカルWebアプリ（Python標準ライブラリのみ）　｜　★57　｜　更新 2026-09-13　｜　ライセンス AGPL-3.0　｜　ドキュメント言語：英語/中国語
- **成果物**：世界観、プロット背骨（必達ビート／可変ビート）、人物ごとの3枚のカード（核・声・心理）、ユニットストーリー／巻プロット
- **技術・方法**：各人物を『知るべきことだけを知る』独立エージェントとして自律行動させ、プロット線は『鉄道ではなく引力場』として世界内の手段で既定ノードへ誘導
- **導入**：python3 ui/serve.py → http://localhost:8787
- **向いている人・用途**：キャラ主導で物語を生成したい人
- **注意点**：AGPL-3.0

#### jacky-0218-lung/character-ip-design　〔ランク A｜18/25〕

- **リンク／基本情報**：https://github.com/jacky-0218-lung/character-ip-design　｜　Agent Skill／Claude Codeプラグイン　｜　★2　｜　更新 2026-08-10　｜　ライセンス Apache-2.0　｜　ドキュメント言語：繁体中国語/英語
- **成果物**：競合IPポジショニング表、世界観、キャラ深層分析（価値観・渇望・禁忌・ギャップ）、3コンセプト案、同一キャラの3画風比較、スーパーシンボル、行動設定書（golden record）、SVG→LINEスタンプ等の多形式出力
- **技術・方法**：研究→設計→商業化の一貫パイプライン。シルエット・展開・色彩の3検証、13画風ライブラリ、AI生成キャラの著作権・商標の確認順序
- **導入**：/plugin marketplace add jacky-0218-lung/character-ip-design
- **向いている人・用途**：オリジナルキャラクターIPの企画書づくり
- **注意点**：法的記述は参考情報

#### FutureFuzzy/novel-distiller　〔ランク A｜17/25〕

- **リンク／基本情報**：https://github.com/FutureFuzzy/novel-distiller　｜　Python CLI＋Claude Codeスキル（/ws）　｜　★51　｜　更新 2026-05-11　｜　ライセンス MIT　｜　ドキュメント言語：中国語
- **成果物**：創世ブループリント、人物ごとの『思考OS』SKILL.md、作者文体DNA、シーン推演ログ、章原稿、プラットフォーム規約チェック結果
- **技術・方法**：World Spirit方法論：想法→創世ブループリント→魂の蒸留（人物ごとに思考様式をSKILL.md化しOOC防止）→作者蒸留→多エージェントによる場面推演（合理性を先に検証）→執筆→アンカー自己点検。YAMLの数値状態層で暗線（伏線）を章横断追跡
- **導入**：pip install -e . → ws init / ws distill-soul / ws plot / ws write
- **向いている人・用途**：キャラ崩壊を防ぎたい長編
- **注意点**：中国語。既存作品人物の蒸留は権利に注意

#### cha1latte/sillytavern-character-generator　〔ランク B｜16/25〕

- **リンク／基本情報**：https://github.com/cha1latte/sillytavern-character-generator　｜　プロンプトファイル（標準版／小型モデル版）　｜　★60　｜　更新 2026-03-16 📦　｜　ライセンス MIT　｜　ドキュメント言語：英語
- **成果物**：SillyTavern Character Card V2 JSON（説明・性格・シナリオ・例示台詞・複数の挨拶文）
- **技術・方法**：プロンプトをClaude/GPT/Gemini等にアップロードし2〜3問に答えるだけで、エスケープ・フィールド順まで正しいJSONを出力。7B〜13B向けの省トークン版も
- **導入**：md ファイルをチャットAIに渡して『execute these instructions』
- **向いている人・用途**：最小コストでキャラシートの型を作る
- **注意点**：アーカイブ済み


### D. 世界観構築（設定DB・地図・言語・暦・ロアブック）

#### Azgaar/Fantasy-Map-Generator　〔ランク S｜23/25〕

- **リンク／基本情報**：https://github.com/Azgaar/Fantasy-Map-Generator　｜　Webアプリ（ブラウザ／Electron）　｜　★6128　｜　更新 2026-10-22　｜　ライセンス 要確認　｜　ドキュメント言語：英語（UIは多言語化進行）
- **成果物**：編集可能なファンタジー世界地図：国家・州・文化・宗教・都市・道路・軍事・マーカー・ノート、各種エクスポート
- **技術・方法**：地形生成から国家・文化圏・宗教の分布、都市配置までを手続き生成し、エディタで手直し。地図データは他ツール（Foundry VTT、CK3変換等）にも連携されるエコシステム
- **導入**：azgaar.github.io/Fantasy-Map-Generator をブラウザで開くだけ
- **向いている人・用途**：地理・政治地図から世界観を立ち上げたい人
- **注意点**：ライセンス表記がNOASSERTION（利用時に要確認）

#### hiveforge-sh/hivemind　〔ランク A｜20/25〕

- **リンク／基本情報**：https://github.com/hiveforge-sh/hivemind　｜　MCPサーバー＋Obsidianプラグイン　｜　★10　｜　更新 2026-10-21　｜　ライセンス MIT　｜　ドキュメント言語：英語
- **成果物**：Vault上のタイムラインビュー、関係グラフビュー、カノン状態（approved/review/draft）管理
- **技術・方法**：Obsidianの設定ノートを『AIファイアウォール』＝真実のアンカーとして構造化アクセスさせ、AIの幻覚による設定矛盾を防ぐ。カノン承認ワークフロー
- **導入**：npm / Obsidianプラグインとして導入しMCP登録
- **向いている人・用途**：Obsidianで設定を管理しつつAIと共作する人
- **注意点**：テンプレートはVault構造に依存

#### owlchester/kanka　〔ランク A｜20/25〕

- **リンク／基本情報**：https://github.com/owlchester/kanka　｜　ソース公開型Webアプリ（kanka.ioでホスト版提供）　｜　★361　｜　更新 2026-10-22　｜　ライセンス 要確認　｜　ドキュメント言語：英語（多言語UI）
- **成果物**：人物・場所・組織・家系・暦・年表・地図・クエスト等を相互リンクしたキャンペーン/世界Wiki
- **技術・方法**：TRPG・創作向けの共同ワールドビルディング管理。月次リリースの長期運用実績、翻訳コミュニティ
- **導入**：kanka.io で利用、または docs/running.md に従いセルフホスト
- **向いている人・用途**：共同で世界観を管理するTRPGグループ・創作チーム
- **注意点**：ソース公開だがOSSライセンスではない（NOASSERTION）

#### virgilianshailer/lorebook-creator　〔ランク A｜20/25〕

- **リンク／基本情報**：https://github.com/virgilianshailer/lorebook-creator　｜　SillyTavern拡張　｜　★16　｜　更新 2026-08-07　｜　ライセンス MIT　｜　ドキュメント言語：英語
- **成果物**：SillyTavern World Info / LoreBook JSON（世界概要、ロア、人物・勢力・場所・物品・事件・魔法/技術・生物・慣習・基本ルールの項目とトリガーキーワード）
- **技術・方法**：一行の前提または『世界タイプ×時代×規模』のガイド付きフォームから相互連関した項目群を生成。既存ロアブックの機械的欠陥監査、自然言語での編集、2冊のマージ、既存項目からの拡張
- **導入**：SillyTavernの拡張機能インストールでURL指定
- **向いている人・用途**：ロールプレイ／対話型創作の世界設定
- **注意点**：SillyTavern環境が前提

#### jeheydorn/nortantis　〔ランク A｜20/25〕

- **リンク／基本情報**：https://github.com/jeheydorn/nortantis　｜　デスクトップアプリ（Java）　｜　★230　｜　更新 2026-10-22　｜　ライセンス AGPL-3.0　｜　ドキュメント言語：英語
- **成果物**：大陸・島・湖・森・川・山・都市を含むファンタジー地図、政治区画・道路・テキスト・独自テクスチャ
- **技術・方法**：ポリゴンベースのプレートテクトニクス・シミュレーションで地形を生成し、物語に合わせて描き直し可能。『作家による作家のための』地図エディタ
- **導入**：プロジェクトページのインストーラ、または ./gradlew :run
- **向いている人・用途**：小説の巻頭地図レベルの完成品を作りたい人
- **注意点**：AGPL-3.0

#### fantasycalendar/Fantasy-Calendar　〔ランク A｜20/25〕

- **リンク／基本情報**：https://github.com/fantasycalendar/Fantasy-Calendar　｜　Webアプリ（fantasy-calendar.com）　｜　★146　｜　更新 2026-10-22　｜　ライセンス なし/不明　｜　ドキュメント言語：英語
- **成果物**：独自の暦（複数の月・季節・紀年・閏ルール）と事件トラッキング
- **技術・方法**：複雑な天体設定や例外的な時間体系を表現でき、Forgotten Realms等のプリセットも利用可
- **導入**：fantasy-calendar.com で利用、またはDockerでセルフホスト
- **向いている人・用途**：暦・祝祭日・季節を物語に組み込みたい人
- **注意点**：リポジトリにLICENSE無し

#### gofastercloud/worldbuilder　〔ランク A｜19/25〕

- **リンク／基本情報**：https://github.com/gofastercloud/worldbuilder　｜　CLI（22コマンド）＋Flask Web UI＋MCPサーバー＋Claude Codeスキル　｜　★7　｜　更新 2026-06-23　｜　ライセンス Apache-2.0　｜　ドキュメント言語：英語
- **成果物**：11種エンティティ（人物・場所・勢力・魔法体系・言語・血統など）のMarkdown＋YAML、関係グラフ可視化、執筆用プロンプト
- **技術・方法**：slugで相互参照し、グラフ整合性レイヤーが双方向関係・年表の整合・ワールドフラグ遵守を検証。各エンティティに『機械可読データ／文体付き散文／画像生成プロンプト』の三重記述。ウィザードで世界全体を生成
- **導入**：uv で導入し scripts/worldbuilder.py、MCPは mcp_server/ を登録
- **向いている人・用途**：ファイルベースでGit管理する設定資料集
- **注意点**：スター少・個人開発

#### morrisalp/ConlangCrafter　〔ランク A｜19/25〕

- **リンク／基本情報**：https://github.com/morrisalp/ConlangCrafter　｜　Python研究コード（ACL 2026 Oral）＋HFデータセット　｜　★49　｜　更新 2026-07-25　｜　ライセンス MIT　｜　ドキュメント言語：英語
- **成果物**：人工言語スケッチ：音韻論（子音・母音・音素配列）、文法、語彙、翻訳例
- **技術・方法**：多段（multi-hop）LLMパイプラインで音韻→形態・統語→語彙→翻訳を順に生成し、制約（--custom-constraints）で方向付け。生成した64言語のデータセットを公開
- **導入**：pip install -r requirements.txt → python src/run_pipeline.py（Gemini/OpenAI/DeepSeek APIキー）
- **向いている人・用途**：種族・国家ごとの言語や固有名詞体系を作りたい人
- **注意点**：API費用が発生

#### javalent/calendarium　〔ランク A｜19/25〕

- **リンク／基本情報**：https://github.com/javalent/calendarium　｜　Obsidianプラグイン　｜　★154　｜　更新 2025-09-27　｜　ライセンス MIT　｜　ドキュメント言語：英語
- **成果物**：Obsidian内のファンタジー/SF暦と、ノートから拾ったイベント表示
- **技術・方法**：Vaultのノート日付と連動させ、年表とカレンダーを一体で管理
- **導入**：Obsidian コミュニティプラグインからインストール
- **向いている人・用途**：Obsidianで設定資料を管理する人

#### benabhi/skills-world-building　〔ランク A｜18/25〕

- **リンク／基本情報**：https://github.com/benabhi/skills-world-building　｜　Claude Code Skills（9個）＋Pythonスクリプト、Obsidian Vault前提　｜　★0　｜　更新 2026-10-14　｜　ライセンス なし/不明　｜　ドキュメント言語：スペイン語
- **成果物**：Obsidian Vault：世界票（Ficha del Mundo）、CLAUDE.md（世界ルール）、28種のエンティティノート（人物・地域・集落・経路・勢力・血統・物品・信仰・神格・種族・文化・言語・暦・時代・事件・現象・生物…）、地図・画像、索引（Bases）
- **技術・方法**：初回インタビューで世界の柱（前提・ジャンル・トーン・力の体系・技術・神々・種族・暦）を確定。拡張エンジン（expandir-mundo）がサイクル毎に『未解決のwikilink』をスコアリングして次に作るものを選び、スクリプトで実際の乱数を使って素材表をロール→文脈収集→作成→検証→記録→git commit。テストモードは別ブランチで生成し採否を判断、finalizar-mundoで新規リンクを止めて世界を閉じる
- **導入**：skills/ を Claude Code に配置し、Obsidian（Bases プラグイン）でVaultを開く
- **向いている人・用途**：世界を自律的に『育てる』大規模ワールドビルディング
- **注意点**：スキル本文はスペイン語。LICENSE無し。スター少

#### loreum-app/loreum　〔ランク A｜18/25〕

- **リンク／基本情報**：https://github.com/loreum-app/loreum　｜　OSS Webプラットフォーム（MCP接続）　｜　★3　｜　更新 2026-09-24　｜　ライセンス AGPL-3.0　｜　ドキュメント言語：英語
- **成果物**：カスタムスキーマのエンティティ、知識グラフ、カスタム暦対応のガントチャート型年表、Lore Wiki、ストーリーボード、スタイルガイド
- **技術・方法**：世界ごとのMCP URLでClaude/Cursorに読み取り／書き込み権限を付与。AI提案のレビューキューをロードマップに
- **導入**：docker compose でセルフホスト、またはホスト版
- **向いている人・用途**：チームでの世界観DB運用
- **注意点**：AGPL-3.0。新しいプロジェクト

#### jasnonaz/vibe-worldbuilding-mcp　〔ランク A｜17/25〕

- **リンク／基本情報**：https://github.com/jasnonaz/vibe-worldbuilding-mcp　｜　MCPサーバー（Claude Desktop等）　｜　★10　｜　更新 2025-10-04　｜　ライセンス なし/不明　｜　ドキュメント言語：英語
- **成果物**：世界コンセプト、カスタム分類体系、相互リンクされた項目、参照先の自動スタブ、AI画像（FAL）、ナビゲーション付き静的Webサイト（Astro）
- **技術・方法**：『浮遊島のファンタジー世界を作って』の一言からタクソノミー設計→項目生成→相互参照→未作成項目のスタブ化→画像→サイト化までをMCPツール群で実行
- **導入**：pip install -e . && npm install → Claude Desktop設定にMCP登録
- **向いている人・用途**：設定資料を『読めるWiki』として公開・共有したい人
- **注意点**：LICENSE無し。最終更新2025-10

#### mm-weber/loremaester　〔ランク B｜16/25〕

- **リンク／基本情報**：https://github.com/mm-weber/loremaester　｜　Claude Code設定（4スキル）＋MCPサーバー群（14ツール）　｜　★19　｜　更新 2026-10-21　｜　ライセンス MIT　｜　ドキュメント言語：英語
- **成果物**：TTRPGキャンペーンVault内のNPC・場所・セッション案・キャンペーン年代記（Campaign_Chronicle.md）
- **技術・方法**：Obsidian VaultをカノンとしてwikilinkグラフをMCPで巡回し、OCR済みソースブック（スキャンPDF含む）をR2Rハイブリッド検索。両者に整合する新要素を正しいfrontmatter・リンク付きで書き込む。chronikはプレイヤーノートから年代記を精密に更新
- **導入**：Docker等でR2Rとmcp-serversを構築（README・デモ手順あり）
- **向いている人・用途**：既存資料（設定本・PDF）を根拠にした世界拡張・TRPG運営
- **注意点**：構築がやや重い

#### wlcarden/worldanvil-mcp　〔ランク B｜16/25〕

- **リンク／基本情報**：https://github.com/wlcarden/worldanvil-mcp　｜　MCPサーバー（90+ツール）／Claude Codeプラグイン　｜　★11　｜　更新 2026-06-01　｜　ライセンス MIT　｜　ドキュメント言語：英語
- **成果物**：WorldAnvil上の記事（人物・場所・アイテム）、地図とマーカー、タイムラインと事件、GM専用シークレット
- **技術・方法**：WorldAnvil APIをAIエージェントから操作し、記事・地図・年表を一括生成・更新
- **導入**：/install wlcarden/worldanvil-mcp または npx worldanvil-mcp（WA_AUTH_TOKEN必要）
- **向いている人・用途**：既にWorldAnvilを使っている作者・GM
- **注意点**：WorldAnvilアカウント必須

#### bmen25124/lorecard　〔ランク B｜16/25〕

- **リンク／基本情報**：https://github.com/bmen25124/lorecard　｜　Webアプリ（Docker）　｜　★99　｜　更新 2026-06-30　｜　ライセンス GPL-3.0　｜　ドキュメント言語：英語
- **成果物**：URL（Fandomのカテゴリページ等）からロアブック／キャラクターカード
- **技術・方法**：リンク群を辿って各ページを抽出し項目化。プロンプトテンプレートをグローバル／プロジェクト単位で編集可能
- **導入**：docker compose up
- **向いている人・用途**：既存資料からのロアブック化
- **注意点**：既存作品Wikiの転用は著作権・規約に注意。GPL-3.0


### E. 歴史・年表・社会シミュレーション

#### sreegjl/timelines　〔ランク S｜21/25〕

- **リンク／基本情報**：https://github.com/sreegjl/timelines　｜　デスクトップアプリ（Electron）／Webビューア　｜　★222　｜　更新 2026-10-21　｜　ライセンス GPL-3.0　｜　ドキュメント言語：英語（i18n対応）
- **成果物**：.timeline（JSON）＋Markdownノート：事件（点）、期間（分岐・合流可能なスパン）、時代帯（Era）、タグ・グループ、地図ビュー
- **技術・方法**：ワールドビルディングと歴史のためのインタラクティブ年表。座標を持たせ時間スライダーで地点の出現・消滅を可視化、MediaWiki/Wikipedia参照、Obsidian Vault連携。ローカルファースト
- **導入**：Releases からインストーラを入手
- **向いている人・用途**：架空史・王朝史・戦史の年表化
- **注意点**：GPL-3.0

#### wailers9/bragi　〔ランク A｜17/25〕

- **リンク／基本情報**：https://github.com/wailers9/bragi　｜　Python CLI＋ローカルWeb UI　｜　★32　｜　更新 2026-05-17　｜　ライセンス なし/不明　｜　ドキュメント言語：中国語
- **成果物**：世界概要・基底ルール・歴史の流れ・空間構造、人物ネットワーク、公開／個人事件ログ、物語断片
- **技術・方法**：一文の設定から世界を生成し、時間（歴史段階）と空間（地点階層）を『1,2,3』の数字パスで表す二重ツリーで管理。現在の時空ノードは全文、近傍は要約、必要時に展開することで文脈を節約しつつ世界を拡張
- **導入**：pip install -e . → CLI / web（Demo Agentは API キー不要）
- **向いている人・用途**：歴史と地理を入れ子で育てる架空世界
- **注意点**：LICENSE無し。スター少

#### ZJU-LLMs/OpenStory　〔ランク A｜17/25〕

- **リンク／基本情報**：https://github.com/ZJU-LLMs/OpenStory　｜　多エージェント推演フレームワーク＋ランチャー　｜　★433　｜　更新 2026-08-19　｜　ライセンス Apache-2.0　｜　ドキュメント言語：中国語/英語
- **成果物**：人物・地点・経路・ルールを持つ対話可能な物語世界、分岐する推演ログ
- **技術・方法**：感知→計画→実行→反省のプラグインで人物が自律行動。WorldKernelは一文から世界を分解生成。過去ノードへの回溯と分岐。『紅楼夢』『ウエストワールド』の実例
- **導入**：Releases のランチャー、または packages からセットアップ
- **向いている人・用途**：群像劇・社会の動きをシミュレートしたい人
- **注意点**：中国語中心

#### atisharma/chasm　〔ランク A｜17/25〕

- **リンク／基本情報**：https://github.com/atisharma/chasm　｜　生成型テキストアドベンチャー（piハーネス上）　｜　★15　｜　更新 2026-09-06　｜　ライセンス MIT　｜　ドキュメント言語：英語
- **成果物**：Markdownファイル群のディレクトリ＝世界（場所・人物・会話・事件が永続化）、gitで配布可能
- **技術・方法**：数文で指定した世界をプレイ中に生成し、重要状態をセッション間で保持。世界をgitリポジトリとして他者が続きを遊べる
- **導入**：curl -sSL https://chasm.run/web-install.sh | bash
- **向いている人・用途**：遊びながら世界と出来事の記録を作る
- **注意点**：ツール呼び出し対応モデルが必要

#### siftystudio/viv　〔ランク B｜16/25〕

- **リンク／基本情報**：https://github.com/siftystudio/viv　｜　創発的物語エンジン（DSL・コンパイラ・ランタイム）＋Claude Codeプラグイン　｜　★39　｜　更新 2026-09-05　｜　ライセンス 要確認　｜　ドキュメント言語：英語
- **成果物**：キャラクター行動定義、ストーリーワールド設計、シミュレーション内の物語線（story sifting結果）
- **技術・方法**：人物行動を記述する専用言語と、シミュレーション結果から物語線を抽出する『ストーリー・シフティング』。Claudeプラグインにdesign/build/critique/write等のスキル
- **導入**：pip / npm パッケージ、またはClaude Codeプラグイン
- **向いている人・用途**：ゲーム・シミュレーション型の歴史生成
- **注意点**：ソース公開（非商用無料、商用は要ライセンス）

#### ShiJbey/neighborly　〔ランク B｜15/25〕

- **リンク／基本情報**：https://github.com/ShiJbey/neighborly　｜　Pythonライブラリ（エージェントベース・シミュレーション）　｜　★80　｜　更新 2026-04-07 📦　｜　ライセンス MIT　｜　ドキュメント言語：英語
- **成果物**：数世代にわたる集落の住民史：特性・地位・関係・職業・ライフイベントのログ（データ分析可能）
- **技術・方法**：Talk of the Town／Dwarf Fortress／Crusader Kings等に着想。就職・恋愛などの出来事を『創発的物語』の素材として記録
- **導入**：pip install（pyproject.toml）→ samples参照
- **向いている人・用途**：町や家系の『それらしい歴史』を素材生成
- **注意点**：アーカイブ（博士研究の保存版）

#### ShiJbey/minerva　〔ランク B｜15/25〕

- **リンク／基本情報**：https://github.com/ShiJbey/minerva　｜　Pythonライブラリ（王朝シミュレーター）　｜　★8　｜　更新 2026-04-07 📦　｜　ライセンス 要確認　｜　ドキュメント言語：英語
- **成果物**：地図上で勢力を争う家系・王朝の年代記（SQLで照会可能）
- **技術・方法**：Game of Thrones、将軍、Crusader Kings III、日本の氏族制度に着想した非対話型ダイナスティ・シミュレーション
- **導入**：pip install → samples参照
- **向いている人・用途**：架空の政治史・家系史の素材づくり
- **注意点**：アーカイブ。ライセンスNOASSERTION

#### amcghm/StoryBox　〔ランク B｜14/25〕

- **リンク／基本情報**：https://github.com/amcghm/StoryBox　｜　研究コード（AAAI 2026）　｜　★19　｜　更新 2026-03-27　｜　ライセンス MIT　｜　ドキュメント言語：英語
- **成果物**：長編物語（ボトムアップ型）
- **技術・方法**：キャラ駆動の多エージェント相互作用（ボトムアップ）とトップダウンの物語計画を組み合わせたハイブリッド生成
- **導入**：uv sync → reverie/ 設定
- **向いている人・用途**：シミュレーション×計画の手法研究
- **注意点**：研究コード


### F. 長編生成ハーネス／パイプライン

#### zenstory-ai/oh-story-claudecode　〔ランク S｜23/25〕

- **リンク／基本情報**：https://github.com/zenstory-ai/oh-story-claudecode　｜　Agent Skills（13個）＋サブエージェント、7種のコーディングエージェント対応　｜　★7905　｜　更新 2026-10-18　｜　ライセンス MIT　｜　ドキュメント言語：中国語
- **成果物**：設定・大綱・細綱・本文・追跡ファイル（伏線・未完の約束）、状態カード、拆文（作品分解）レポート、表紙
- **技術・方法**：ファイルシステムを記憶として使い、文脈圧縮後も進捗と伏線を復元。状態カードで『作者の真相』と『読者が知っていること』を分離。執筆前後に決定論的チェック（細綱・追跡、AI的文型）をhooksで自動実行。ランキング調査→人気作分解→執筆の流れ
- **導入**：npx skills add zenstory-ai/oh-story-claudecode -y -g → /story-setup
- **向いている人・用途**：長編連載の運用設計の参考（中国Web小説向けだが手法は汎用）
- **注意点**：中国の網文プラットフォーム前提の部分あり

#### Narcooo/inkos　〔ランク S｜23/25〕

- **リンク／基本情報**：https://github.com/Narcooo/inkos　｜　Agentシステム（Studio / TUI / CLI）＋20スキル　｜　★10432　｜　更新 2026-10-18　｜　ライセンス AGPL-3.0　｜　ドキュメント言語：中国語/英語/日本語README
- **成果物**：truth files（設定・伏線・人物状態）、章原稿、審稿・修訂記録、短編、脚本、互動影游（インタラクティブ映像ゲーム）、開放世界、翻訳、表紙・分鏡
- **技術・方法**：長編は各章執筆後に『監査→修訂→状態書き戻し』。play-world（開放世界）・interactive-film・fanfic・imitation・spinoff等のスキル
- **導入**：pnpm でセットアップ、またはWeb版（README.ja.mdあり）
- **向いている人・用途**：ジャンル横断で一つの基盤を使いたい人
- **注意点**：AGPL-3.0。README内に広告多め

#### lingfengQAQ/webnovel-writer　〔ランク S｜22/25〕

- **リンク／基本情報**：https://github.com/lingfengQAQ/webnovel-writer　｜　Claude Code プラグイン（8スキル＋context/data/reviewer等エージェント）　｜　★7617　｜　更新 2026-10-22　｜　ライセンス GPL-3.0　｜　ドキュメント言語：中国語
- **成果物**：初期設定・総綱、巻綱・章綱、章原稿、多次元レビュー、状態DB＋RAGへの事実コミット、読み取り専用ダッシュボード
- **技術・方法**：『数百章書いても設定を忘れない・伏線を拾う・大綱を守る』ための一貫性システム。章執筆後に事実を状態ライブラリへ提出し、伏線や人物を照会可能に。200万字規模の連載を想定
- **導入**：Claude Code版はmasterブランチ（.claude-plugin/marketplace.json）
- **向いている人・用途**：超長編の設定管理
- **注意点**：GPL-3.0。v8はDeepSeek Harness版で別系統

#### YILING0013/AI_NovelGenerator　〔ランク S｜21/25〕

- **リンク／基本情報**：https://github.com/YILING0013/AI_NovelGenerator　｜　ローカル実行の執筆ワークスペース（Web UI）　｜　★6325　｜　更新 2026-10-16　｜　ライセンス AGPL-3.0　｜　ドキュメント言語：英語/中国語
- **成果物**：物語方向、世界、勢力・人物・関係グラフ、巻→アーク→シーン→章計画、原稿
- **技術・方法**：スノーフレーク法で核となるアイデアから段階的に展開。人物・勢力・物品・伏線の状態を管理し、AI候補を人がレビュー・保存
- **導入**：start.bat / launcher.py（Docker/MongoDB構成あり）
- **向いている人・用途**：GUIで段階的に長編を設計したい人
- **注意点**：AGPL-3.0

#### notnotype/neuro-book　〔ランク A｜20/25〕

- **リンク／基本情報**：https://github.com/notnotype/neuro-book　｜　長編執筆IDE（デスクトップ）＋スキル群　｜　★751　｜　更新 2026-10-14　｜　ライセンス AGPL-3.0　｜　ドキュメント言語：中国語/英語
- **成果物**：Markdown＋SQLiteのワークスペース：設定・プロット・本文・世界状態、伏線『約束台帳』、llmlintレポート
- **技術・方法**：世界状態をモデルの記憶でなくエンジンが時間スライスで推算（イベントソーシング）。伏線を技術的負債のように記帳、360ルールでAI臭をlint。キャラカード工房、SillyTavernカード取込
- **導入**：Windows版をReleasesから（v2再構築中）
- **向いている人・用途**：工学的に長編を管理したい人
- **注意点**：AGPL-3.0。開発中で不安定

#### ExplosiveCoderflome/AI-Novel-Writing-Assistant　〔ランク A｜20/25〕

- **リンク／基本情報**：https://github.com/ExplosiveCoderflome/AI-Novel-Writing-Assistant　｜　Web/デスクトップアプリ　｜　★3275　｜　更新 2026-10-21　｜　ライセンス 要確認　｜　ドキュメント言語：中国語
- **成果物**：世界サンプル庫・人物庫、世界地図、人物関係図、章計画・場面・本文、短編（3千〜3万字）
- **技術・方法**：自動ディレクターが題材・人物目標・候補方向を整理し章を推進。RAG、写法エンジン、トークン予算管理
- **導入**：Windows版インストーラ、またはソースから pnpm
- **向いている人・用途**：初心者が一冊を完成させる
- **注意点**：中国語UI。ライセンスNOASSERTION

#### PenglongHuang/chinese-novelist-skill　〔ランク A｜19/25〕

- **リンク／基本情報**：https://github.com/PenglongHuang/chinese-novelist-skill　｜　単一Agent Skill　｜　★4123　｜　更新 2026-10-20　｜　ライセンス MIT　｜　ドキュメント言語：中国語
- **成果物**：10〜50章の完結した中国語小説、創作記憶（嗜好プロファイル）
- **技術・方法**：三層の段階的Q&A（核心→詳細→任意）でスキップ・ランダム生成可。直列／サブエージェント並列／Agent Teamsの3モード、中断再開、字数・連貫性の自動検証と自動書き直し
- **導入**：npx skills add PenglongHuang/chinese-novelist-skill
- **向いている人・用途**：短〜中編を最後まで完走させたい人
- **注意点**：中国語Web小説の『爽』志向。スポンサー広告あり

#### NousResearch/autonovel　〔ランク A｜18/25〕

- **リンク／基本情報**：https://github.com/NousResearch/autonovel　｜　Pythonパイプライン（自律型）　｜　★1638　｜　更新 2026-03-20　｜　ライセンス なし/不明　｜　ドキュメント言語：英語
- **成果物**：世界・人物・アウトライン・文体・canon、章原稿、印刷用PDF、ePub、オーディオブック、LP
- **技術・方法**：karpathy/autoresearchの『修正→評価→保持/破棄』ループを小説に適用。基盤スコア>7.5まで反復、章はスコア>6.0で採用、敵対的編集・削除適用・読者パネル・Opusによる二人格レビュー。ANTI-SLOP.md／CRAFT.md等の知見文書
- **導入**：uv sync → uv run python run_pipeline.py --from-scratch
- **向いている人・用途**：評価駆動の自律生成の参照実装
- **注意点**：LICENSE無し。API費用大

#### raestrada/storycraftr　〔ランク A｜18/25〕

- **リンク／基本情報**：https://github.com/raestrada/storycraftr　｜　Python CLI（pipx）＋VS Code拡張　｜　★175　｜　更新 2026-03-06　｜　ライセンス MIT　｜　ドキュメント言語：英語
- **成果物**：世界設定（歴史・地理・文化・魔法体系・技術）、アウトライン（全体プロット・章構成・人物要約）、章原稿
- **技術・方法**：サブコマンドで世界観要素を個別生成し、プロジェクト内の資料を参照して章を生成
- **導入**：pipx install storycraftr
- **向いている人・用途**：CLIで設定資料を段階的に作る

#### mrigankad/Novel-OS　〔ランク A｜18/25〕

- **リンク／基本情報**：https://github.com/mrigankad/Novel-OS　｜　多エージェント執筆スタジオ（API＋Web）　｜　★54　｜　更新 2026-08-09　｜　ライセンス MIT　｜　ドキュメント言語：英語
- **成果物**：中央状態ファイル（人物・場所・プロットスレッド・伏線・品質スコア）、章原稿
- **技術・方法**：Architect→Scribe→Editor→Guardian→Curatorの受け渡しと、無料のローカル決定論的継続性エンジン（休眠スレッド・未回収伏線・年表ドリフト検出）
- **導入**：pip install -r requirements.txt → web/
- **向いている人・用途**：決定論的チェックとLLM評価の併用例

#### xindoo/sumeru　〔ランク A｜17/25〕

- **リンク／基本情報**：https://github.com/xindoo/sumeru　｜　Agent Skills（7個）　｜　★215　｜　更新 2026-08-23　｜　ライセンス なし/不明　｜　ドキュメント言語：中国語
- **成果物**：選題分析、世界観・人物・プロット大綱、章原稿、整合性レビュー、各プラットフォーム形式への書き出し
- **技術・方法**：sumeru-worldbuilderが全体をオーケストレーション。時間線・プロット・人物OOC（キャラ崩壊）を自動校閲、中断再開
- **導入**：npx skills add xindoo/sumeru
- **向いている人・用途**：Web小説の一気通貫ワークフロー
- **注意点**：LICENSE無し

#### Lanerra/saga　〔ランク A｜17/25〕

- **リンク／基本情報**：https://github.com/Lanerra/saga　｜　ローカルPython CLI（Neo4j＋LangGraph）　｜　★114　｜　更新 2026-09-15　｜　ライセンス Apache-2.0　｜　ドキュメント言語：英語
- **成果物**：アウトライン、人物/世界ファイル、シーン単位草稿、要約、Markdown原稿
- **技術・方法**：Neo4j知識グラフで人物・事件・関係を追跡し、LangGraphのチェックポイントで中断再開
- **導入**：Python環境＋Neo4j＋モデルエンドポイントを自前用意
- **向いている人・用途**：知識グラフで整合性を管理したい技術者
- **注意点**：構築難度高め

#### jblemee/bmad-book-builder　〔ランク B｜16/25〕

- **リンク／基本情報**：https://github.com/jblemee/bmad-book-builder　｜　BMADメソッドのモジュール（8エージェント・17ワークフロー）　｜　★33　｜　更新 2026-01-25　｜　ライセンス WTFPL　｜　ドキュメント言語：英語
- **成果物**：Story Bible、人物監査、テーマ・リズム分析、章原稿
- **技術・方法**：Story Architect / Character Keeper / Style Coach / Continuity Editor等が分担。章ごとの監査チェーン、TTR・文長など定量的文体指標、執筆前22項目チェック
- **導入**：BMAD環境にモジュールとして追加
- **向いている人・用途**：BMADを既に使っている人
- **注意点**：WTFPL

#### principia-ai/WriteHERE　〔ランク B｜15/25〕

- **リンク／基本情報**：https://github.com/principia-ai/WriteHERE　｜　OSSフレームワーク（バックエンド＋フロント）　｜　★976　｜　更新 2026-09-03　｜　ライセンス なし/不明　｜　ドキュメント言語：英語
- **成果物**：長編フィクション、技術レポート
- **技術・方法**：異種再帰計画：執筆タスクを検索・推論・執筆の異種サブタスクに再帰分解し、実行と計画を交互に動的適応（EMNLP 2025 Oral）
- **導入**：setup_env.sh / start.sh
- **向いている人・用途**：固定ワークフローでない長文生成を試したい人
- **注意点**：LICENSE無し

#### aiwaves-cn/RecurrentGPT　〔ランク B｜13/25〕

- **リンク／基本情報**：https://github.com/aiwaves-cn/RecurrentGPT　｜　研究コード＋Gradioデモ　｜　★999　｜　更新 2024-05-15　｜　ライセンス GPL-3.0　｜　ドキュメント言語：英語
- **成果物**：任意長の小説・インタラクティブフィクション
- **技術・方法**：LSTMの状態を自然言語で模擬：各ステップで段落と次段落の計画を出力し、短期記憶を書き換え、段落要約を意味検索可能な長期記憶へ追加。人が次の計画を選べる
- **導入**：recurrent.sh の設定を編集して実行
- **向いている人・用途**：長文記憶設計の基礎理解
- **注意点**：GPL-3.0。2024年以降更新なし


### G. 推敲・品質評価（De-AI・批評・ベンチマーク）

#### Nanako0129/sepia　〔ランク S｜21/25〕

- **リンク／基本情報**：https://github.com/Nanako0129/sepia　｜　Agent Skill（77+エージェント対応）＋ネイティブプラグイン　｜　★3429　｜　更新 2026-10-15　｜　ライセンス MIT　｜　ドキュメント言語：英語/中国語
- **成果物**：診断レポート（review）、最小修正版（refactor）、全面書き直し版（recreate）
- **技術・方法**：StoryScope研究（人間＋LLMの61,608編）に基づき、語彙より先に物語構造（主題の明示、因果連鎖、開示のタイミング）を修正する三段階De-AI
- **導入**：npx skills add Nanako0129/sepia（Claude Code等はプラグインも）
- **向いている人・用途**：AIっぽい物語構造の診断
- **注意点**：中国語の文リズム調整あり、日本語専用ルールは無し

#### XTmingyue/wenfeng-skill　〔ランク A｜17/25〕

- **リンク／基本情報**：https://github.com/XTmingyue/wenfeng-skill　｜　Agent Skill（スキル蒸留器）　｜　★21　｜　更新 2026-05-26　｜　ライセンス MIT　｜　ドキュメント言語：中国語
- **成果物**：作品から抽出した執筆用SKILL.md（叙事モデル・言語指紋・モチーフ・人物造形・プロット技法・創作境界）
- **技術・方法**：規則の採用条件を『再現性（作中で複数回）・生成力（新場面に使える）・排他性（凡庸な助言でない）』で選別し、筋の要約や原文抜粋はしない
- **導入**：npx skills add XTmingyue/wenfeng-skill
- **向いている人・用途**：自作・参考作の『書き方』を再利用可能にする
- **注意点**：権利のある作品の扱いに注意

#### jmcnestrie/novel-harness　〔ランク B｜16/25〕

- **リンク／基本情報**：https://github.com/jmcnestrie/novel-harness　｜　Claude Codeハーネス（drafter＋レビュアー群）　｜　★4　｜　更新 2026-07-07　｜　ライセンス MIT　｜　ドキュメント言語：英語
- **成果物**：ボイス固定の章草稿、reviews/配下の批評ノート
- **技術・方法**：鉄則『批評者は編集しない』『エージェントは提案、作者が昇格』。散文・継続性・テーマ逸脱・AI臭検出の並列レビュアー＋決定論的lint＋他モデルファミリーによるクロス批評
- **導入**：リポジトリをプロジェクトとして clone
- **向いている人・用途**：作者主導で品質管理したい人

#### EQ-bench/creative-writing-bench　〔ランク B｜15/25〕

- **リンク／基本情報**：https://github.com/EQ-bench/creative-writing-bench　｜　ベンチマークコード（EQ-Bench Creative Writing v3）　｜　★147　｜　更新 2026-06-24　｜　ライセンス なし/不明　｜　ドキュメント言語：英語
- **成果物**：モデル別の創作評価（ルーブリック点＋Elo/Glicko）
- **技術・方法**：32プロンプト×3反復をジャッジモデルがルーブリック採点し、近傍モデルとのペア比較で順位付け
- **導入**：pip install -r requirements.txt → creative_writing_bench.py
- **向いている人・用途**：創作に使うモデルの選定
- **注意点**：LICENSE無し。ジャッジAPI費用


### H. Hugging Face データセット・モデル・Space

#### tori29umai/Qwen-Image-2509-CharacterSheet　〔ランク A｜18/25〕

- **リンク／基本情報**：https://huggingface.co/spaces/tori29umai/Qwen-Image-2509-CharacterSheet　｜　Space（Gradioデモ）　｜　♥240　｜　更新 2025-11-11　｜　ライセンス apache-2.0　｜　ドキュメント言語：英語/日本語
- **成果物**：キャラクターシート画像（設定画）
- **技術・方法**：Qwen-Image-Edit-2509系の画像編集でキャラクターの設定画（キャラクターシート）を生成するデモ
- **導入**：ブラウザでSpaceを開く
- **向いている人・用途**：キャラ設定画のラフ
- **注意点**：生成画像の権利・規約を確認

#### sphiratrioth666/Character_Generation_Templates　〔ランク A｜17/25〕

- **リンク／基本情報**：https://huggingface.co/sphiratrioth666/Character_Generation_Templates　｜　プロンプトテンプレート集（モデルリポジトリ形式）　｜　♥62　｜　更新 2025-08-12　｜　ライセンス cc-by-nc-4.0　｜　ドキュメント言語：英語
- **成果物**：キャラクター生成用テンプレート
- **技術・方法**：LLMにキャラクター設定一式を生成させるための構造化プロンプト
- **導入**：リポジトリのファイルをダウンロードしてプロンプトに使用
- **向いている人・用途**：キャラシートの型
- **注意点**：CC BY-NC 4.0（商用不可）

#### malper/ConlangCrafter　〔ランク A｜17/25〕

- **リンク／基本情報**：https://huggingface.co/datasets/malper/ConlangCrafter　｜　データセット　｜　♥2　｜　更新 2026-01-25　｜　ライセンス cc-by-4.0　｜　ドキュメント言語：英語
- **成果物**：生成済み人工言語64件（音韻・文法・語彙など）
- **技術・方法**：ConlangCrafterの出力サンプル集。言語設定の書式例として参照可能
- **導入**：datasets.load_dataset('malper/ConlangCrafter')
- **向いている人・用途**：架空言語の設定書式の参考

#### sphiratrioth666/Lorebooks_as_ACTIVE_scenario_and_character_guidance_tool　〔ランク B｜16/25〕

- **リンク／基本情報**：https://huggingface.co/sphiratrioth666/Lorebooks_as_ACTIVE_scenario_and_character_guidance_tool　｜　手法解説＋ロアブック例　｜　♥37　｜　更新 2025-01-24　｜　ライセンス cc-by-nc-4.0　｜　ドキュメント言語：英語
- **成果物**：指示を注入する『能動的』ロアブック
- **技術・方法**：ロアブックを設定情報の挿入ではなく、キーワードで『指示』を発火させる手続き的誘導生成（procedural guided generation）に使う手法
- **導入**：SillyTavernにロアブックとして読み込み
- **向いている人・用途**：シナリオ進行の制御
- **注意点**：CC BY-NC 4.0

#### VAST-AI/CharacterGen　〔ランク B｜16/25〕

- **リンク／基本情報**：https://huggingface.co/spaces/VAST-AI/CharacterGen　｜　Space＋研究コード（SIGGRAPH'24）　｜　♥230　｜　更新 2026-02-14　｜　ライセンス apache-2.0　｜　ドキュメント言語：英語
- **成果物**：単一画像からの3Dキャラクター（マルチビュー→3D）
- **技術・方法**：多視点ポーズ補正による3Dキャラ生成。VRMレンダリングスクリプト付属
- **導入**：ブラウザでSpaceを開く
- **向いている人・用途**：キャラの立体確認・ゲーム用素体

#### Aratako/Japanese-Creative-Writing-39.6k　〔ランク B｜16/25〕

- **リンク／基本情報**：https://huggingface.co/datasets/Aratako/Japanese-Creative-Writing-39.6k　｜　データセット（日本語）　｜　♥9　｜　更新 2025-07-04　｜　ライセンス mit　｜　ドキュメント言語：日本語
- **成果物**：日本語の小説執筆タスク約39,600件（2ターン対話）
- **技術・方法**：DeepSeek-V3で作成した日本語創作指示データ。日本語創作モデルのSFTや指示文例の参考に
- **導入**：datasets.load_dataset
- **向いている人・用途**：日本語創作モデルの学習・プロンプト例
- **注意点**：一部NSFWを含む

#### kahuja/flawed-fictions　〔ランク B｜15/25〕

- **リンク／基本情報**：https://huggingface.co/datasets/kahuja/flawed-fictions　｜　データセット（FlawedFictions）　｜　♥4　｜　更新 2025-04-15　｜　ライセンス mit　｜　ドキュメント言語：英語
- **成果物**：矛盾（プロットホール）入り物語と正解ラベル：414件＋長編200件＋陰性例
- **技術・方法**：継続性エラーの有無・説明・該当行・矛盾行を付与。自作の整合性チェッカーやレビュー用LLMの検出力評価に使える
- **導入**：datasets.load_dataset('kahuja/flawed-fictions')
- **向いている人・用途**：継続性チェッカーの評価
- **注意点**：英語のみ

#### lars1234/story_writing_benchmark　〔ランク B｜14/25〕

- **リンク／基本情報**：https://huggingface.co/datasets/lars1234/story_writing_benchmark　｜　データセット　｜　♥6　｜　更新 2025-03-01　｜　ライセンス mit　｜　ドキュメント言語：英語
- **成果物**：多言語で生成された短編と品質評価
- **技術・方法**：LLM生成短編を多言語・多観点で評価したデータ。創作用モデル比較や評価器学習に
- **導入**：datasets.load_dataset
- **向いている人・用途**：モデル選定の参考

#### NousResearch/CharacterCodex　〔ランク B｜14/25〕

- **リンク／基本情報**：https://huggingface.co/datasets/NousResearch/CharacterCodex　｜　データセット　｜　♥256　｜　更新 2024-06-17　｜　ライセンス apache-2.0　｜　ドキュメント言語：英語
- **成果物**：多様なメディアの人気キャラクターの詳細情報と、各キャラ固有のシナリオ
- **技術・方法**：キャラクター記述のフォーマット例・few-shot素材として利用可能
- **導入**：datasets.load_dataset('NousResearch/CharacterCodex')
- **向いている人・用途**：キャラシート項目設計の参考
- **注意点**：既存作品キャラ由来（二次利用に注意）

#### Local-Novel-LLM-project/Vecteus-v1　〔ランク B｜13/25〕

- **リンク／基本情報**：https://huggingface.co/Local-Novel-LLM-project/Vecteus-v1　｜　モデル（日本語ローカルLLM）　｜　♥36　｜　更新 2026-02-16　｜　ライセンス apache-2.0　｜　ドキュメント言語：日本語
- **成果物**：日本語小説の生成
- **技術・方法**：日本語の小説生成向けに作られたローカルLLM（Ninja系の兄弟モデルあり）
- **導入**：transformers / GGUF 変換版で実行
- **向いている人・用途**：ローカルで日本語下書きを生成
- **注意点**：新しい大型モデルとの比較を推奨

#### MiniMaxAI/role-play-bench　〔ランク B｜13/25〕

- **リンク／基本情報**：https://huggingface.co/datasets/MiniMaxAI/role-play-bench　｜　ベンチマーク　｜　♥157　｜　更新 2026-01-28　｜　ライセンス apache-2.0　｜　ドキュメント言語：英語/中国語
- **成果物**：ロールプレイエージェント評価（中・英）
- **技術・方法**：『状況的再演（Situated Reenactment）』で没入型ロールプレイ能力を評価
- **導入**：datasets.load_dataset
- **向いている人・用途**：キャラ演技モデルの選定

#### ConicCat/Litbench-Creative-Writing-RM-3B　〔ランク C｜12/25〕

- **リンク／基本情報**：https://huggingface.co/ConicCat/Litbench-Creative-Writing-RM-3B　｜　報酬モデル（Bradley-Terry）　｜　♥4　｜　更新 2025-09-15　｜　ライセンス llama3.2　｜　ドキュメント言語：英語
- **成果物**：草稿の好ましさスコア
- **技術・方法**：LitBench（Reddit WritingPromptsを精選）で学習した創作全体評価の報酬モデル。複数案の自動ランキングに
- **導入**：transformersでロード
- **向いている人・用途**：候補案の一次ふるい
- **注意点**：英語・Llama 3.2ライセンス

#### jondurbin/gutenberg-dpo-v0.1　〔ランク C｜11/25〕

- **リンク／基本情報**：https://huggingface.co/datasets/jondurbin/gutenberg-dpo-v0.1　｜　データセット（DPO）　｜　♥173　｜　更新 2024-01-12　｜　ライセンス cc-by-4.0　｜　ドキュメント言語：英語
- **成果物**：Project Gutenberg章原文（選好）とLLM生成文（非選好）のペア
- **技術・方法**：パブリックドメイン小説を章分割し、要約プロンプトから生成した文と比較する選好データ。小説的文体へのチューニング用
- **導入**：datasets.load_dataset
- **向いている人・用途**：創作モデルの微調整
- **注意点**：英語・学習用途

#### VatsaDev/worldbuild　〔ランク C｜10/25〕

- **リンク／基本情報**：https://huggingface.co/datasets/VatsaDev/worldbuild　｜　データセット　｜　♥13　｜　更新 2024-01-09　｜　ライセンス mit　｜　ドキュメント言語：英語
- **成果物**：Worldbuilding StackExchangeの質問約18,000件＋ロールプレイデータ
- **技術・方法**：ワールドビルディングQ&Aを中心にしたコーパス
- **導入**：dataset.jsonl を直接取得
- **向いている人・用途**：世界設定Q&Aの事例集
- **注意点**：元データのライセンス（CC BY-SA）に注意

#### jukofyork/creative-writing-control-vectors-v3.0　〔ランク C｜10/25〕

- **リンク／基本情報**：https://huggingface.co/jukofyork/creative-writing-control-vectors-v3.0　｜　コントロールベクトル（GGUF, llama.cpp用）　｜　♥63　｜　更新 2025-03-17　｜　ライセンス apache-2.0　｜　ドキュメント言語：英語
- **成果物**：文体・語り・トーン傾向を操作したローカルモデル出力
- **技術・方法**：事前生成済みの制御ベクトルでモデルの出力傾向を軸ごとに押し引きする
- **導入**：llama.cpp の --control-vector で適用
- **向いている人・用途**：ローカルモデルの文体調整
- **注意点**：対応モデル限定・上級者向け


### I. メタ情報源（キュレーションリスト）

#### UnderleveledBuilder/awesome-story-skills　〔ランク REF｜17/25〕

- **リンク／基本情報**：https://github.com/UnderleveledBuilder/awesome-story-skills　｜　キュレーションリスト（819件）＋catalog.json＋METHODS.md＋選定用Skill　｜　★3　｜　更新 2026-10-19　｜　ライセンス CC0-1.0　｜　ドキュメント言語：中国語/英語
- **成果物**：方法別・ジャンル別の索引、機械可読カタログ、手法ガイド
- **技術・方法**：12の方法タグ（規劃先行・叙事理論・設定/世界観・人物・長編記憶・多エージェント・シミュレーション・審稿・文体学習・去AI味・交互共創・事実制約）で分類。storytelling-methods スキルに『○○を書きたいので方法を選んで』と頼める
- **導入**：npx skills add UnderleveledBuilder/awesome-story-skills
- **向いている人・用途**：本カタログの外側を探索する起点
- **注意点**：中国語中心

#### Picrew/awesome-llm-story-generation　〔ランク REF｜15/25〕

- **リンク／基本情報**：https://github.com/Picrew/awesome-llm-story-generation　｜　論文・OSSリスト（302件）　｜　★117　｜　更新 2026-10-07　｜　ライセンス なし/不明　｜　ドキュメント言語：英語/中国語
- **成果物**：計画・エージェント協調・サンドボックス/世界シミュレーション・記憶・一貫性・評価等10分類の索引
- **技術・方法**：リンク検証付きの研究リスト
- **導入**：閲覧のみ
- **向いている人・用途**：手法の学術的背景を調べる

#### yingpengma/Awesome-Story-Generation　〔ランク REF｜15/25〕

- **リンク／基本情報**：https://github.com/yingpengma/Awesome-Story-Generation　｜　論文リスト（199本）　｜　★668　｜　更新 2026-10-19　｜　ライセンス CC-BY-4.0　｜　ドキュメント言語：英語
- **成果物**：必読マーク・一行要約付きの論文索引（長編・脚本・ゲーム・物語世界モデル・評価・共創）
- **技術・方法**：MoPS著者らによる維持
- **導入**：閲覧のみ
- **向いている人・用途**：研究動向の把握

---

## 5. 目的別レシピ（組み合わせ例）

### 5.1 日本語の長編Web小説・ライトノベル
1. **設計**：`claude-novel-workflow` の templates で canon・人物バイブル・世界バイブル・用語集・年表・文体・禁止パターンを作る（数日かける前提）
2. **構造**：`screenwriting-skills`（日本語で質問可）で構成とシリーズ・エンジンを詰め、`writers-room-story-engine` で因果ビートを点検する
3. **執筆運用**：`story-skills` の継続性チェック、または `inkos` の truth files 方式で章ごとに監査→書き戻しを行う
4. **推敲**：`sepia` で構造面のAI臭を診断し、作者が推敲する（`claude-novel-workflow` の AI草稿⇔推敲版の比較が参考になる）

### 5.2 ファンタジー世界の設定資料集（地理・歴史・言語・暦）
1. 地図：`Azgaar FMG`（国家・文化・宗教の分布）→ 巻頭地図の仕上げに `Nortantis`
2. 歴史：`Minerva`／`Neighborly` で出来事ログ → LLMで叙述化 → `Timelines Studio` で年表化
3. 言語：`ConlangCrafter` で種族・国家ごとの言語スケッチと命名規則
4. 暦：`Fantasy-Calendar` または `Calendarium`
5. 集約：`hivemind`（Obsidian）または `Loreum` に入れ、MCPで執筆エージェントから参照する。自律的に広げたい場合は `skills-world-building`

### 5.3 TRPGキャンペーン
`Kanka`／`WorldAnvil MCP` で世界を管理し、`loremaester` でソースブックPDFとVaultを横断検索してNPC・セッション・年代記を作成。地図は Azgaar（Foundry VTT 連携エコシステムあり）。

### 5.4 キャラクター設定・キャラクターIP
`Calliope character-card-builder`（質問形式で作成）→ `haowjy character-sim`（声と関係の検証）→ `reverse-character-cards`（原稿との突合）。ビジュアルは `Qwen-Image CharacterSheet` でラフを作り、IP展開は `character-ip-design`。

### 5.5 脚本・連続ドラマ
`screenwriting-skills`（シリーズバイブル、ライターズルーム）＋ 階層展開の参考として `Dramatron`。

### 5.6 ゲーム・インタラクティブ作品
`Viv`（創発的物語＋ストーリー・シフティング）、`OpenStory`（WorldKernel）、`chasm`（Markdownファイル群を世界として扱うテキストアドベンチャー）、`lorebook-creator`＋SillyTavern。

---

## 6. 導入時の注意

- **ライセンス**：LICENSEファイルがないリポジトリ（本カタログの「なし/不明」）は、著作権法上は全権利留保です。改変・再配布・商用利用の前に作者に確認してください。AGPL/GPL のアプリは、改変して公開・サービス提供する場合にソース公開義務があります。Viv は商用利用に別ライセンスが必要です。
- **既存作品の扱い**：Fandom Wiki からのロアブック化（lorecard）、既存作品からの文体・人物の蒸留（wenfeng-skill、novel-distiller）、既存キャラのデータセット（CharacterCodex）は、私的な研究・学習の範囲を超えると権利侵害のおそれがあります。
- **スキルに付属するスクリプト**：Agent Skills は Python・シェルスクリプトを実行することがあります。導入前に中身を読んでください（awesome-story-skills も同じ注意を明記しています）。
- **コスト**：多エージェント構成や自律ループ（autonovel、inkos、haowjy）はトークン消費が大きくなります。予算上限を設定できるツール（AI-Novel-Writing-Assistant など）もあります。
- **NSFWと広告**：Hugging Face の創作系データには NSFW を含むものが多くあります（収録分は注意点に明記）。中国語圏の一部リポジトリには API 中継サービスの広告が含まれます。
- **数値の鮮度**：スター数・更新日は 2026-10-23 時点の値です。この分野は変化が速いため、`data/catalog.jsonl` の URL から最新の状態を確認してください。

---

## 7. 付録：同梱データ（JSONL）の仕様

### 7.1 `data/sources.jsonl`（使用した情報源のメタデータ、231件）
| フィールド | 説明 |
|---|---|
| source_id | 連番ID（SRC-0001…） |
| source_type | `api_search_query`（APIの検索クエリ）／`web_search_query`・`web_search_result`／`secondary_catalog`（二次カタログ）／`primary_repository`・`primary_hf_item`（一次情報源）／`verification_file`（裏付けに使った個別ファイル） |
| platform, url, title, query | 取得元、URL（APIエンドポイント含む）、表題、検索語 |
| retrieval_method, retrieved_at | 取得方法（API、git clone、HTTP GET）、取得日 |
| stars / forks / likes / downloads_30d, license, created_at, last_updated, archived | 一次情報源の指標 |
| inspected | 一次確認の結果（ファイル数、SKILL.md 数、プラグインマニフェスト・MCP関連ファイルの有無、README を読んだか） |
| used_in_catalog, catalog_id, used_for | カタログとの対応、用途 |

### 7.2 `data/catalog.jsonl`（選定79件）
`catalog_id, name, url, platform, category_code, category, subtags, format, deliverables, techniques, install, best_for, caveats, documentation_language, scores{5軸}, score_total, rank, stars/likes, license, created_at, last_pushed_at/last_modified, inspection, cross_reference_awesome_story_skills` など

### 7.3 `data/candidates_screened.jsonl`（スクリーニング候補1,741件）
検索でヒットした全候補（`selected` が true なら採用）。再現と追加調査のために残しています。

---
*本レポートは公開リポジトリの記述と構成の確認にもとづく調査で、各ツールの執筆品質を実測したものではありません。*
