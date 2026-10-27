# U-03 dogfood: 実応答だけで3章を完走した記録

標準フロー（`scripts/story_project.py`）を、**実応答**で1作品ぶん回した記録。
題材と制約だけを人間が決め、世界・歴史・人物・関係・物語構造・場面・文体・本文の14件を
Arena のセッション内で生成し、relay 形式（`<<<ANSWER タグ>>>`）で逐語的に取り込んだ。
モデル応答の捏造はしていない。スクリプト化された台本（U-02）ではなく、ここで初めて
「読める原稿が出るところまで」を通した。

- 原稿: [`manuscript.md`](manuscript.md)（`render` の出力、SHA-256 `09727401b2ae98cef68b72cfc8a1199043560d28a23930165e617cac93af952c`）
- 作品ディレクトリ: `work/prj-mine/`（project.json・nodes・relay。`runs/` は `.gitignore` 対象）
- 全14件の応答の逐語: `work/prj-mine/relay/responses/`
- `answers.txt` は**最終ラウンドの貼り付けだけ**を残している（各ラウンドで1件ずつ上書きした）。

## 題材と条件

| 項目 | 内容 |
| --- | --- |
| 題名 | 宛名のない手紙 |
| premise（人間が指定） | 閉山した銅山の町。最後の坑道に残された、宛名のない手紙を届ける郵便配達員の話。手紙は三通あり、差出人はいずれも同じ人物。町の公式記録と、年寄りたちの記憶は食い違っている。 |
| 章数 / 1章の目安 | 3章 / 900字 |
| 場所と日付 | 尾根野（閉山15年）、沢渡（役場の支所、歩いて2日） |
| 人物 | 佐伯スミ34（郵便配達員）・大庭源太郎78（源じい）・野々宮あおい26（沢渡支所の記録係）・三村トオル30（15年前に死亡、三通の差出人） |
| 事実 | F-01 三通は差出人が同じで宛名がない／F-02 公式記録の死者は零／F-03 トオルは事故当日に入坑していない |
| 伏線 | fs-001 切手のない手紙（ch01→ch03）・fs-002 源じいが言いよどむ理由（ch01→ch02）・fs-003 零の死者欄（ch02→ch03） |
| 文体 | third人称、視点=佐伯スミ、禁止表現 b1運命・b2奇跡・b3「涙が…」 |

## 実行したこと（Arena セッション内で完結）

```bash
.venv/bin/python scripts/story_project.py --root experiments/2026-10-dogfood-01/work \
  init --project-id prj-mine --title 宛名のない手紙 --chapters 3 --target-chars 900 --premise "…"
.venv/bin/python scripts/story_project.py --root experiments/2026-10-dogfood-01/work run prj-mine   # exit 3

# 以降は 1 ラウンド = 「待ちを知る → 応答を書く → submit」の繰り返し
.venv/bin/python scripts/story_project.py --root experiments/2026-10-dogfood-01/work relay status prj-mine
#   → Next request: tag <8hex> (<purpose>)
.venv/bin/python scripts/story_project.py --root experiments/2026-10-dogfood-01/work \
  relay submit prj-mine --file experiments/2026-10-dogfood-01/answers.txt

.venv/bin/python scripts/story_project.py --root experiments/2026-10-dogfood-01/work \
  render prj-mine --out experiments/2026-10-dogfood-01/manuscript.md
.venv/bin/python scripts/story_project.py --root experiments/2026-10-dogfood-01/work doctor prj-mine
```

`init` のオプション名は実際に使ったもの。`relay status` は生成せず、`submit` は記録済みの
応答を作り直さない（U-02 のテストが固定している）。

## 結果

- **14ラウンドで complete**（plan 1・設計 11・本文 3）。設計が11なのは修復が2回入ったため。
- `submit` の最終出力: `Stages: plan=done, design=done, draft=done` / `Relay: 14 answered / 0 pending / 14 request(s) recorded` / exit `0`。
- `doctor`: `findings: 0 (errors=0, warnings=0, info=0)`、`project/node_tree/revisions/checkpoints/links/world/runs` すべて pass、`runs: 17 (interrupted 0)`。
- `render`: 3章・本文合計 2,110字（マーカー込み 2,531字）。

