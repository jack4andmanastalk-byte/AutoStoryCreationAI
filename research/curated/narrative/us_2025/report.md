# 現代アメリカのストーリーテリング技法カタログ
## Storytelling Techniques in Contemporary America: A Source-Verified Catalog

**作成日 / Date:** 2026-10-22
**範囲 / Scope:** メディア横断(小説・創作、映画・TV脚本、ジャーナリズム、マーケティング、ポッドキャスト・音声、オーラル・パフォーマンス、ゲーム・インタラクティブ、コミックス)。現代(おおむね20世紀後半以降)に実務・教育・研究で継続的に用いられる技法を対象とし、現在も構成原理として生きている古典(キャンベル1949、Booth 1961、Swain 1965、Freytag 1863の英訳書等)を含む。
**成果物セット:**
1. 本レポート (`report.md`)
2. 出典メタデータ (`sources.jsonl` — 77件、1行1JSON)
3. 技法の構造化データ (`techniques.jsonl` — 83件、1行1JSON)

---

## 1. エグゼクティブ・サマリー / Executive Summary

本調査は、現代アメリカで実務・教育・研究として機能しているストーリーテリング技法を、**引用に耐える出典(学術論文、大学出版会書物、権威あるクラフト書、一次Web資料)**に紐づけてカタログ化したものである。収集した技法は**12カテゴリ83件**、参照ソースは**77件**(査読論文・会議録・学術書24、権威的クラフト・古典書32、産業・報道・辞書等21)。

主要な発見は次の通りである。

1. **構造論は「三幕構成」の単一モデルではない。** Syd Field [S23]が定式化した三幕構成は、Kristin Thompson (Harvard UP) の四部構造という実証的修正 [S12]、Frank Daniel 発祥の8シーケンス手法 [S28]、Blake Snyder の15ビート、John Truby の22ステップ、Dan Harmon の8ステップ円環、Kurt Vonnegut の「物語の形」に実証的裏付けを与えた6感情アーク研究 [S01] など、互いに競合・補完するモデル群として今日機能している。
2. **「没入 (immersion)」は、あらゆる分野で技法の説明原理として収斂している。** Gardner の「連続的な夢」[S30]、Green & Brock の narrative transportation [S02]、Stephens らの脳同期 [S03]、NPR の driveway moment [S60] は、ジャンルを超えて同一現象の異名であると整理できる。
3. **ジャーナリズムと小説の技法融合はアメリカの独自潮流**であり、Wolfe の4技法 [S40]→ Nieman 財団のナラティブ・ジャーナリズム [S41]→『Serial』以降の音声ドキュメンタリー [S62, S21] → NYT『Snow Fall』の没入型長編 [S58] と、連続した系譜をたどれる。
4. **読者・観客は「埋める存在」として設計に組み込まれている。** McCloud の closure [S43]、ゲームの創発ナラティブ [S20, S18]、トランスメディアの受動的消費の否定 [S55] は、受容者の能動性を設計原理とする共通の転回を示す。
5. **1990年代以降、物語は説得・マーケティングの工学となった。** Green & Brock の実証 [S02] を継承する StoryBrand [S44]、SUCCESs [S45]、STEPPS [S46] などのフレームワークは、認知科学と広告実務の橋渡しとして体系化されている。

以下、第4章で83の技法を出典付きで列挙し、第5章で横断的な解説を行う。引用は `[S##]` で `sources.jsonl` の `source_id` と対応する。

---

## 2. 収集方針と方法 / Methodology

### 2.1 収集対象の基準
- **現代的意義:** 米国のクリエイティブ産業、創作教育(MFA、映画学校)、ジャーナリズム実務、マーケティング実務、学術研究のいずれかで、20世紀末〜現在まで継続的に参照される概念・術語・形式であること。
- **命名可能性:** 固有の名称を持つ技法・構造モデル・概念であること(「三幕構成」のような一般化した用語を含む)。
- **出典の同定可能性:** 定式化者・原典・定義的文献を文献的に指摘できること。

### 2.2 ソースの階層(3層モデル)
各インスタンス(技法または語)に対して、最も権威の高い同定可能な出典を採用した。`sources.jsonl` の `tier` フィールドは次の区分である。

| tier | 種別 | 例 |
|---|---|---|
| 1 | 査読論文・学術会議・大学出版会(academic) | Reagan et al. 2016 [S01]、Mittell 2015 [S11]、Booth 1961 [S13] |
| 2 | 権威ある実務・クラフト書、古典(trade/classic) | McKee 1997 [S24]、Swain 1965 [S31]、Campbell 1949 [S22] |
| 3 | 産業記事・報道・辞書・一次Web資料(web/industry) | Hocking 2007 [S56]、Snow Fall [S58]、Merriam-Webster [S65] |

### 2.3 JSONLの仕様
- `sources.jsonl`: 1行=1出典。スキーマ: `source_id, type, tier, title, authors[], year, venue_or_publisher, doi, url, accessed_date, notes_ja, related_technique_ids[]`。`accessed_date` は 2026-10-22 統一。DOIは取得可能な場合に記録。
- `techniques.jsonl`: 1行=1技法。スキーマ: `technique_id, name_en, name_ja, category, origin_or_proponents, primary_source_ids[], summary_ja`。
- 両ファイルは本レポートの `[S##]` / `T##` IDと対応し、フィルタ・再集計に利用できる。

### 2.4 文献学的注意
- 技法の「原典」は必ずしも厳密な学術文献ではない(例: Pixarの22ルールは非公式ツイート集 [S35])。そのような場合は **普及経路そのものを一次的記録として記録** した。
- 辞書・Wikipedia型の参照 [S65-S74] は術語の定義水準を示すために限定使用し、その旨を `type: reference_entry` で明示した。
- 英米混在の取り扱い: カタログの中心は米国の実務・研究だが、米国で標準参照される英・欧の古典(Forster, Freytag, Aristotle等)は、米国の教育体系における古典として併記した。

---

## 3. 学術的意義(背景) / Why a source-verified catalog?

「アメリカの物語技法」を網羅する公開資料は、個別分野のクラフト書か断片的なブログ記事に散在し、品質の担保に乏しい。一方で、物語学(narratology)、メディア研究、説得研究は、同じ現象を別語彙で研究してきた(例: Gardner の「夢」= 認知科学の transportation)。本カタログは、(a) 術語の一次・二次出典を同定することで **引用可能性を確保** し、(b) tier により **利用者が証拠水準でフィルタ可能** にし、(c) 相互参照(技法 ↔ 出典)により、**実務と研究の往還** を可能にすることを目的とする。

---

## 4. 技法カタログ / The Catalog

凡例: **EN名(和訳名)**、定義、起源/定式化、現代的用法、主要出典 `[S##]`。

### A. 大構造のフレームワーク(Macro-Structure Frameworks)

**T01. Three-Act Structure(三幕構成)**
- 定義: 物語を Setup(設定)/Confrontation(対立)/Resolution(解決)に分け、第1幕終(~25%)と第2幕終(~75%)にプロット・ポイントを置く構造モデル。
- 起源: Syd Field『Screenplay: The Foundations of Screenwriting』(1979) が「パラダイム」として世界の脚本教育に定式化。
- 現代: 映画のみならずTV・長編小説の概説モデルとして標準。Thompson の四部構造 [S12] や Truby [S26] による批判・修正の基準点として常に言及される。
- 出典: [S23][S12][S67]

**T02. Four-Part Structure(四部構造)**
- 定義: 映画は実質的に setup → complicating action → development → climax(+epilogue) の4部からなるという実証モデル。
- 起源: Kristin Thompson『Storytelling in the New Hollywood』(Harvard UP, 1999)。David Bordwell の補強エッセイ [S67] と併せてハリウッド映画研究の標準見解。
- 現代: 三幕構成の「第2幕が長すぎる」問題の学術的解答として脚本実務にも逆輸入されている。
- 出典: [S12][S67]

**T03. Hero's Journey / Monomyth(英雄の旅)**
- 定義: 出発(Departure)→試練と選定(Initiation)→帰還(Return)の17段階にわたる普遍的神話パターン。
- 起源: Joseph Campbell『The Hero with a Thousand Faces』(1949)。「モノマイス」の語は Joyce より借用。
- 現代: Vogler [S27] による12段階化、Harmon による8ステップ円環化 [S37] を通じて、映画・TV・ゲーム・ブランド戦略の設計言語となった。
- 出典: [S22]

