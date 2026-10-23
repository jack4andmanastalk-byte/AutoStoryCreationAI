# 現代アメリカのゲーム開発における物語・人物・世界・歴史の構築
## 公開資料スコーピング調査と制作実務カタログ

**調査基準日：2026年10月23日（Asia/Tokyo）｜版：1.0｜記述言語：日本語**  
**成果物：本レポート／情報源台帳 `sources.jsonl`／実務台帳 `practices.jsonl`**

> **結論の読み方**：本稿は、米国を主要な制作拠点とする開発組織の公開事例を中心に、関連研究・比較事例・ツール仕様を整理したものである。米国全企業の悉皆調査、PRISMA準拠のシステマティックレビュー、手法の因果効果のメタ分析ではない。観察された実務、発表者の自己説明、理論、筆者による推奨設計を区別する。

---

## 要旨

ゲームのストーリー構築は、完成した脚本を後からゲームに載せる単独工程としては説明しきれない。公開事例からは、**体験目標・人物像・ルール・空間・情報提示・会話条件・音声・翻訳・テストをつなぐ、複数の長さの反復**が確認できる。ただし、これを一つの業界標準工程や全米での普及率として扱うことはできない。実証研究のレビュー自体も、開発方法の呼称と実際の運用の不一致、創造的要求の変化、組織差を指摘している。[^S001]

主要な知見は次の7点である。

1. **評価の単位は文章だけではなく、プレイヤーの体験である。** Portalでは物語とゲームプレイの隔たりを減らす設計、Spider-Manでは「何をするか／なぜするか」の理解テストが示される。面白くても人物像に反する試作を退けたRiotの事例もあり、単一の楽しさ指標だけでは判定しない。[^S006][^S025][^S009]
2. **低コストで不確実性を切り分ける。** 紙、簡易デジタル版、仮文、scratch dialogueは、それぞれ情報理解、分岐構造、音声接続等の異なるリスクを先に試す。簡易版での成功は実機で再検証する必要がある。[^S016][^S054][^S060]
3. **執筆と実装を短い往復にする道具が重要である。** Hadesの表・ゲームデータ・定期収録、Firewatchのイベントと条件、Wildermythの著者向けエディタは、異なる形で書き手を実行可能なゲームに接続している。[^S011][^S047][^S022]
4. **人物・世界・作中史を状態と接続する方法は複数ある。** 手書きイベントの配役を変えるWildermythと、状態・文法から神話的な歴史を生成するCaves of Qudは、同じ「procedural narrative」でも異なる。いずれも、本資料で確認した仕組みはLLMによる自由生成ではない。[^S021][^S023][^S018]
5. **歴史は少なくとも二種類ある。** 作中史・ロア・カノンの継続管理と、現実の歴史・文化の調査考証は別の仕事である。Bungie／Blizzardの設定照会と、Pentimentの専門史家への相談を混同しない。[^S029][^S031][^S032][^S033][^S035]
6. **収録・映像・翻訳が進むほど改稿は周辺資産への変更になる。** 安定した台詞ID、文脈情報、変更範囲、実機確認を含む制作設計が必要となる。Firewatchの英語本文を翻訳キーにした反省は、この問題を具体的に示す。[^S047][^S043][^S042]
7. **発売後も物語は改訂され得る。** Hades IIの2025年公式記録では、フィードバックを受けた改訂をpreviewから正式パッチへ移し、セーブと翻訳、既読者の再訪を扱った。ただし、変更したことと満足度が因果的に向上したことは別である。[^S014][^S015]

**収録規模**：候補61件のうち、採用55件・補助3件・除外3件。実務カタログは42項目。採用資料には要旨のみの資料1件を含む。取得量と精読量は同じではなく、各資料の確認範囲を台帳に記載した。

---

## 目次