| # | purpose | タグ | 修復 |
| --- | --- | --- | --- |
| 1 | `plan` | `AA177E3C` | |
| 2 | `design:brief` | `7F1A1B59` | |
| 3 | `design:world` | `9CCE16F7` | |
| 4 | `design:history` | `C1243E87` | |
| 5 | `design:character` | `3C036510` | speech.sample が30字未満 |
| 6 | `design:character:repair` | `71D64E0E` | ← 修復 |
| 7 | `design:relation` | `9AD03B2B` | |
| 8 | `design:plot` | `67C0038D` | |
| 9 | `design:scene` | `E0BABEF0` | planted に canon の布石ID |
| 10 | `design:scene:repair` | `E284E2A3` | ← 修復 |
| 11 | `design:voice` | `01BFBFCF` | |
| 12 | `draft:ch01` | `EAFDAF65` | |
| 13 | `draft:ch02` | `A4DC8CA4` | |
| 14 | `draft:ch03` | `B484AF7A` | |

## 本文の実測

| 章 | 作中 | 場所 | 本文（マーカー・空白除く） | 目安との比 |
| --- | --- | --- | --- | --- |
| ch01 | 1日目 | 尾根野 | 647字 | 72% |
| ch02 | 3日目 | 沢渡 | 668字 | 74% |
| ch03 | 5日目 | 尾根野 | 795字 | 88% |

- マーカーは依頼どおり冒頭の `{{time: …}}{{location: …}}`、`{{learn: …}}`、`{{foreshadow: … setup|payoff}}` だけで、情景説明には使っていない。
- 伏線は ch01 で fs-001/fs-002 を張り、ch02 で fs-002、ch03 で fs-001/fs-003 を回収した。設計メモの幕（setup/turn/close）と転換点 t1〜t3 の選択も、章ごとに1つずつ踏んでいる。
- 幕・転換点・場面・伏線の対応は**設計どおりに収まっている**が、これは「矛盾しない」という意味であって、面白さの主張ではない。

## 摩擦ログ（F-18〜F-26）

分類: 完走（導線）／本文（生成物）／編集（修正の経路）／運用（記録の残し方）。
F-17 までは U-02 の記録（`experiments/2026-10-u02-relay-round-t01/note.md`）。

### 完走

- **F-18 ラベルが二重に出る**（修正済み）。`Next request: tag A4DC8CA4 (draft: draft:ch02)`。
  `purpose` が既に stage を含むのに、表示側が stage を前置していた。`relay submit` の
  報告にだけ出る表示バグで、進行には影響しない。表示を `purpose` だけにし、テストで
  `draft: draft:` / `design: design:` が出ないことを固定した（docs の実例も直した）。
- **F-19 待ちの正が2箇所に見える**（記録のみ）。`relay/index.json` の `pending` は
  `relay export` 時点の控えで、取り込み後も更新されない。完成後も最後の依頼が
  `pending` に残っていた。コードは変えず、quickstart / standard_flow / project の3箇所に
  「待ちの正は `relay status`」と明記した。
- **F-20 1ラウンドの読み込み量**（変更なし）。応答を書くには `relay/requests/<key>.json` の
  `prompt` 全文を読む必要がある。設計の依頼は台帳 JSON を含むため1件 3〜5KB、本文の依頼は
  前章の末尾も入る。14ラウンドで延べ十数万トークン程度の読み込みになった。`relay status` が
  `request:` のパスを出すので迷いはしない。圧縮（要約版プロンプトの併記）は、まず実害の
  測定が要るので今回は入れていない。
- **F-21 貼り付けファイルは1件ずつ上書きで足りる**（問題なし）。`submit` は毎回ファイル全体を
  解析するが、1件だけ書いても、全件を溜めて書いても同じ結果になる（冪等性は U-02 の
  `test_relay_round.py` が固定）。今回は各ラウンドで上書きしたため、`answers.txt` には
  最終ラウンドの1件だけが残る。