**T04. The Writer's Journey 12 Stages(作家の旅12段階)**
- 定義: キャンベルのモノマイスを脚本家具の12段階(Ordinary World→…→Return with the Elixir)に翻訳した実務モデル。併せて8アーキタイプ(後述 T40)を提示。
- 起源: Christopher Vogler の Disney 社内メモ(1985)を1985/1992/2007年の書籍で拡張。
- 現代: ハリウッドの開発部門(development)の共通言語。TVシリーズのキャラクター・アーク設計にも転用。
- 出典: [S27]

**T05. Save the Cat! Beat Sheet(15ビートシート)**
- 定義: Opening Image → Theme Stated → Set-Up → Catalyst → Debate → Break into Two → B Story → Fun and Games → Midpoint → Bad Guys Close In → All Is Lost → Dark Night of the Soul → Break into Three → Finale → Final Image の15ビートを指定頁位置に配置する設計図。
- 起源: Blake Snyder『Save the Cat!』(Michael Wiese Productions, 2005)。
- 現代: 公式サイト [S25] のビートシート・ライブラリとして産業化。映画分析から小説執筆(Save the Cat! Writes a Novel)まで拡張。
- 出典: [S25]

**T06. Truby's 22 Steps(トゥルービーの22ステップ)**
- 定義: 三幕構成を「機械的」と排し、ghost/weakness and need → desire → opponent → plan → battle → self-revelation → new equilibrium 等の22の有機的ステップで設計する体系。テーマ(道徳的主張)を設計の核心に据える。
- 起源: John Truby『The Anatomy of Story』(Faber & Faber, 2007)。
- 現代: ハリウッドの上級脚本コンサルティングの標準体系。「反転の連鎖(reveal sequence)」はプロット・ツイスト設計(T29)の直接の理論。
- 出典: [S26]

**T07. Seven-Point Story Structure(7点構造)**
- 定義: Hook → Plot Turn 1 → Pinch 1 → Midpoint → Pinch 2 → Plot Turn 2 → Resolution の7点と、try/fail cycles の連鎖で中盤を設計するモデル。
- 起源: Dan Wells の BYU 講義(2010)、Writing Excuses 7.41 [S38] で記録。
- 現代: SF/ファンタジーおよびナラティブ・ゲーム(RPG) 文化圏で標準的な講義動画として参照される。
- 出典: [S38]

**T08. The Story Circle(ストーリー・サークル)**
- 定義: You → Need → Go → Search → Find → Take → Return → Change の8ステップ円環。キャンベルをTVの1話サイズに簡約。
- 起源: Dan Harmon が Channel 101 で公表した「Story Structure 101」シリーズ(草稿) [S37]。
- 現代: 『Community』『Rick and Morty』の設計図として分析対象化され、ショーランナー教育の教材。
- 出典: [S37]

**T09. Sequence Approach(シーケンス手法)**
- 定義: 映画を8つの約10-15分シーケンス(2+4+2)に分割し、各シーケンスを独自の緊張と解決を持つ短篇として設計する手法。
- 起源: Frank Daniel(USC/Columbia の脚本教育) 発祥。Paul Gulino『Screenwriting: The Sequence Approach』(2004) が書籍化。
- 現代: 「第2幕たるみ」への標準処方。中級脚本コースの必須概念。
- 出典: [S28]

**T10. Freytag's Pyramid(フライタークのピラミッド)**
- 定義: 導入→上昇→頂点→下降→破局の五部で、劇の運動を対称的ピラミッドに図式化。3つの危機(exciting force 等)を含む。
- 起源: Gustav Freytag『Die Technik des Dramas』(1863)。英訳(1894, MacEwan訳)はパブリックドメイン [S51]。
- 現代: 米国の国語・創作教育における最も広く教えられるプロット図式であり、三幕構成・五幕構成の双方の理論的祖先。
- 出典: [S51]

**T11. Story Spine(ストーリー・スパイン)**
- 定義: "Once upon a time… / Every day… / But, one day… / Because of that… (×3) / Until finally… / And, ever since that day…" の8行雛形。
- 起源: Kenn Adams が1991年に即興演劇の練習具として考案。考案者自身が経緯を解説 [S36]。
- 現代: Rebecca Stockley 経由で Pixar に導入され、社内のピッチ(企画提示)の標準形に。Pixar 22ルールの第4条 [S35] としても存続。
- 出典: [S36][S35]

**T12. Pixar's 22 Rules of Storytelling(ピクサーの22ルール)**
- 定義: 「キャラクターの成功より挑戦に好感を持て」「結末を先に考えろ」「アイデアが頭から離れないなら書け」等の22の簡潔な心得。
- 起源: Pixar の元ストーリーアーティスト Emma Coats のツイート集(2011-12) [S35]。**公式規則ではない点に注意。**
- 現代: 創作教育・企業研修の引用集としてグローバルに流通。
- 出典: [S35]

**T13. The Story Grid / Foolscap Method(ストーリー・グリッド)**
- 定義: ① foolscap1枚による全体概要 ② 全シーンを値(value)転換・ビート・頁数で記録するスプレッドシートの2層で、「物語が機能するか」を診断する編集手法。ジャンルの必須場面(obligatory scenes)を重視。
- 起源: Shawn Coyne(25年の編集者)『The Story Grid』(2015)。
- 現代: 自費出版・プロ作家育成の標準ツール。ビート単位の客観化は McKee 系の継承。
- 出典: [S34]

**T14. Premise(プレミース)**
- 定義: 「悪は自滅する」のような、物語が証明すべき因果的主題命題。登場人物・対立・結末はすべて premise の証明のために配列されるという設計原理。
- 起源: Lajos Egri『The Art of Dramatic Writing』(1946版; Touchstone 1960)。
- 現代: Field のパラダイム以前の、テーマ主導型設計の思想的源流。Truby (T06) や Pixar の「story's spine 的テーマ」へ連なる。
- 出典: [S29]

**T15. Shapes of Stories / Six Emotional Arcs(物語の形/6感情アーク)**
- 定義: 時間軸に対する主人公の幸運度(ill fortune ↔ good fortune)の曲線として物語を捉えるモデル。実証研究は6類型(Rags to riches, Riches to rags, Man in a hole, Icarus, Cinderella, Oedipus)を抽出。
- 起源: Kurt Vonnegut の提唱(講義) [S64] → Reagan et al., EPJ Data Science (2016) が Project Gutenberg 大規模分析で検証 [S01]。
- 現代: 計算物語論(computational narratology) の代表作。構造化教育と機械分析の橋渡し。
- 出典: [S64][S01]

---

### B. プロット装置とビート単位の技工(Plot Devices & Beat-Level Craft)

**T16. Inciting Incident / Catalyst(発端事件)**
- 定義: 日常の均衡を破り、主人公に「追うべき目標」を課す最初の大事件。Snyder は Catalyst として頁位置を規定。
- 現代: 全構造モデルが必須の第1ビートとして有する。導入10分説は放映・配信の第1話設計に直結。
- 出典: [S23][S24][S25]

**T17. Plot Point(プロット・ポイント)**
- 定義: 物語の進行方向を不可逆反転する事件(PP1/PP2)。Field の幕構造の錨。
- 現代: McKee の turning point (value charge の変化) として精密化 [S24]。コミックや小説では「転換点」と訳される。
- 出典: [S23][S24]

**T18. Midpoint(ミッドポイント)**
- 定義: 物語中間点での虚の勝利/敗北(false victory/defeat)。stakes の上昇と「点の不可逆性」を与える。
- 現代: Field が初提唱後、Snyder の15ビートにも位置づく。Thompson の四部構造では development の開始点として映画史に定着 [S12]。
- 出典: [S23][S25][S12]

**T19. All Is Lost / Dark Night of the Soul(全失と魂の暗夜)**
- 定義: 第2幕終盤、計画の完全崩壊(All Is Lost)と、直後の内的絶望を経た変容準備(Dark Night)。「死のにおい」が漂うビートとして Snyder が規定。
- 現代: Structure の感情経路として広く踏襲。三幕構成の感情設計の標準語彙。
- 出典: [S25]

