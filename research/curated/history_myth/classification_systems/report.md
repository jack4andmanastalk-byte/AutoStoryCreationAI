# 物語・キャラクター・世界観構築に転用できる分類体系カタログ

**調査日：2026年10月23日**  
**対象：** 民間伝承の索引・型分類を中心に、物語構造・行為者分類、地域別索引までを収集。  
**付属データ：** [`catalog.jsonl`](catalog.jsonl)（10件、各レコードに分類概要・創作上の使い道・限界・出典URLを記録）

## サマリー

創作に転用しやすい分類体系は、同じ「物語分類」でも見ている単位が異なります。大きな筋の類似を探す**ATU**、筋を構成する要素を拾う**ThompsonのMotif-Index**、展開順序を見る**プロップ**、人物・制度・道具の関係を描く**グレマス**を組み合わせると、プロット・設定・役割の別々の層を扱えます。伝説や世界神話を重視する場合は**ChristiansenのML**と**Berezkin–Duvakin**、日本・中国の物語ではそれぞれの地域索引を補助線にするのが有効です。

特に実務的な出発点は、(1) ATUで筋の家族を探す、(2) Motif-Indexで使いたい要素を抽出する、(3) ProppまたはGreimasで因果・役割を再設計する、(4) 地域索引・原資料で文化的な位置づけを確認する、という四段階です。これは学術的な分類をそのまま「創作公式」にするのではなく、発想と比較の道具として使う方法です。

## 使い分け早見

| 何を考えたいか | 第一候補 | 使い方 |
|---|---|---|
| 既存の筋・物語型と異文 | ATU | 物語の大枠を照合し、変奏・反転の候補を得る |
| 魔法具、禁忌、試練、怪異など | Thompson Motif-Index | 要素を検索し、複数の筋へ組み替える |
| プロットの進行・転換点 | Propp | 機能の列として骨格を点検する（全機能を必須にしない） |
| キャラクター・組織・環境の利害 | Greimas | 主体／対象などの関係図を作る |
| 土地伝説・怪談・信仰 | Christiansen ML | 伝説型と地域ごとのローカライズを調べる |
| 世界神話の広域比較 | Berezkin–Duvakin | モチーフの地理的分布を比較する |
| 日本・中国の伝承の固有性 | 地域別索引 | ATUやThompsonに加え、地域内の型・異文を確認する |
| 寓話の短い型 | Perry Index | イソップ系寓話の型・異文を追う |

## 各体系の解説

### 1. Aarne–Thompson–Uther（ATU）—物語型

