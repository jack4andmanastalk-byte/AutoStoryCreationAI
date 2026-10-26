# 二段階方式 第1段階：外部候補の比較と現行実装の独立点検

- 日付: 2026-10-26
- 基準: `main` = `origin/main` = `ce596e8d1e0c72953adbe4e9ed50609b8b73da54`（PR #46 マージコミット）。作業ブランチ `arena/938a6399-autostorycreationai`。
- 前提文書: [`two_stage_next_steps_2026-10-26.md`](two_stage_next_steps_2026-10-26.md) §5 の資料一式、[`docs/two_stage_slice.md`](../../docs/two_stage_slice.md)、[`experiments/2026-10-trpg-slice-t01/`](../../experiments/2026-10-trpg-slice-t01/note.md)
- 点検用スクリプト: [`scripts/probe_gamelog_contracts.py`](../../scripts/probe_gamelog_contracts.py)（読み取り専用。実装は一切変更しない）

## 1. 何をしたか／していないか

今回の作業は**調査と点検だけ**である。次の 3 点を成果物とする。

1. 外部候補 5 件の比較表（一次資料・確認日・コミット・ライセンス 4 分類つき）
2. 現行実装の「契約文が主張する検査能力」と「コードが実際に保証する内容」のギャップ一覧（再現例つき）
3. 試走前に必要な最小修正の優先順位と、Stage B 単独試走 → 全工程試走の手順案

**していないこと**: エンジン導入、依存追加、スキーマ・検査器の変更、実モデルの呼び出し、Arena リレー、効果測定。
実モデルの応答・スコア・効果は一切生成しておらず、以下に数値として現れるのは**固定台本（`scripted`）と、コミット済み入力のメモリ上変異に対する決定論的検査器の出力**だけである。

評価上の位置づけは従来どおり。

- L1 は構造・衛生の検査であり、物語の質・面白さ・読者選好の証拠ではない。
- **L2/L3 と G3/G4 は `frozen_not_measured` を維持**する。未達とも合格とも記録しない。
- 版を固定できない Arena 経路で G5 を主張しない。protocol-v1 の系（S0–S3）・指標・閾値は変更しない。
- **自動検査が `clean` を返すことを意味的整合性の保証として扱わない。** §4 は、まさにその差の一覧である。

## 2. 手続き

### 2.1 事前確認（2026-10-26）

| 確認項目 | 結果 |
| --- | --- |
| `origin/main` | `ce596e8`（PR #46 のマージコミット）。作業ブランチはこれを基点とする |
| PR #46 | `MERGED`（2026-10-26T09:05:28Z）。Phase 1–2 の実装・固定台本バンドル・文書を含む |
| テスト | `.venv/bin/python -m pytest tests -q` → **615 passed, 3 warnings**（既存の fpdf2 A5 警告のみ）。文書記載と一致。本稿と点検スクリプトの追加後にも再実行して同じ結果 |
| 研究カタログ | `python3 scripts/build_research_catalog.py --check` → `catalog is up to date` |
| 環境 | リポジトリに `.venv` が無かったため `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` で作成（`PyYAML` が無いと `asc.evaluation` の import が失敗する） |

### 2.2 点検の方法

1. **契約文の所在を特定**する: `docs/two_stage_slice.md` の §5・§6 の表、`check.py` / `rewrite.py` の `CHECKS` 定数の `acceptance_ja`、`run_twostage.py` の docstring。
2. **コードの実経路を読む**: 各検査関数が実際に読むフィールド、走査するオブジェクト、出力する severity。
3. **コミット済み入力の変異で確かめる**: `experiments/2026-10-trpg-slice-t01/inputs/` をメモリ上で書き換え、`check_game_log` / `check_rewrite` / `--resume` の出力を見る（[`scripts/probe_gamelog_contracts.py`](../../scripts/probe_gamelog_contracts.py)）。
4. **テストが何を固定しているか**を確認し、テストの存在を契約の正しさの根拠にしない。

変異プローブは**実装の欠陥を「期待される失敗」として固定しない**ため、テストには入れていない。代わりに読み取り専用スクリプトとして残し、次セッションが同じ手順を再実行できるようにした。

```bash
.venv/bin/python scripts/probe_gamelog_contracts.py             # Stage A / B の変異
.venv/bin/python scripts/probe_gamelog_contracts.py --only b    # Stage B のみ
.venv/bin/python scripts/probe_gamelog_contracts.py --include-resume   # 再開と記録保全（experiments/_probe-contracts-<pid>/ を一時使用し削除）
```

### 2.3 この方法の限界

- 変異は「検査器が何を見ていないか」を示すが、**実モデルが実際にその誤りを犯す頻度**は示さない。
- 逆に、変異で `unresolved` になった項目（A4・A5・A9・A10）は「検出できる」ことの確認にすぎず、実応答での検出率の証拠ではない。
- 一次資料は 2026-10-26 時点の公開情報で、法務判断ではない。ライセンスは**コード／ルール本文／データ／モデル**を分けて記載したが、最終判断は利用者側の確認を要する。

---

## 3. A. 外部候補の比較

### 3.1 調査方法

- GitHub REST API（`api.github.com`）でリポジトリの `license`・既定ブランチの最新コミット SHA・ルート構成を取得。
- ライセンス本文・README・データファイルは同 API の raw 取得で確認（2026-10-26）。
- npm registry でパッケージ単位の `license` を確認（Datasworn のサブパッケージ）。
- Ironsworn の権利者ページ（Tomkin Press）を直接取得して、リポジトリ内の表示と突き合わせた。
- 予備候補（Datasworn/Ironsworn、Dramatron、ink）は**採用済みではない**。以下は「何を借りられるか」の確認であって、導入決定ではない。

### 3.2 比較表（概要・借りる層・判定）

| # | 候補 | 一次資料（確認日 2026-10-26） | 解決する問題 | 解決しない問題 | 借りる層 | 判定 |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | **Datasworn / Ironsworn**（`rsek/datasworn`） | `https://github.com/rsek/datasworn` / commit `0e995ed485d7f6bf56e30342a4b91b8348282b4c`（2024-06-17） | ムーブの判定結果（strong hit / weak hit / miss）と**オラクル表の JSON 表現**（`dice: "1d100"`＋`rows[{min,max,text}]`）。「行動 → 結果／代償」を機械可読に持つ先例 | 散文の整合性、人物別知識、時系列の検査は持たない。GM 進行の手続き（フェイズ管理）も持たない | データ形式とオラクル設計の**考え方**のみ。表の本文は取り込まない | **見送り（形式のみ参考）**。ライセンス条件が層で分かれ、MIT リポジトリに本文を取り込めない |
| C2 | **Dramatron**（`google-deepmind/dramatron`） | `https://github.com/google-deepmind/dramatron` / commit `2e7c36afadacf8321b77a468940024371b7a8c7a`（2024-07-16） | 階層生成の**受け渡し順序**（logline → 人物記述 → プロット点 → 場所 → 台詞。README の記載） | 検査器・状態管理・再現手順は無い。実体は単一 notebook（`colab/dramatron.ipynb`、約 176 KB）で、`sample()` と `__init__` を自分で実装しないと動かない（README に明記） | **設計の参照のみ**（コード・プロンプト文は取り込まない） | **部分参考（設計）**。今回の Stage A/B 分離の根拠づけには使えるが、導入する部品は無い |
| C3 | **ink**（`inkle/ink`） | `https://github.com/inkle/ink` / commit `35c63e52f1d36060930dc7ed3cfba38ea224b528`（v1.2.1, 2026-05-05） | 状態変数・条件分岐・訪問回数・リストによる**状態付きナラティブの表現**（`Documentation/WritingWithInk.md` の Part 3「Variables and Logic」、Part 5「Advanced State Tracking」） | 生成はしない（オーサリング言語とランタイム）。LLM 連携も検査も無い。散文の事実保持は対象外 | 状態表現の**語彙と考え方**のみ | **見送り**。直線的な 1 章 1 場面スライスにランタイム（C#/JS）を入れる必然性が無い |
| C4 | **Re3**（`yangkevin2/emnlp22-re3-story-generation`） | `https://github.com/yangkevin2/emnlp22-re3-story-generation` / commit `3a97ebde04e3333962c2825146897efe1dc87dd8`（2022-12-21） | 長文生成の**Plan → Draft → Rewrite → Edit** 分割（`story_generation/{plan,draft,rewrite,edit}_module/`）と、整合性を reranker で選ぶ発想 | 決定論的な状態検査ではなく、判定は学習済み分類器。人物別知識境界・現在地・生死の型は持たない | **構成の参照のみ** | **見送り（参考）**。判定器を確率的モデルに置く方針は現行の L1-only 運用と噛み合わない |
| C5 | **Generative Agents**（`joonspk-research/generative_agents`） | `https://github.com/joonspk-research/generative_agents` / commit `fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4`（2023-08-11） | **人物ごとの記憶**という単位の持ち方。`reverie/backend_server/persona/` に人物別モジュールを置く構成（ディレクトリ構成のみ確認。記憶の内部設計は未確認） | 物語の設計・伏線・章立ては対象外。散文の品質評価もしない | 人物別知識の**データ構造の考え方**のみ | **部分参考（設計）**。今回の「人物別知識境界」の検査設計の参照先になるが、コードは取り込まない |