**T20. Setup and Payoff(セットアップとペイオフ/布石と回収)**
- 定義: 後の反転・解決に必要な要素を事前に配置し、観客に遡及的納得を与える原則。
- 現代: binge視聴・再視聴文化で「二周目設計」として戦略化。McKee/Cron 系で明示的に教授 [S24][S32]。
- 出典: [S24][S32]

**T21. Chekhov's Gun(チェーホフの銃)**
- 定義: 「一幕で銃を壁に掛けたなら、次幕で発射せよ。」要素の経済性(すべての要素に機能を持たせる)の原理。
- 起源: チェーホフの1889年書簡と同時代人の回想(参照: [S68])。
- 現代: 米国クラフト教育で setup/payoff の装飾法則として内在化。逆に「銃を撃たない」偽装型(red herring化)も運用される。
- 出典: [S68]

**T22. Ticking Clock(時限装置)**
- 定義: 「3日以内に」「30分で爆発」等、物語弧に明示的締切を与えて緊張を圧縮する装置。
- 現代: アクション映画のみならず単場面・連載の「次回期限味」としても実務化。Eboch の解説が代表的 [S75]。
- 出典: [S75][S23]

**T23. Cliffhanger(クリフハンガー)**
- 定義: 危機・反転直前で話を切断し、次回への復帰を誘導する装置。連続活劇(1930年代)に語源。
- 現代: 配信ドラマのエピソード末尾、ポッドキャストの分割 [S62]、縦読みコミックの必須装置。
- 出典: [S71]

**T24. MacGuffin(マクガフィン)**
- 定義: 登場人物の目的物でありつつ、その内容自体は観客にとって不重要な装置(政府の機密、フィガロ等)。
- 起源: Angus MacPhail 創案、Hitchcock が命名・普及(Hitchcock/Truffaut の対談で定義) [S54][S69]。
- 現代: ミッション駆動型アクション/スパイ物の標準語彙。「大事なのは銀時計の人生」的格言化。
- 出典: [S54][S69]

**T25. Red Herring(レッド・ヘリング/偽手がかり)**
- 定義: 結末の驚きを高めるため観客を意図的に間違った容疑・方向へ導く偽の手がかり。ミステリの fair play の内側で運用。
- 現代: whodunit 型TV・真実犯罪 [S62] の情報デザインの標準術語。
- 出典: [S72]

**T26. Deus ex Machina(デウス・エクス・マーキナ)**
- 定義: 劇内部的必然性を欠く外因による安易な解決。アリストテレス『詩学』以来の反則的装置。
- 現代: クラフトでは禁忌だが、メタ的使用(『Dodgeball』の "Deus Ex Machina" の金庫)やコメディでは自己言及的に運用。
- 出典: [S73]

**T27. Dramatic Irony(劇的アイロニー)**
- 定義: 観客が登場人物より多くを知る情報設計。言動に二重の意味を宿し、緊張(「知っていながら見ている」)と哀切を生む。
- 現代: ヒッチコック的サスペンス装置(「テーブルの下の爆弾」)の理論的土台。ホラー・コメディの標準機構。
- 出典: [S70]

**T28. In Medias Res(イン・メディアス・レス/途中から開始)**
- 定義: 時系列の途中から開始し、背景を後から開示する開始技法。ホラティウス『詩学』の術語。
- 現代: cold open(T35)・flashforward 冒頭と融合して『プレミアムTV』様式化。
- 出典: [S74]

**T29. Plot Twist(プロット・ツイスト)**
- 定義: 蓄積した前提を再解釈させる大規模な反転。公正な twist は「見えていたが読めていなかった」情報配置に依る。
- 現代: 『The Sixth Sense』以降の twist 映画、『Gone Girl』型スリラー、最終話反転のドラマで産業化。Truby の reveal sequence [S26] はその段階化の理論。
- 出典: [S26][S72]

**T30. Flashback / Flashforward(フラッシュバック/フォワード)**
- 定義: 語りの順序と物語時制のずれ(anachrony)を情報統制(誰がいつ何を知るか)に利用する技法。
- 現代: 『Lost』以後の複雑性TV [S11]、回想形式の現代小説、ドキュメンタリー音声での時制往還として常套化。
- 出典: [S14][S11]

**T31. Frame Narrative(枠物語)**
- 定義: 外枠の語りが内側の物語を導入・包囲する構造(『フゥランケンシュタイン』手紙枠等。回想形式)。
- 現代: 現代フィクションでは回想語り(『Forrest Gump』)、ドキュメンタリーの「この話は…」構造、ポッドキャストの司会者枠として存続。
- 出典: [S76]

---

### C. 米国TVシリーズの構造技法(Television Serial Craft)

**T32. Narrative Complexity(物語的複雑性)**
- 定義: 通常のエピソード形式と連続性を再定義し、パズル的時間構造、多重視点、反復、世界内「操作手引」(Lost の hatch、Westworld の loop)を恒常的に運用するTVの詩学。
- 起源: Jason Mittell『Complex TV』(NYU Press, 2015)。出版前草稿は MediaCommons で公開 [S11]。
- 現代: 「プレステージTV」の学術的規定語。ストリーミングの一話完結/連続の混在設計の理論枠組。
- 出典: [S11]

**T33. Antihero(アンチヒーロー/ディフィカルト・メンの時代)**
- 定義: 倫理的に問題のある主人公(共感を拒む)を中心に据え、視聴者に愛憎を強いる設計。
- 起源: HBO『The Sopranos』(1999)以後の第三期黄金期として Brett Martin『Difficult Men』(2013) が整理 [S49]。Mittell も viability として論じる [S11]。
- 現代: キャラクター駆動の連続ドラマの世界的標準となった米国の革新。
- 出典: [S49][S11]

**T34. A/B/C Storylines(A/B/Cストーリー構造)**
- 定義: 主軸(A:≈60%)、サブ(B:≈30%)、ランナー(C:≈10%)を1話内で並進させる配分構造。
- 現代: 脚本家チームの分業(それぞれが別ラインを担当)→統合の編集に適する運用形式としてネットワークTVに定着 [S77]。
- 出典: [S77]

**T35. Cold Open / Teaser(コールド・オープン)**
- 定義: タイトル・オープニング・クレジット前の物語直行部。視聴者の転換防止という産業起源の、のちの芸術的形式。
- 現代: シットコムの(non-sequitur ギャグ)、ドラマの flashforward 冒頭(『Breaking Bad』)、ミニシリーズの風景先行導入として多様化。
- 出典: [S66]

**T36. Bottle Episode(ボトル・エピソード)**
- 定義: 既存セット・最小キャスト・最小効果で制作する低コスト話。制約が濃密な人間劇を生む形式として再評価。
- 現代: 2019年に Merriam-Webster 採録(用法の定着の証左)。『Community』の幾つかの回は自己言及的実践。
- 出典: [S65]

---

### D. キャラクターの設計(Character)

**T37. Want vs. Need / Ghost / Lie(ウォントとニード/ゴースト/嘘)**
- 定義: 主人公の自覚的目的(want)と真に必要な内的変化(need)を分離し、その対立がテーマとアークを生む設計。need の起源を過去の傷(ghost)、誤信念(lie)で動機づける。
- 発展: Truby の ghost/need [S26] → Cron [S32]・Weiland [S33] の系統的クラフト化。
- 現代: アニメーション(ピクサー型)から連続ドラマまで、キャラクター・エピソード設計の標準言語。
- 出典: [S26][S32][S33]

**T38. Character Arc Types(アークの3類型)**
- 定義: Positive Change(嘘→真実)、Negative(真実放棄/堕落)、Flat(自己変化せず世界を変える触媒型)の3類型と各ビート対応。
- 起源: K.M. Weiland『Creating Character Arcs』(2016) の明確化。
- 現代: 商業小説教育・オタク的文法としても流通(e.g., 連載シリーズの「主人公不変」設計の正当化に Flat を使用)。
- 出典: [S33]

**T39. "Save the Cat" Moment(「猫を救え」モーメント)**
- 定義: 主人公の登場初期に小さな利他的行為を置き、観客の移入を獲得する。
- 現代: 頁位置決めの形式例として Snyder [S25] が命名。アンチヒーロー時代(T33)は「救わない猫」の設計として対置される(e.g., Walter White は犬を殺さないが人を殺す)。
- 出典: [S25]

