# U-03 追加 dogfood（2 作目）: 機能変更後の標準フロー再走

標準フロー（`scripts/story_project.py`、既定 provider = Arena relay）を、前回の
[`2026-10-dogfood-01`](../2026-10-dogfood-01/note.md) 以降の変更を入れた状態で、**実応答**で
もう一度通した記録。題材と制約だけを人間が決め、plan・8設計・本文3章を生成し、
`relay submit` で逐語的に取り込んだ。モデル応答の捏造はしていない。

- 原稿: [`manuscript.md`](manuscript.md)（SHA-256 `fd65caccc03ce22b9fd84f1d001796e5d1642861a3d7753f5ff48bd2c25e77db`）
- 読書用: [`manuscript.reader.md`](manuscript.reader.md)
- 要約: [`summary.md`](summary.md)
- 作品ディレクトリ: `work/prj-yunome/`（project.json・nodes・relay。応答 16 件すべて `relay/responses/`）
- `answers.txt` は最終ラウンド（ch03 の revise）の貼り付けだけを残している。

## 題材と条件（人間が決めたのはここだけ）

| 項目 | 内容 |
| --- | --- |
| 題名 | 湯の目盛り |
| premise | 源泉の温度が三年続けて下がっている山あいの温泉町・湯ノ瀬。配湯係の若い女性が、町が隠している古い湯脈の記録を追う。源泉を守る古老と、観光に賭ける組合の若手は、それぞれ別の理由で記録を伏せている。 |
| 章数 / 1章の目安 | 3章 / 1200字 |
| 場所と日付 | 湯ノ瀬（1日目）→ 奥湯（4日目、徒歩1日）→ 湯ノ瀬（7日目） |
| 人物 | 瀬川ミナ27（配湯係）・桐生源治74（元湯守）・高梨ユウジ31（観光組合）・瀬川宗一（15年前に病死、以後は行為者にならない） |
| 事実 | F-01 温度は年〇・四度ずつ低下／F-02 公式調査は昭和三十八年で終了／F-03 旧湯口は人の手で封鎖／F-05 源治が加わった／F-06 ユウジが低下を伏せて掘削を進める |
| 伏線 | fs-001 目盛りを削られた温度計（ch01→ch03）・fs-002 源治の火傷（ch01→ch02）・fs-003 赤インクの日付（ch02→ch03） |
| 文体 | third人称、視点=瀬川ミナ、禁止 b1運命・b2奇跡・b3涙が・b4心が読める |

## 実行したこと

```bash
.venv/bin/python scripts/story_project.py --root experiments/2026-10-dogfood-02/work \
  init --project-id prj-yunome --title "湯の目盛り" --chapters 3 --target-chars 1200 --premise "…"
.venv/bin/python scripts/story_project.py --root experiments/2026-10-dogfood-02/work run prj-yunome   # exit 3
# 以降は 1 ラウンド = relay status → 応答を answers.txt に書く → relay submit
.venv/bin/python scripts/story_project.py --root experiments/2026-10-dogfood-02/work \
  revise prj-yunome --chapter ch03            # 読み直しのあと、ch03 だけ作り直した
.venv/bin/python scripts/story_project.py --root experiments/2026-10-dogfood-02/work \
  render prj-yunome --out experiments/2026-10-dogfood-02/manuscript.md
.venv/bin/python scripts/story_project.py --root experiments/2026-10-dogfood-02/work \
  render prj-yunome --reader --out experiments/2026-10-dogfood-02/manuscript.reader.md
.venv/bin/python scripts/story_project.py --root experiments/2026-10-dogfood-02/work \
  summary prj-yunome --out experiments/2026-10-dogfood-02/summary.md
.venv/bin/python scripts/story_project.py --root experiments/2026-10-dogfood-02/work doctor prj-yunome
```

## 結果

- **16 ラウンドで complete**（plan 1・設計 8＋修復 3・本文 3＋revise 1）。`submit` の最終出力は
  `Stages: plan=done, design=done, draft=done` / `Relay: 16 answered / 0 pending` / exit `0`。
- `doctor`: `findings: 0 (errors=0, warnings=0, info=0)`、7 検査すべて pass、`runs: 22 (interrupted 0)`。
- `summary`: Blocker 0 / Warning 1 / Observation 0。警告は ch03 の字数のみ。
- 本文合計 **3601 字**（目安 3600、マーカー込み 3964）。