> C1 は「予備候補」として挙げられていた Datasworn/Ironsworn を 1 行にまとめた。C2・C3 も予備候補。C4・C5 は今回の点検で不足が見えた部品（長文の段階分割／人物別知識）から追加で探した候補で、**採用検討の対象であって採用ではない**。

### 3.3 ライセンスの 4 分類（コード／ルール本文／データ／モデル）

| # | コード | ルール本文（表現） | データ（表・JSON 等） | モデル／重み | 帰属・条件 |
| --- | --- | --- | --- | --- | --- |
| C1 Datasworn | 型定義・JSON Schema・内部ツールは **MIT**（README「Core package content (the typings and JSON schema) and internal tooling use the MIT license」、npm `@datasworn/core` の `license: MIT`） | **層で分かれる**。README は「Textual and image content … is CC-BY-4.0 or CC-BY-NC-4.0」。権利者ページは *Ironsworn* 完全版テキストを **CC BY-NC-SA 4.0**（非商用）、商用利用は **SRD・アセットカード・オラクル表が CC BY 4.0** と明記 | 各 JSON のトップレベル `license` フィールド。`datasworn/classic/classic.json` は `https://creativecommons.org/licenses/by/4.0`、`datasworn/starforged/starforged.json` は同 `by/4.0`、`datasworn/delve/delve.json` も同 `by/4.0`。npm `@datasworn/ironsworn-classic` は `CC-BY-4.0` | なし（表データのみ） | クレジット文の指定あり（"This work is based on &lt;game titles&gt;, created by Shawn Tomkin, and licensed …"）。画像・アイコン・トレードドレスは対象外と明記 |
| C2 Dramatron | **Apache-2.0**（リポジトリ `LICENSE`、README「All software is licensed under the Apache License, Version 2.0」） | README の「All other materials」= **CC-BY-4.0**（notebook 内プロンプト文・文書を含むと読める） | なし | 同梱なし。Colab は「unplugged」で、利用者が自前の LLM を接続する | Apache-2.0 の NOTICE 慣行。CC-BY は帰属表示 |
| C3 ink | **MIT**（`LICENSE.txt`、Copyright (c) 2025 inkle Ltd.） | リポジトリ内 `Documentation/*.md` はリポジトリのライセンス下（個別表示は無し）。**ink で書かれた作品の権利は著者側**で、リポジトリのライセンス対象ではない | なし | なし（ランタイムとコンパイラ） | MIT の著作権表示。inkle のロゴ・トレードマークは対象外 |
| C4 Re3 | **MIT**（`LICENSE`） | 論文（arXiv 2210.06774）は別著作物 | 学習・評価データは S3 の配布物で、**README にライセンス条項の記載がない（未確認）**。WritingPrompts 由来 | GPT-3 API と `allenai/longformer-base-4096`（別途 Apache-2.0）。**重みの再配布なし** | MIT。データの条項は別途確認が必要 |
| C5 Generative Agents | **Apache-2.0**（`LICENSE`） | 論文（arXiv 2304.03442）は別著作物 | 同梱のシミュレーション保存データの条項は**未確認**（`environment/` 配下の圧縮ストレージ） | なし。OpenAI API キーを自前で用意する構成 | Apache-2.0 |

**Ironsworn のライセンスについて確認できた緊張関係（重要）**: 同一の Ironsworn 素材に対して 3 つの表示が一致しない。

1. Datasworn README: 「CC-BY-4.0 or CC-BY-NC-4.0」
2. Datasworn の各 JSON の `license` フィールド: `by/4.0`（＝商用も可）
3. 権利者ページ（`https://tomkinpress.com/pages/licensing`、2026-10-26 取得）: 完全版テキストは非商用 **BY-NC-SA 4.0**、商用は **SRD＋アセットカード＋オラクル表のみ BY 4.0**

→ **リポジトリ内の `license` フィールドを権利者条件の代用にしない。** 本リポジトリは MIT（`LICENSE`）であり、BY-NC-SA の本文を取り込むとライセンス非互換になる。今回の結論は「**表・本文は取り込まない。形式と設計だけを参考にする**」である。将来 `game_log.json` にオラクルを入れる場合も、**自前で書いた最小の表**を使い、Ironsworn 由来の文面をコピーしない。

### 3.4 接続コストと最小実行例

| # | 現行 canon / `game_log.json` への接続 | 依存 | 最小実行例 | 今回の判断 |
| --- | --- | --- | --- | --- |
| C1 | `state_delta` に「判定結果（成功/代償）」の型が無い。足すなら `outcome` の列挙値追加から。オラクルは `foreshadow` とは別チャネルが要る | `@datasworn/*` は npm（JS/TS）。Python 側は JSON を読むだけなら依存追加不要 | 表を JSON として読むだけなら 10 行程度。ただし**ライセンス上、本文を持ち込めない** | 今は導入しない。代償・失敗の型が要る段階で、**自前の最小表**を設計する |
| C2 | Stage A のプロンプト構成（設計 → ログ）と発想が近い。取り入れるなら「段の順序」だけ（段間で何を渡すかの詳細は未確認） | Python／Jupyter のみ（コードは持ち込まない） | 参照のみ | 設計の参照として記録。導入しない |
| C3 | 分岐を入れる段階（Phase 3 以降）で、状態の表現を参照 | C#/JS ランタイム（Python からは不可） | 参照のみ | 今は不要 |
| C4 | 既存の `stage-a-repair`／`stage-b-repair` が「Rewrite 相当」を既に持つ。Edit に相当する工程は未実装 | 重い（PyTorch・reranker・API） | 導入しない | 段階分割の比較対象として記録 |
| C5 | 人物別知識（`canon.characters[].knows` と `learn`）の**構造**の参照先。現行の `knows`＋時系列は既に同種の考え方 | なし（読むだけ） | 参照のみ | 検査設計の参照として記録 |

### 3.5 この節の結論

- 5 件とも**今回の試走を止める理由にも、先に導入すべき部品にもならない**。第1段階で必要だったのは「不足する部品の名前」であり、それは (a) 行動→結果／代償の型、(b) 人物別記憶の単位、(c) 段階分割の順序、として整理できた。
- ライセンス面で即断できないのは C1 のみ。**コード（MIT）・ルール本文（BY-NC-SA / BY）・データ（JSON ごとに `license`）・モデル（無し）を分けたまま扱う**必要がある。
- 「もっとも簡単な TRPG を入れる」方向は採らない。現行の `game_log.json` は既に B5（状況→行動→結果）と B2（シーン制）の最小形を持っており、外部ルールの導入は**検査できない状態変数を増やす**方向に働きやすい。

---

## 4. B. 現行実装のギャップ一覧

### 4.1 読み方

- **契約**: 文書・docstring・`acceptance_ja` が読者に約束している内容（引用箇所つき）。
- **コードの実際**: 実際に読むフィールドと severity。
- **再現**: プローブ ID（`scripts/probe_gamelog_contracts.py` の出力）またはコマンド。
- **分類**: `試走前必須`／`全工程試走前`／`後回し`／`仕様上の制限`。
- 「テストがある」ことは「契約が満たされている」ことの根拠にしない。実際、以下の多くは `615 passed` のまま成立している。

### 4.2 一覧表

件数は **27 件**（Stage A 10・Stage B 9・再開と記録保全 8）。**この表は点検時点の記録**であり、P0 は §9、P1 は §11 で修正済み。以下の「コードの実際」は修正前の挙動を指す。

#### Stage A（`check_game_log`）