**T40. Archetypes(アーキタイプ)**
- 定義: Hero, Mentor, Threshold Guardian, Herald, Shapeshifter, Shadow, Trickster, Ally 等、神話パターンに由来する機能的キャラクター類型。
- 起源: Campbell [S22]→ Vogler の実務化 [S27]。
- 現代: 開発会議での配役確認・ステレオタイプ批判の双方の語彙として使用。
- 出典: [S22][S27]

**T41. Unity of Opposites(対立物の統一)**
- 定義: 主人公と敵対者を「妥協不可能」な必然の関係で結びつけ、対立劇に内的強度を与える。
- 起源: Egri [S29]。
- 現代: 「ヴィラン設計=物語設計」というハリウッドの常識の理論的礎。
- 出典: [S29]

**T42. Flat vs. Round Characters(平面的/立体的キャラクター)**
- 定義: 単一性質で要約可能(flat)か、驚きと矛盾を含む(round)かの区別。Forster は flat の擁護(「一夫をを裒める」)も含意。
- 起源: E.M. Forster『Aspects of the Novel』(1927; 全文公開 [S52])。
- 現代: 米MFA・学部創作教育の標準術語。「side character は flat でよい」の実務判断に使用。
- 出典: [S52]

---

### E. 視点と語り(Narration & Point of View)

**T43. Point of View & Psychic Distance(視点と心的距離)**
- 定義: 視点の文法上の選択(一人称/三人称限定/全知)と、読者が「人物の頭内にいる度合い」を連続的に調整する(psychic distance) による没入制御。
- 起源: Gardner『The Art of Fiction』(1983) [S30]; 俯瞰的理論化は Booth [S13]。
- 現代: 「deep POV」への現代的移行(後述 T44 と連動)。視点違反(head-hopping)はワークショップの基準的批評語。
- 出典: [S30][S13]

**T44. Free Indirect Discourse / Narrated Monologue(自由間接話法)**
- 定義: 三人称・過去形の語りの外形を保ちながら、人物の口調・語彙で思考を呈示する混合形。
- 起源/権威: Dorrit Cohn『Transparent Minds』(Princeton UP, 1978) の narrated monologue 概念 [S15]。
- 現代: 限定三人称の没入感の正体を技術的に説明する道具として、deep POV 教育の理論的支柱。
- 出典: [S15]

**T45. Unreliable Narrator(信頼できない語り手)**
- 定義: 語り手の報告・解釈・評価が暗黙の作者の基準からズレていることを読者に読み取らせる構造。
- 起源: Wayne Booth 創出 [S13]。James Phelan が6類型(過少/誤報告×3軸)に精密化 [S16]。
- 現代: 『Gone Girl』『The Girl on the Train』型の home スリラーで産業的再流行。2重語り設計の規定概念。
- 出典: [S13][S16]

**T46. Stream of Consciousness / Interior Monologue(意識の流れ/内的独白)**
- 定義: 論理を飛躍させる思考の直接流通を模す技法(Cohn の quoted/autonomous monologue)。
- 権威: Cohn [S15]。
- 現代: 実験的书写とジャンル越境(一人称の内面ドラマ型スリラー)に継続使用。一人称過去形の「ぼくは…し、思った」からの深化として教授。
- 出典: [S15]

---

### F. 場面と文レベルの技法(Scene & Style)

**T47. Scene and Sequel(シーンとシークエル)**
- 定義: シーン(目標-葛藤-災難)で推進し、シークエル(反応-ジレンマ-決意)で処理と次目標の設定を行う交互運動。
- 起源: Dwight V. Swain『Techniques of the Selling Writer』(1965) [S31]。
- 現代: 商業フィクションのリズム教育学として、シーン删减・アウトライン化の判断基準。
- 出典: [S31]

**T48. Motivation-Reaction Unit(動機-反応ユニット/MRU)**
- 定義: 動機的刺激 → 感覚(1)→ 行動(2)→ 発話(3)の順序で文レベルの因果を設計する最小単位。
- 起源: Swain [S31]。
- 現代: 「show」の技術的正体として、体感のシーケンスを演習化(ワークショップで文の並替え訓練として使用)。
- 出典: [S31]

**T49. Show, Don't Tell(見せよ、語るな)**
- 定義: 抽象説明(「彼は怒っていた」)より場面・行動・細部(「彼はグラスを落とした」)での呈示。
- 学術的位置づけ: Booth (1961) が「評価的な tell」にも修辞的価値を認めた相対化以後、極端運用への警戒も教授 [S13]。Gardner の「連続的夢」の維持として再定義 [S30]。
- 現代: 米国創作ワークショップの第一標語。
- 出典: [S13][S30]

**T50. Vivid and Continuous Fictional Dream(鮮やかで連続的な夢)**
- 定義: よいフィクションは読者の中に「見取れる・途切れない夢」を作り、一切の技巧はそれを保つことに奉仕するという規範理論。
- 起源: Gardner『The Art of Fiction』(1983) [S30]。
- 現代: 没入の倫理として引用され続ける米国の創作美学の中心概念。認知科学の transportation(T53)と対応関係。
- 出典: [S30]

**T51. Iceberg Theory / Theory of Omission(氷山理論/省略の理論)**
- 定義: 書き手が十分に知っていれば、水面下の8/9を省略しても読者には伝わる。無知からの省略は「空洞」になる。
- 起源: Hemingway『Death in the Afternoon』(1932) [S53]。
- 現代: 米国散文美学(簡潔性・暗示・短編の切詰)の最有力模範。Raymond Carver 系 minimalism に継承。
- 出典: [S53]

**T52. Subtext(サブテキスト)**
- 定義: 台詞・行動の表層(text)の下で流れる真の欲求・感情。優れた場面は「言われたこと」ではなく「言われなかったこと」で駆動する。
- 権威: McKee『Story』の text/subtext 枠組 [S24](俳優・演出実践に由来する伝統の書物化)。
- 現代: 脚本自動チェック(「その場面のサブテキストは何か」)として企画会議の標準問。
- 出典: [S24]

---

### G. 認知・感情の科学(The Cognitive & Affective Science of Story)

**T53. Narrative Transportation(物語的トランスポーテーション/没入)**
- 定義: 注意・感情・表象が物語世界へ一体没入する状態。没入が信念と態度を物語と一致させる方向に変容させる。
- 権威: Green & Brock, JPSP (2000) [S02]。
- 現代: 説得的物語設計(広告・公共啓発)の中心的理論語。「没入させれば説得できる」の科学的根拠。
- 出典: [S02]

**T54. Neural Coupling(ニューラル・カップリング/脳同期)**
- 定義: fMRI上、成功した物語伝達では語り手と聞き手の脳活動が時間的に結合する。理解成功ほど同期が強い。
- 権威: Stephens, Silbert, Hasson, PNAS (2010) [S03]。
- 現代: 「物語は経験の転送装置」という直観の神経科学的証拠として、TED・教育実践に普及。
- 出典: [S03]

**T55. Oxytocin & the Dramatic Arc(オキシトシンと劇的アーク)**
- 定義: 劇的アーク(問題→葛藤→解決)を持つ物語映像が、注意(コルチゾル)→共感(オキシトシン)→行動的利他の鎖を引き起こす。
- 権威: Paul Zak, Cerebrum (2015) [S04]。
- 現代: NPO・企業ストーリーの「アーク必須性」の神経科学的根拠として普及(応用解釈の限界にも留意)。
- 出典: [S04]

**T56. Fiction as Social Simulation(社会的シミュレーションとしてのフィクション)**
- 定義: 物語は社会経験を抽象・圧縮したモデルであり、読者は没入的シミュレーションで社会認知を訓練する。
- 権威: Mar & Oatley (2008) [S06]; 進化的基盤は Boyd (2009) [S17]; 一般化は Gottschall (2012) [S50]。
- 現代: 「なぜ物語か」という問への最も影響力ある学術的回答セット。
- 出典: [S06][S17][S50]

**T57. Narrative Mode of Thought(物語的思考様式)**
- 定義: 人は論理-科学的様式とは別に、意図・正準性・時制で世界を組織する物語的様式を持つ。現実さえ物語として構成される。
- 権威: Jerome Bruner, Critical Inquiry (1991) [S05]。
- 現代: ブランディング・組織論・臨床(ナラティブ・セラピー)の理論的源流。
- 出典: [S05]