### 本文

- **F-22 目安字数は助言で、警告が `draft.json` に埋もれていた**（修正済み）。900字の目安に
  対し実測 647/668/795字（72〜88%）。`draft.py` は既に `warnings_ja` に「目安 900〜900 字の外」
  と書いていたが、`relay status` / `relay submit` には出ていなかった。完成後の round 報告に
  `Warnings:` として表示するようにした（失敗にはしない）。
- **F-23 場面設計の `foreshadows.planted` の条件が依頼文に書かれていなかった**（修正済み）。
  character の「口調サンプルは 30 字以上」は既に依頼文にあった（見誤りによる修復）。一方、
  scene の `planted` に canon の布石 ID を書かない条件は依頼文に無く、修復1往復の原因だった。
  `prompts/design-scene.md` を **v1.1** に上げ、「`planted` には canon の布石 ID を書かない
  （新規がなければ `[]`）」を明記した（完了済み run / relay は触っていない）。
- **F-24 誤字を機械は拾わない**（記録のみ）。ch01 に簡体字「开」が1箇所混入した（「すぐには
  开けなかった」）。`doctor` は pass。応答は逐語で取り込む約束なので、書き換えずに残した。
  直すなら `revise --chapter ch01` で新しい revision を作る（未実施）。

### 編集・運用

- **F-25 `Manuscript:` は既定パスしか見なかった**（修正済み）。`relay status` は従来
  `work/prj-mine/manuscript.md` しか見ず、別パスへ `render --out` したときも「(not written yet)」
  と表示していた。`render --out <path>` 実行時にノード・リビジョン単位で出力先（および `--reader`
  の出力先）を `<node_dir>/rendered.json` に記録し、`status` / `relay status` がそのパスと現リビジョン
  での書き出し有無を表示するようにした。また `relay status --out <path>` / `relay submit --out <path>`
  で任意の出力先を直接指定して確認できるようにもした。
- **F-26 design 成果物はコミットに残らない**（運用として明記）。`runs/` は `.gitignore` 対象
  なので、世界・歴史・人物・関係・物語構造・場面・文体の実体（`runs/*-design/design/*.json`）
  はリポジトリに入らない。残るのは `relay/requests`（プロンプト）と `relay/responses`（応答の
  逐語）、`nodes/`（revision・checkpoint・artifact 参照）、`manuscript.md`。応答から
  `relay submit` で同じ設計を再取り込みできるので再現経路はあるが、成果物を直接読みたい
  読者には `responses` を開いてもらう必要がある。

- **F-17 / U-08 原稿に章見出しが無く検査マーカーが残る**（修正済み）。`render --reader` を
  追加し、既定の `render`（検査対象と同じマーカー込みの正本）は変えずに、読書用のコピー
  （[`manuscript.reader.md`](manuscript.reader.md)、`## 第1章` 付き・`{{…}}` なし）を出せるようにした。

## 続き（U-04 改訂・U-05 第4章の追加・設計1文書の回復）

初版（`rev-3a23302eaef74437a2464da0d714b647`、3章・14ラウンド）のあと、同じ作品で
「1章だけ改訂」「第4章を足す continuation」「設計1文書だけ再生成」をすべて実応答の relay で通した。