| ID | 契約（引用） | コードの実際 | 再現 | 影響 | 分類 |
| --- | --- | --- | --- | --- | --- |
| A-01 | 「章・場面順序」（[`two_stage_next_steps`](two_stage_next_steps_2026-10-26.md) §3 B） | `_check_schema_shape` は**場面** ID の重複だけを見る。章 ID の重複は名指しで報告しない。`_check_timeline_travel` は canon 順にソートしてから比較するため、ログの並び順そのものは検査しない | A9（逆順）→ 章順の違反としては報告されず、`foreshadow_order` の「回収が設置より前」など**別の所見として現れる**。A10（章の複製）→ `schema_shape` は「場面 ID g01 が重複」とだけ言う | 章順の誤りが原因と分からない所見になり、修復プロンプトが的外れになる | 全工程試走前（安価） |
| A-02 | 場面の `day` / `location` を schema が受理する（`schema.py` の `Scene.day` / `Scene.location`） | パースはするが**どの検査も参照しない**（`check.py` 全体で `scene.day` / `scene.location` の利用なし） | A11（場面 `location: "港"`, `day: 99`）→ `clean` | 場面単位の移動・日内進行を書いても検証されない。「章内移動なし」という制限が**書けるのに検査されない**形で残る | 後回し（または schema から削除） |
| A-03 | 「厳密ローダー。malformed structure raises `GameLogError`」（`schema.py` の docstring） | 型の誤りは拒否するが、**未知キーは黙って捨てる**（`row.get(key)` 方式） | A8（`present_character`, `state_delta.learn`）→ `clean` | 実モデルの綴り誤りが「検査を弱める」方向に働く。`state_delta.learn` と書かれた学習はマーカーにも知識境界にも現れない | 全工程試走前（安価） |
| A-04 | 「人物の現在地・移動の継続性」（next_steps §3 B）／README §4.4「現在地」 | `canon` の `Character.location` を**一度も読まない**。`location_moves` は `travel_days` との日数比較と、章 day との前後比較だけ。移動の起点が当人の実際の位置と一致するか、前の移動の到着地と次の出発地が繋がるか、その人物が本当にその章にいるかは見ない | A7（登場しない `celia` の移動だけを宣言）→ `clean` | **現在地の連続性は実質未検査**。章の `location` は年表との一致だけを見るので、「人物が移動していない場所に現れる」を止められない | **全工程試走前（中規模）**。Stage B 単独試走はログ固定なので非該当 |
| A-05 | 「死者が現在時に行動していないか」（`presence_death` の `acceptance_ja`） | 現在時型の検査は (a) `actor` が死者、(b) `actor` が `present_characters` にいない、(c) `target` が死者と**完全一致**、の 3 点のみ。`subject` は現在時型では検査しない。`summary` / `text` の自由記述は走査しない | A1（`summary` に「ヨハンが戸口に立って笑った」）→ `clean`。A2（`target: "ヨハンの潮札"`）→ `clean`。A3（現在時 `action` に `subject: johan`）→ `clean` | **設計の中心（現在時行動と記録言及の型分離）が、自由記述と `target` の部分一致で抜けられる** | **試走前必須**（`subject` の型検査は安価）。自由記述の走査は偽陽性とのトレードオフがあるため「low 報告」から |
| A-06 | 「死者が現在時に…知識を使っていないか」（`presence_death` の趣旨） | `_check_knowledge_boundary` は `learned_facts` の人物が死者なら `high`、`used_facts` には**死者判定が無い** | A4（`johan` の `used_facts`）→ `knowledge_boundary` は「ch02 の場面にいない」`medium` のみ。`high` は `design_alignment` と `emitted_markers` の偶然の所見 | 死者の現在時の知識使用が `high` にならない。`present_characters` に入れれば A-05 で捕まるが、入れなければ `medium` | 全工程試走前（安価） |
| A-07 | 「`use` は `knows` か過去の `learn` の後」（`knowledge_boundary`） | `known` は場面をまたいで蓄積されるが、**同一場面内では `used_facts` を `learned_facts` より先に判定**する | A5（同一場面で `learn F-02` → `use F-02`）→ `high`「まだ知らないのに使っている」 | **実モデルがほぼ確実に出す形の偽陽性**。修復で直らない場合、Stage A が `clean` にならず Stage B が `skipped`（fail-closed）になる | **全工程試走の前に必須**（Stage B 単独試走はログ固定なので非該当） |
| A-08 | 「`scene.json` の目的/対立/変化と照合する」（`design_alignment` の `acceptance_ja` は「学習事実が開示・保留の宣言と矛盾しないこと」） | 設計との照合は **ID・章・`tension`・開示/保留の事実集合・`paid` の有無**だけ。場面の `purpose` / `conflict` / `change` の**文面は一切比較しない**。`schema_shape` は空でないことだけを見る | A6（設計と無関係な目的・対立・変化）→ `clean` | 「設計と実際に照合される範囲」は、文書から読めるより狭い。ログが設計と別の話を書いても通る | **仕様上の制限として明記**。意味照合は L2 相当なので自動化しない。試走では人手の照合項目に入れる |
| A-09 | 「全設計場面の被覆を要求」（`design_alignment`） | 未参照の設計場面・幕・転換点は `medium`。`canon_refs` は canon の全章を要求（`high`） | 既知（[`docs/two_stage_slice.md`](../../docs/two_stage_slice.md) §10） | 共有設計（9 場面）をそのまま使うと全工程試走が通らない。部分ログを評価できない | 試走設計の制約として扱う（§6.2） |
| A-10 | 「死者の解釈」 | `check.py` は `status_since` が無ければ「物語開始前から死亡」とみなす（`_dead_at`）。既存 `continuity-ledger` は `char.status_since or self.chapters[0].id` で**第1章を死亡章**とみなす（`continuity.py:241-242`） | 固定台本では `johan` に `status_since` が無く、legacy 監査は ch01 の言及を違反にしない（§4.4） | 同じ canon に対して 2 つの検査器が別の解釈をする。ch01 で死者を現在時に動かしても legacy 監査は反応しない | 仕様上の制限として明記＋新規 canon では `status_since` を書く運用 |

#### Stage B（`check_rewrite`）

| ID | 契約（引用） | コードの実際 | 再現 | 影響 | 分類 |
| --- | --- | --- | --- | --- | --- |
| B-01 | 「本文に出る人物が…許容された死者言及だけ」（`character_boundary`） | 許容判定は**章スコープ**。その章のログに 1 件でも `record_reference` があれば、その死者の**すべての言及**を無条件で飛ばす（`rewrite.py:142,149`）。本文中の言及ごとに `medium`（記録・遺物・回想）を要求しない | B1（`johan` の記録言及がある章に「ヨハンが戸口から入ってきて肩を叩いた」を追加）→ `clean` | **Stage B の中心的保証（現在時行動の排除）が、記録言及 1 件で無効化される。** 実応答ではこの形の混入が最も起きやすい | **試走前必須**。最小修正案: 言及ごとに、その名前を含む段落内に宣言済み `medium` の文字列があることを要求し、無ければ `high` |
| B-02 | 「名前・別名の文字列一致」（`character_boundary` の `limits_ja`） | `len(name) >= 2` の名前だけを走査（`rewrite.py:136`） | B6（canon の別名「兄」を現在時の行動主にする）→ `clean`。固定台本 ch01 の「兄の名を…」も同じ理由で走査されない（こちらは許容される言及だが、区別はされていない） | 1 文字の別名（兄・父）は検出されない。逆に 2 文字の一般名詞（灯守・鍵屋）は偽陽性源 | 仕様上の制限＋canon 運用（別名は 2 文字以上にする、または走査対象を別名と明示） |
| B-03 | 「本文に出る人物が…だけである」 | 走査は `canon.characters` の**既知の人物のみ**。canon にない人物名・場所・出来事を検出しない | B2（「マルタという女」）→ `clean`。B5（「港の桟橋」「船で対岸へ」）→ `clean` | 本文がログにない人物・場所・移動を足しても通る。**`prompts/stage-b-rewrite.md` の契約 2 は既にこれを禁じているが、機械的な強制は無く、プロンプト遵守に依存している** | 仕様上の制限（決定的な検出は不可能）。試走の人手照合項目へ |
| B-04 | 「本文のマーカー列が導出列と完全一致」→ 事実の保持と読まれうる | `marker_sequence` は**マーカーの文字列と順序**だけを見る。本文が事実を否定・省略・改変していても、マーカーが残っていれば `clean` | B3（「王都まで何日かかるかは、どこにも書かれていない」＋`{{learn: aria fact=F-05}}`）→ `clean`。B4（マーカーは残し、事実の記述を削除）→ `clean` | **マーカー保持 ≠ 本文の事実保持。** 検査が通ることは、ログの事実が散文に反映されたことを意味しない | **仕様上の制限。** 試走では章ごとに「ログの出来事→本文の該当箇所」の対応表を人手で作り、検出漏れとして記録する（§6） |
| B-05 | 「未開示の事実の語彙…が現れない」（`fact_boundary`） | `canon.facts[].terms` の部分文字列一致のみ。語彙は人手で列挙した 1〜2 語で、**言い換え・含意・代名詞による言及は対象外** | B3・B4（語彙を使わずに事実を否定／省略）→ `clean`。なお固定台本は「検査器に合わせて書かれた」入力なので、この穴の実例を自分では含まない（ch01 の「鍵は二本ある」は `fs-001` の設置として canon 側に宣言済みで、漏洩ではない） | 語彙一致を「事実が守られた」証拠にできない。`terms` の拡充は偽陽性とのトレードオフ | 仕様上の制限。試走では人手照合で補い、検出漏れを記録する |
| B-06 | 「タスクの必須語」（protocol-v1 の L1 指標） | `run_twostage.py` は `task.avoid` を `voice_contract` で検査するが、`task.must_include` は**検査しない**。`_l1_hygiene` が率を記録するだけ | B7（「灯り」を「明かり」に置換）→ `clean` | 必須語を落とした本文が `clean` になる。S1 との L1 比較で条件差が混ざる | 試走前（安価） |
| B-07 | 「本文が最低長以上」（`voice_contract`） | `MIN_REWRITE_CHARS = 200`（`run_twostage.py:65`）。プロンプトの目標は 1,000〜1,400 字 | 300 字程度の固定台本本文が通る | 長さゲートが実質無効。短文が `clean` になる | 試走条件として明示（下記 §5） |
| B-08 | 人物境界は「その章の」登場人物 | `present` は**章内の全場面の和**（`rewrite.py:124`） | t01 は 1 章 1 場面のため未観測（コード根拠のみ） | 複数場面の章で、後の場面の人物が前の場面に現れても検出されない | 後回し（1 章複数場面を扱う段階で） |
| B-09 | 「人物別の知識境界」 | 本文側は語彙チェックのみで、**誰がその語を口にしたか**を判定しない。人物別の境界は Stage A の `{{use:}}` マーカーに依存 | コード根拠のみ | 本文で別人物が未習得の事実を口にしても、語彙が `terms` に無ければ通る | 仕様上の制限（話者推定は L2 相当） |