**T58. High-Arousal Emotions Drive Sharing(高覚醒感情の共有駆動)**
- 定義: 畏敬・怒り・不安の高覚醒感情は共有(バイラリティ)を促進し、悲しみは抑制する。
- 権威: Berger & Milkman, Journal of Marketing Research (2012) [S07]。
- 現代: 見出し設計・感情デザインのマーケティング標準(T70と接続)。
- 出典: [S07]

---

### H. ジャーナリズムとノンフィクション(Journalism & Nonfiction)

**T59. Inverted Pyramid(逆ピラミッド)**
- 定義: 最重要情報を先頭に、重要性順に配列する報道形式。
- 学術的再考: Pöttker (Journalism Studies, 2003) は起源を電信技術神話ではなく1880年代の編集実務に帰する [S08]。
- 現代: 速報・オンライン報道の検索性に継続適合。ナラティブ報道の対概念としても必須語彙。
- 出典: [S08]

**T60. Nut Graf(ナット・グラフ)**
- 定義: 「この記事は何について、なぜ読むべきか」を約束する要旨段落。逸話リードの直後に置く。
- 権威: WSJ 実務; Poynter の Chip Scanlan が定義を整理 [S59]。
- 現代: 物語化とニュース価値の橋渡し装置として全米の編集教育の標準。
- 出典: [S59][S39]

**T61. Anecdotal Lead & WSJ Formula(逸話リードとWSJ式)**
- 定義: 具体的人物の場面で開き、ナット・グラフで抽象化し、証拠と反証を交互に、再び人間の場面で閉じる(ダイヤモンド/円環)。
- 権威: William Blundell『The Art and Craft of Feature Writing』(1988) [S39]。
- 現代: 全米の特集報道の定型。「抽象のハシゴ」(T65)の運用形。
- 出典: [S39][S59]

**T62. New Journalism(ニュー・ジャーナリズムの4技法)**
- 定義: ① 場面ごとの構成 ② 完全な対話 ③ 人物の視点(他者の頭内から見せる) ④ 地位を示す細部(社会的地位の記録)。
- 権威: Tom Wolfe『The New Journalism』(1973) 序文とアンソロジー [S40]。
- 現代: 文学化した報道(Gay Talese, Joan Didion) の系譜として現在のナラティブ・ノンフィクションに直結。
- 出典: [S40]

**T63. Narrative (Literary) Journalism(ナラティブ・ジャーナリズム)**
- 定義: 事実の正確性を保ちながら長編の物語技法(アーク・場面・視点)で報じる制度的形式。
- 制度化: ハーバード Nieman 財団の会議とKramer & Call『Telling True Stories』(2007) [S41]。
- 現代: ピューリッツァー特集部門・全米誌の長報の質基準をこの伝統が規定。
- 出典: [S41]

**T64. Kicker(キッカー)**
- 定義: 記事の末尾に置く余韻の一撃(場面回収・引用・反転)。「結末は二度書く」(意味と感情)。
- 権威: Blundell [S39] および Poynter 系ツール [S42]。
- 現代: ニュース記事からニュースレターまで、スクロール文化の「最終行」設計。
- 出典: [S39][S42]

**T65. Ladder of Abstraction(抽象のハシゴ)**
- 定義: 具体(犬の名前、色)と抽象(制度、傾向)を意識的に往还させる文体技能。
- 権威: Roy Peter Clark『Writing Tools』ツール#30 [S42]。
- 現代: 記者・ノンフィクション作家の核心技能として教授。WSJ式(T61)の内部機構。
- 出典: [S42]

**T66. Immersive Multimedia Longform / Scrollytelling(没入型マルチメディア長編)**
- 定義: 長文と動画・対話グラフィック・アニメーションをスクロール連動で統合する形式。
- 画期: NYT『Snow Fall』(2012) [S58]。2013年ピューリッツァー特集部門。
- 現代: 各社の「ビジュアル企画」隊の標準企画形。『Snow Fall 化』は業界用語化。
- 出典: [S58]

**T67. Data Storytelling(データ・ストーリーテリング)**
- 定義: 可視化の選択、装飾除去、導入-対立-解決のナラティブ配置で、データを行動に接続する技術。
- 権威: Cole Nussbaumer Knaflic『Storytelling with Data』(Wiley, 2015) [S47]。
- 現代: 報道のデータ班と企業プレゼンの双方の標準化。
- 出典: [S47]

---

### I. マーケティングとブランド(Marketing & Brand)

**T68. SB7 Framework / StoryBrand(顧客をヒーローに)**
- 定義: ① 人物(顧客=ヒーロー) ② 問題 ③ ガイド(ブランド=Yoda) との出会い ④ 計画 ⑤ 行動喚起 ⑥ 失敗回避 ⑦ 成功の7要素でメッセージを明確化。
- 権威: Donald Miller『Building a StoryBrand』(HarperCollins Leadership, 2017) [S44]。
- 現代: 米国中小企業マーケティングの実務標準化。Campbell の実用的下位モデル。
- 出典: [S44]

**T69. SUCCESs Model(SUCCESs 6原則)**
- 定義: Simple / Unexpected / Concrete / Credible / Emotional / Stories を持つアイデアが記憶され伝播する。
- 権威: Heath & Heath『Made to Stick』(Random House, 2007) [S45]。
- 現代: 広告・教育・公益メッセージの品質チェックリスト。Stories は単なる装飾でなく行動の予行演習として位置づく。
- 出典: [S45]

**T70. STEPPS / Trojan Horse Stories(トロイの木馬型ストーリー)**
- 定義: Social currency / Triggers / Emotion / Public / Practical value / Stories の6原則。物語はブランド情報を内蔵する「木馬」として設計され、語られる過程でメッセージが伝達不可分になる。
- 権威: Berger『Contagious』(2013) [S46]; 実証的基盤 [S07]。
- 現代: バイラル設計の教科書。UGC・シェア設計の標準語彙。
- 出典: [S46][S07]

**T71. Transmedia Storytelling(トランスメディア・ストーリーテリング)**
- 定義: 1つの物語世界を複数メディアに分散し、各媒体が固有の貢献をする設計(完全消費に全プラットフォームを渡る必要はない)。
- 起源: Henry Jenkins, MIT Technology Review (2003) [S55]; 詳述は『Convergence Culture』(2006)。Mittell は transmedia 型複雑性として分析 [S11]。
- 現代: MCU・ゲーム・ARG連動のフランシズ設計の標準理論。
- 出典: [S55][S11]

---

### J. 音声・ポッドキャストとオーラル(Audio & Oral)

**T72. Anecdote + Moment of Reflection(逸話と省察の往還)**
- 定義: 逸話(この次この次…の連鎖)が動量を作り、省察(「これがなぜ重要か」を明示)が意味を与える。両者の交互が『This American Life』の公式。
- 権威: Ira Glass の講義/インタビュー [S61]。
- 現代: ポッドキャスト物語構成の最も影響力ある公式(説教の構造に似ると本人も言及)。
- 出典: [S61]

**T73. Serialized Audio Documentary(連載型音声ドキュメンタリー)**
- 定義: 1つの実在事件を複数エピソードで追い、進行中の調査プロセス自体を物語化。ナレーターの迷い・檎の「進行形」を含む。
- 画期: 『Serial』(2014) [S62]。倫理・音響・物論は McCracken 編 (Routledge, 2017) [S21]; ジャーナリズム形式論は Lindgren (2016) [S09]。
- 現代: ポッドキャストを大衆メディア化した形式的革新。true crime の倫理問題の基準言説も提供。
- 出典: [S62][S21][S09]

**T74. Driveway Moment(ドライブウェイ・モーメント)**
- 定義: 車を降りてもラジオを切れないほど音声の物語に聴き入る状態。
- 権威: NPR の概念として語の用法が定着 [S60]。
- 現代: 音声メディアの「没入の絶頂」の品質規準。TVでいう「viral clip」に相当する体験的指標。
- 出典: [S60]

**T75. Live First-Person True Story(The Moth 形式)**
- 定義: ノートなし・時間制限の舞台上での一人称実話。主題の明確さ・ステークス・語り手自身の変化を要件とする。
- 権威/組織: The Moth(1997〜) [S63]。
- 現代: 「個人を語る」競技型文化(StorySLAM)として全米化。企業コミュニケーション研修にまで浸透。
- 出典: [S63]