| 版 | 種類 | 往復 | 内容 | 結果 |
| --- | --- | ---: | --- | --- |
| `rev-3a23302e…` | 初版（3章） | 14 | plan 1 + 設計 11（修復2） + 本文 3 | complete（[`manuscript.md`](manuscript.md) / [`manuscript.reader.md`](manuscript.reader.md)） |
| `rev-36f36744…` | `revise --chapter ch01` | 1 | ch01 だけ再生成（簡体字「开」→「開」、本文 647 → 807字）。plan・8設計・ch02・ch03 はバイト単位で持ち越し | complete、ch02/ch03 の SHA-256 不変 |
| `rev-2ebe138c…` | `continue --add-chapters 1` | 11 | 4章化の plan（`ch04` day=7 沢渡、`F-04`、`fs-004`）+ 8設計（scene 修復1）+ `draft:ch04`（646字）。ch01〜ch03 はバイト単位で持ち越し | complete（scene 1件が `unresolved` で残る） |
| `rev-5f5c678e…` | `revise --design scene` | 1 | `design:scene` 1文書だけ再生成（`s04` の `disclosed` に `F-03` を追加）。plan・他7設計・ch01〜ch04 全4章はバイト単位で持ち越し | complete、`doctor` findings 0（[`manuscript.4ch.md`](manuscript.4ch.md) / [`manuscript.4ch.reader.md`](manuscript.4ch.reader.md)） |

合計 **27 応答 / 0 pending**、4版すべてが `nodes/.../revisions/` に残り、旧版の本文と応答は1バイトも書き換えていない。

### 追加で見つかり直した摩擦（F-27〜F-29）

- **F-27 `revise` / `branch` だけ `--provider` 省略時に拒否していた**（修正済み）。
  `quickstart.md` は `--provider` なしで `revise --chapter ch02` を案内していたが、実装は
  `--provider scripted ... or --provider command ...` を要求して終了コード 2 で落ちていた。
  再生成があるときは `run` / `continue` と同じく既定で Arena relay を使うように統一した
  （純粋なコピーのときは従来どおり provider を使わない）。
- **F-28 `design` の `unresolved` が `relay status` / `relay submit` に出ない**（修正済み）。
  設計段階は fail-open のため、修復後も所見が残った設計書（`unresolved`）があっても `draft` まで進み
  `complete` になる。`doctor` を叩くまで気づけなかったため、round 報告の `Warnings:` に
  `design (scene): checker findings remained after repair; regenerate with ... revise prj-mine --design scene`
  を出すようにした。実際にこの1コマンド・1ラウンドで全4章の本文を保ったまま `scene` だけ直せた。
- **F-29 `continue` は設計8文書を毎回すべて再要求していた**（修正済み）。
  台帳に `ch04` が増えるため、従来は `brief`〜`voice` の8文書すべてを新しい要求として出していた
  （1章足すのに 1 + 8 + 1 = 10〜11 ラウンド）。章一覧に依存しない設計書（`brief` / `history` /
  `character` / `voice`）は既定で前版の完了済み design run から SHA-256 検証付きで持ち越し、
  `world` / `relation` / `plot` / `scene` だけを再生成するようにした（1章追加の基本ラウンドが
  10 → 6 に減少）。`--design DOC` で再生成対象を個別に指定することも、`--all-design` で全8文書を
  再生成することもできる。

## 入れ子作品（U-06 子作品の追加・生成・採用・編纂）

本編『宛名のない手紙』（4章、`node-4e577937…`）の下に、閉山当夜の沢渡町役場支所を描く
1章の外伝『切り取られた頁』（`node-sawatari`、`link-sawatari`）を `add-child` で追加し、
実応答の relay で完走させて `compose` で1冊の編纂原稿にした。

| 操作 | コマンド / ラウンド | 結果 |
| --- | --- | --- |
| 子作品の追加 | `add-child prj-mine --node-id node-sawatari --link-id link-sawatari --title 切り取られた頁 --chapters 1 --target-chars 700` | 親の完成版は不変のまま子ノードを作成 |
| 子作品の生成 | `run prj-mine --node node-sawatari` → `relay submit --node node-sawatari` × 11（plan `BE1F7416` / brief `BAEE621E` / world `D0BA1616` / history `EA958608`→repair `AEBB28FB` / character `27008C26` / relation `225112AD` / plot `4AD1D0F5` / scene `B4180A81` / voice `E0200C29` / draft:ch01 `CB8E3D72`、713字） | 子作品 complete（祖先の canon 要約が `asc-context-packet-pre1` として子の依頼文に自動で渡り、親の本文全文は渡らないことを確認） |
| 設計1文書の回復 | `revise prj-mine --node node-sawatari --design history`（tag `2D9C4D23`、1ラウンド） | `events[].title` / `sources[].holder` を揃えて `history` だけ再生成、子の `ch01` 本文（713字）はバイト単位で持ち越し |
| 親リンクへの採用 | `adopt-child prj-mine link-sawatari` | 改訂後の子版 `rev-60a71ed1…` を親リンクに固定（`doctor` findings 0、Nodes: 2） |
| 編纂（正本 / 読書用） | `compose prj-mine --out .../collection.md` / `compose prj-mine --reader --out .../collection.reader.md` | 親4章（`# 宛名のない手紙` + `## 第1章`〜`## 第4章`）の後ろに子1章（`## 切り取られた頁` + `### 第1章`）が結合された編纂原稿（[`collection.reader.md`](collection.reader.md)） |