民話を、複数の異文にまたがって認識できる「物語型」として整理する番号体系です。全体の筋を単位にするため、似た筋の比較や既存伝承のバリアント探索に向きます。2024年版の案内では、国際的な型を複数の文化・国民集団に確認されるものとして扱い、型ごとに筋の要約・説明を付すとされています。[Folklore Fellowsの2024年版案内](https://www.folklorefellows.fi/ffc-284-286-2024-edition/)、[Harvardの分類ガイド](https://guides.library.harvard.edu/folk_and_myth/indices)。

**創作への転用：**「この筋はどの型の親類か」を考え、主人公・舞台・解決の仕方を入れ替えて変奏する。番号は作品に貼るラベルではなく、比較検索の入口として扱います。

### 2. Stith ThompsonのMotif-Index —物語要素

民話・神話・バラッド・寓話・伝説などに現れる要素を階層的に整理した索引です。ATUが「ひとまとまりの筋」を扱うのに対し、こちらはモチーフ（人物、物品、行為、状況など）を扱います。印刷版は6巻で、Indiana Universityの案内はその検索データベースが民間文芸のテーマ・モチーフ・人物・出来事を索引化すると説明しています。[Indiana University Libraries](https://libraries.indiana.edu/motif-index-folk-literature)、[Harvardの分類説明](https://guides.library.harvard.edu/folk_and_myth/indices)。

**創作への転用：**世界設定の素材集として使えます。たとえば「禁忌」「変身」「試練」「死者」「報酬」などを個別に探し、異なる伝承の要素を新しい因果関係に組み直す。ただし、要素を剥ぎ取るだけでなく、その出典文化での意味を確認するのが望ましいです。

### 3. プロップ『昔話の形態学』—機能と順序

プロップはロシアの魔法昔話を対象に、登場人物の行為が物語進行上果たす役割を「機能」として抽象化しました。31機能と7つの行為領域（敵対者、贈与者、援助者、王女／報酬、派遣者、主人公、偽主人公）がよく知られています。[Harvardの構造ガイド](https://guides.library.harvard.edu/folk_and_myth/indices)、[MIT掲載の原著抜粋](https://web.mit.edu/allanmc/www/propp.pdf)。

**創作への転用：**プロットを「状況の乱れ→旅立ち→試練／援助→対決→帰還・認知」のような機能列として整理し、欠けた因果や転換を点検する。原対象は限定されているため、31段階をあらゆる小説に当てはめないことが重要です。

### 4. グレマスのアクタンシアル・モデル—関係の図

物語内の具体的な人物名でなく、行為上の役割（アクタン）を6項に整理します。主体／対象、送り手／受け手、援助者／対抗者の3組です。人間だけでなく、道具・制度・環境も援助者や対抗者になり得ます。[Narrative Environmentsの解説](https://narrative-environments.github.io/CourseCompendium/Actantial-Model-Greimas.html)、[モデル解説PDF](https://www.revue-texto.net/Parutions/Livres-E/Hebert_AS/5.Actantial-Model.pdf)。

**創作への転用：**「誰が何を欲し、誰が開始し、誰が結果を受け取り、何が助け／妨げるか」を図にします。キャラクターの役割が一人に重なる設計や、環境・歴史制度を物語上の力として表現するのに有用です。

### 5. Christiansen Migratory Legends（ML）—伝説型

1958年にChristiansenがノルウェー資料を基礎に作った伝説型の索引です。SAMLAの説明によると、信仰伝説・歴史伝説を含み、ML番号を用いています。[SAMLAカタログ説明](https://samla.no/viewer/typekatalog/segn/)。

**創作への転用：**同じ怪異・伝説が地名や地形に適応して各地に伝わる仕組みを、ローカルな怪談、土地の記憶、噂の変種の設計に活かせます。ノルウェー起点の資料なので、そのまま世界標準とみなさないようにします。

### 6. Berezkin–Duvakin分析カタログ—世界神話・モチーフ分布

Thompsonの索引とは別の枠組みで、神話・口承伝承のモチーフと地域分布を比較する研究カタログです。研究紹介では、世界各地の口承テキスト要約と、宇宙論・起源・冒険・トリックスター等のモチーフ分布を扱うとされています。[カタログの構成と研究可能性](https://sisu.ut.ee/wp-content/uploads/sites/172/berezkin_folklore_and_mythology_catalogue_its_lay-1_out_and_potential_for_research.pdf)、[Boston Universityの索引ガイド](https://library.bu.edu/c.php?g=515642&p=3525314)。

**創作への転用：**世界の起源譚や文化圏別の神話要素を比較し、同一要素の分布をもとに接触・伝播・異伝を考える。ただし、分布の一致だけで直接の影響関係を断定することはできません。

### 7. 日本の昔話型索引—柳田・関・池田・稲田など

日本の昔話研究には、柳田國男の『日本昔話名彙』に関連する型整理のほか、関敬吾・池田弘子・稲田浩二らの異なる索引・コーパスが存在します。Indiana University Pressの英訳ガイドは347の型と日本国内の異文分布を掲げ、池田のタイプ／モチーフ索引についても説明しています。[Yanagitaガイド](https://publish.iupress.indiana.edu/read/the-yanagita-kunio-guide-to-the-japanese-folk-tale/section/845d6b10-b29a-4f70-9095-44cbe21c81c7)、[稲田の索引に関する書評](https://asianethnology.org/article/1051/download)。

**創作への転用：**日本を舞台とする物語で、全国的な型だけでなく地域異文や採録史を踏まえるために使います。分類番号や体系が複数あるため、出典ごとの対応関係を記録してください。

### 8. 中国民間故事のタイプ索引群

Wolfram Eberhard、Ding Naitong、Jin Ronghuaらによる中国民間故事のタイプ索引があります。中国の物語を国際型と地域固有型の両方から扱う研究の蓄積を示しています。[Folklore Fellows掲載の研究資料](https://www.folklorefellows.fi/wp-content/uploads/Tsetsenmunkh.pdf)、[Thompson索引序文（他地域索引への言及）](https://en.wikisource.org/wiki/Motif-Index_of_Folk-Literature/Volume_1)。

**創作への転用：**中国語圏の物語をATUだけで代表させず、地域内の型分類・異文を探す入口になります。各書の採録範囲・番号は別々なので、参照する版を明記します。

### 9. Perry Index—寓話型

イソップ系寓話を識別する専門索引です。一般的な世界観分類ではなく、短い寓話の型・異文・出典を追う用途に向きます。SurLaLuneは同サイトの分類にPerry分類も含めるとしています。[SurLaLuneデータベース概要](https://www.surlalunefairytales.com/about.php)。

## 実務での組み合わせ方

1. **狙いを決める：**筋の比較ならATU、要素の探索ならMotif-Index、役割図ならGreimas、順序の検討ならProppを選ぶ。
2. **素材を出典と一緒に記録する：**分類番号だけでなく、資料名・採録地・語り手／版・翻訳・アクセス日を残す。
3. **組み換える：**一つの型をそのまま再話せず、主人公の動機、対価、禁忌、解決、語り手の立場など複数の軸を変える。
4. **地域性を補う：**日本・中国など舞台となる文化圏に対応する索引と一次資料を照合する。
5. **分類を仮説として扱う：**物語が複数型にまたがる、既存分類に収まらない、という状態は欠陥ではありません。分類は創作物の価値判定ではなく、比較の足場です。

## 調査上の注意・範囲

- これは「創作に転用できる可能性」を基準に選んだ初期カタログです。網羅的な書誌ではありません。
- URLはアクセス可能な公式機関・大学図書館・学術資料を優先し、各レコードにも出典を格納しました。資料の全文閲覧は所蔵・地域・利用条件に左右されます。
- ATUやThompsonのMotif-Indexを「世界中の物語すべてを中立に網羅する分類」と扱うべきではありません。地域索引や原資料を併用することで、偏りや分類の粒度を補います。
- JSONLは1行1レコードのUTF-8 JSONです。行単位で読み込めるよう、各体系を独立オブジェクトとして記録しています。

## 主な参照先

- [Harvard Library: Folktale Classification and Structure](https://guides.library.harvard.edu/folk_and_myth/indices)
- [University of Washington Libraries: Tale Type & Motif Indexes](https://guides.lib.uw.edu/research/folklore/motif)
- [Folklore Fellows: 2024 ATU edition](https://www.folklorefellows.fi/ffc-284-286-2024-edition/)
- [Indiana University Libraries: Motif-Index](https://libraries.indiana.edu/motif-index-folk-literature)
- [SAMLA: Migratory Legends](https://samla.no/viewer/typekatalog/segn/)
- [Boston University: folklore indexes](https://library.bu.edu/c.php?g=515642&p=3525314)