#### 再開・記録保全（`run_twostage.py --resume`）

| ID | 契約（`run_twostage.py` docstring／next_steps §4） | コードの実際 | 再現 | 影響 | 分類 |
| --- | --- | --- | --- | --- | --- |
| R-01 | 「`state.json` の `resume_command` を実行する」 | `resume_command` に `--script` / `--command` / `--seed` / `--temperature` / `--max-attempts` / `--results` が入らない（`run_twostage.py:697-700`） | R1 → `rc=2 error: --provider scripted requires --script` | **文書どおりの再開が失敗する。** 実試走は必ず pending を踏むため致命的 | **試走前必須** |
| R-02 | 「回答待ちで exit 3、`--resume` で続行」 | provider の `ProviderError` 時に `state.json` を書かない（`ledger.fail()` は manifest のみ） | R4 → `state.json=False`、`responses.jsonl` 2 行、`--resume` は `rc=2 --resume needs state.json` | 部分的な記録が**再開不能な形で残る**。同じ run-id は作り直せない | **試走前必須** |
| R-03 | 「記録済み応答を再生して続行」 | `--resume` は冒頭で `responses.jsonl` を空にする（`run_twostage.py:552`） | コード根拠（R2/R3 の再開は成功するが、途中失敗時は切り詰め後の内容しか残らない） | 再開の途中失敗で**既存の記録が失われる** | **試走前必須**（完了後に置換する、または別ファイルへ書く） |
| R-04 | 「プロンプトが変わった記録は stale として拒否」 | 照合するのは `prompt_hash` のみ。`config` の比較は 3 つの入力ハッシュだけ（`run_twostage.py:539`）。`task` / `seed` / `temperature` / `max_attempts` / `provider` は比較しない | R3（`--resume --seed 7`）→ `rc=0`、`state.config.seed` が 0→7 に**上書き**、`bundle_resume` された応答 **0/4**（全再要求） | 条件が違う再開が黙って通る。記録済み応答が捨てられ、来歴が混ざる | **試走前必須**（安価。config 全項目を比較し、不一致は拒否） |
| R-05 | 「応答ハッシュで来歴が追える」 | `RunLedger.record` は `response_sha256` を書くが、`BundleProvider` は**照合しない**（`prompt_hash` のみ） | R2（記録本文の「嵐」→「霧」に改変して `--resume`）→ `rc=0` | 記録の改変・取り違えを検出できない。人手編集が「モデル応答」として再生される | 試走前（安価） |
| R-06 | 「自己完結バンドル」 | 入力は `<out>/<run-id>/inputs/` に複製するが、`resume_command` は**バンドル外の `--canon` / `--design-dir`** を指す。`--resume` も外を読む | R1 の `resume_command` に絶対パスで現れる | バンドルを移動・複製しても再開できない。`inputs/` があるのに使わない | 試走前（中） |
| R-07 | 「取り違えを防ぐ」 | `BundleProvider` のキーは `(purpose, attempt, chapter, seed)`。重複キーは後勝ちで、警告しない | コード根拠 | 同じキーの記録が複数あると、どちらが使われたか分からない | 後回し（記録の検査を足すときに併せて） |
| R-08 | pending の提示 | `_write_prompts` は**すべての `*.prompt.txt`** を並べ、未回答は先頭で 1 件だけ示す | コード根拠 | 回答済みプロンプトが未回答に見える。取り違えの温床 | 試走前（表示のみ・安価） |

### 4.3 とくに指定された 6 点への回答

| 指定項目 | 結論 | 根拠 |
| --- | --- | --- |
| 人物の現在地と移動の継続性 | **未検査に近い**。`canon` の `Character.location` は未使用、移動は日数のみ、移動の連結・人物の登場との対応は無い | A-04 / A7 |
| 事実の学習・使用の順序と人物別知識 | Stage A の**場面をまたぐ順序**は検査される。**同一場面の learn→use で偽陽性 high**。**本文側の人物別境界は語彙のみ** | A-07 / B-09 / A5 |
| plot/scene 設計との実際の照合範囲 | ID・章・`tension`・開示/保留集合・`paid` のみ。**目的/対立/変化の文面は非照合**。全設計場面の被覆は要求 | A-08 / A-09 / A6 |
| 死者への記録・回想の言及と現在時行動 | **型はあるが、章スコープの許容で現在時行動が通る**（B-01）。Stage A でも自由記述・`target` 部分一致・`subject` で抜けられる（A-05）。短い別名は不可視（B-02） | B1 / A1-A3 / B6 |
| マーカー保持と本文の事実保持 | **別物**。マーカーが一致しても、事実の否定・省略・言い換えによる漏洩は検出しない（B3・B4 の変異は `clean`）。固定台本が `clean` なのは、台本が検査器に合わせて書かれているためでもある | B-04 / B-05 / B3-B5 |
| pending・再開時の記録保全と自己完結性 | `resume_command` の欠落、失敗時の `state.json` 不在、再開冒頭の切り詰め、config 非照合、`response_sha256` 非照合、バンドル外パス参照 | R-01〜R-06 |

### 4.4 既存監査との関係（誤解を避けるための注記）

- 既存 `continuity-ledger` の `dead_character_reappears`（`name_mention` / `medium`）は、**ch01 の死者言及を違反にしない**。`status_since` が無い死者の死亡章を「第 1 章」とみなすため（`continuity.py:241-242`）。固定台本の 3 件が ch02・ch03 に出るのはこの理由である。
- したがって「Stage B の `character_boundary` は legacy 監査の誤検出を減らした」とは**言えない**。両者は別の規則で動いており、B-01 のとおり Stage B 側は現在時行動を見逃す方向の穴を持つ。**L1 の改善として主張しない。**
- 固定台本の `results.json` にある `continuity.violations = 3`（すべて `medium`）は、上記の既知類型である。今回の点検で新しい測定は行っていない。

### 4.5 テストが固定している範囲（テストの存在を契約の根拠にしない）

`tests/test_gamelog_check.py`（8 件）・`tests/test_gamelog_schema.py`（8 件）・`tests/test_twostage_pipeline.py`（14 件）は、**実装された挙動**を固定している。上記のギャップの多くは、これらのテストが緑のまま成立する。代表例だけ挙げる。