合計 **39 応答 / 0 pending**、2ノード（親4版＋子2版）、`doctor` findings 0。

### 入れ子で見つかり直した摩擦（F-30〜F-32）

- **F-30 `relay status` に `--node` が無かった**（修正済み）。
  `relay submit` には `--node` があったのに `relay status` には無く、親が完成済みの状態で
  子ノードの待ちを見ようとすると親の `complete` だけが表示されていた。`relay status --node`
  を追加して親子どちらの round も同じコマンドで見られるようにした。
- **F-31 子ノードを `revise` したあと `adopt-child` が必要なことが round 報告に出ない**（修正済み）。
  初版の完了時は `sync_child_links` が自動でリンクを埋めるが、子を `revise` して新しい版を
  作ったあとは親リンクが旧版を指したままになる。子の `relay status --node` の `Warnings:` に
  `parent link <id>: not pinned to this revision yet; run ... adopt-child <project> <link> before compose`
  を出すようにした。
- **F-32 `compose` に `--reader` が無かった**（修正済み）。
  単体作品の `render --reader` と同じく、`compose --reader` でも親（`## 第N章`）と子（`### 第N章`）
  に階層見出しを付け、全作品の `{{…}}` 監査マーカーを外した読書用編纂原稿を出せるようにした
  （既定の `compose` と `artifacts/` の正本は1バイトも変えない）。

## 共有 world 台帳と世界編纂（U-07 年代記・地誌・文化誌・作品集の編纂）

親『宛名のない手紙』（閉山から15年後＝1965年・尾根野と沢渡）と子『切り取られた頁』（閉山の年＝1950年・沢渡）の2作品に対して、共有 `world` 台帳（時代・地域・文化・作品バインディング・明示的 canon 採用）を登録し、4種の編纂プロファイル（`chronicle` / `gazetteer` / `culture` / `collection`）から決定論的な編纂文書を出力した。

| 種別 | 登録・編纂したレコード / 出力 | 結果 |
| --- | --- | --- |
| 時代（`timeframe` / `time-span`） | `tf-showa`（昭和（銅山暦）、閉山年=1950）、`span-heizan`（1950年）、`span-15yrs`（1965年、`before_span_ids=["span-heizan"]`） | 親子2作品の15年の時間差を DAG で固定 |
| 地域（`region` / `spatial-relation`） | `reg-gun`（銅山郡）配下に `reg-oneno`（尾根野）と `reg-sawatari`（沢渡）、峠道 `sp-toge`（`mountain_pass`） | 地域包含木と空間関係を固定 |
| 文化（`culture` / `culture-state` / `culture-relation`） | `cul-post`（銅山町の郵便と記録の慣行）、`cs-heizan`（1950年）→ `cs-15yrs`（1965年、`crel-1` 継承） | 時代ごとの郵便・記録慣行の変遷を固定 |
| 作品バインディング（`world bind`） | 親 `bind-root`（`span-15yrs`, `reg-oneno`, `reg-sawatari`, `cs-15yrs`）、子 `bind-sawatari`（`span-heizan`, `reg-sawatari`, `cs-heizan`） | `context show` で `asc-context-packet-world1`（親 6,608 bytes / 子 7,222 bytes）を確認 |
| 正史の明示採用（`world adopt-canon`） | 親から `wcanon-letters`（`region:reg-oneno`, `/facts/0`）・`wcanon-margin`（`timeframe:tf-showa`, `/facts/3`）、子から `wcanon-cutpage`（`timeframe:tf-showa`, `/facts/1`）・`wcanon-seisho`（`culture:cul-post`, `/facts/0`）の計4件 | 完了済み plan の `canon/facts.json` から JSON Pointer でピン留め採用（`stale=0`） |
| 編纂出力（`world compile`） | [`chronicle.md`](chronicle.md)（年代記）、[`gazetteer.md`](gazetteer.md)（地誌）、[`culture.md`](culture.md)（文化誌）、[`world-collection.md`](world-collection.md)（作品集） | 4種すべて決定論的ハッシュ付きで出力、`doctor prj-mine` findings 0 |