**T76. Five-Second Moment & Homework for Life(5秒の瞬間と日常訓練)**
- 定義: 語りの核心は大事件ではなく「認識が変わった5秒」にあり、日々その瞬間を記録する訓練(Homework for Life)で素材を蓄える。
- 権威: Matthew Dicks『Storyworthy』(New World Library, 2018) [S48]。
- 現代: ポッドキャスター・TED話者の実践教材。
- 出典: [S48]

---

### K. ゲームとインタラクティブ(Games & Interactive)

**T77. Environmental Storytelling(環境ストーリーテリング)**
- 定義: 空間そのものに物語情報を埋め込む設計(部屋の散らかり方、配置)。
- 系譜: Don Carson の Gamasutra 記事(2000) がテーマパークの作法をゲームに橋渡し [S57]; Jenkins が4形態(evocative/enacted/embedded/emergent)に整理 [S20]。
- 現代: AAAからインディーまで:「説明なしに世界を語る」の標準設計語彙。The Last of Us 等の死体・配置演出。
- 出典: [S57][S20]

**T78. Indexical Storytelling(指標的ストーリーテリング)**
- 定義: 痕跡(index; Peirce 意味論)を読み解くことでプレイヤーが過去の出来事を再構成する玩法。
- 権威: Fernández-Vara, DiGRA (2011) [S10]。
- 現代: walking simulator / 『Return of the Obra Dinn』 型の推理実装の理論化。
- 出典: [S10]

**T79. Embedded vs. Emergent Narrative(埋め込み型/創発型)**
- 定義: 設計者が予め配した物語(embedded) と、ルールとプレイから発生する物語(emergent) の区別。
- 権威: Jenkins (2004) [S20]; Janet Murray は procedural authorship として理論化 [S18]。
- 現代: サンドボックス・シム系設計の基礎対立軸。ストーリー部門とシステム部門の分業共通語。
- 出典: [S20][S18]

**T80. Multiform / Branching Narrative(マルチフォーム/分岐)**
- 定義: 単一線形を排し、選択に応じた複数経路・結末を提供する設計。目的は agency(自分の行為が意味を持つ感覚)の創出。
- 権威: Murray『Hamlet on the Holodeck』(1997; 更新版 2017) [S18]。
- 現代: 対話木・マスエフェクト型の基本構造。「再プレイ性の物語化」に接続。
- 出典: [S18]

**T81. Ludonarrative Dissonance(ルド・ナラティブ的不協和)**
- 定義: プレイ(ルールが教える倫理)とストーリー(物語が言う倫理)の矛盾。Hocking は BioShock におけるプレイヤー契約の裏切りとして定式化。
- 起源: Clint Hocking, Click Nothing (2007) [S56]。
- 現代: ゲーム批評の標準術語。『The Last of Us Part II』論争等で反復使用。
- 出典: [S56]

**T82. Procedural Rhetoric(手続き的レトリック)**
- 定義: 言葉・映像ではなく「ルールとプロセスの実行」で主張を組み立てる説得形式(シミュレーションによる議論)。
- 権威: Ian Bogost『Persuasive Games』(MIT Press, 2007) [S19]。
- 現代: 広告ゲーム、教育ゲーム、社会批評ゲーム(Darfur is Dying 等) の設計理論。
- 出典: [S19]

---

### L. コミックス(Comics)

**T83. Closure and the Gutter(クロージャーとガター)**
- 定義: コマ間の空白(gutter)を読者が想像で埋める能動的行為 = closure こそがコミックスの本質(「目に見えない芸術」)。トランジションの6類型(moment-, action-, subject-, scene-, aspect-, non-sequitur)で制御。
- 権威: Scott McCloud『Understanding Comics』(1993) [S43]。
- 現代: 「読者=共犯者」という設計思想はウェブトゥーン・ゲーム演出・配信の「chapter機能」にまで接続する、米国メディア理論の原点。
- 出典: [S43]

---

## 5. 組織的解説: カタログを貫く5つの軸 / Cross-Cutting Analysis

### 5.1 構造の多様化と「幕」への疑い
20世紀末の米国の物語設計は、「幕(act)」の自明性を次々と解体してきた。Field の三幕 [S23] は産業標準化の勝利だが、Thompson の四部構造 [S12] はハリウッド映画の実際の計測結果として三幕を修正し、Daniel/Gulino のシーケンス手法 [S28] は「幕の下位の運転可能な単位」を提供した。Snyder [S25] はこれらを再び1枚のビートシートに大衆化し、Truby [S26] はテーマ駆動の「非幕的」設計を対置した。さらに Vonnegut→Reagan 系 [S64, S01] は構造を「感情の時間曲線」として定式化し直した。構造論は今や **設計思想の違い(機械的/有機的/感情的)** の選択肢として機能しており、実務家はこれらを併用(ex. Trubyで設計→Story Gridで検証)する。

### 5.2 没入(immersion)の統一理論
Gardner の「鮮やかで連続的な夢」(T50) は、認知科学では narrative transportation [S02]、神経科学では speaker-listener coupling [S03]、生化学では Zak のオキシトシン [S04]、音声メディアでは driveway moment [S60] として、それぞれ独立に実証・概念化された。これらは **同一現象を説明言語だけ変えて言い直している** と考えるとカタログの見通しがよい。「show, don't tell」(T49)、Swain の MRU (T48)、Cohn の自由間接話法(T44)は、いずれも **没入を切らない技術の詳細** を提供する。ここに米国の物語研究の特色がある:「没入とは何か」を学際的に解明し、逆にそれを技術として設計可能にしてきた。

### 5.3 ジャーナリズムとフィクションの越境
Wolfe の4技法(T62) は「小説の技法をジャーナリズムへ」移すことで、20世紀後半の米国文化(magazine arts の黄金期)を作った。Nieman 財団 [S41] はこの営みを倫理と方法の両面で制度化し、『Serial』(T73) はその方法を音声に移管して倫理問題を物体化した [S21]。『Snow Fall』(T66) はこの越境をマルチメディアに拡張した。**フィクションは「真実感覚」の技術であり、ジャーナリズムは「事実の物語化」である** ⁠— この往還が米国のノンフィクション技術の本質である。

### 5.4 受容者の能動化: 観客は「空白を埋める者」
McCloud の closure (T83) は、受容者が常に物語を完成させるという原理の最もラディカルな陳述だが、同じ思想は、flashforward(T30)の意味補完、劇的アイロニー(T27)、トランスメディア(T71)における受動的消費の否定、ゲームの emergent narrative(T79)にまで及んでいる。**現代の米国的物語技術は、情報の「隠す穴」を設計し、受容者の能動性をそれで購う** という方向に進化した。「答えを教える」より「埋めさせる」方が没入とbateが深い、という calculate がある。

### 5.5 説得の時代の物語: マーケティング工学
Green & Brock の transportation(T53) は、説得としての物語の第一実証だった。以後、Heath 兄弟の SUCCESs(T69)、Berger の STEPPS(T70)、Miller の StoryBrand(T68) は、学術を直接ビジネスのフレームワークに落とし込み、米国で「ブランド=物語」という実務常識を作った。ここでの注目点は、各フレームワークが **キャンベル的普遍物語思想(T03)の産業適応形** だという点である。物語はもはや単なる娯楽の技術ではなく、説得工学であり、そしてその誤用(ビラの物語化)は premise(T14) の思想が既に予見していた倫理問題である。

---

## 6. 応用ガイド: 目的別の技法マッピング / Quick Mapping

| 目的 | 推奨技法の組合せ |
|---|---|
| 長編小説の設計 | T14 + T37 → T06/T07 で設計 → T47/T48 でシーン構築 → T49/T51/T52 で文を書く → T13 で検証 |
| 長編映画脚本 | T01/T02 のスケルトン + T16/T18/T19 のビート配置 + T20 による伏線管理 + T09 で第2幕を解痙 |
| TVシリーズ(フラッグシップ) | T32/T33 の世界設定 + T34 の話設計 + T35/T23 の冒頭・末尾装置 + T40 の配役確認 |
| 特集記事・長報 | T61 で構成 + T60 で約束 + T65 で文を往還 + T64 で締める + 必要時 T66 の企画化 |
| 企業プレゼン・広告 | T68 のSB7で主客整理 + T69/T70 で伝播設計 + T53/T58 の感情設計 + T67 のデータ語り |
| ポッドキャスト1話 | T72 の交互構造 + T75/T76 の素材学 + T74 を頂点として設計 |
| ゲームのナラティブ・デザイン | T77/T78 で世界を語らせ + T79 で埋込み/創発のバランス + T80 の経路設計 + T81/T82 で批評的健全性を監査 |