| # | purpose | タグ | 修復 | 備考 |
| --- | --- | --- | --- | --- |
| 1 | `plan` | `0BED85D2` | | canon 一発合格 |
| 2 | `design:brief` | `DADBEB28` | | logline の四要素が逐語で入っていない |
| 3 | `design:brief:repair` | `CDEBEC8B` | ← | 1 往復で通過 |
| 4 | `design:world` | `5AD011BC` | | |
| 5 | `design:history` | `FD0F61D7` | | 異説が年表の文言と一致せず |
| 6 | `design:history:repair` | `D97B978A` | ← | 1 往復で通過 |
| 7 | `design:character` | `8DD7E7FF` | | 4 人分一発合格（前回は修復 1 回） |
| 8 | `design:relation` | `4D935DA6` | | |
| 9 | `design:plot` | `33C7E1BB` | | |
| 10 | `design:scene` | `900C48EF` | | `gained` を `disclosed` に置かず |
| 11 | `design:scene:repair` | `081491B3` | ← | 1 往復で通過 |
| 12 | `design:voice` | `0AE2D258` | | |
| 13 | `draft:ch01` | `EF45EA49` | | 1200 字ちょうど |
| 14 | `draft:ch02` | `9BE7EF24` | | 1200 字ちょうど |
| 15 | `draft:ch03` | `70ED6FB5` | | 1201 字（警告 1 件） |
| 16 | `draft:ch03`（revise） | `B78ED9FB` | | 読み直しで見つけた重複台詞を除去 |

### 本文の実測

| 章 | 作中 | 場所 | 本文 | 目安との差 |
| --- | --- | --- | --- | --- |
| ch01 | 1日目 | 湯ノ瀬 | 1200字 | 0 |
| ch02 | 4日目 | 奥湯 | 1200字 | 0 |
| ch03 | 7日目 | 湯ノ瀬 | 1201字 | +1（警告） |

- マーカーは冒頭の `{{time: …}}{{location: …}}`、`{{learn: …}}` 4 件、`{{foreshadow: … setup/payoff}}` 5 件のみ。
  情景説明には使っていない。
- 伏線は fs-002 を ch01 で張って ch02 で回収、fs-003 を ch02→ch03、fs-001 を ch01→ch03 で回収した。
- 章の日付と移動日数（湯ノ瀬⇄奥湯 1 日）は本文の「三日目の朝」「歩いて一日」と一致し、監査の指摘は 0 件。
- 宗一は現在の場面で一度も行為者・発話者になっていない（回想の言及のみ）。

## 読後の所見（作品として）

- **通った**。職人の手順（測定→掲示→帳面）が場面の骨になり、数字が感情の代わりに働いている。
  3 章で「記録は直らないが、誰が書いたかは残る」という主題に着地しており、設計の狙いどおり。
- **説明がやや多い**。源治の「閉じた言うたら、誰が得したかが分かる…」と、ユウジの
  「温度の低下を書類に書けば、通らん」は、どちらも人物の口で利害を説明しきっている。
  同じ情報を、書類の日付や漆喰の指の跡だけで読ませる余地がある。
- **ミナの内面が細い**。体温・手の冷たさ・湯気の匂いなどの身体感覚が少なく、
  「測る人」の抽象に寄っている。voice 設計の `sample` が体温寄りなので、本文でもう少し拾いたい。
- 誤字・簡体字の混入は今回なかった（前回 F-24 の再発なし）。

## 摩擦ログ（F-27〜F-34）

分類: 完走（導線）／本文（生成物）／編集（修正の経路）／運用（記録の残し方）。
前回までは F-26（[`2026-10-dogfood-01`](../2026-10-dogfood-01/note.md)）。

### 完走

- **F-27 ログラインの四要素は逐語一致を要求される**（記録のみ、修復 1 往復）。
  `design-brief` の検査は `elements` の who/where/wants/obstacle がログラインに
  **一字一句そのまま**現れることを要求する。依頼文にもそう書いてあるが、
  「一文にまとめる」作業のなかで言い換えてしまい、修復 1 往復を消費した。
  修復プロンプトが欠けている要素を名指しするので、1 往復で直る。実害は小さい。
  改善案: 依頼文の出力例を、四要素を埋めた 1 文の実例にする（現状は空の雛形だけ）。