### 共有 world 台帳で見つかり直した摩擦（F-33〜F-35）

- **F-33 `.gitignore` の `runs/` が全階層の `runs/` にマッチし、Git 共有後の実験プロジェクトで `doctor` が `run.missing` を出していた**（修正済み）。
  `.gitignore` の `runs/` をルート直下の `/runs/` に限定し、`experiments/2026-10-dogfood-01/work/prj-mine/runs/`（完了済み 18 run）を Git 追跡に含めることで、別コンテナや clone 後でも `doctor prj-mine`（findings 0）と `world adopt-canon` がそのまま再現できるようにした。
- **F-34 `world adopt-canon --artifact` が `runs/att-...-plan/canon/facts.json` のフルパスしか受け付けなかった**（修正済み）。
  対象ノードの現在の完了済み plan チェックポイントにピン留めされた成果物であれば、`--artifact canon/facts.json` のような短縮相対パスでも一意に解決できるようにした（フルパスも従来どおり有効）。あわせて `--pointer /facts/0` の例を `--help` に明記した。
- **F-35 `world status` のテキスト出力にバインディング先 ID と採用済み canon 一覧が出なかった**（修正済み）。
  `Current node binding: yes (id=...; time_spans=...; regions=...; culture_states=...)` と、各 canon エントリの `id [scope] subject (current|stale)` を一覧表示するようにした。

## 次にやるなら（優先順）

1. **F-20**: 依頼プロンプトの要約版を併記するかは、まず読み込み量の実測をとってから。
2. **F-24**: `revise --chapter ch01` で簡体字混入を直した改訂版を必要に応じ採用する（現状は第2版 `rev-36f36744…` 以降で解消済み）。

## 再現と検証

- 同じ作品ディレクトリでは、生成なしで何度でも確認できる。

```bash
.venv/bin/python scripts/story_project.py --root experiments/2026-10-dogfood-01/work doctor prj-mine
.venv/bin/python scripts/story_project.py --root experiments/2026-10-dogfood-01/work render prj-mine \
  --out experiments/2026-10-dogfood-01/manuscript.md
```

- 14件の応答は `work/prj-mine/relay/responses/<key>.json` に `prompt_hash` と `model` 付きで
  残る。依頼側は `work/prj-mine/relay/requests/<key>.json`（同じ key、`prompt` 全文）。
- 新しい root での再構築は試していない。`init` は node ID を新しく振るため、request key
  （`s1-<node>-s<n>-<purpose>-a<n>`）が変わり、既存の応答がそのままは当たらない。同じ題材で
  やり直すなら、応答を新しいタグで貼り直す（逐語のまま）。

## 主張しないこと

- 品質・面白さ・完成度は主張しない。ここで確かめたのは「人間が題材と制約だけを渡し、
  14ラウンドで読める原稿まで到達できる」ことと、その途中で詰まった箇所。
- 率・再発率・因果効果は測っていない。修復2回／14ラウンドは1作品の観測値で、条件を変えた
  比較ではない。
- L2/L3 は `frozen_not_measured` のまま。事前登録・`results.json`・完了済み run・relay は
  書き換えていない（今回の応答は新規の `prj-mine` にだけ入っている）。
