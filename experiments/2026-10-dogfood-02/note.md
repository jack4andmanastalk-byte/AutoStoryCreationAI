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
| 16 | `draft:ch03`（revise） | `B78ED9FB` | | 読み直しで見つけた重複台詞を除去（後に F-41 として `--note` を追加） |

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

## 摩擦ログ（F-36〜F-43）

分類: 完走（導線）／本文（生成物）／編集（修正の経路）／運用（記録の残し方）。
前回までは F-35（[`2026-10-dogfood-01`](../2026-10-dogfood-01/note.md)、
[`docs/practical_roadmap.md`](../../docs/practical_roadmap.md) §7）。
ID は通し番号。前回 dogfood が F-27〜F-35 を使っているため、今回の記録は F-36 から振った。

### 完走

- **F-36 ログラインの四要素は逐語一致を要求される**（記録のみ、修復 1 往復）。
  `design-brief` の検査は `elements` の who/where/wants/obstacle がログラインに
  **一字一句そのまま**現れることを要求する。依頼文にもそう書いてあるが、
  「一文にまとめる」作業のなかで言い換えてしまい、修復 1 往復を消費した。
  修復プロンプトが欠けている要素を名指しするので、1 往復で直る。実害は小さい。
- **F-37 異説（apocrypha）は「内容」ではなく文字列で照合される**（記録のみ、修復 1 往復）。
  依頼文は「出来事の題・結果・痕跡のいずれかにも**同じ内容**が現れるもの」と書くが、
  検査は句読点・空白を除いた**部分文字列**一致で見ている。私は「内容が対応していればよい」と
  読んで別の言い回しを置き、修復になった。
- **F-38 場面で「得る事実」は開示か保留に必ず置く**（自分の見落とし、修復 1 往復）。
  依頼文にも検査にも明記されている。`knowledge[].gained` に書いた事実を
  `disclosure.disclosed` に足し忘れた。プロンプト側の問題ではない。
- **F-42 `run` と `relay submit` で response のパス表記が違う**（記録のみ）。
  `run` が exit 3 のときは絶対パス、`relay submit` の `Next request:` はリポジトリ相対。
  どちらも辿れるので実害はないが、同じ欄が 2 書式なのは読み手に優しくない。

### 本文

- **F-39 目安字数が単一値だと、±1 字で警告になる**（修正済み）。
  `--target-chars 1200` は `chapter_target = (1200, 1200)` に変換されるため、
  1201 字でも `Warnings` に出た。今回は 3 章のうち ch03 だけが該当し、各章で 5〜10 回の
  字数調整を手作業で行った（生成そのものより字数合わせに時間を使った）。
  実害は「警告が常態化して読まれなくなること」と、書き手が ±数十字のために文章を削ること。

### 編集

- **F-41 `revise` に「何を直すか」を渡す口がない**（修正済み）。
  `revise --chapter ch03` の依頼文には「ch03 を作り直す／ch01・ch02 は保持」しか入らず、
  理由（今回は同じ内容の台詞が二度出た）を伝える手段がなかった。今回は依頼文を見ずに
  自分の判断で書き直したが、意図を渡せないと、直したい点と別の点が変わりうる。

### 運用

- **F-40 `revise` 後の `summary` で、設計書の修復履歴が 0 になる**（修正済み）。
  ch03 を revise した結果、8 設計は新リビジョンへ `carried` され、
  `summary` は全設計を「状態: `carried` (試行 0, 修復 0, 残存所見 0)」と表示した。
  実際には brief・history・scene で各 1 回の修復が起きている。人間向け要約から
  「この作品が何回作り直されたか」が消えるので、U-06（編集支援としての表示）の観点で直した。
- **F-43 `relay/index.json` の `pending` は最後の依頼を残したまま**（既知・記録のみ）。
  F-19 で「待ちの正は `relay status`」と明記済みで、実際に `relay status` は 0 件を返す。
  完成後の `index.json` は `"pending": 1` のままなので、docs の注記どおりの挙動。

### 再発しなかったもの

- F-18（`draft: draft:` の二重ラベル）— 表示は `purpose` のみ。
- F-22（目安字数の警告が埋もれる）— 完成報告に `Warnings: 1` として出た。
- F-23（scene の `planted` に canon の布石 ID を書く）— 依頼文 v1.1 の明記どおり `[]` にした。
- F-24（簡体字の混入）— 今回は 0 件。

## 対応（2026-10-28）

dogfood のあと、F-36〜F-41 のうち4つを直した（F-42 / F-43 は記録のみ）。

| 摩擦 | 対応 | 回帰 |
| --- | --- | --- |
| F-39 | `asc.project.adapter.target_band` で単一値を **±5%** の許容幅に変換（`1200` → `1140〜1260`）。draft の警告は幅の外だけ。依頼文・`brief.md`・`summary` も幅で表示 | `tests/test_project_runner.py::test_a_chapter_inside_the_advisory_band_draws_no_length_warning`、`test_work_spec_adapter_uses_project_identity_and_targets`、`tests/test_relay_round.py` |
| F-40 | carried した設計書は元 run の `design.json` から試行・修復・所見を引き継ぐ（`asc.pipeline.design.carried_row` / `asc.project.revise.design_history`）。修復前のデータは `summary` が元リビジョンから補う。`summary` の Info に「設計の累計」と「このリビジョンでの作り直し」を追加 | `tests/test_carried_history_and_note.py`、`tests/test_project_continuation.py`（byte リプレイ維持） |
| F-41 | `revise` / `branch` に `--note`。依頼文の `## 改訂の意図` に入り、`derived.note`（最大1000字）と `summary` に残る | `tests/test_carried_history_and_note.py` |
| F-36 / F-37 | `design-brief` v1.1 → **v1.2**（四要素を埋めたログラインの実例）、`design-history` v1.1 → **v1.2**（異説は「そのままの文字列」で含める） | `tests/test_design_prompt_contracts.py`、`tests/test_pipeline_design.py`、`tests/test_measure_realrun_b.py`（登録 pin の再固定は試験用コピーのみ） |

- F-37 の変更は、依頼文に「言い換えない」と書いただけで検査は変えていない
  （既存の検査契約をそのまま言い直した）。F-36 も同様。
- F-42 / F-43 は実害がないため、記録だけ残した。

## 次の一手

1. 次作品の dogfood で F-39 の警告が実際に消えるか、字数調整の手作業が減ったかを見る。
2. 続き（`continue`）を挟んだ作品でも F-40 の累計が正しく積み上がるかを見る（今回は revise のみ）。
3. 原稿の説明過多（人物の口で利害を言い切る箇所）は、`design-brief` の禁止条件として
   書き手に渡す余地がある。次の作品で2例以上出たら、プロンプトの版を上げて扱う。