| テスト | 固定していること | 固定していないこと（本節の該当 ID） |
| --- | --- | --- |
| `test_gamelog_check.py::test_dead_present_is_forbidden_but_declared_reference_is_allowed` | 死者が `present_characters` にいれば `high`、宣言済みの `memory_mention` は `allowed_dead_references` に入る | 現在時型の `subject`、`summary` の自由記述、`target` の部分一致（A-05） |
| `test_gamelog_check.py::test_travel_days_are_checked_for_moves_and_between_chapters` | 移動日数と章間日数の算術 | 人物の現在地・移動の連結・実際の登場との対応（A-04） |
| `test_gamelog_schema.py::test_malformed_logs_raise_a_precise_error` | 型の誤りは `GameLogError` | **未知キーは拒否しない**（A-03） |
| `test_twostage_pipeline.py::test_rewrite_check_flags_marker_loss_unlogged_names_and_dead_state_markers` | canon の人物名（`セリア`）の未記録な登場 → `medium`、`{{state: johan …}}` → `high` | canon に**ない**人物（B-03）、記録言及のある章での死者の現在時行動（B-01）、1 文字の別名（B-02） |
| `test_twostage_pipeline.py::test_resume_refuses_changed_inputs` | `canon` / `design` / `script` のハッシュ差は拒否 | `seed` / `temperature` / `max_attempts` / `task` の差（R-04） |
| `test_twostage_pipeline.py::test_pending_operator_response_exports_prompts_into_the_bundle` | `state.json` に `"--resume" in resume_command` があること | **そのコマンドが実行できること**（R-01 のとおり実行できない） |
| `test_twostage_pipeline.py::test_bundle_provider_refuses_a_stale_recorded_response` | `prompt_hash` が変われば委譲先に投げる（＝記録を使わない） | `response_sha256` の照合（R-05）、「stale として報告する」こと（現状は黙って再要求） |

したがって `make ci` の `615 passed` は「検査器が期待どおり動く」ことの確認であり、**本節の穴の不存在の証拠ではない**。プローブ（`make probe-gamelog`）はこの差を再現するために置いている。

---

## 5. C. 試走前に必要な修正と、後回しにするもの

### 5.1 必須（P0）— 修正しないと試走の記録が成立しない

| # | 内容 | 根拠 | 目安 |
| --- | --- | --- | --- |
| P0-1 | `resume_command` に**実行に必要な全引数**を含める（`--script` / `--command` / `--seed` / `--temperature` / `--max-attempts` / `--results`）。加えて `state.json` に `argv` を保存する | R-01 | 小 |
| P0-2 | provider 失敗・例外時に **`state.json` を必ず書く**（`status: failed` + エラー + 次の手順） | R-02 | 小 |
| P0-3 | `--resume` は `responses.jsonl` を**冒頭で切り詰めない**。完了時に置換するか、`responses.replay.jsonl` に分けて書く | R-03 | 小〜中 |
| P0-4 | `--resume` で `task` / `seed` / `temperature` / `max_attempts` / `provider` / `protocol_version` を**比較し、不一致は拒否**する（`--allow-config-change` を明示したときだけ続行） | R-04 | 小 |
| P0-5 | `BundleProvider` で `response_sha256` を**照合**し、不一致は `stale`／`tampered` として停止 | R-05 | 小 |
| P0-6 | Stage B の死者言及許容を**言及単位**に狭める: 名前を含む段落に宣言済み `medium` の文字列があるときだけ許容し、無ければ `high` | B-01 | 中 |
| P0-7 | **Stage B 単独実行の入口**を用意する。現行 `run_twostage.py` は常に Stage A から走るため、「検証済み固定ログから本文だけを実応答で生成」ができない（`stage_a` を台本で固定し `stage_b` だけ実応答にする混合も不可: `--provider` は 1 つ） | 手順上の必須（§6） | 中 |

> P0-7 は「修正」ではなく「試走に必要な機能の欠落」。最小案は `--stage {a,b,both}` と `--game-log <path>` の追加、または `--provider-a` / `--provider-b` の分離。どちらも既存の `state.json`／`results.json` 形式を壊さない範囲で実装できる。

### 5.2 全工程試走の前に必要（P1）

| # | 内容 | 根拠 |
| --- | --- | --- |
| P1-1 | 同一場面の `learn` → `use` を許容する（`used_facts` の判定を、その場面の `learned_facts` を反映した後に行う）。許容した場合は `low` で情報提供 | A-07 / A5 |
| P1-2 | 未知キーを**報告**する（拒否までは不要。`low`〜`medium`）。実モデルの綴り誤りで検査が黙って弱まるのを防ぐ | A-03 / A8 |
| P1-3 | 現在時型でも `subject` を検査する（死者 → `high`、死者でなくても現在時型に `subject` があれば `low` で「型の混同」として報告） | A-05 / A3 |
| P1-4 | 死者の `used_facts` を `high` にする | A-06 / A4 |
| P1-5 | 章 ID の重複を名指しで `high`、ログの章順が canon 順と違う場合を `high`（ソート前の並びで比較） | A-01 / A9・A10 |
| P1-6 | 章ごとの `present_characters` が、canon 初期位置＋宣言された移動から導いた位置と矛盾しないかを検査する（移動の連結も含む） | A-04 / A7 |
| P1-7 | `must_include` を Stage B の検査に含める（`voice_contract` の `medium`） | B-06 / B7 |
| P1-8 | 試走条件として `MIN_REWRITE_CHARS` を上げる（例: 800）か、上げない場合は「長さは評価しない」と `results.json` に明記する | B-07 |
| P1-9 | `_write_prompts` で未回答の 1 件だけを抜き出し、回答済みは折りたたむ | R-08 |

### 5.3 後回し・仕様上の制限として文書に残す（実装しない）

| 内容 | 扱い |
| --- | --- |
| 場面 `day` / `location` の未使用（A-02） | schema から消すか、複数場面対応時に検査を足す。現状は「書けるが検査されない」ので、少なくとも `low` で「未使用」と報告する |
| 設計文の目的/対立/変化との照合（A-08） | 意味照合は L2 相当。自動化しない。試走では人手照合の項目に入れる |
| canon にない人物・場所・出来事（B-03） | 決定的検出は不可能（`person` の総当たりは偽陽性とコストが大きい）。`prompts/stage-b-rewrite.md` の契約 2「ゲームログにない新しい事実・人物の行動・会話・場所・時点・伏線を追加しない」が既に定めているため、**試走では人手照合（§6）で契約の遵守を確認する** |
| 本文の事実の否定・省略・言い換え（B-04/B-05） | 同上。同プロンプトの契約 1・4 が対応する。`terms` は「手掛かり」であり断定ではない、という現行の但し書きを維持し、人手照合で補う |
| 人物別知識の本文側判定（B-09） | 話者推定を含むため L2 相当。凍結方針に合わせて実行しない |
| 1 文字の別名（B-02） | canon 運用で回避（別名は 2 文字以上、または一般名詞を避ける）。走査対象の明示を文書に書く |
| 章内複数場面の人物境界（B-08） | 複数場面対応時に `present_characters` を場面単位で判定する |
| 章を複製したときに同じ所見が二重に出る（A-01 の副次） | 検出はされるが、メッセージが原因（章の複製）を指さない。優先度低 |

### 5.4 修正の順序の提案

1. **P0-1〜P0-5（再開・記録保全）** — 試走は必ず `exit 3` と `--resume` を踏む。ここが壊れていると、実応答が取れても記録が残らない。
2. **P0-7（Stage B 単独の入口）** — 次段の目的そのもの。
3. **P0-6（死者言及の単位）** — 修正しないと「Stage B で現在時行動が出ない」を検証できない。
4. P1-1〜P1-6 を全工程試走の前までに。P1-7〜P1-9 は試走条件として先に決める。

修正は**1 つずつ**行い、そのたびに `make ci` と `scripts/probe_gamelog_contracts.py` の該当 ID が変わることを確認する。プローブは「欠陥の固定」ではなく「修正の観測」に使う。

---

## 6. D. 次の試走手順（提案）

### 6.1 Stage B 単独試走

目的は**素材の十分性・事実保持・検査の検出漏れ／誤検出の切り分け**であり、品質評価ではない。

```text
experiments/2026-11-stageb-t01/          ← 新規。自己完結バンドル
  inputs/canon/                          ← t01 の canon を固定コピー（SHA-256 を state に記録）
  inputs/design/voice.json ほか          ← 設計書も同梱（実検査器の report も含める）
  inputs/game_log.json                   ← Phase 1–2 の検証済みログ（scripted の出力をそのまま）
  relay/                                 ← 実応答（Arena リレー）。回答はここだけに置く
  results.json / note.md                 ← 決定論的要約と限界
```

手順:

1. **P0 修正を適用**し、`make ci` が通ることを確認（修正ごとにプローブを再実行）。
2. 起点 run を作る: `--provider command --command "<chat_operator 経由>" ... --out experiments/2026-11-stageb-t01 --run-id stageb-t01-s0`。
   Stage A は固定ログから**再生**し、Stage B だけ実応答にする（P0-7 の実装による）。
3. `exit 3` で止まったら、`PROMPTS.md`（未回答 1 件のみ）を Arena へ渡し、返答を置いて `--resume` で続行する。回答の置き場所は 2 通り:
   - `scripts/chat_operator.py --dir experiments/<id>/relay` を使う場合: `relay/requests/<key>.json` を読み、`relay/responses/<key>.json` に書く（prompt が変わった回答は exit 4 で stale）。
   - `run_twostage.py` の `pending['response_path']`（provider が指定）に従う場合: `state.json` の `pending` を見て同じパスへ置く。
   **どちらでも、gitignored な `runs/` / `build/` を唯一の置き場にしない。**
   **プロンプトが変わった回答は stale として拒否する**（`chat_operator.py` の exit 4 と同じ規約）。
4. 3 章すべての本文がそろったら、章ごとに次を作る（**人手**・決定論的検査ではない）:
   - ログの各 `action` と、本文の該当箇所の対応表
   - 生死・現在地・知識開示の照合表（誰が、いつ、どこで、何を知ったか）
   - 検出漏れ（検査は `clean` だが対応が取れない箇所）と誤検出（検査が `high`/`medium` だが実際は妥当）の一覧
5. 記録するもの: `responses.jsonl`（プロンプト・応答・ハッシュ）、`rewrite.report.json`、`audit.json`、`results.json`、`note.md`、そして上記の**人手照合表**。
6. **主張しないこと**: 面白さ、S1 との優劣、L1 の改善。1 条件・1 バンドル・版非固定のため、G5 は主張しない。L2/L3・G3/G4 は `frozen_not_measured` のまま。

受入条件（試走を「記録として成立」とみなす条件）:

- 未検証ログが Stage B に渡っていない（`game_log` の検査記録が `clean`）。
- 回答の消失・重複・取り違えが無く、`state.json` から `--resume` が再現できる。
- 実応答と固定台本が `results.json` の `provider` と `provenance` で区別できる。
- 人手照合表があり、検出漏れ／誤検出が件数つきで残っている。

### 6.2 全工程試走

1. 設計は**3 章 3 場面の最小スライス**（t01 の既存 `design/`）を使う。9 場面の共有設計を使う場合は A-09 の制約（全設計場面の被覆要求）を先に解く。
2. 1 件目: Stage A を実応答で実行 → `clean` か、修復回数と所見の型を記録。`clean` になれば同じログで Stage B。
3. 1 件目の失敗型（例: 同一場面 learn→use、未知キー、自由記述の死者行動）に対して**最小修正を 1 つだけ**入れ、2 件目を実行。
4. 比較は「失敗の説明可能性」を優先する。多数生成しない。
5. 3 件目以降（S1 直接生成との L1 ペア比較）は、Stage B の入力差（前章本文を渡さない）を条件として明示したうえで、別の区切りで行う。

### 6.3 観測項目（試走時に記録する表）

| 層 | 項目 | 出所 |
| --- | --- | --- |
| 構造（L1） | Stage A の 8 検査の状態・所見数・修復回数・`first_attempt_findings` | `game_log.report.json` |
| 構造（L1） | 導出マーカー数と種別、Stage B のマーカー一致（欠落／余分／順序差） | `game_log.report.json` / `rewrite.report.json` |
| 構造（L1） | Stage B 4 検査の状態、`must_include` 率、禁止語、文字数 | `rewrite.report.json` / `run-summary.json` |
| 構造（L1） | 既存 `continuity-ledger` の違反型・severity・`checks_skipped`・CED | `audit.json` |
| 意味（人手） | ログの出来事と本文の対応、生死・現在地・知識開示の一致、検出漏れ／誤検出 | 人手照合表（新規） |
| 来歴 | provider / model / model_version / プロンプトハッシュ / 応答ハッシュ / 再開回数 | `manifest.json` / `state.json` |
| 非測定 | L2 / L3 / G3 / G4 / G5 | 記録のみ。`frozen_not_measured` |

---

## 7. 未確認事項（次セッションで確認する）

1. Tomkin Press の背景記事（`https://tomkinpress.com/blogs/news/lets-talk-about-ironsworn-licensing`）は**未読**。ライセンス解釈の参考であって条件本文ではない。
2. `rsek/datasworn` の `package.json` は `SEE LICENSE IN LICENSE.md` を指すが、**リポジトリ直下に `LICENSE.md` は存在しない**（2026-10-26 の contents API で確認）。README と npm メタデータ、各 JSON の `license` を根拠にした。
3. Re3 の配布データ（`emnlp22_re3_data.zip`）の利用条件は README に記載が無く**未確認**。
4. Generative Agents の同梱シミュレーション保存データの条項は**未確認**。
5. Dramatron の notebook 内プロンプト文が CC-BY-4.0 の「All other materials」に含まれるという読みは、README の文面からの**解釈**であり法務判断ではない。
6. ink の `Documentation/*.md` に個別ライセンス表示は無い（リポジトリの MIT に従うと解釈）。inkle の商標・ロゴは対象外。
7. 本稿のライセンス確認は 2026-10-26 時点の公開情報に基づく。将来の変更は反映していない。

## 8. 変更ファイル

| ファイル | 変更 |
| --- | --- |
| `research/curation/two_stage_stage1_audit_2026-10-26.md` | 本稿（新規） |
| `scripts/probe_gamelog_contracts.py` | 点検用の読み取り専用プローブ（新規）。パイプラインの挙動は変えない |
| `docs/two_stage_slice.md` | §11 に本稿への参照と「契約と実装の差」の要約を追加 |
| `README.md` | §4.4 に点検結果への参照を 1 行追加 |
| `docs/protocol.md` | §10 の二段階方式の行に、第1段階の点検結果と未実施事項を追記 |
| `Makefile` | `make probe-gamelog` を追加（プローブの再実行のみ。CI の内容は変えない） |
| `research/curation/two_stage_next_steps_2026-10-26.md` | §1 に本稿への追記（方針文書は変更しない） |

**第1段階の調査時点では実装（`src/asc/gamelog/`、`scripts/run_twostage.py`）を変更していない。** P0 の修正は §9 のスプリントで実施し、P1 は次の作業単位とする。

---

## 9. P0 修正スプリントの実施記録（2026-10-26、同日）

利用者の承認後に P0-1〜P0-7 を実装した。**P1 は未着手**。実モデルは呼び出していない。

### 9.1 何を変えたか

| # | 変更 | コード |
| --- | --- | --- |
| P0-1 | `resume_command` に `--script` / `--command` / `--stage` / `--game-log` / `--seed` / `--temperature` / `--max-attempts` / `--results` を含め、`sys.executable` で起動する。`state.json` に `argv` と `resume_count` を追加 | `scripts/run_twostage.py: _resume_command` |
| P0-2 | provider 失敗・入力不合格でも `state.json` を書く（`status: failed` / `unresolved`、`error` つき） | `_write_state` |
| P0-3 | `--resume` は `responses.jsonl` を空にしない。既存の行を一時ファイルへ書き、`os.replace` で置き換えてから追記する | `main` の resume ブロック |
| P0-4 | `CONFIG_COMPARE`（task / system / stage / seed / temperature / max_attempts / provider / protocol_version）と `INPUT_COMPARE`（canon・design・script・game-log・プロンプトのハッシュ）を比較し、不一致は `exit 2`。`--allow-config-change` で続行し、差分を `config_changes` に残す | `_config_mismatches` |
| P0-5 | `BundleProvider` が `response_sha256` を照合。不一致は `ReplayError` で停止。再生した応答は `responses.jsonl` に二重追記しない。`replay.report.json` に `replayed` / `stale` / `missing` と重複キーを残す | `BundleProvider` / `_record_once` |
| P0-6 | 死者言及を**文スコープ**で判定。名前を含む文に、宣言済み媒体の語（完全一致＋2 文字の部分語）か参照の語彙（`REFERENCE_CUES`）がある場合だけ許容する。無ければ `high` | `src/asc/gamelog/rewrite.py: _mentions_without_medium` |
| P0-7 | `--stage both|a|b` と `--game-log` を追加。`--stage b` は Stage A を実行せず、与えたログを `check_game_log` で再検査し、`clean` のときだけ Stage B へ渡す。不合格は `exit 2`（`--allow-unverified-log` で続行可、`unverified: true` を残す）。入力ログは `inputs/game_log.input.json` に固定コピー | `main` / `_write_state` |