---

## 7. 限界と今後の課題 / Limitations & Future Work

- **出版記録の不完全性:** 多くの最重要理論(Booth, Cohn, Phelan)は大学出版会の書物であり、安定URLには JSTOR/出版社ページを使用した。契約・地域によってアクセス不可の場合がある。DOIは取得可能なものすべて記録した。
- **Web 一次資料の揮発性:** Hocking [S56] は Internet Archive、Harmon [S37] は Fandom wiki 経由である。原投稿の将来的消失に備え、アーカイブURLを併記した。『Pixar 22ルール』[S35] は Coats 本人の削除済ツイートの二次編集として記録した(公式ではなく「そのように受容された」もの)。
- **本カタログの非収録:** 詩(韻律・意象技法)、演劇の舞台技法、スタンドアップ・コメディ(ギャグ工学)、詞・音楽の語り、kishōtenketsu(起承転結)のような非西洋枠組、および最新の LLM による物語生成技術(これは技法でなく生成方式)。これらは将来の拡張対象。
- **米国の外的伝統との対比:** 本カタログは米国内の参照実態に従ったため、アリストテレス・Forster・Freytag のような欧米共有の古典は「米国での位置づけ」として記載している。

---

## 8. 出典一覧(Sources S01–S77)

完全な構造化情報は `sources.jsonl` を参照。以下は簡易一覧(区分: ①学術 ②クラフト/古典 ③産業/参考)。

| ID | 区分 | 主著者・タイトル(短名) | 年 | URL |
|---|---|---|---|---|
| S01 | ① | Reagan et al., "Emotional arcs...six basic shapes" | 2016 | https://link.springer.com/article/10.1140/epjds/s13688-016-0093-1 |
| S02 | ① | Green & Brock, transportation | 2000 | https://pubmed.ncbi.nlm.nih.gov/11079236/ |
| S03 | ① | Stephens, Silbert, Hasson, neural coupling | 2010 | https://www.pnas.org/doi/10.1073/pnas.1008662107 |
| S04 | ① | Zak, neuroscience of narrative | 2015 | https://pmc.ncbi.nlm.nih.gov/articles/PMC4445577/ |
| S05 | ① | Bruner, narrative construction of reality | 1991 | https://www.jstor.org/stable/1343711 |
| S06 | ① | Mar & Oatley, function of fiction | 2008 | https://journals.sagepub.com/doi/abs/10.1111/j.1745-6924.2008.00073.x |
| S07 | ① | Berger & Milkman, viral content | 2012 | https://journals.sagepub.com/doi/10.1509/jmr.10.0353 |
| S08 | ① | Pöttker, inverted pyramid | 2003 | https://www.tandfonline.com/doi/abs/10.1080/1461670032000136596 |
| S09 | ① | Lindgren, podcast journalism | 2016 | https://intellectdiscover.com/content/journals/10.1386/rjao.14.1.23_1 |
| S10 | ① | Fernández-Vara, indexical storytelling | 2011 | https://dl.digra.org/index.php/dl/article/view/512 |
| S11 | ① | Mittell, Complex TV | 2015 | https://nyupress.org/9780814769607/complex-tv/ |
| S12 | ① | Thompson, Storytelling in the New Hollywood | 1999 | https://www.hup.harvard.edu/books/9780674839755 |
| S13 | ① | Booth, The Rhetoric of Fiction | 1961 | https://press.uchicago.edu/ucp/books/book/chicago/R/bo5965941.html |
| S14 | ① | Chatman, Story and Discourse | 1978 | https://books.google.com/books/about/Story_and_Discourse.html?id=ewrOp9uPjYUC |
| S15 | ① | Cohn, Transparent Minds | 1978 | https://www.jstor.org/stable/j.ctvzxx9vd |
| S16 | ① | Phelan, Living to Tell about It | 2005 | https://books.google.com/books/about/Living_to_Tell_about_it.html?id=GDY5r0uecz0C |
| S17 | ① | Boyd, On the Origin of Stories | 2009 | https://www.jstor.org/stable/j.ctvjf9xvk |
| S18 | ① | Murray, Hamlet on the Holodeck | 2017 | https://mitpress.mit.edu/9780262533485/hamlet-on-the-holodeck/ |
| S19 | ① | Bogost, Persuasive Games | 2007 | https://direct.mit.edu/books/monograph/4392/Persuasive-GamesThe-Expressive-Power-of-Videogames |
| S20 | ① | Jenkins, Game Design as Narrative Architecture | 2004 | https://web.mit.edu/~21fms/People/henry3/games&narrative.html |
| S21 | ① | McCracken (ed.), Serial podcast volume | 2017 | https://www.routledge.com/The-Serial-Podcast-and-Storytelling-in-the-Digital-Age/McCracken/p/book/9780367887179 |
| S22 | ② | Campbell, The Hero with a Thousand Faces | 1949 | https://www.jcf.org/learn/joseph-campbell-heros-journey |
| S23 | ② | Field, Screenplay | 1979 | https://en.wikipedia.org/wiki/Screenplay_(book) |
| S24 | ② | McKee, Story | 1997 | https://books.google.com/books/about/Story.html?id=TShO0_ANhZAC |
| S25 | ② | Snyder, Save the Cat! | 2005 | https://savethecat.com/get-started |
| S26 | ② | Truby, The Anatomy of Story | 2007 | https://books.google.com/books/about/The_Anatomy_of_Story.html?id=hOrQQr1cx4QC |
| S27 | ② | Vogler, The Writer's Journey | 2007 | https://en.wikipedia.org/wiki/The_Writer%27s_Journey:_Mythic_Structure_for_Writers |
| S28 | ② | Gulino, Screenwriting: The Sequence Approach | 2004 | https://books.google.com/books/about/Screenwriting.html?id=ZKvMgETJxecC |
| S29 | ② | Egri, The Art of Dramatic Writing | 1946 | https://en.wikipedia.org/wiki/Lajos_Egri |
| S30 | ② | Gardner, The Art of Fiction | 1983 | https://www.kirkusreviews.com/book-reviews/john-gardner/the-art-of-fiction/ |
| S31 | ② | Swain, Techniques of the Selling Writer | 1965 | https://www.barnesandnoble.com/w/techniques-of-the-selling-writer-dwight-v-swain/1103673635 |
| S32 | ② | Cron, Wired for Story | 2012 | https://www.penguinrandomhouse.com/books/215504/wired-for-story-by-lisa-cron/ |
| S33 | ② | Weiland, Creating Character Arcs | 2016 | https://www.kmweiland.com/book/creating-character-arcs/ |
| S34 | ② | Coyne, The Story Grid | 2015 | https://books.google.co.uk/books?id=lp92CAAAQBAJ |
| S35 | ③ | Coats, Pixar's 22 Rules (compilation) | 2012 | https://www.tubefilter.com/2012/06/12/pixar-rules-of-storytelling/ |
| S36 | ③ | Adams, Back to the Story Spine | 2013 | https://www.aerogrammestudio.com/2013/06/05/back-to-the-story-spine/ |
| S37 | ③ | Harmon, Story Structure 101 | 2009 | https://channel101.fandom.com/wiki/Story_Structure_101:_Super_Basic_Shit |
| S38 | ③ | Wells, Seven-Point Story Structure | 2012 | https://writingexcuses.com/writing-excuses-7-41-seven-point-story-structure/ |
| S39 | ② | Blundell, Art and Craft of Feature Writing | 1988 | https://books.google.com/books/about/The_Art_and_Craft_of_Feature_Writing.html?id=oKCmRaLcug4C |
| S40 | ② | Wolfe, The New Journalism | 1973 | https://archive.nytimes.com/www.nytimes.com/books/98/11/08/specials/wolfe-journalism.html |
| S41 | ② | Kramer & Call, Telling True Stories | 2007 | https://www.penguinrandomhouse.com/books/298458/telling-true-stories-by-mark-kramer/ |
| S42 | ② | Clark, Writing Tools | 2006 | https://archive.org/details/writingtools50es0000clar_o1l7 |
| S43 | ② | McCloud, Understanding Comics | 1993 | https://en.wikipedia.org/wiki/Understanding_Comics |
| S44 | ② | Miller, Building a StoryBrand | 2017 | https://www.goodreads.com/book/show/34460583-building-a-storybrand |
| S45 | ② | Heath & Heath, Made to Stick | 2007 | https://www.gsb.stanford.edu/faculty-research/books/made-stick-why-some-ideas-survive-others-die |
| S46 | ② | Berger, Contagious | 2013 | https://knowledge.wharton.upenn.edu/article/contagious-jonah-berger-on-why-things-catch-on/ |
| S47 | ② | Knaflic, Storytelling with Data | 2015 | https://www.wiley.com/en-us/Storytelling+with+Data:+A+Data+Visualization+Guide+for+Business+Professionals-p-9781119002253 |
| S48 | ② | Dicks, Storyworthy | 2018 | https://books.google.com/books/about/Storyworthy.html?id=Xwx1swEACAAJ |
| S49 | ② | Martin, Difficult Men | 2013 | https://www.publishersweekly.com/978-1-59420-419-7 |
| S50 | ② | Gottschall, The Storytelling Animal | 2012 | https://books.google.com/books/about/The_Storytelling_Animal.html?id=Gd3lT5yP3ZQC |
| S51 | ② | Freytag, Freytag's Technique of the Drama (tr. MacEwan) | 1894 | https://archive.org/details/freytagstechniqu00freyuoft |
| S52 | ② | Forster, Aspects of the Novel | 1927 | https://www.gutenberg.org/files/70492/70492-h/70492-h.htm |
| S53 | ② | Hemingway, Death in the Afternoon (iceberg) | 1932 | https://en.wikipedia.org/wiki/Iceberg_theory |
| S54 | ② | Truffaut, Hitchcock/Truffaut (MacGuffin) | 1967 | https://en.wikipedia.org/wiki/Hitchcock/Truffaut |
| S55 | ③ | Jenkins, Transmedia Storytelling (Tech Review) | 2003 | https://www.technologyreview.com/2003/01/15/234540/transmedia-storytelling/ |
| S56 | ③ | Hocking, Ludonarrative Dissonance in Bioshock | 2007 | https://web.archive.org/web/20200114172154/https:/clicknothing.typepad.com/click_nothing/2007/10/ludonarrative-d.html |
| S57 | ③ | Carson, Environmental Storytelling (Gamasutra) | 2000 | https://www.gamedeveloper.com/design/environmental-storytelling-creating-immersive-3d-worlds-using-lessons-learned-from-the-theme-park-industry |
| S58 | ③ | Branch, Snow Fall (NYT) | 2012 | https://www.nytimes.com/projects/2012/snow-fall/index.html |
| S59 | ③ | Scanlan, The Nut Graf Part I (Poynter) | 2003 | https://www.poynter.org/archive/2003/the-nut-graf-part-i/ |
| S60 | ③ | NPR, Crafting Radio's Driveway Moments | 2008 | https://www.npr.org/2008/07/20/92716706/crafting-radios-driveway-moments |
| S61 | ③ | Ira Glass / Current, radio storytelling tips | 2016 | https://current.org/2016/02/tips-from-ira-glass-on-better-radio/ |
| S62 | ③ | Serial Productions (About) | 2014 | https://serialpodcast.org/about |
| S63 | ③ | The Moth (About) | 1997 | https://www.themoth.org/about |
| S64 | ③ | Open Culture, Vonnegut shapes of stories | 2014 | https://www.openculture.com/2014/02/kurt-vonnegut-masters-thesis-rejected-by-u-chicago.html |
| S65 | ③ | Merriam-Webster, "bottle episode" | 2019 | https://www.merriam-webster.com/dictionary/bottle%20episode |
| S66 | ③ | Merriam-Webster, "cold open" | — | https://www.merriam-webster.com/dictionary/cold%20open |
| S67 | ① | Bordwell, Anatomy of the Action Picture | 2007 | https://www.davidbordwell.net/essays/anatomy.php |
| S68 | ③ | Chekhov's gun (reference; cf. 1889 letter) | — | https://en.wikipedia.org/wiki/Chekhov's_gun |
| S69 | ② | OUPblog, In search of the MacGuffin | 2024 | https://blog.oup.com/2024/04/in-search-of-the-macguffin/ |
| S70 | ③ | Merriam-Webster, "dramatic irony" | — | https://www.merriam-webster.com/dictionary/dramatic%20irony |
| S71 | ③ | Merriam-Webster Wordplay, "cliff-hanger" | 2019 | https://www.merriam-webster.com/wordplay/where-cliff-hangers-come-from |
| S72 | ③ | Red herring (reference) | — | https://en.wikipedia.org/wiki/Red_herring |
| S73 | ② | U Hawaii CriticaLink, deus ex machina | — | https://www.english.hawaii.edu/criticalink/aristotle/terms/deus.html |
| S74 | ③ | Britannica, in medias res | — | https://www.britannica.com/art/in-medias-res-literature |
| S75 | ③ | No Film School, tension/ticking clock | 2025 | https://nofilmschool.com/build-tension-screenwriting |
| S76 | ② | Malewitz (OSU), What is a Frame Story? | — | https://liberalarts.oregonstate.edu/wlf/what-frame-story |
| S77 | ③ | TV Calling, A/B/C stories | 2019 | https://www.tv-calling.com/what-are-a-b-and-c-stories-in-screenwriting-tv-writing-101/ |