1. [対象・方法・証拠の扱い](#1-対象方法証拠の扱い)
2. [四つの構築対象と理論的な見取り図](#2-四つの構築対象と理論的な見取り図)
3. [制作パイプラインの参照モデル](#3-制作パイプラインの参照モデル)
4. [PDCA／PDSAとプロダクト反復](#4-pdcapdsaとプロダクト反復)
5. [領域別の構築とデータ設計](#5-領域別の構築とデータ設計)
6. [米国制作事例の比較](#6-米国制作事例の比較)
7. [検証・指標・品質保証](#7-検証指標品質保証)
8. [音声・翻訳・アクセシビリティ・変更管理](#8-音声翻訳アクセシビリティ変更管理)
9. [42項目の実務カタログ](#9-42項目の実務カタログ)
10. [導入・調査のための推奨テンプレート](#10-導入調査のための推奨テンプレート)
11. [限界と今後の調査](#11-限界と今後の調査)
12. [出典台帳と参考文献](#12-出典台帳と参考文献)

---

## 1. 対象・方法・証拠の扱い

### 1.1 対象範囲

- **地域**：制作組織の主要拠点が米国である事例を中心とする。出版社・報道媒体・講演会場の所在地だけで米国開発と判定しない。国外スタッフの国籍を一律に米国と見なすものでもない。
- **時期**：主たる事例は2010年代〜2026年。2004年のMDA／空間物語論、2008年のPortal等は、現在の実務を理解する基礎・歴史的資料として明示的に含める。
- **対象物**：台詞、プロット、クエスト、人物、関係性、環境、文化・社会、作中史、カノン、実在史の調査、運用時の改訂。その制作を可能にする道具、職能接続、試験、音声・翻訳も含む。
- **比較・方法資料**：Ubisoft Montreal等の非米国事例、スウェーデンの教育研究、英国inkleのink等を含めるが、米国での採用証拠にはしない。Choice of Games掲載の著者個人の方法も、米国出版社の必須工程や著者の制作所在地とは同一視しない。[^S002][^S041][^S045][^S046][^S054]
- **除外する推論**：公開情報がない社内工数・会議頻度・ROI・採用率・現行人員・生成AI導入率。過去の講演から2026年の組織図を推定しない。

### 1.2 調査方法

公式開発ブログ、公開講演スライド、作者・開発者へのインタビュー、学術誌・会議録、職能団体のガイド、ツール公式文書を、ウェブ探索と参照先の追跡で収集した。検索の軸は、narrative pipeline、character development、worldbuilding、lore／canon、procedural narrative、narrative playtest、dialogue tools、localization等と、作品・スタジオ名の組合せである。これは探索的・目的抽出的な収集で、検索結果総数を固定した機械的なスクリーニングではない。

資料ごとに、題名、著者または表示上の団体、媒体、初出・更新日、URL、DOI、地域上の関係、資料種別、取得方法、確認範囲、根拠箇所、和文の要約、限界、実務項目との対応を記録した。PDFの頁は、特記しない限り**表紙を1とするPDF内の順序**である。動画を視聴したとの主張はしていない。

| 区分 | 件数 | 意味 |
|---|---:|---|
| 採用 | 55 | 確認した本文・要旨・文書内容を、その範囲に限定して使用 |
| 補助 | 3 | S048・S051・S061。講演の同定や追跡候補であり、実装効果の証拠にしない |
| 除外 | 3 | S030・S049・S052。本文アクセスまたは内容確認が不十分 |
| 採用資料の本文全体確認 | 7 | ウェブ文書の全体確認。講演全体や「7本の論文の全文精読」という意味ではない |
| 採用資料の選択箇所確認 | 47 | 関連節、PDF頁、取得できた本文チャンク等を確認 |
| 採用資料の要旨のみ確認 | 1 | S045。細かい方法の記述は別資料S046を引用 |

採用資料には学術誌論文3件、学術会議録2件が含まれるが、S059は要旨・導入、S045は要旨のみである。S001の48論文レビューとS059の69研究レビューを参照したことは、その全一次研究を本調査が再評価したことを意味しない。[^S001][^S059][^S045]

### 1.3 証拠のレベルを混ぜない

| 資料の性格 | 主に確認できること | それだけでは言えないこと |
|---|---|---|
| 開発者の資料・スライド | 当人が説明した工程、道具、失敗、変更理由 | 全社での遵守率、独立した効果検証 |
| 公式パッチ・方針 | 何を変更・計画・告知したか | 計画の全面達成、利用者評価の因果的改善 |
| 当事者インタビュー | 制作判断と具体的な経験 | 記憶の完全性、非公開工程の全体 |
| 学術的記述・研究 | 公開された対象・方法・概念・結果 | 対象外地域や企業への無条件な一般化 |
| ツール仕様 | 何が実装可能か、どう動くか | 米国企業での普及、他製品への優越 |
| 講演の二次報告 | 記者が報告する手順・主張・数値 | 未公開の元データ、完全な講演内容 |
| 告知・索引要旨 | 講演題名、登壇者、扱う主題 | 実装の詳細、実施後の成績 |

たとえばRiotのD&Iレビューは会社が説明する仕組みであり、その存在から表象上の問題が解消したとは結論しない。PlayStation Blog上の現地調査も、作品の歴史的・文化的正確さを第三者が認証したことにはならない。[^S055][^S058]

### 1.4 日付・アクセス・再現性

アクセス日は2026-10-23（Asia/Tokyo）。先行検索は2026-10-22 UTCにも行われた。公開日の表記は、媒体の元の日付・UTCタイムスタンプ等を尊重し、アクセス日のタイムゾーンへ一律変換しない。

移転日・更新日を初出としないように照合した。例として、VICEのSpider-Man記事は2020年、Alexander Freedの指標記事は2015年、Double Fineインタビューは2014年、IGDA文書の第2稿は2012年である。Steamのpreviewは2025-10-23、正式パッチは2025-10-31で、previewの10月30日更新とは異なる。[^S025][^S037][^S060][^S043][^S014][^S015]

HTTP 200でもメンテナンス画面の場合があり、逆にS026／S059は通常取得が403でも別の本文抽出経路で一部を確認できた。**取得成功・全文取得・関連箇所の読解を別の属性にした。** ハッシュは取得した応答の識別であり、主張の真実性の保証ではない。ブロック画面のハッシュを本文のハッシュと取り違えない。

## 2. 四つの構築対象と理論的な見取り図

### 2.1 用語の操作的定義

以下は本報告の比較用の定義で、統一された業界用語集を発見したという主張ではない。

| 対象 | 構築するもの | 隣接領域と区別する点 |
|---|---|---|
| **ストーリー** | 出来事の因果、進行、場面、選択、情報提示、プレイヤーの役割 | 設定資料の量と、実際の体験の成立は別 |
| **キャラクター** | 欲求・価値観・行動・関係・外観・声・プレイヤーとの接点 | 長い経歴だけでなく、ゲーム内で何をする／どう反応するか |
| **世界観** | 空間、自然・社会のルール、文化、制度、生活、美術・音響の意味体系 | 地図や用語集だけでなく、行動が可能／不可能になる制約 |
| **作中史・ロア** | 過去の出来事、その因果、記録・伝承・人物の記憶、年表 | 世界内の事実と、それを語る者の認識を分ける |
| **カノン管理** | 何がどの作品・版・分岐で有効か、変更の権限・記録 | ファンの解釈、古い設定、会社の方針発表を自動的に同一視しない |
| **実在史の調査・考証** | 史料・研究・専門家・現地に照らした時代と文化の検討 | 架空世界の内部整合性とは異なる、外部の証拠を必要とする |

### 2.2 理論を工程へ接続する

**MDA**は、作り手が実装するmechanics、遊びの中で現れるdynamics、プレイヤーの感情的な経験としてのaestheticsを区別する。したがって、感情を生みたいときに台詞だけを調整するのではなく、繰り返す行動、失敗条件、情報の順序も検討するためのレンズになる。ただし、その因果が作品ごとに自動保証されるモデルではない。[^S003]

**Narrative architecture**は、空間が物語を喚起・実演し、手掛かりを保持し、創発の余地を作ると整理する。WorchとSmithの実務資料は、痕跡を因果の連鎖にし、レベル設計者と環境アーティストが共有する構造へ落とす例を示す。理論と実装の接点がここにある。[^S004][^S008]

人物主導の設計に関する2025年レビューは、人物・物語と、ルドナラティブ構造、視聴覚表現、主題の交点を扱う。本稿では関連研究の位置づけとして利用し、米国企業の工程頻度を示す資料とはしない。[^S059]

### 2.3 職能は役職名だけで切らない

IGDAは、会話、全体構造、文書等を書く仕事と、それを別の職務に加えて担う人の存在を説明する。Insomniacの取材でも、設計者の作る体験に書き手が協働する関係が示される。したがって「writerが物語、designerが遊び」と分離する図は、工程の実態を取り逃がし得る。[^S053][^S025]

本報告では、責任を**仕事の機能**として記す。典型的に関わるのは、creative／narrativeの方向づけ、執筆、ゲーム・レベル・クエスト設計、人物・環境美術、technical narrative／ツール開発、音声・演技、制作管理、QA／ユーザーリサーチ、翻訳、考証・文化相談、アクセシビリティである。これは推奨する観察項目であり、各社に同名の専任者がいるとの主張ではない。

## 3. 制作パイプラインの参照モデル

### 3.1 一方向の工程ではなく、戻り道を持つ接続

以下は複数事例を比較するための**分析上の参照モデル**である。8段階を全社が同じ順序・名称で採用しているわけではなく、alpha・beta・lockの定義も会社や作品によって異なる。

```text
体験目標・IPの核・調査上の問い
        ↓              ↖ 大きい設計の再検討
outline・人物・世界の仮説
        ↓
低忠実度試作 ── 理解／人物像／分岐の評価
        ↓                     ↖ 改訂
代表的な遊べる単位・実行データ・著者用ツール
        ↓
場面／クエスト／会話／環境の量産
        ⇄ 仮音声・収録・翻訳・美術・映像
        ⇄ QA・物語理解・表象／考証レビュー
        ↓
リリース／EA／シーズン／物語パッチ
        ⇄ フィードバック・セーブ互換・再訪・再試験
        ↓
ポストモーテム → 道具・責任・次の制作単位の更新
```

| 段階 | 主な問い | 成果物の例 | 確認・戻り先 | 対応資料 |
|---|---|---|---|---|
| 1. 方向づけ | 何を感じ・行い、何を守る作品か | 体験目標、IP brief、core truth、主題 | 人物像と操作の不一致なら方向づけへ | [^S009][^S003] |
| 2. 調査・構造 | 誰が何を望み、何が因果でつながるか | outline、人物表、世界のルール、調査文献 | 設定・場面・実現性を相互改訂 | [^S011][^S038][^S033] |
| 3. 不確実性の試作 | いちばん分からないことは何か | 紙／demake、仮文、仮音声 | 情報理解、分岐構造、テンポを分離 | [^S016][^S054][^S060] |
| 4. 実装接続 | 書いた内容がゲームで正しく発生するか | 条件・変数、イベント、エディタ、ID | 条件・データ形式・道具を改訂 | [^S007][^S047][^S022] |
| 5. 内容制作 | 小単位をどの順で作り検証するか | 会話・場面・環境・音声のまとまり | 直接プレイして反復 | [^S011][^S024][^S025] |
| 6. 統合・安定化 | 不整合、未到達、欠落、翻訳差はないか | 自動試験、レビュー、LQA、字幕 | ロジック・文脈・資産を修正 | [^S040][^S043][^S044] |
| 7. 公開・継続 | 既読者と未読者にどう届くか | 更新計画、preview、パッチ記録 | 内容、優先順位、公開範囲を再決定 | [^S012][^S013][^S014][^S015] |
| 8. 工程の改善 | 同じ詰まりを道具で減らせるか | lessons learned、改善backlog | 次の制作サイクルの仕組みへ戻す | [^S011][^S047] |

### 3.2 「一本の大きい脚本」より制作単位を考える

- **台詞・会話**：発生条件、優先度、割込み、既読、相手、再訪を含めて一単位とする。
- **場面・クエスト**：プレイヤーが入る条件、場面中に必要な行動、終わった後の世界状態を含める。
- **探索コンテンツ**：手掛かりの発見順が一定でないため、知識の前提と、情報の再提示・記録を含める。
- **人物**：本文だけでなく、美術、操作、関係性、声、音楽との適合を試す。
- **世界・作中史**：事実、伝承、遺物、空間、現在のシステム上の効果を接続する。

これらの接続は、Firewatchの条件付きイベント、Outer Wildsの理解試験、Riotの人物共同開発、Qudの歴史と遺物の接続に具体例がある。ここで示した「制作単位」の一般化自体は本稿の横断的整理である。[^S047][^S016][^S056][^S057][^S018]

## 4. PDCA／PDSAとプロダクト反復

### 4.1 名称の採用と、反復があることを分ける

公開資料で「試作→観察→改稿」が確認できても、各社がそれをPDCAと呼んだとは限らない。本章はユーザーの関心に合わせ、**観察した反復をPDCAに対応づけた分析**である。

Deming Instituteは、PDSAのStudyを予測と結果から学ぶ活動として説明し、Checkとの違いを強調する。物語評価では「合格したか」だけでなく、「なぜその理解・選択になったか」「別の原因ではないか」を扱うため、Check／Studyを併記するのが有用である。これはゲーム業界の命名実態ではなく方法上の提案である。[^S005]

| 段階 | ゲームナラティブへの対応 | 記録するもの（推奨） | 陥りやすい誤り |
|---|---|---|---|
| Plan | 体験・理解・人物像の仮説と制約を定義 | 仮説、期待する観察、対象状態、予測 | 「もっと良くする」だけで判定基準がない |
| Do | 必要最小限の試作・改稿・実装 | build、データ版、実装差分、実施条件 | 音声・美術等を一度に変え、原因が不明になる |
| Check / Study | 行動・説明・状態ログ・制作結果を照合 | 観察、否定例、代替説明、限界 | 選択率・完了数だけで感情や価値を断定 |
| Act | 採用・再設計・保持・保留を決める | 判断理由、担当、影響資産、次の試験 | 問題ごとに文章だけを追加して情報過密にする |

### 4.2 入れ子になる四つの反復

以下の四層は本稿の整理で、共通の会議周期を示すものではない。

| 層 | 単位 | よく変わる対象 | 実務上の例 |
|---|---|---|---|
| 局所 | 一行・一イベント・一選択 | 条件、言い回し、タイミング、fallback | 条件付き台詞、役柄の任意化、自動試験 [^S007][^S024][^S040] |
| 内容のまとまり | 場面、音声batch、人物、地域 | 進行、配役、導線、演技、情報の量 | Hadesの収録〜実装、Riotの人物試作 [^S011][^S009] |
| プロダクト／運用 | 作品全体、EA更新、シーズン、パッチ | 物語の大枠、公開順、結末前後、継続性 | Hades／Hades II、Destiny [^S012][^S015][^S029] |
| メタ工程 | 道具・責任・制作方式 | ID、データモデル、ファイル管理、会話抽象 | FirewatchとHadesの反省点 [^S047][^S011] |

Agile／Scrum等の管理方法名から、物語制作の実際の単位・周期を一意に推定しない。実証レビューは方法の名目と運用の差を指摘する。本稿では、全社共通の「2週間sprint」等の周期を仮定せず、観察できる執筆・実装・収録・公開の接続を記録する。[^S001]

一層だけ速くしても、他層が詰まれば改稿は進まない。たとえば本文の即時編集ができても、翻訳IDが壊れる、古い音声が残る、重要な会話が優先されない、といった制約がある。公開資料からこのような依存関係は読み取れるが、層ごとの標準周期や改善ROIは算定できない。[^S047][^S011]

### 4.3 観察された往復をPDCAで読む

**Riot／Illaoi**：人物の核と目標・禁止条件を置く（P）→粗い能力を作る（D）→楽しさに加えて「その人物らしいか」を判定（C/S）→整合しない案を再設計（A）。「プレイテストで楽しい」だけでは通さない事例である。[^S009]

**Mobius／Outer Wilds**：操縦以外の情報理解を調べる（P）→紙／Processingのdemake（D）→ノート行動、理解、情報過密を観察（C/S）→記録機能や情報配置の方向を見直し、元の3Dで再検証する（A）。抽象化した試験の限界まで記されている。[^S016]

**Sucker Punch／Ghost of Yōtei**：探索コンテンツへの関心不足を問題化（P）→地域の初期体験要件と導入順序を変更（D）→再プレイテストの完了数を比較（C/S）→地域共通の言語として整理（A）、という流れを二次報道から追える。数値の限界は第7章で扱う。[^S050]

**Supergiant／Hades II**：発売後のフィードバックで改訂範囲を決め（P）、previewを配布し（D）、翻訳・セーブ・再訪条件に注意して反応を得る機会を設け、正式パッチへ移す（A）。ただし、公開された記録から内部の全評価項目や採否基準までは分からない。[^S014][^S015]

## 5. 領域別の構築とデータ設計

### 5.1 ストーリー：因果とプレイヤー行動を同時に設計

**観察された方法**：高レベルoutlineから直近の実装を書くHades、他部門が作業できる行動ベースのoutlineを勧めるHeart Machineの講演報道、設計者との協働を説明するInsomniacは、異なる規模で脚本と制作を結びつける。God of Warの開発約1年後の大きな改稿は、構造の見直しが実際に起こり得る例だが、その時期を推奨標準とはしない。[^S011][^S038][^S025][^S028]

**推奨する構造チェック（本稿の統合）**：

- 場面の前提、起きる行動、障害、結果、次への因果を分ける。
- 台詞で説明する事実と、行動・空間で分かる事実を分ける。
- 選択の価値を、結果の差、主題、人物の自己表現に分ける。
- 選択後に合流しても、関係性や反応の差がプレイヤーに認識できるか確かめる。
- 物語上の不明点が意図した謎なのか、必要情報の欠落なのかを事前に区別する。

分岐を、結果を大きく変える方式、主題を表す方式、人物定義の方式に分ける整理はNessa Cannonの講演報道に依拠する。すべての選択を巨大な別ルートにする必要があるという主張ではなく、費用と体験価値の関係を考えるための区別である。[^S039]

**執筆パスの具体例**：Ben Servissは一章ごとに、①Stub Text、②Stub Text Revision、③First-Pass Text、④Text Revision、⑤Variables、⑥Export and Logicを分けた。構造の修正中に完成文を磨かず、変数値の検討も分離する。ただし本人も、早くstubをゲームに移す別方式を挙げており、一本道の必須工程とはしていない。[^S054]

### 5.2 キャラクター：経歴だけでなく、行動・関係・媒体間整合

RiotのDNAは、人物を叙述・操作・美術の共同課題とする。Neon／Zeriでは短い人物紹介、紙試作、コンセプト画が用いられ、共通する文化的背景を異なる性格・反応に展開した。音楽制作の説明では、その人物のロアや関係性も作曲家へ渡される。[^S009][^S056][^S057]

Hadesの資料は、人物ごとの必要性・関係・声、キャスティング用台本、音声をゲームに入れた評価、収録と修正を示す。Double Fineのインタビューは、動的に組み合わせる台詞を想定した執筆、仮音声での接続試験、俳優への文脈・演出指示を強調する。[^S011][^S060]

Wildermythは別の構築問題を扱う。人間がイベントを書き、人物の性格・関係・能力・履歴が役柄に合うかを判定する。「人物を生成する」と「場面の文章を自由生成する」は同義ではない。発表では、名前の稀な破綻、フックの設計、履歴と作品トーンのずれが反復課題として明示される。[^S021][^S023]

**推奨人物シート（本稿の設計案）**：目的／価値観／行動上の制約、他者との関係、プレイヤーとの接点、口調、声・演技上の幅、外観と操作の整合、変化する状態、レビュー上の懸念。全項目を長文で埋めることより、試作の判定に使えることを重視する。

### 5.3 世界観：設定と、世界で起こることを接続

WildermythのWriter’s Guideは、世界のトーン、用語、魔法、人物の履歴・aspects・stats、編集ツール、資産の制作負荷を一つの著者向け文書で扱う。これは、百科事典型の設定だけでなく、何を書けば実際にゲームへ載るかを伝える例である。ただし共同編集WikiにはTODOや旧仕様も残る。[^S022]

環境物語では、物・地形・痕跡の関係から過去を推論させる。小道具の一覧だけでなく、どの順に何を見て、どう因果を結ぶかを、レベル設計と美術の共通図として作る方法が提案されている。[^S008][^S004]

Qudでは、固定の世界・ロアの骨格に手続き生成を組み合わせる。生成履歴は碑文の文章だけにとどまらず、歴史的な場所や遺物、現在の物の属性に接続される。公式press kitは作者と関連資料への入口として用いたが、古い予定欄が残るため現在の発売状況の証拠にはしない。[^S018][^S019][^S020]

### 5.4 作中史・カノン：事実、語り、発見を分ける

**三つを同じ表に押し込まない（本稿の推奨区別）**：

1. **世界内の出来事**：何がいつ起きたか。別分岐や版の違いも含む。
2. **世界内の語り・記録**：誰が何を知り、どう記したか。嘘、偏見、不確かな伝承もあり得る。
3. **プレイヤーの知識**：どの記録・会話・痕跡に到達したか。未発見と事実の不存在は異なる。

Qudの生成された出来事と文化的な遺物の関係、Outer Wildsの手掛かりの理解・記録を比較すると、この分離は有用である。ただし、上記三層の同一schemaを両社が採用したという意味ではない。[^S018][^S016]

**継続制作の観察例**：Bungieでは過去ロアの関係箇所を選び、historianに照会し、既存設定の内側から新しい物語を作ると説明する。Blizzardの2013／2018年取材では、照会、lore bible、出版・美術のレビュー、発音資料、オンボーディング等が挙げられる。設定を検索できる人と、最終的に新しい物語を決める人は同一とは限らない。[^S029][^S031][^S032]

**方針と実施の差**：Riotは2023年に新しい物語を共通カノンへ置く方針を公表したが、既存作品の不整合を一度にすべて直すとはしていない。方針発表を「全媒体の整合完了」に読み替えない。[^S010]

**推奨する設定項目（本稿の設計案）**：

```json
{
  "fact_id": "fictional.example.001",
  "statement": "架空の出来事の記述",
  "scope": "作品・分岐・版の範囲",
  "event_time": "作中時点または前後関係",
  "truth_status": "確定・暫定・作中人物の主張・廃止等",
  "claimant_or_record": "誰の発言／どの文書か",
  "source_asset_ids": ["出典となる台詞・文書・資産のID"],
  "player_reveal_conditions": "いつ何を発見できるか",
  "revision": "改訂と判断の履歴",
  "decision_owner": "そのプロジェクトで決めた承認担当"
}
```

これは実在スタジオのschemaではなく、参照・版・認識の違いを取り違えないための例である。矛盾は、誤記、意図的な不確かな語り、後からの再解釈、設定置換、別連続性のいずれかを区別して判断することを推奨する。

### 5.5 実在史・文化：調査の存在と正しさの保証を区別

Pentimentの取材では、史学文献、専門家への質問、史料の翻訳、衣服・室内等の美術への指摘が挙がる。専門家への照会が、脚本だけでなく制作資産のレビューまで届いている点が重要である。物語上の選択と長い時間の変化、説得システムの繰り返し改訂も説明される。[^S033][^S034][^S035][^S036]

Sucker PunchのNate Foxは、現地調査、文化アドバイザー、北海道への二度の訪問が、景観・人物・象徴の着想に関わったと説明する。同時に、ゲームは現実の場所の完全再現ではなく創作だと明記する。本稿はこの**制作手順の自己報告**を引用し、歴史解釈の正しさや表象の妥当性そのものを認証しない。[^S058]

**推奨調査台帳（本稿の統合）**：史料と後世の研究の区別／専門家に尋ねた問い／合意・異論・不明点／採用した表現／創作した理由／当事者・地域への含意。Riotの地域・D&IレビューやIGDAのculturalizationも関連するが、文化は一人の相談者や一人の登場人物で代表し尽くせない。[^S055][^S056][^S043]

## 6. 米国制作事例の比較

### 6.1 比較表

「実際に全工程を観察した」という表ではなく、公開資料で追える範囲を並べている。同じスタジオの複数資料は独立した企業標本ではない。

| 制作組織・事例 | 追跡できる制作上の接続 | 反復で変えた／検討したもの | 主な限界 |
|---|---|---|---|
| Valve／Portal | 物語・レベル・観察テスト | Companion Cube、終盤、台詞と場面の役割 | 2008年の基礎事例。現在の全社工程ではない [^S006] |
| Valve／文脈台詞 | facts→条件照合→既製台詞選択 | 作者向け表現、記憶・状態、デバッグ | 2012年の技術説明。LLMではない [^S007] |
| Riot／Illaoi、Neon・Zeri | DNA、人物brief、紙・操作試作、美術 | 人物像と楽しさの両立、ゲーム別の適応 | 特定の人物開発。全キャラの共通書式とは限らない [^S009][^S056] |
| Supergiant／Hades | outline→直近執筆→収録→編集・処理→実装 | 人物、演技、イベント、優先順位、整理法 | 成功作の自己報告。詳細は後述 [^S011][^S012] |
| Supergiant／Hades II | 大型更新、発売後のpreview→正式版 | 結末前後のイベント、発生条件、既読者の再訪 | 効果量なし。変更範囲を限定して読む [^S013][^S014][^S015] |
| Mobius／Outer Wilds | 紙・Processing版→理解観察→3D | 手掛かり、記録、情報密度、故郷の人物 | 開発初期の試作であり最終版全体ではない [^S016][^S017] |
| Campo Santo／Firewatch | events・blackboards・条件→反応、著者ツール | 会話抽象、割込み、翻訳ID、道具の接続 | Further Workは出荷済み機能ではない [^S047] |
| Insomniac／Spider-Man | IP調査、台本DB、設計者との協働、理解試験 | 目標・行動理由、場面の切替、人物の二重性 | 取材・概算。S026は冒頭の該当節のみ [^S025][^S026] |
| Bungie／Destiny 2 | writers’ room、複数部門、historian照会 | 既存ロアと次シーズンの接続 | 2023年時点の体制 [^S029] |
| Blizzard／WoW | lore bible・照会・出版／美術レビュー | 設定の照合、retcon、共有・教育 | 2013／2018年の資料で現行体制は不明 [^S031][^S032] |
| Freehold／Caves of Qud | 固定ロア＋状態・文法による歴史生成 | 出力の声、因果の事後合理化、遺物への接続 | 作者による質的評価が中心 [^S018][^S019] |
| Worldwalker／Wildermyth | 手書きplay＋配役、入出力、エディタ | 名前、履歴、フック、役柄fallback | 公開Wikiは版・TODOに注意 [^S021][^S022][^S023][^S024] |
| Obsidian／Pentiment | 歴史調査・専門家・美術・時間経過・選択 | 説得システム、数十年後の関係・世界の変化 | 複数取材だが独立した史学的検証ではない [^S033][^S034][^S035][^S036] |
| Sucker Punch／Ghost of Yōtei | 初期体験の要求→地域ガイド→導入段階→再試験 | 情報の順番、再提示、人物の誘導、探索理由 | 2026年講演の二次報告。元データ未確認 [^S050] |
| Double Fine／動的会話 | システムに合う執筆、scratch、俳優への文脈 | フレーズの接続、タイミング、演技 | 2014年インタビューで講演本体未視聴 [^S060] |
| Heart Machine／outline | 他職種が制作判断できる行動記述 | 共有outlineの可読性と制作との接続 | 講演報道に基づく方法提案 [^S038] |

Santa MonicaのGod of War改稿は大きな構造変更の存在を示すが、詳細な全工程は再構成しない。Naughty Dogの公式告知はLost Legacyの非線形空間と人物関係を扱う講演を同定する資料で、講演の具体的な手法や効果を読んだ証拠にはしない。[^S028][^S027]

### 6.2 Hades：執筆・演技・実装をまたぐ反復

GDC 2021資料の特に関連する箇所は、PDF pp.21–22（人物群の設計）、p.30（配役用台本とゲーム内評価）、p.32（執筆）、pp.34–36（収録・編集・音声処理・技術面）、p.40（フィードバック）、pp.41–42（工程と課題）、p.46（改善点）である。[^S011]

- 高レベルのoutlineは早期に作るが、主に**近く実装する内容**を書く。
- Sheetsとゲームデータを扱い、配役候補の声をゲーム内へ入れて判断する。
- Darrenが収録・一次フィードバック、Bradが編集、Darrenが音声処理、Gregが台詞をゲームへ接続するという担当の往復が示される。
- 内部での節目のプレイ、EA、配信等の反応がフィードバック経路となる。
- ファイル整理とイベント優先順位等は改善点として残る。

多い時で週3–4回の収録という記述はこの作品の運用であり、業界の必要頻度や標準人員にはしない。初期outlineがあるため「計画せずに必要な分だけ書いた」とも解釈しない。スライド中の集計画像の正確な台詞数等は、本調査の文字抽出では再確認できなかったため数値比較には使用しない。[^S011]

### 6.3 Outer Wilds：試作を「問い」に合わせて作る

demakeは本製品を安価に再現するだけでなく、操縦の難しさを取り除き、プレイヤーが手掛かりを結びつけられるかを調べる装置だった。紙版からProcessing版へ移り、その場で変更し、ノートの取り方から記録機能の必要を判断した。一方、情報を集めすぎた簡易版は空間移動や休息の働きを失うことも示した。[^S016]

ここから導く推奨は、**試作ごとに「残すもの」と「抽象化するもの」を書き、抽象化の副作用を本来の環境へ戻して検証する**ことである。これは特定のツール選定より移転しやすい原則だが、他作品で同じ成果が出ると証明されたわけではない。

### 6.4 Firewatch：改善する対象は文章だけではない

イベント発火、facts、requirements、responsesを結ぶ仕組みは、台詞と世界の状態を接続する。その一方、スライドは、英語本文を翻訳参照のキーにしたため、誤字修正でも翻訳側との対応が壊れる問題を示す。提案されたstatefulなConversation単位は、割込みや継続を一つの抽象として扱う将来改善であり、出荷時に実装済みとは書かない。[^S047]

この事例は、内容を反復しやすくするには、**識別子・状態の寿命・会話の単位・道具の責任境界**まで反復対象にする必要があることを示唆する。製品内容のPDCAと制作システムのPDCAを分けて記録する理由である。

### 6.5 二つの手続き的ナラティブを区別

| 項目 | Wildermyth | Caves of Qud |
|---|---|---|
| 主な作者制作単位 | イベント／playと台詞 | 世界の骨格、状態・出来事・置換文法 |
| 変動させるもの | 配役、条件、人物に応じた差分、結果 | 歴史上の出来事、神話的記述、場所・遺物 |
| 人物・歴史との接続 | 性格・関係・履歴で役柄を選ぶ | 生成した過去が現在の文化的・物的痕跡になる |
| 明示された課題 | 名前の破綻、フックと履歴の整合 | 神話的な声、整合性、評価の難しさ |
| 本調査での根拠 | 発表・著者ガイド・公開ツール例 | 学術会議論文・開発者取材 |

根拠：[^S021][^S023][^S024][^S018][^S019]。手続き的な選択・構成と、LLMによる文章生成、因果世界の完全シミュレーションは区別する。

## 7. 検証・指標・品質保証

### 7.1 何を検証したいかを分ける

以下は資料を横断して構成した**評価テンプレート**であり、標準KPI一覧ではない。Freedの6指標、Insomniacの理解テスト、ChoiceScriptの自動試験、XAGの情報伝達等を参照している。[^S037][^S025][^S040][^S044]

| 評価軸 | 確認する問い | 方法・指標の候補 | 注意点 |
|---|---|---|---|
| 理解 | 目的、動機、因果が分かったか | 誘導しない説明・想起、観察、誤解類型 | 意図した謎や曖昧さを誤答扱いしない |
| 関与・情動 | 誰を気にし、何に反応したか | 行動＋聞き取り、自由回答、場面別の反応 | 完了率だけで感情を推定しない |
| 選択・主体性 | 意図を表せ、結果を認識できたか | 選択理由、結果の認知、別ルート経験 | 多数派の枝だけが成功ではない |
| 到達・発見 | 必要な内容にどの条件で届くか | 到達率、未遭遇、発見順、条件別比較 | 遭遇可能者等の分母が必要 |
| 技術的正しさ | 不可能な状態や矛盾した台詞はないか | 自動実行、条件検査、再現save、手動境界試験 | 行到達と全状態網羅は別 |
| 人物・世界・歴史 | 口調、関係、時代、カノンが整合するか | 多職種レビュー、根拠照会、専門家検討 | 意図的な作中誤認と設定ミスを分ける |
| 音声・翻訳・情報保障 | 文脈と必須情報が言語・設定差で届くか | 実機LQA、音声なし試験、字幕・caption確認 | 音声が再生されるだけでは十分でない |
| 制作の信頼性 | 改稿を安全に取り込めるか | 資産欠落、ID不整合、再録・再翻訳の差分 | 速度だけを最適化して品質を損なわない |

### 7.2 指標は説明の入口であり、理由そのものではない

Freedは、セッション長、対象層、完了者、プレイスタイル、内容・外見の選択、分岐選択を観察対象として挙げる。同じ選択率でも理由は異なり、選ばれない枝にも「別の選択ができる」と感じさせる価値がある、とする。[^S037]

推奨する記録は、指標定義、分母、対象build、対象者の前提、露出した内容、収集条件、代替説明である。行動計測を行う場合は、同意・目的限定・必要最小限のデータを前提にし、個人の感情や属性を過剰に推測しない。これは本稿の推奨であり、各社の実施状況を示すものではない。

### 7.3 Ghost of Yōteiの「141%増」をどう読むか

Daniel Newの2026年講演報道では、同じ20人による再試験で、完了した探索コンテンツ数が**317から764**になったとされる。差は447、元の317を基準にした増加は約141%である。これは**完了数の増加**であり、完了率、継続率、全利用者の満足度ではない。[^S050]

- 一次のデータセット、個人ごとの値、分散、厳密な課題・露出条件、統制群は本調査で確認していない。
- 同じ参加者の再試験なら、学習・慣れ・追加露出の影響を排除できない。
- 複数の変更が束になっていれば、どの変更が寄与したかを分離できない。
- したがって「この手法で全ゲームの関与が141%改善する」とは書けない。
- 講演の公式索引は同定の補助だが、現在の直接URLは404であり、数値結果の独立検証にはならない。[^S051]

移転しやすいのは効果量ではなく、**不足を文章量ではなく導入・理解・導線の問題として診断し、部門間の共通要求に翻訳し、もう一度測った**という工程である。次の検証では新しい参加者・順序の影響・条件差を考慮することを推奨する。

### 7.4 自動試験ができること／できないこと

ChoiceScriptはQuicktestとRandomtestを用意し、条件や未到達行、実行時の問題を探す。一方、Quicktestは近似的に枝をたどるため偽陽性があり、状態の再訪にも制約がある。Randomtestは標本実行で、hit countはその試験で通った行の記録である。どちらも人間による内容評価の代わりとはされていない。[^S040]

inkは分岐・合流・変数・既読回数等を実行可能にする文法例で、こうした構造を記述する方法の参考になる。英国のツール仕様を、米国企業での採用率の証拠にはしない。[^S041]

完全に独立した二択が合流せずn段続くモデルなら経路は2のn乗になるが、実作品には合流・条件制限・状態共有があるため、この式をそのまま制作量に当てはめない。推奨するのは、意図した主要経路、極端な状態、既読／未読、死亡・欠員、順序違いを選び、再現可能な状態と手動評価を組み合わせることである。Wildermythの公開チュートリアルにも、死亡した役柄への対処、optional化、代替イベントが示される。[^S024]

### 7.5 早期レビューと実機テストは補完関係

Ubisoftのnarrative reviewは、実装後には大きな変更が困難になる物語を早く評価する方法として要旨に記され、Polygonの報道は要約・提示・改善可能な返し方を説明する。これは非米国比較例である。[^S045][^S046]

ただし要約が面白いことは、移動・操作・戦闘・中断・反復を伴う実機で成立することの証明ではない。早期の構造レビュー、低忠実度試作、実機での意味理解、技術的QAを段階ごとに組み合わせるのが、本稿の推奨である。

## 8. 音声・翻訳・アクセシビリティ・変更管理

### 8.1 本収録を最初の意味検証にしない

Double Fineの説明は、仮録音とシステムを理解した執筆、俳優に渡す文脈を重視する。Hadesは、配役のゲーム内評価と、収録・編集・処理・実装を往復する具体例を示す。台本が読めることと、反復される会話が自然に聞こえることは異なる。[^S060][^S011]

**推奨handoff項目**：line ID、話者、相手、直前・直後の意味、発生条件、演出意図、割込み可否、タイミング制約、テイク選択、実装版。これは両社共通の既存schemaではなく、公開された課題から組み立てたチェックリストである。

### 8.2 本文と識別子を分ける

Firewatchの例では、原文の修正が翻訳参照を壊した。Yarn Spinnerの公式文書は、line ID、言語別の文字列、対応する音声等の資産、Line Providerの役割を説明する。本文・ID・改訂・資産を分けることが、反復可能性の基盤になる。[^S047][^S042]

IDが同じでも意味が変われば翻訳・演技は古くなる。したがって安定したIDだけでなく、意味変更の通知、差分、要再翻訳／要再録、廃止・置換の記録が必要である。後半の管理項目は本稿の推奨設計である。

### 8.3 翻訳は末尾の置換処理ではない

IGDA文書はculturalization、用語集、スタイル、文脈、VO、LQA、各制作段階の準備を扱う。2012年第2稿のガイドであって全社の現行規程ではないが、ローカライズを工程の最初から考慮する参照資料となる。[^S043]

翻訳者が知る必要があるのは文字列だけではなく、人物の関係、口調、分岐条件、冗談の前提、変数の範囲、表示の長さ、声の制約である。実機LQAでは原文の問題が見つかる可能性もあるため、修正が一方向とは限らない。

### 8.4 字幕・キャプションも物語設計

XAG 104は、会話だけでなく重要な音、話者、伝達の性質等を音声に頼らず理解できるよう扱う。環境音が危険・人物・過去の痕跡を伝えるなら、その情報がどの設定でも失われないかを確認する。ガイドへのリンクは個別製品の準拠証明ではない。[^S044]

### 8.5 物語変更の範囲を明示する

Hades IIのpreviewは、セーブのバックアップ、翻訳準備、すでに遊んだ人の再訪を案内した。正式パッチは、主な変更がUnderworld側でSurfaceはほぼ不変、Epilogueは変えないと区分した。本稿では具体的な結末の内容には踏み込まず、**変更する部分／変えない部分／既存進行への影響を公開する実務**として扱う。[^S014][^S015]

推奨する変更要求票は、変更理由、対象line／event／fact ID、影響する音声・映像・翻訳・条件・セーブ、承認担当、テスト、公開説明を含む。これは本稿のテンプレートで、同じ票を各社が使っているという証拠ではない。

## 9. 42項目の実務カタログ

下表は索引である。**各項目の説明、artifact、根拠ID、PDCA対応、注意点は `practices.jsonl` に収録した。** PDCA対応は全項目で本稿の分析的マッピングである。P36・P42は特に、観察された同名の社内手順ではなく、資料を横断した推奨として分類している。

| ID | 実務 | 主なartifact | 根拠 |
|---|---|---|---|
| P01 | 体験目標・主題から設計制約を置く | 体験目標／設計原則 | [^S003][^S006][^S009] |
| P02 | IP・人物のcore truthと禁止条件 | IP brief／core truth | [^S009][^S026] |
| P03 | 職能横断の小チームで初期探索 | flash bio／paper prototype | [^S009][^S056] |
| P04 | writers’ roomと他部門による読み合わせ | 脚本／レビューメモ | [^S029][^S053] |
| P05 | 高レベルoutlineを生きた共有文書にする | outline／logline | [^S011][^S038] |
| P06 | 場面を行動と因果で記述する | 行動を記したbeat／scene brief | [^S038][^S025] |
| P07 | 人物群の役割・関係性・声を対照化する | character roster／relationship map | [^S011][^S026][^S027] |
| P08 | 文化・地域・表象のレビューを制作途中へ入れる | review brief／指摘と対応記録 | [^S055][^S056][^S058][^S035] |
| P09 | 声の候補をゲーム内でオーディションする | casting sides／audition recordings | [^S011][^S060] |
| P10 | 世界のルールとトーンを実装可能な形で定義 | world guide／tone guide | [^S022][^S018][^S017] |
| P11 | 実在史の資料調査と考証を分けて記録 | bibliography／research question list | [^S033][^S034][^S035][^S058] |
| P12 | ロアの照会・出典・履歴を管理する | lore bible／source-linked fact register | [^S029][^S031][^S032] |
| P13 | カノン変更を方針・範囲・版で扱う | canon policy／change log | [^S010][^S031] |
| P14 | 手掛かりとプレイヤー知識を設計する | clue map／discovery flow | [^S016][^S008] |
| P15 | 低忠実度試作で不確実性を切り分ける | paper model／demake | [^S016][^S002] |
| P16 | 構造・文章・変数を別パスで推敲する | stub graph／prose draft | [^S054] |
| P17 | scratch dialogueで本収録前に試す | scratch recordings／in-engine timing | [^S060][^S011] |
| P18 | 分岐の価値とコストを区別する | branch graph／consequence register | [^S039][^S041][^S054] |
| P19 | 条件・既読・関係性を明示した状態モデル | state variables／preconditions | [^S007][^S023][^S041][^S047] |
| P20 | 文脈に合う台詞・イベントの選択と優先順位 | rule table／event criteria | [^S007][^S021][^S023][^S047] |
| P21 | 書き手の資料を実行データへつなぐ | script database／spreadsheet | [^S011][^S025][^S047][^S022] |
| P22 | 環境の痕跡を因果連鎖として配置する | environmental beat／prop chain | [^S004][^S008][^S006] |
| P23 | 手書きイベントを役柄にキャスティング | library of plays／role requirements | [^S021][^S023] |
| P24 | 生成作中史を遺物・地名・物語へ接続する | history generator／event records | [^S018][^S019] |
| P25 | 生成結果の低頻度の破綻を重点確認 | sample corpus／bad-case register | [^S021][^S018] |
| P26 | 著者自身が小単位を実行・再生できる環境 | developer mode／event launch | [^S022][^S024][^S040] |
| P27 | 物語理解を行動・説明と照合するプレイテスト | test protocol／observations | [^S006][^S016][^S025][^S050] |
| P28 | 高コスト化前の物語レビュー | synopsis／review notes | [^S045][^S046] |
| P29 | テレメトリを診断の手掛かりとして使う | event taxonomy／denominator | [^S037][^S050] |
| P30 | 自動分岐試験と人間の意味評価を併用 | Quicktest／Randomtest | [^S040][^S041] |
| P31 | なぜこの台詞になったかをデバッグ可能にする | fact view／rule diagnostics | [^S007][^S047] |
| P32 | 収録・編集・音声処理・実装を反復する | VO batch／takes | [^S011][^S060] |
| P33 | 本文から独立した安定したline ID | line ID／locale table | [^S047][^S042][^S043] |
| P34 | 翻訳へ人物・文脈・改訂情報を渡す | glossary／style guide | [^S043][^S042][^S060] |
| P35 | 字幕・キャプションを物語情報の伝達経路にする | subtitle／caption spec | [^S044] |
| P36 | 改稿の依存資産と再作業範囲を見える化 **〔統合提案〕** | change request／dependency list | [^S047][^S011][^S043] |
| P37 | 連載・EAに適合するモジュール構造 | content modules／update plan | [^S011][^S012][^S013] |
| P38 | 物語パッチをpreview・正式版・セーブ互換で扱う | preview notes／save guidance | [^S014][^S015] |
| P39 | シーズン間で既存設定と制作責任を引き継ぐ | lore references／seasonal outline | [^S029] |
| P40 | ポストモーテムで道具・工程を変更する | lessons learned／tool backlog | [^S001][^S011][^S047] |
| P41 | 音楽を人物・世界・操作と接続する | character brief／theme sketches | [^S057] |
| P42 | 体験・整合性・運用の複数基準で判断 **〔統合提案〕** | test matrix／qualitative notes | [^S001][^S003][^S037][^S040][^S050] |

## 10. 導入・調査のための推奨テンプレート

本章は**調査結果を利用するための提案**であり、米国全社の実態記述ではない。導入する場合は、作品の規模・ジャンル・音声有無・継続運用の有無に応じて削る。

### 10.1 最小限の成果物セット

| 管理するもの | 最小限の項目 | 接続する先 |
|---|---|---|
| 体験の約束 | 誰に何を感じ・理解・行ってほしいか、避けたいこと | 評価質問と試作 |
| 生きたoutline | 行動、因果、場面の役割、未確定箇所 | 場面・クエスト・資産 |
| 人物と世界のガイド | 行動原理、関係、語彙、ルール、視聴覚上の制約 | 台詞・美術・操作・音楽 |
| 事実と根拠 | fact ID、作中時点、出典、語り手、scope、改訂 | ロア照会・カノン判断 |
| 実行する物語 | line／event ID、条件、結果、既読、優先、fallback | ゲーム状態・セーブ・試験 |
| 試験の記録 | 仮説、build、対象者・状態、観察、代替説明 | 変更要求と再試験 |
| 資産と改訂 | 原文、言語、音声等のID、意味変更、要再作業 | VO・翻訳・QA・公開 |
| 判断の履歴 | 何を変え／変えず、誰が、なぜ決めたか | 引継ぎ・次の制作サイクル |

### 10.2 物語のissueを文章修正へ即変換しない

```text
観察された症状
  → 知識不足か／操作か／UIか／人物の動機か／状態の不具合か
  → 仮説と、区別するための最小試験
  → 場面・ルール・配置・台詞・音声・情報提示のうち必要な変更
  → 元の状況で再試験
  → 残った問題と副作用を記録
```

Outer Wildsの情報過密、Portalの物語とレベルの相互調整、Yōteiの探索導入の改変は、台詞の追加だけで考えないための事例となる。[^S016][^S006][^S050]

### 10.3 責任の分け方

推奨するのは、役職名の定型化ではなく、①方向づけ、②内容執筆、③実行条件、④カノン／考証判断、⑤資産更新、⑥試験、⑦公開の各機能について、作成者・最終判断者・相談先・共有先をプロジェクト内で決めることである。一人が兼任してもよい。RiotのDNA、Bungieの共同レビュー、Hadesの具体的handoffは、それぞれ別の編成が成立する例である。[^S009][^S029][^S011]

### 10.4 面談・追加調査で尋ねると有用な質問

1. 直近に捨てた人物案・物語案は何か。誰が何を根拠に決めたか。
2. 初めて遊べたのは何ができる版か。文章だけのreviewとどう違ったか。
3. 一行の変更がどの資産・言語・条件へ波及するか。
4. 既存ロアと衝突したとき、検索する人と決める人は誰か。
5. 意図した謎と、単なる理解不足をどう区別しているか。
6. 自動試験に通るが、人間が見ると失敗する例は何か。
7. 稀な生成結果・欠員・順序違い・再訪をどう再現するか。
8. 公開後に物語を変える際、既読者とセーブをどう扱うか。
9. 前作の反省で、本文ではなく道具・責任・工程を何か変えたか。
10. 公開できない失敗・費用・労働条件が、成功事例の説明から何を欠落させているか。

## 11. 限界と今後の調査

1. **公開・成功事例への偏り**：発表できる成果、著名な作品、講演に参加できる職種が多い。中止作・失敗作・小規模受託・モバイル運用・スポーツ・教育等の範囲は薄い。
2. **英語資料中心**：多国籍・外部委託の現場を米国企業名だけで代表させる危険がある。地域・職種横断の面談が必要。
3. **自己報告と回顧**：企業広報、講演、取材は選択的に語られる。実際のチケット、版管理、観察、費用データとは異なる。
4. **確認範囲の限界**：多くは関連箇所を確認したもので、すべてのPDF画像・全文・動画を精読したのではない。S026／S059の一部チャンク、S045の要旨、索引しか残らない資料を区別した。
5. **独立性・件数**：55件は55社・55実験ではない。同じゲーム・同じ発表に由来する資料があり、件数を採用率に使えない。
6. **年代差**：古い基礎事例は2026年の組織・道具・雇用の証拠ではない。特にlive-serviceの体制は変わり得る。
7. **因果・定量の限界**：一般的なROI、最適人数、工数削減、適正スプリント長は算出できない。Yōteiの数値も統制された効果量ではない。
8. **学術レビューとしての限界**：事前登録、定型データベース全検索、完全な検索履歴の保存、複数独立コーダー、研究品質の二重評価は行っていない。再探索用のテーマと個別ソース台帳を残すスコーピング・カタログとして位置づける。
9. **歴史・表象の限界**：本稿は制作手順を調べたのであり、扱われる時代・文化に関する歴史学的な事実検証や当事者の受容研究を代替しない。
10. **生成AIの限界**：本資料で確認したルール／文法／作者制作イベントから、現在の生成AI活用の有無・普及率を推定できない。未調査を不使用の証明ともしない。

今後は、スタジオ規模・ジャンル・収益形態で層化し、中止・失敗も含めた複数事例の縦断観察を行うとよい。比較したいのは道具名だけではなく、変更から実装までの経路、判断の根拠、再作業の発生、学習が工程へ反映されたかである。頻度や効果を推定するには、本調査とは別の標本設計と一次データが必要となる。

## 12. 出典台帳と参考文献

### 12.1 JSONLを正本とする

`sources.jsonl` は**1行1資料のUTF-8 JSON**で、S001〜S061を固定IDとして使う。`publication_date`と`date_modified`、`accessed_on`、`review_extent`、`retrieval_scope`、`inclusion_status`を分けた。不明な著者・日付は、推測で埋めず空配列または`null`とした。DOI、巻号頁、版情報は確認できたものに付す。

`practices.jsonl` はP01〜P42の実務台帳で、構築対象、段階、説明、artifact、根拠ID、分析上のPDCA、限界を含む。両台帳を結合すれば、「作中史に関係する項目」「米国の実装事例」「要旨しか読めない資料」等を分けて取り出せる。データ項目の定義はREADMEとschemaを参照。

引用形式は、読みやすさのため**和文中の固定ID付き脚注＋著者・年月・題名・媒体・URL／DOI**とした。特定の学会スタイルに完全準拠するものではなく、必要に応じてJSONLから変換する。脚注の和文説明は意訳・要約である。

### 12.2 補助・除外の明示

| ID | 扱い | 理由 |
|---|---|---|
| S048 | 補助 | OEI Toolsに関する講演は索引要旨のみ。本体はメンテナンスへ転送 [^S048] |
| S051 | 補助 | Yōtei講演の公式索引は確認できるが直接session URLは404 [^S051] |
| S061 | 補助 | Telltale／Backlightのスポンサー付き講演は索引要旨のみ [^S061] |
| S030 | 除外 | Bungie一次記事の本文がcookie／SPA画面のみ [^S030] |
| S049 | 除外 | Avowed講演の一覧上の同定にとどまり、手法本文未確認 [^S049] |
| S052 | 除外 | ベンダー発表の転載先が403等で、本文未確認 [^S052] |

### 12.3 参考文献・参照資料

以下には採用55件に加え、透明性のため補助・除外も掲載する。掲載自体が本文の根拠として採用したことを意味しない。各脚注に使用区分と確認範囲を示す。

[^S001]: **S001** — Björn Berg Marklund; Henrik Engström; Marcus Hellkvist; Per Backlund. (2019-09-24). *What Empirically Based Research Tells Us About Game Development*. The Computer Games Journal / Springer; vol. 8(3), pp. 179–198. [原資料](https://link.springer.com/article/10.1007/s40869-019-00085-1)／[DOI](https://doi.org/10.1007/s40869-019-00085-1)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Abstract; §4.2.1 Methods in Theory and Execution; §5 Discussion and Conclusion。

[^S002]: **S002** — Henrik Engström; Jenny Brusk; Patrik Erlandsson. (2018-06-05). *Prototyping Tools for Game Writers*. The Computer Games Journal / Springer; vol. 7(3), pp. 153–172. [原資料](https://d-nb.info/1168140374/34)／[DOI](https://doi.org/10.1007/s40869-018-0062-y)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：PDF pp.1–3 / printed pp.153–155; §4 Method; §6 Conclusions。

[^S003]: **S003** — Robin Hunicke; Marc LeBlanc; Robert Zubek. (2004). *MDA: A Formal Approach to Game Design and Game Research*. AAAI Workshop on Challenges in Game AI; Proceedings of the AAAI Workshop on Challenges in Game AI, pp. 1–5. [原資料](https://users.cs.northwestern.edu/~hunicke/MDA.pdf)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：PDF pp.1–3: Introduction; MDA; MDA as Lens; Aesthetics。

[^S004]: **S004** — Henry Jenkins. (2004). *Game Design as Narrative Architecture*. First Person: New Media as Story, Performance, and Game / MIT Press; pp. 118–130. [原資料](https://web.mit.edu/~21fms/People/henry3/games&narrative.html)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Spatial Stories and Environmental Storytelling; Evocative Spaces; Enacting Stories; Embedded Narratives; Emergent Narratives。

[^S005]: **S005** — The W. Edwards Deming Institute. (n.d.（初出日未確認）). *PDSA Cycle*. The W. Edwards Deming Institute. [原資料](https://deming.org/explore/pdsa/)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：本文全体。根拠箇所：Plan / Do / Study / Act の説明; PDSA and PDCA。

[^S006]: **S006** — Kim Swift; Erik Wolpaw. (2008). *Integrating Narrative and Design: A Portal Post-Mortem*. Valve / GDC. [原資料](https://cdn.akamai.steamstatic.com/apps/valve/2008/GDC2008_PortalPostMortem.pdf)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：PDF pp.7,12–15,20–31,32–60。

[^S007]: **S007** — Elan Ruskin. (2012). *Rule Databases for Contextual Dialog and Game Logic*. Valve / GDC. [原資料](https://cdn.fastly.steamstatic.com/apps/valve/2012/GDC2012_Ruskin_Elan_DynamicDialog.pdf)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：PDF cover visually checked; PDF p.3; pp.34–36; pp.50–53; pp.83–98（特に98）。

[^S008]: **S008** — Matthias Worch; Harvey Smith. (2010). *What Happened Here? Environmental Storytelling*. GDC / Matthias Worch. [原資料](https://www.worch.com/files/gdc/What_Happened_Here_Web_Notes.pdf)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：PDF pp.1–3; environmental storytelling definition; Chain of Events; Puzzle Structures; conclusions。

[^S009]: **S009** — Illaoi Dev Team. (2022-08-01). */dev: Illaoi in Project L*. Riot Games. [原資料](https://www.riotgames.com/en/news/dev-illaoi-in-project-l)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Shaun Rivera introduction / DNA; Scott Hawkes champion brief; goals and guardrails; prototype revision。

[^S010]: **S010** — Riot Brightmoon; Meddler; Poisonpixxi; Riot Lexical. (2023-10-12). *TL;DW: Champs, Lore & More Dev Update*. Riot Games / League of Legends. [原資料](https://www.leagueoflegends.com/en-us/news/dev/tl-dw-champs-lore-more-dev-update/)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：本文全体。根拠箇所：Lore bullet list: shared canon; inconsistencies; updates over time。

[^S011]: **S011** — Darren Korb; Greg Kasavin. (2021). *Breathing Life Into Greek Myth: The Dialogue of HADES*. Supergiant Games / GDC. [原資料](https://media.gdcvault.com/GDC+2021/33103_Korb.pdf)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：PDF pp.4,11–12,16,21–22,27–28,30,32,34–36,40–42,44,46。

[^S012]: **S012** — Supergiant Games. (2018-12-07). *Hades FAQ*. Supergiant Games. [原資料](https://www.supergiantgames.com/blog/hades-faq/)。アクセス：2026-10-23（Asia/Tokyo）。 更新：2025-07-16。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Last Updated July 16, 2025; Early Access; characters and story; mythology sections。

[^S013]: **S013** — Supergiant Games. (2025-02-19). *HADES II: Strike True in The Warsong Update*. Supergiant Games. [原資料](https://www.supergiantgames.com/blog/hades2-warsong-update/)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：本文全体。根拠箇所：About the Update; Development Progress; Beyond the Final Confrontation。

[^S014]: **S014** — Supergiant Games. (2025-10-23). *Post-Launch Patch 1 Preview & Notes*. Supergiant Games / Steam. [原資料](https://steamcommunity.com/games/1145350/announcements/detail/505090299391902120)。アクセス：2026-10-23（Asia/Tokyo）。 更新：2025-10-30。
    使用区分：**採用**。確認：選択箇所。根拠箇所：How to Play the Patch 1 Preview; What’s In the Patch 1 Preview; Voice & Narrative。

[^S015]: **S015** — Supergiant Games. (2025-10-31). *Post-Launch Patch 1 Notes*. Supergiant Games / Steam. [原資料](https://steamcommunity.com/games/1145350/announcements/detail/499462068471074278)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Introduction; Highlights; Voice & Narrative; Bug Fixes。

[^S016]: **S016** — Alex（本文署名）. (2015-07-30). *Demaking Outer Wilds*. Mobius Digital. [原資料](https://www.mobiusdigitalgames.com/blog/demaking-outer-wilds)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：本文全体。根拠箇所：Archaeology In Space; It’s Only A Model; From Paper to Processing。

[^S017]: **S017** — Kelsey（本文紹介）. (2015-07-07). *A Very Narrative UPDATE!*. Mobius Digital. [原資料](https://www.mobiusdigitalgames.com/news/a-very-narrative-update)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Hearthian dialogue rewrites; Nomai history/culture discussion。

[^S018]: **S018** — Jason Grinblat; C. Brian Bucklew. (2017-08-14). *Subverting Historical Cause & Effect: Generation of Mythic Biographies in Caves of Qud*. ACM / Foundations of Digital Games 2017; Proceedings of the 12th International Conference on the Foundations of Digital Games, pp. 1–7. [原資料](https://www.freeholdgames.com/papers/Generation_of_mythic_biographies_in_Cavesofqud.pdf)／[DOI](https://doi.org/10.1145/3102071.3110574)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：PDF pp.1–6 §§1–5; §6 Future Work。

[^S019]: **S019** — John Harris. (2022-03-10). *Tapping into the potential of procedural generation in Caves of Qud*. Game Developer. [原資料](https://www.gamedeveloper.com/design/tapping-into-the-potential-of-procedural-generation-in-caves-of-qud)。アクセス：2026-10-23（Asia/Tokyo）。 更新：2023-11-20。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Interview: static backbone / procedural content; creators’ design goals。

[^S020]: **S020** — Freehold Games. (n.d.（初出日未確認）). *Caves of Qud Press Kit*. Freehold Games. [原資料](https://cavesofqud.com/press-kit/)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Factsheet; History; Features; Additional Links。

[^S021]: **S021** — Nate Austin. (2022). *Getting Players Emotionally Invested in Procedural Characters in Wildermyth*. Worldwalker Games / GDC. [原資料](https://media.gdcvault.com/GDC+2022/Speaker+Slides/GettingPlayersEmotionally_Austin_Nate.pdf)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：PDF pp.5–14: Names / History / Library of Plays; later pitfalls and conclusions。

[^S022]: **S022** — Wildermyth Wiki contributors（個別著者未確認）. (n.d.（初出日未確認）). *Writer’s Guide*. Wildermyth Wiki. [原資料](https://wildermyth.com/wiki/Writer%27s_Guide)／[固定版](https://wildermyth.com/w/index.php?title=Writer%27s_Guide&oldid=22450)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Lore; Heroes; Effects: Triggers, Targets and Outcomes; Tools; Stretching and Establishing new Content。

[^S023]: **S023** — Wildermyth Wiki contributors（個別著者未確認）. (n.d.（初出日未確認）). *Story Inputs and Outputs*. Wildermyth Wiki. [原資料](https://wildermyth.com/wiki/Story_Inputs_and_Outputs)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Particular Heroes; Ordering your Roles; Greenlighting your Story; Story Outcome Guidelines; Add History Lines。

[^S024]: **S024** — Wildermyth. (2019-08-30). *How To: Write your own Villain for Wildermyth — Part 2*. Worldwalker Games / itch.io. [原資料](https://wildermyth.itch.io/wildermyth/devlog/97578/how-to-write-your-own-villain-for-wildermyth-part-2)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Step 3: Test it; Step 6: write the comics; Step 8: play your story; fallback roles。

[^S025]: **S025** — Patrick Klepek. (2020-02-07). *‘Spider-Man’ Developers Want More People to Know How Games Are Written*. VICE. [原資料](https://www.vice.com/en/article/spider-man-developers-want-more-people-to-know-how-games-are-written/)。アクセス：2026-10-23（Asia/Tokyo）。 更新：2024-07-27。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Online database discussion; designers as writers; usability testing; story beat wall。

[^S026]: **S026** — 著者未確認. (n.d.（初出日未確認）). *Marvel’s Spider-Man: How Insomniac Spun Its Web*. GameSpot. [原資料](https://www.gamespot.com/articles/marvels-spider-man-how-insomniac-spun-its-web/1100-6464062/)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Into The Spider-Verse; A Superior Spider-Man（fetch_page chunk 0）。 通常取得は403、別経路の一部チャンクで確認。

[^S027]: **S027** — Naughty Dog. (2018-03-14). *Naughty Dog at GDC 2018*. Naughty Dog. [原資料](https://www.naughtydog.com/blog/naughty_dog_at_gdc_2018)。アクセス：2026-10-23（Asia/Tokyo）。 更新：2025-07-23。
    使用区分：**採用**。確認：本文全体。根拠箇所：Josh Scherr session description; David Shaver / Robert Yang blockmesh and lighting descriptions。

[^S028]: **S028** — Colin Stevens. (2019-03-22). *God of War’s Script Was Rewritten After a Year of Development — GDC 2019*. IGN. [原資料](https://www.ign.com/articles/2019/03/22/god-of-wars-script-was-rewritten-after-a-year-of-development-gdc-2019)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Script rewrite and Kratos / Atreus relationship paragraphs。

[^S029]: **S029** — Sam Chandler. (2023-07-03). *Destiny 2’s dev team talks crafting the narrative, dungeon challenges & more*. Shacknews. [原資料](https://www.shacknews.com/article/136140/destiny-2-story-dungeon-interview-2023)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Ultra-collaborative writers’ room; Kimberly Brooks; existing lore; seasonal development discussion。

[^S030]: **S030** — Bungie. (n.d.（初出日未確認）). *From Presage to Nightmares, the Cycle of Narrative Evolution*. Bungie. [原資料](https://www.bungie.net/en/News/Article/51794)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**除外**。確認：本文未確認。根拠箇所：本文取得不可（SPA / cookie shell）。 検索索引や転載断片は見えるが、一次本文を再確認できないため除外。

[^S031]: **S031** — Game Informer Editorial（現在の表示）. (2018-08-14). *A Look Inside How Blizzard Maintains World Of Warcraft’s Lore*. Game Informer. [原資料](https://gameinformer.com/2018/08/14/a-look-inside-how-blizzard-maintains-world-of-warcrafts-lore)。アクセス：2026-10-23（Asia/Tokyo）。 更新：2025-03-25。
    使用区分：**採用**。確認：選択箇所。根拠箇所：The Lorewalkers; Revisionist History; Book Worms。

[^S032]: **S032** — Anne Stickney. (2013-09-12). *A day in the life of Blizzard Historian Sean Copeland*. WoW Insider / Engadget. [原資料](https://www.engadget.com/2013-09-12-a-day-in-the-life-of-blizzard-historian-sean-copeland.html)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：What exactly is a historian?; expertise; lore reviews; internal resources。

[^S033]: **S033** — Andy Kelly. (2022-06-27). *Interview: Obsidian’s Josh Sawyer On Pentiment, A Historical Murder Mystery Where Your Choices Echo Through The Ages*. TheGamer. [原資料](https://www.thegamer.com/interview-obsidian-josh-sawyer-pentiment/)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Research / historians Christopher de Hamel, Edmund Kern, Winston Black; consequences across time。

[^S034]: **S034** — Bradly Shankar. (2022-11-08). *Obsidian unpacks the making of Pentiment’s choice-based historical narrative*. MobileSyrup. [原資料](https://mobilesyrup.com/2022/11/08/xbox-obsidian-pentiment-alec-frey-interview/)。アクセス：2026-10-23（Asia/Tokyo）。 更新：2022-11-09。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Research question; bibliography; consultants; accessibility / art discussion。

[^S035]: **S035** — Jakob Hansen. (2022-11-18). *How Obsidan brought the past to life in Pentiment*. Gamereactor. [原資料](https://www.gamereactor.eu/how-obsidan-brought-the-past-to-life-in-pentiment-1221583/)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Hannah Kennedy: historical advisers; art anomalies; house dressing / costumery。

[^S036]: **S036** — Giovanni Colantonio. (2022-11-15). *To make every choice matter, Pentiment rewrote the rules of narrative RPGs*. Digital Trends. [原資料](https://www.digitaltrends.com/gaming/pentiment-interview-alec-frey-choice/)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Lean team; Change over time; Less is more / persuasion system。

[^S037]: **S037** — Alexander Freed. (2015-06-29). *Six Metrics for Better Game Narrative*. Game Developer. [原資料](https://www.gamedeveloper.com/design/six-metrics-for-better-game-narrative)。アクセス：2026-10-23（Asia/Tokyo）。 更新：2026-08-17。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Introduction; metrics 1–6; branching choices caveat。

[^S038]: **S038** — Chris Kerr. (2023-03-22). *How to create functional narrative outlines that your team will actually read*. Game Developer. [原資料](https://www.gamedeveloper.com/marketing/how-to-create-functional-narrative-outlines-your-team-will-actually-read)。アクセス：2026-10-23（Asia/Tokyo）。 更新：2023-11-09。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Tyler Hutchison: living document; verb your characters; SO/BUT; production legibility。

[^S039]: **S039** — Bryant Francis. (2024-04-12). *How to build branching narrative without breaking the bank*. Game Developer. [原資料](https://www.gamedeveloper.com/design/how-to-build-branching-narrative-when-you-don-t-have-a-big-budget-)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Three pillars: consequential branching / theme / character definition; mixing methods。

[^S040]: **S040** — Choice of Games. (n.d.（初出日未確認）). *Testing ChoiceScript Games Automatically*. Choice of Games. [原資料](https://www.choiceofgames.com/make-your-own-games/testing-choicescript-games-automatically/)。アクセス：2026-10-23（Asia/Tokyo）。 更新：2026-03-19。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Quicktest; Randomtest; Detecting Dead Code; Fake Bugs; Hit Count; *bug。

[^S041]: **S041** — inkle / ink contributors. (n.d.（初出日未確認）). *Writing with ink*. inkle / public repository. [原資料](https://github.com/inkle/ink/blob/master/Documentation/WritingWithInk.md)／[固定版](https://raw.githubusercontent.com/inkle/ink/ff697147c10bf72a5d1339a1406d88f1dc59ab56/Documentation/WritingWithInk.md)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Knots; Diverts; Choices; Variables; Read counts; Conditional choices; Tunnels / Threads。

[^S042]: **S042** — Yarn Spinner contributors. (n.d.（初出日未確認）). *Localisation and Assets*. Yarn Spinner. [原資料](https://docs.yarnspinner.dev/yarn-spinner-for-unity/assets-and-localization)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Localisation Terminology; Workflow; Adding Line IDs; Line Provider。

[^S043]: **S043** — Richard Honeywood; Jon Fung; IGDA Localization SIG. (2012-02-01). *Best Practices for Game Localization（Second Draft / v2.2）*. IGDA Localization SIG; Second Draft, February 1, 2012 (filename v22). [原資料](https://igda-website.s3.us-east-2.amazonaws.com/wp-content/uploads/2021/04/09142137/Best-Practices-for-Game-Localization-v22.pdf)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：PDF p.1; pp.4–7 Culturalization; pp.20–24 Localization; pp.25–26 Project Planning; Appendix 1。 原稿は2012年、2021年は再掲パス。

[^S044]: **S044** — Microsoft Xbox Accessibility. (n.d.（初出日未確認）). *Xbox Accessibility Guideline 104: Subtitles and captions*. Microsoft Learn. [原資料](https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/104)。アクセス：2026-10-23（Asia/Tokyo）。 更新：2026-06-17。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Goal; Overview; speaker identification / audio cues; implementation guidance。

[^S045]: **S045** — Jonathan Dankoff; Elizaveta Shkirando. (2015). *Narrative Review Process: Getting Useful Feedback on Your Story*. Interactive Storytelling / ICIDS 2015 / Springer; Interactive Storytelling (ICIDS 2015), vol. 9445. [原資料](https://link.springer.com/chapter/10.1007/978-3-319-27036-4_17)／[DOI](https://doi.org/10.1007/978-3-319-27036-4_17)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：要旨のみ。根拠箇所：Publisher Abstract; authors and affiliations; Cite this paper。

[^S046]: **S046** — Dave Tach. (2015-03-05). *Ubisoft Montreal is feeding its writers criticism sandwiches*. Polygon. [原資料](https://www.polygon.com/2015/3/5/8140249/ubisoft-montreal-narrative-review-writers-clients-gdc-2015/)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Narrative review methodology; early testing; writer as client; feedback structure。

[^S047]: **S047** — Patrick Ewing; William Armstrong. (2017). *Do You Copy? Dialog System and Tools in Firewatch*. Campo Santo / GDC. [原資料](https://media.gdcvault.com/gdc2017/Presentations/Armstrong_Do_you_copy.pdf)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：PDF pp.1–3; event system / blackboards; tool chain; pp.62–70 Localization Schemata; pp.71–75 Lessons Learned / Further Work。

[^S048]: **S048** — Carrie Patel; David Szymczyk. (2019). *Technical Tools for Authoring Branching Dialogue*. Obsidian Entertainment / GDC. [原資料](https://gdcvault.com/play/1026384/Technical-Tools-for-Authoring-Branching)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**補助**。確認：索引のみ。根拠箇所：GDC indexed session abstract（本文はmaintenanceへ転送）。 補助候補のみ。講演本体・スライドは未確認。索引記述以上の機能評価・効果主張には使わない。

[^S049]: **S049** — David Benefield. (2025). *‘Avowed’ Branching Narratives: Shifting from QA Testing to Analyzing*. Obsidian Entertainment / GDC. [原資料](https://gdcvault.com/browse/gdc-25/)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**除外**。確認：索引のみ。根拠箇所：GDC 2025 browse index / search discovery。 一覧以外の一次本文未確認のため除外。二次紹介だけで内部QAの方法を再構成しない。

[^S050]: **S050** — Daniel New. (2026-03-26). *How Ghost of Yōtei got a ‘good old dose of narrative design’*. Thumbsticks. [原資料](https://www.thumbsticks.com/how-ghost-of-yotei-got-a-good-old-dose-of-narrative-design/)。アクセス：2026-10-23（Asia/Tokyo）。 更新：2026-04-08。
    使用区分：**採用**。確認：本文全体。根拠箇所：The Wrong Target; The Cone of Entry; A Shared Language; reported playtest result。

[^S051]: **S051** — Ariadna Martinez. (2026). *Meaningful Reasons to Wander: Creating Open World Engagement in 'Ghost of Yōtei'*. GDC Festival of Gaming. [原資料](https://schedule.gdconf.com/session/meaningful-reasons-to-wander-creating-open-world-engagement-in-ghost-of-ytei/914335)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**補助**。確認：索引のみ。根拠箇所：Search-indexed official session listing; session ID 914335。 補助候補。現在の検索一覧は2027年へ切替済み。索引要旨を講演本体または数値結果の独立検証とは扱わない。

[^S052]: **S052** — Backlight. (n.d.（初出日未確認）). *Backlight to Debut its Narrative Design Solution at GDC*. Business Wire / StreetInsider. [原資料](https://www.streetinsider.com/Business+Wire/Backlight+to+Debut+its+Narrative+Design+Solution+at+GDC/21350850.html)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**除外**。確認：本文未確認。根拠箇所：403 / challenge; search discovery only。 提供元の宣伝で独立検証なし。転載先も本文未取得のため除外。

[^S053]: **S053** — IGDA Game Writing SIG. (n.d.（初出日未確認）). *Game Writing*. International Game Developers Association. [原資料](https://igda.org/sigs/game-writing/)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Overview: writer tasks; additional responsibilities; membership。

[^S054]: **S054** — Ben Serviss. (2015-01-19). *Writing Interactive Fiction in Six Steps*. Choice of Games. [原資料](https://www.choiceofgames.com/2015/01/writing-interactive-fiction-in-six-steps/)。アクセス：2026-10-23（Asia/Tokyo）。 更新：2023-05-11。
    使用区分：**採用**。確認：本文全体。根拠箇所：Passes 1–6; Other Methods。

[^S055]: **S055** — Riot Games. (n.d.（初出日未確認）). *Gaming Industry Diversity and Inclusion at Riot Games*. Riot Games. [原資料](https://www.riotgames.com/en/diversity-and-inclusion/industry)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Authentic Storytelling & In-Game Representation。

[^S056]: **S056** — Erika “Riot Cashmiir” Haas. (2022-01-14). *Co-Developing Neon & Zeri*. Riot Games / VALORANT. [原資料](https://playvalorant.com/en-us/news/dev/co-developing-neon-zeri/)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：DNA introduction; shared origin / different reactions; Why Not?; cross-team collaboration。

[^S057]: **S057** — Riot Games. (2023-06-13). *The Making of a League of Legends Champion Theme*. Riot Games. [原資料](https://www.riotgames.com/en/news/creating-champion-themes-riot-games-music)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Opening DNA and composer collaboration; Making Milio’s Champion Theme。

[^S058]: **S058** — Nate Fox. (2025-05-15). *Ghost of Yōtei: How Sucker Punch chose Hokkaido for the game’s setting*. Sucker Punch Productions / PlayStation.Blog. [原資料](https://blog.playstation.com/2025/05/15/ghost-of-yotei-how-sucker-punch-chose-hokkaido-for-the-games-setting/)。アクセス：2026-10-23（Asia/Tokyo）。 更新：2025-06-11。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Opening research trips; cultural advisors; two Hokkaido trips; synthesis of setting and Atsu。

[^S059]: **S059** — Athirah Zaini; Allan Fowler; Robert Amor; Burkhard C. Wünsche. (2025-09-24). *Character-Driven Storytelling Design for Digital Games: A Scoping Review*. Games and Culture / SAGE. [原資料](https://journals.sagepub.com/doi/10.1177/15554120251380423)／[DOI](https://doi.org/10.1177/15554120251380423)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Publisher Abstract; Introduction / RQ1–RQ3（fetch_page chunk 0）。 通常取得は403、別経路の一部チャンクで確認。

[^S060]: **S060** — Game Developer. (2014-07-02). *Q&A: Double Fine’s Anna Kipnis digs into the mechanics of good dialog*. Game Developer. [原資料](https://www.gamedeveloper.com/audio/q-a-double-fine-s-anna-kipnis-digs-into-the-mechanics-of-good-dialog)。アクセス：2026-10-23（Asia/Tokyo）。 更新：2023-10-08。
    使用区分：**採用**。確認：選択箇所。根拠箇所：Scratch dialog; actor context / stage directions; holistic collaboration; system-aware writing。

[^S061]: **S061** — Zac Litton; Stephen Stanford. (n.d.（初出日未確認）). *Planning for Change: How Telltale Games Developed Their Modern Writing Pipeline (Presented by Backlight Gem)*. Telltale Games / Backlight Gem / GDC. [原資料](https://gdcvault.com/play/1033601/Planning-for-Change-How-Telltale)。アクセス：2026-10-23（Asia/Tokyo）。
    使用区分：**補助**。確認：索引のみ。根拠箇所：GDC indexed session abstract（本文はmaintenanceへ転送）。 スポンサー付きの補助候補。講演本体未確認で独立した効率改善の証拠とはしない。開催年は当該閲覧経路だけでは確定せずnull。


---

**配布範囲**：本稿、和文要約、メタデータ、分類、実務テンプレート、検証スクリプト。元の論文・スライド・記事の全文やPDFは同梱しない。著作権のある資料は掲載URLから閲覧されたい。外部ページの削除・改訂によるリンク切れは起こり得る。