`results.json` は `inputs` に `game_log_sha256` が加わったため再生成した（他は不変、`test_committed_bundle_summary_is_reproducible` が固定）。

### 9.2 確認したこと（テスト 9 件を追加、計 624 passed）

| 契約 | テスト | プローブ |
| --- | --- | --- |
| `resume_command` がそのまま実行できる | `test_resume_command_is_complete_and_executable` | R1 → rc=0, `resume_count=1` |
| provider 失敗後も再開できる | `test_a_provider_failure_still_writes_resumable_state` | R4 → `state.json` あり, 記録 2 行保持 |
| 再開で記録が消えない・二重にならない | `test_resume_keeps_the_record_and_replays_without_duplicating` | — |
| 条件を変えた再開は拒否、明示時のみ続行 | `test_resume_with_a_different_seed_is_refused_and_can_be_allowed` | R3 → rc=2 / `--allow-config-change` で rc=0 |
| 改変された記録は再生しない | `test_a_modified_recorded_response_is_refused` | R2 → rc=2（`response_sha256` 不一致） |
| Stage B 単独が Stage A を呼ばない | `test_stage_b_only_rewrites_a_verified_log_without_calling_stage_a` | — |
| 不合格ログは fail-closed、明示時のみ続行 | `test_stage_b_only_refuses_a_log_that_fails_its_checks` | — |
| 引数の矛盾を拒否、`--stage a` は B を skip | `test_stage_selection_rejects_contradictory_arguments` | — |
| 死者の現在時行動は媒体語のない文で `high` | `test_dead_mention_needs_its_medium_in_the_same_sentence` | B1 → `high` |

固定台本（`scripted`）の結果は不変: Stage A `clean`（3 章 3 場面・8 検査 0 所見・マーカー 19 件）、Stage B 3 章 `clean`、既存監査の違反 3 件（`medium`）。

### 9.3 P0-6 の残る限界（重要）

文スコープの判定は**語彙による近似**であり、次の形は通る。

- 「ヨハンが潮札を革袋に入れた」— 媒体語と同じ文で死者が行為する。
- 「ヨハンが入ってきた」+ 同じ文に「思い出」等の語彙がある場合。
- 1 文字の別名（`兄`）だけの言及（B-02、変更なし）。

したがって「死者の現在時行動を検出できる」とは主張しない。**この検査は、章に 1 件の宣言があるだけで現在時行動が通った従来の穴（B-01）を塞ぐもので、残余の検出漏れは §6.1 の人手照合で記録する。**

### 9.4 変わっていないこと

- 意味的整合性の保証（B-03〜B-05、A-08、B-09）。マーカー一致は本文の事実保持を意味しない。
- 実モデル応答・Arena リレー・L1 ペア比較は未実施。L1 は構造・衛生のみ、**L2/L3 と G3/G4 は `frozen_not_measured`**、G5 は主張しない。
- protocol-v1 の系・指標・閾値は変更していない。
- P1（§5.2）は未着手: A-07（同一場面 learn→use の偽陽性）は全工程試走の前に必要。

## 10. Stage B 単独の実応答試走（同日、P0 の後）

詳細は [`experiments/2026-10-stageb-solo-t01/note.md`](../../experiments/2026-10-stageb-solo-t01/note.md)。
`--stage b --game-log` で t01 の検証済みログを使い、Stage A を呼ばずに 3 章を実応答で書いた
（`arena-agent-mode` / `unversioned-2026-10-26`、生成と検査は同一エージェント、N=1）。

| 観点（§4 の分類） | 実応答で観測したこと |
| --- | --- |
| 現在地・移動（A-01） | ch03 の「四日ぶりの灯台」は誤り（day 1 出発・day 7 帰着＝六日）。`location_moves` は日数の前後だけを見るため `clean` のまま |
| 事実の保持（B-03/B-04） | 「片方だけでは、灯りは消せない」は前提と矛盾。マーカーは残るので `marker_sequence` も `fact_boundary` も通る |
| 保留事実（A-05） | ch01 の「鍵は二本ある」は F-02（setup ch02）の内容だが `terms` は `予備の鍵` のみで一致しない。fs-001 の setup と同文面で、保留と伏線設置が重なる |
| 死者言及（A-02） | **偽陽性 1 件**。「書いたのはヨハンだった。」を `high` とし修復 1 回。記録への言及だが同じ文に媒体語がない |
| 再開・記録（A-10） | 章ごとに exit 3 → 回答 → `--resume` の往復が 4 要求で成立。`replay.report.json` に replayed/missing の内訳が残り、二重追記なし |
| 来歴（§4.6） | `results.json` の `claim` が provider 固定文言だったため、relay run に「not a model response」と出ていた。provider 別に分岐し、`provider.observed` に記録された model/model_version を残すよう修正 |

**結論は §4 と同じ**: 決定論的検査は `clean` を返しても、事実・日数・推論の整合は保証しない。
次の全工程試走では、`clean` の章に対して §6.1 の人手照合を必ず行う。

## 11. P1 修正の実施記録（2026-10-26、Stage B 単独試走の後）

全工程試走の前に必要な 9 件（§5.2）を実装した。**大規模改修ではなく、各検査の判定範囲を狭める/広げる最小変更**である。
テストは 9 件追加し **634 passed**。`make probe-gamelog` の A3・A4・A5・A7・A8・A9・A10・B7 の結果が変わった。

| # | 変更（コード） | 修正後の挙動（プローブ） | テスト |
| --- | --- | --- | --- |
| P1-1 | `check._check_knowledge_boundary`: 場面ごとに `learned_facts` を先に反映し、`used_facts` を判定。同一場面の learn→use は `low` | A5（F-05 を同一場面で learn→use）→ `clean` / `low` 1 件 | `test_same_scene_learn_then_use_is_allowed` |
| P1-2 | `schema`: 各階層の既知キー集合を定義し、未知キーを `GameLog.unknown_keys` に収集（`as_dict` には出さない）。`check._check_schema_shape` が `low` で報告 | A8 → `clean` / `low` 2 件（キー名がそのまま出る） | `test_unknown_keys_are_reported_not_dropped` / `test_unknown_keys_are_kept_for_reporting` |
| P1-3 | `check._check_presence_death`: 現在時型の `subject` を検査（死者 `high`、生存者は型混同として `low`） | A3 → `unresolved` / `high` 1 件 | `test_present_tense_subject_is_checked` |
| P1-4 | `check._check_knowledge_boundary`: 死者の `used_facts` を `high` | A4 → `high`「死者 johan が ch02 で F-04 を現在時に使っている」 | `test_a_dead_characters_knowledge_use_is_high` |
| P1-5 | `check._check_schema_shape`: 章 ID の重複を `high`（名指し）、canon と違う章順を `high`（重複があるときは順序の所見を抑制） | A9 → `high`「章の並び順が canon…」、A10 → `high`「章 ID ch01 が重複」 | `test_chapter_ids_and_order_are_named` |
| P1-6 | `check._check_timeline_travel`: canon の初期位置＋宣言された移動から現在地を導出。起点の不連結 `high`、章の場所と現在地の不一致 `medium`、登場しない人物の移動 `medium` | A7 → `high`（aria の起点）＋`medium` 2 件（celia の移動・aria の現在地） | `test_current_location_and_movement_chain_are_checked` |
| P1-7 | `rewrite.missing_must_include` を追加し、`run_twostage` が全章を書き終えた後に作品単位でゲート | B7（全章から「鍵」を除く）→ 章ごとは `clean`、作品単位で `unresolved` | `test_a_missing_required_word_fails_the_work_not_the_chapter` |
| P1-8 | `--min-chars` を追加（既定 200）。`l1_hygiene.length_gate` に「目標長は合否に使わない」と記録 | 固定台本は 200 字ゲートで `clean` のまま | `test_committed_bundle_summary_is_reproducible` |
| P1-9 | `run_twostage._write_prompts`: 未回答の 1 件だけを載せ、回答済みは件数のみ | 2 件回答済み → `PROMPTS.md` に `stage_b/ch01` だけ | `test_prompts_md_lists_only_the_unanswered_request` |

### 11.1 修正後も残る穴（変わらないこと）

- 意味的整合性（A-08、B-03〜B-05、B-09）。語彙・ID・順序の検査であり、本文が事実を否定・省略しても通る。
  実際、Stage B 単独試走の実応答は `clean` のまま「四日ぶりの灯台」（正しくは六日）などを通した（§10）。