(注)「年」の空欄(—)は辞書・参考資料等で公開年を一意に特定できないもの。`sources.jsonl` の `year: null` と対応。

---

## 付録 A. JSONL スキーマ / Schema

### sources.jsonl
```json
{
  "source_id": "S01",              // 一意ID [S##]
  "type": "peer_reviewed_article", // 型(後述の型一覧)
  "tier": 1,                       // 1=学術, 2=権威書物/古典, 3=産業/参考/web
  "title": "...",                  // 正式タイトル
  "authors": ["..."],              // 著者配列
  "year": 2016,                    // 初出年(不明は null)
  "venue_or_publisher": "...",     // 掲載誌/出版社
  "doi": "10.1140/...",            // DOI(ある場合)
  "url": "https://...",            // 最も安定な公式/権威URL
  "accessed_date": "2026-10-22",
  "notes_ja": "...",               // 一意になる同定上の注意
  "related_technique_ids": ["T15"] // 関連技法
}
```
型一覧: `peer_reviewed_article`, `academic_journal_essay`, `conference_paper`, `academic_press_book`, `academic_book_chapter`, `academic_edited_volume`, `trade_book`, `trade_book_classic`, `classic_public_domain`, `interview_book_classic`, `lecture_and_podcast`, `magazine_article`, `industry_article`, `industry_interview`, `news_article`, `news_feature_multimedia`, `broadcast_segment`, `web_compilation`, `web_essay_primary`, `organization`, `reference_entry`, `reference_feature`, `scholarly_web_essay`, `scholarly_web_reference`, `university_web_page`。

### techniques.jsonl
```json
{
  "technique_id": "T01",           // 一意ID [T##]
  "name_en": "Three-Act Structure",
  "name_ja": "三幕構成",
  "category": "macro_structure",   // 12カテゴリのいずれか
  "origin_or_proponents": "Syd Field (1979)による范式化",
  "primary_source_ids": ["S23","S12","S67"],
  "summary_ja": "..."
}
```
カテゴリ: `macro_structure`(大構造), `plot_devices`(プロット装置/ビート), `tv_serial`(TVシリーズ), `character`(キャラクター), `narration_pov`(視点と語り), `scene_style`(場面と文), `cognition_emotion`(認知・感情), `journalism`(ジャーナリズム), `marketing`(マーケティング), `audio_oral`(音声・オーラル), `games`(ゲーム), `comics`(コミックス)。

---

*本カタログは引用目的での利用を想定しています。各出典の本文に当たる際は必ず一次資料をご確認ください。技法の記述は要約であり、各原典の精緻な議論を代替するものではありません。*