- **F-28 異説（apocrypha）は「内容」ではなく文字列で照合される**（記録のみ、修復 1 往復）。
  依頼文は「出来事の題・結果・痕跡のいずれかにも**同じ内容**が現れるもの」と書くが、
  検査は句読点・空白を除いた**部分文字列**一致で見ている。私は「内容が対応していればよい」と
  読んで別の言い回しを置き、修復になった。
  改善案: `prompts/design-history.md` を上げ、「異説の文は、出来事の題・結果・痕跡のいずれかに
  **そのままの文字列**として含める」と明記する（v1.2）。
- **F-29 場面で「得る事実」は開示か保留に必ず置く**（自分の見落とし、修復 1 往復）。
  依頼文にも検査にも明記されている。`knowledge[].gained` に書いた事実を
  `disclosure.disclosed` に足し忘れた。今回はプロンプト側の問題ではない。
- **F-30 目安字数が単一値だと、±1 字で警告になる**（改善候補、実害あり）。
  `--target-chars 1200` は `chapter_target = (1200, 1200)` に変換されるため、
  1201 字でも `Warnings` に出る。今回は 3 章のうち ch03 だけが 1201 字で警告になった。
  実害は「警告が常態化して読まれなくなること」と、**書き手（ここでは AI）が
  ±数十字のために文章を削る作業に追い込まれること**。今回は各章で 5〜10 回の
  字数調整を手作業で行った（生成そのものより、この調整のほうが時間を使った）。
  改善案: 単一値指定のときは既定の許容幅（例 ±5%、または `CHAPTER_TARGET` の 1000〜1400）を
  併用し、警告は「許容幅の外」でだけ出す。`summary` にも許容幅を表示する。
- **F-31 `revise` 後の `summary` で、設計書の修復履歴が 0 になる**（改善候補、実害あり）。
  ch03 を revise した結果、8 設計は新リビジョンへ `carried` され、
  `summary` は全設計を「状態: `carried` (試行 0, 修復 0, 残存所見 0)」と表示する。
  実際には brief・history・scene で各 1 回の修復が起きている。人間向け要約から
  「この作品が何回作り直されたか」が消えるので、U-06（編集支援としての表示）の観点で直したい。
  改善案: `carried` の設計書は元リビジョンの試行・修復回数を併記する、または
  作品全体の「修復回数・再生成回数」を Info に 1 行で出す。
- **F-32 `revise` に「何を直すか」を渡す口がない**（改善候補）。
  `revise --chapter ch03` の依頼文には「ch03 を作り直す／ch01・ch02 は保持」しか入らず、
  理由（今回は同じ内容の台詞が二度出た）を伝える手段がない。今回は依頼文を見ずに
  自分の判断で書き直したが、意図を渡せないと、直したい点と別の点が変わりうる。
  改善案: `revise --note "…"` を追加し、依頼文に「改訂の意図」として差し込む。
- **F-33 `run` と `relay submit` で response のパス表記が違う**（記録のみ）。
  `run` が exit 3 のときは絶対パス、`relay submit` の `Next request:` はリポジトリ相対。
  どちらも辿れるので実害はないが、同じ欄が 2 書式なのは読み手に優しくない。
- **F-34 `relay/index.json` の `pending` は最後の依頼を残したまま**（既知・記録のみ）。
  F-19 で「待ちの正は `relay status`」と明記済みで、実際に `relay status` は 0 件を返す。
  完成後の `index.json` は `"pending": 1` のままなので、docs の注記どおりの挙動。

### 再発しなかったもの

- F-18（`draft: draft:` の二重ラベル）— 表示は `purpose` のみ。
- F-22（目安字数の警告が埋もれる）— 完成報告に `Warnings: 1` として出た。
- F-23（scene の `planted` に canon の布石 ID を書く）— 依頼文 v1.1 の明記どおり `[]` にした。
- F-24（簡体字の混入）— 今回は 0 件。

## 次の一手（小さく直すなら）

1. F-30: 単一値 `--target-chars` に許容幅を持たせる（警告の常態化を止める）。
2. F-31: `carried` 設計書の修復履歴を `summary` に残す。
3. F-28: `design-history` の依頼文に「そのままの文字列で含める」を明記。
4. F-27: `design-brief` の出力例を、四要素を埋めた 1 文の実例にする。
5. F-32: `revise --note` を足して、改訂の意図を依頼文に渡す。