- 1 文字の別名（B-02）、章内複数場面の人物境界（B-08）、場面 `day` / `location`（A-02）、`status_since` の二重解釈（A-10）。
- `must_include` は作品単位でしか見ないため、「1 章だけ落とした」場合は通る。
- 現在地の連続性は「宣言された移動」と「章の場所」の整合だけを見る。移動日数の内訳や、移動中の場面は扱わない。

## 12. 全工程試走の実施記録（2026-10-26）

[`experiments/2026-10-full-t01/note.md`](../../experiments/2026-10-full-t01/note.md)。
Stage A の実応答が 1 回で `clean`（修復 0）、そのログから Stage B の 3 章がこれも 1 回で `clean`。
計 3,047 字、必須語 1.0、既存監査の違反 2 件（既知の誤検出）。

人手照合で見つけた検出漏れ 4 件は §13.1 と同内容:

1. **ch03「四日ぶり」**（正しくは六日）。日数の検査はログ側のみで、本文を読まない。
2. ch02 の「火傷の跡」— canon・ログにない人物細部。
3. ch01 の「刻みの深さ」— ログにない細部。
4. ch02 の「半日だけずれた日付」— ログが宣言していない数値。

2 run 目で 1 を直しても、機械的な結果は 1 run 目と同一（状態・所見・文字数・必須語・違反数）。
**`clean` の再現は修正の証拠にならない**。§4 の B-03〜B-05（意味照合は L2 相当）と
A-01/A-04（本文の現在地・日数は未検査）が、実応答でもそのまま現れた形である。

この結果を受けて、次段で検討する候補は次の 2 つ（**どちらも未実装**）。

- 本文の日数・現在地を語彙で拾う検査（「○日ぶり」「翌朝」など）。偽陽性が多く、語彙の拡充は
  B-05 と同じトレードオフに入る。
- 人手照合を手順として固定する（ログの出来事→本文箇所の対応表を章ごとに作り、検出漏れと誤検出を
  同じ様式で記録する）。本試走と Stage B 単独試走の記録がその雛形になる。

## 13. 時間の権威を決定論側へ移す（2026-10-26、実装記録）

§12 の検出漏れ 1（ch03「四日ぶり」）への対応。**観測ではなく改修**である。仕様と限界は
[`docs/two_stage_slice.md`](../../docs/two_stage_slice.md) §14。

- 追加: `src/asc/gamelog/world.py`（`World` = 無向の移動グラフ + Dijkstra 最短経路、
  `derive_timeline` = canon とログの畳み込み、`render_chapter_timeline` = Stage B への要約）。
- 追加: `check_rewrite` の 5 番目の検査 `timeline_consistency`。**明示された日数だけ**を、
  種類ごとの許容集合（滞在 / 章の日 / 経過 / 移動）と比べる。`medium`、既定は警告、
  `--strict-timeline` のときだけ修復対象。抽象表現と、書かれていない誤りは対象外（`skipped`）。
- 追加: run ディレクトリの `timeline.json`（`schema: trpg-timeline-v1`、派生成果物）。
  `run-summary.json` / `results.json` には要約と SHA-256 だけを入れた。
- 追加: Stage B プロンプト v1.1（`$timeline` プレースホルダと契約 6「日数を自分で計算しない」）。
- 追加: probe `B8`（3 通りの比較）、`tests/test_gamelog_timeline.py`（25 件）。
- 変更なし: protocol-v1 の系・指標・閾値、L1 の値、Stage A の 8 検査、既存 `results.json`
  （`2026-10-full-t01` の記録は再生成していない）。L2/L3 と G3/G4 は `frozen_not_measured` のまま。

残る検出漏れ（§12 の 2〜4、M-2/M-3/M-4）は今回の範囲外である。ログにない細部の追加や、
ログが宣言していない数量は、依然として機械的に検出できない。**`clean` は意味的整合の保証ではない**
という §4・§11・§12 の結論は変わらない。

## 14. S1 直接生成との L1 参考比較（2026-10-26、観測）

[`experiments/2026-10-l1-pair-t01/`](../../experiments/2026-10-l1-pair-t01/note.md)。同じ canon・
同じ設計書から、**検証済みログを渡す腕**（二段階 Stage B）と**渡さない腕**
（`--system s1 --stage draft --canon … --design-dir …`）を同じ L1 関数で並べた。N=1・単一タスク。

- 両腕で必須語 1.0・題材の禁止語 0・禁止パターン 0・未実行検査 0。文字数 3,047 対 3,313、
  違反 2 対 3（すべて既知の `dead_character_reappears`）、CED 5.799 対 8.217、
  マーカー 19 対 16（`use` 3 対 0）、会話率 0.007 対 0.047。
- **L1 のパターン集合では 2 条件を識別できない**。§11（S0–S3）と同じ結論が、方式の比較でも出た。
- 違いは検査可能性にある。ログがない腕には照合先が無いので、人手照合で見つかった台帳外の追加
  4 件は「検出漏れ」に数えることすらできない。一方、ログがある腕でも §12 の M-2〜M-4 は通る。
- 副作用の記録: Stage B プロンプトを v1.1（§13）に上げたため、`2026-10-full-t01/relay-r2/` の
  記録済み応答は `prompt_hash` 不一致で replay できなくなった（exit 4）。比較では応答の `text` を
  直接用い、抽出値が当時の `results.json` と一致することを確認した。**記録は残るが、現在の
  プロンプトでの再生成は別途必要**という、再生契約どおりの状態である。
- 未実施: S1 全体（plan・設計を含む）との比較、直接生成本文への変異注入による検出力の測定。

## 15. Stage B プロンプト v1.1 での再生成（2026-10-26、観測）

[`experiments/2026-10-stageb-v11-t01/`](../../experiments/2026-10-stageb-v11-t01/note.md)。同じ検証済み
ログを入力に、`$timeline` 入りの v1.1 で 3 章を作り直した（`--stage b`）。状態は `clean`、
試行 1/2/1、修復 1 回、計 2,867 字、必須語 1.0、既存監査の違反 1、CED 3.059。

- §13.1 の M-1（ch03 の「四日ぶり」）は、v1.1 では**六日ぶり**と書かれ、`timeline_consistency` が
  照合して不一致 0 で通った。導出表をプロンプトに載せた効果の 1 例（N=1・同一著者）。
- ch02 の初回は「三年前」（F-04 の語彙）で `fact_boundary` に止められ、修復で外した。
  ログの `outcome` が「三年前」と書く一方で本文では禁じられる、という語彙境界のねじれが見えた。
  v1.0 の ch02 は同語を使っていないため発火していない。**v1.1 が危険という意味ではない。**
- 長さは目安（1 章 1,000〜1,400 字）に届かず、ch02 989 字・ch03 835 字。`--min-chars` 200 の
  下限のみ満たす。run は `clean` のままなので、**`clean` が目標長の達成を意味しない**ことの例。
- v1.0 の記録は `prompt_hash` 変更により replay 不可（exit 4）。この run が現在のプロンプトに
  対する有効な記録で、`relay/` から同一の 3 章を再生成できる。
- 未実施: `--strict-timeline` での同条件の試行、誤った日数を注入したときの修復の観測。

## 16. 検査の検出力と `--strict-timeline`（2026-10-26、観測）

- **検出力**: [`experiments/2026-10-detect-power-t01/`](../../experiments/2026-10-detect-power-t01/note.md)。
  既知の誤りを 5 種注入し、既存の `check_rewrite` が発火するかを 2 腕（ログを見て書いた本文／
  見ずに書いた本文）で数えた。日数・死者の現在時行動・保留事実の語彙は 3/5 が両腕で発火。
  ログ外の場所・移動と宣言のない数量は 0/2（**§13.1 の M-2〜M-4 と同じ穴**）。
  ログを見ずに書いた本文は、ログ契約を当てると**ベースラインで既に 3 件**（「三年前」2 件・
  `present_characters` 外のボリス 1 件、すべて `medium`）の所見を持つ。検査が走っていないので
  通っていた、という §15 の結論の具体例。
- **`--strict-timeline`**: [`experiments/2026-10-stageb-v11-t01/note.md`](../../experiments/2026-10-stageb-v11-t01/note.md)
  の追記。ch03 を意図的に「四日ぶり」にすると、既定は `clean`＋警告 1（修復 0）、
  `--strict-timeline` は `unresolved`＋修復 1 回（指摘どおり六日に戻して `clean`）。
  run 全体は `clean`・計 2,867 字。**strict は修復の線を動かすだけで、直すのは修復の側**である。
- どちらも決定論的・L1 のみ。L2/L3 は `frozen_not_measured`、G5 は未達。protocol-v1 は不変。
