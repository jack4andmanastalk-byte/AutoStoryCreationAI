# U-12 検証 dogfood（3 作目）: 字数の許容幅と carried 履歴の実測

標準フロー（`scripts/story_project.py`、既定 provider = Arena relay）で、「F-39（字数の許容幅）」
と「F-40（carried 設計書の履歴）」の修正が実運用で効いているかを確かめるための、
**実応答**による 3 作目の dogfood。
題材と制約だけを人間が決め、plan・8設計・本文 3 章を生成し、`relay submit` で逐語的に
取り込んだ。モデル応答の捏造はしていない。続けて `continue --add-chapters 1` で 4 章へ
拡張し、carried 設計書の履歴と章追加の経路も通した。

- 原稿: [`manuscript.md`](manuscript.md)（SHA-256 `18bb3a63e9c83f945500aac6375b4dd5646a916221dd412dd95e8419363dded4`）
- 読書用: [`manuscript.reader.md`](manuscript.reader.md)
- 要約: [`summary.md`](summary.md)（4 章版 / 現在リビジョン `rev-88dd9f8f…`、種別 `continue`）
- 作品ディレクトリ: `work/prj-kazami/`（project.json・nodes・relay。応答 19 件すべて `relay/responses/`）
- `answers.txt` は最終ラウンド（ch04）の貼り付けだけを残している。

## 題材と条件（人間が決めたのはここだけ）

| 項目 | 内容 |
| --- | --- |
| 題名 | 風速の窓 |
| premise | 閉鎖が決まった高原の測候所で、最後の観測員が先代の観測記録の食い違いに気づく。町は閉鎖を急ぎ、先代の妻は記録の一部を預かったまま黙っている。観測は続けられるのか、閉じられるべきなのか。 |
| 章数 / 1章の目安 | 3章（のち `continue` で 4 章へ） / 1000字 |
| 場所と日付 | 霧ヶ原（1日目）→ 沢根（3日目、徒歩1日）→ 霧ヶ原（6日目）→ 沢根（9日目） |
| 人物 | 佐倉ヒナ29（観測員）・宮内サダ68（先代の妻）・黒沢タケシ41（町役場）・佐倉ツカサ52（先代、3年前に病死。以後は行為者にならない） |
| 事実 | F-01 年度末で閉鎖／F-02 昭和五十八年の風速欄が二重／F-03 老朽化は実際の理由ではない／F-04 サダが日誌二冊を預かったまま／F-05 先代が署名を集めていた／F-06 土地の転用案／F-07（4章で追加）書庫の日誌は町民なら誰でも閲覧請求できる |
| 伏線 | fs-001 二重の風速欄（ch01→ch03）・fs-002 仏壇の引き出し（ch01→ch02）・fs-003 鍵の札（ch02→ch03） |
| 文体 | third人称、視点=佐倉ヒナ、禁止 運命／奇跡／涙が／心が読める |

## 実行したこと

```bash
.venv/bin/python scripts/story_project.py --root experiments/2026-10-dogfood-03/work \
  init --project-id prj-kazami --title "風速の窓" --chapters 3 --target-chars 1000 --premise "…"
.venv/bin/python scripts/story_project.py --root experiments/2026-10-dogfood-03/work run prj-kazami   # exit 3
# 以降は 1 ラウンド = relay status → 応答を answers.txt に書く → relay submit
.venv/bin/python scripts/story_project.py --root experiments/2026-10-dogfood-03/work continue prj-kazami --add-chapters 1
.venv/bin/python scripts/story_project.py --root experiments/2026-10-dogfood-03/work doctor prj-kazami
.venv/bin/python scripts/story_project.py --root experiments/2026-10-dogfood-03/work \
  summary prj-kazami --out experiments/2026-10-dogfood-03/summary.md
.venv/bin/python scripts/story_project.py --root experiments/2026-10-dogfood-03/work \
  render prj-kazami --out experiments/2026-10-dogfood-03/manuscript.md
```

## 結果

- **19 ラウンドで complete**（3 章版 13・4 章版 6）。修復は brief の 1 回だけ。
- `doctor`: `findings: 0 (errors=0, warnings=0, info=0)`、7 検査すべて pass、`runs: 25 (interrupted 0)`。
- `summary`（4 章版）: Blocker 0 / Warning 0 / Observation 0。3 章版の時点でも Warning 0。
- 本文合計 **3020 字**（3 章版、目安 3000）→ **4018 字**（4 章版、目安 4000、マーカー込み 4433）。

| # | 版 | purpose | タグ | 修復 | 備考 |
| --- | --- | --- | --- | --- | --- |
| 1 | 3章 | `plan` | `BC22F1DF` | | 目安が既に `2850〜3150 字` で提示された |
| 2 | 3章 | `design:brief` | `BC233F20` | | `logline_elements` で 1 所見（medium） |
| 3 | 3章 | `design:brief:repair` | `BDF34D10` | ← | 1 往復で通過 |
| 4 | 3章 | `design:world` | `30F3199A` | | |
| 5 | 3章 | `design:history` | `A219517C` | | |
| 6 | 3章 | `design:character` | `9C88E0B3` | | |
| 7 | 3章 | `design:relation` | `C63EABEC` | | |
| 8 | 3章 | `design:plot` | `8A67227D` | | |
| 9 | 3章 | `design:scene` | `74155800` | | |
| 10 | 3章 | `design:voice` | `BA023662` | | |
| 11 | 3章 | `draft:ch01` | `BC931FFE` | | 1004 字 / 警告なし |
| 12 | 3章 | `draft:ch02` | `9151C2AA` | | 1010 字 / 警告なし |
| 13 | 3章 | `draft:ch03` | `A40FC704` | | 1006 字 / 警告なし |
| 14 | 4章 | `plan` | `7735A426` | | `## 前版からのcontinuation` に compact canon |
| 15 | 4章 | `design:world` | `5D6F9010` | | 前版の応答をそのまま再提出 |
| 16 | 4章 | `design:relation` | `26EFD5BD` | | 同上 |
| 17 | 4章 | `design:plot` | `829FD147` | | act と turn t4 を追加 |
| 18 | 4章 | `design:scene` | `DAD9334D` | | s07・s08 を追加 |
| 19 | 4章 | `draft:ch04` | `F7AFF4ED` | | 998 字 / 警告なし |

### 検証 (a) 字数の許容幅（F-39）

同じ設定で、修正前の 2 作目と修正後の本作を比べると差がはっきり出た。

| 実行 | 章 | 実測 | 依頼文の目安 | `draft.json` の `warnings_ja` |
| --- | --- | --- | --- | --- |
| dogfood-02 | ch03 | 1201 字 | `1200 字`（単一値） | `ch03: 1201 字（目安 1200〜1200 字の外）` |
| dogfood-03 | ch01 | 1004 字 | `950〜1050 字`（±5%） | `[]` |
| dogfood-03 | ch02 | 1010 字 | `950〜1050 字` | `[]` |
| dogfood-03 | ch03 | 1006 字 | `950〜1050 字` | `[]` |
| dogfood-03 | ch04 | 998 字 | `950〜1050 字` | `[]` |

- 依頼文（plan / draft）の目安は最初から帯で出た。plan は `合計 3800〜4200 字`、draft は各章 `950〜1050 字`。
- 4 章すべて帯の内側に収まり、**警告は 1 件も出なかった**。2 作目で +1 字に対して出ていた警告が、
  本作では同じ程度の上振れ（+10 字 = +1.0%）で出ない。
- 帯の**外**に振った場合の挙動は本作では試していない（`tests/test_carried_history_and_note.py` が
  帯外・帯内の両方を固定している）。1 作の観測なので「警告が出ない率」のような数値は主張しない。

### 検証 (b) 累計と carried 履歴（F-40）

`continue --add-chapters 1` 後の design run（`att-f6de4c7dc8e34a7d84fa35e9285823dd-design/design.json`）:

```
carried: ['brief', 'history', 'character', 'voice']
docs.brief:     {attempts: 2, repairs: 1, findings: 0, status: 'carried', carried_history: true}
docs.history:   {attempts: 1, repairs: 0, status: 'carried', carried_history: true}
docs.character: {attempts: 1, repairs: 0, status: 'carried', carried_history: true}
docs.voice:     {attempts: 1, repairs: 0, status: 'carried', carried_history: true}
docs.world/relation/plot/scene: attempts 1, repairs 0, status 'clean'（作り直し）
```

`summary.md` 側の表示も一致した。

- `- **設計の累計**: 試行 9 回 / 修復 1 回`（3 章版と 4 章版で同じ値）
- `### 企画核（brief） — 状態: carried (試行 2, 修復 1, 残存所見 0; 元リビジョンの履歴を引き継ぎ)`
- `history` / `character` / `voice` も `carried` として試行 1・修復 0 を保持。
- `- **continuation 再生成設計書**: world, relation, plot, scene` と、作り直した 4 冊が明示された。

つまり、章を足しても brief の「試行 2・修復 1」は 0 に戻らず、`carried` の 4 冊は
元リビジョンの数字を保ったまま Info の累計に効いている。**「8 冊すべてが試行 0 に見える」現象は再現しなかった。**

## 読後の所見（作品として）

- 章の字数が揃ったぶん、4 章版は「観測を閉じる」（ch01〜ch03）と「記録を町に渡す」（ch04）で
  重心が二つに割れた。`continue` は既存章を触らないので、ch03 の結末（鍵を机に置く）が
  ch04 の出発点とやや重複する。改稿するなら ch03 の末尾を「閉じる」で止め、ch04 に運搬を任せる。
- 台帳の F-05（先代の署名）を ch04 でサダに返さないまま終えたが、これは `unresolved` に
  意図的未解決として登録したので、検査は通っている。物語としては、未解決の数が 2 件に増えて
  やや散らかった。

## 摩擦ログ（F-44〜F-47）

### 完走

- F-44 **brief の `logline_elements` が、例示を入れても 1 回修復になった**。v1.2 の依頼文には
  「要素の文字列をそのまま含める」例が入っているが、自然な日本語に整えようとして
  「〜を望む」を言い換えてしまい、逐語一致で落ちた。例示は効いている（前回は 3 件だった所見が
  今回は 1 件）が、**1 回は残る**。恒久対策は「要素をそのまま連結した文案を先に出す」段取りか、
  検査を「要素の語を含む」ではなく「要素の主要語を含む」に緩めるかのどちらか。
- F-45 **`continue` は plan から作り直す**。3 章版の canon をそのまま貼れるので作業量は小さいが、
  compact canon（前版の要約）と自分の回答の突き合わせが要る。今回は plan 応答をほぼコピーし、
  ch04 と F-07 だけ足した。仕様どおりだが、「章を足すたびに canon を書き直す」コストは残る。

### 本文

- F-46 **章を足すときの設計差分は人間の裁量**。`continue` の既定は world / relation / plot / scene の
  作り直しで、plot の `acts` と scene の `scenes` に新章を入れないと整合しない可能性がある
  （未検証）。こちらは act `handover` と turn `t4`、s07・s08 を自分で足して通した。
  「新章ぶんの act を要求する」検査があるかは、`tests/` を読む限り明示的でない。
- 文字数は `summary` を見ないと分からない。`relay submit` の成功出力には章の字数が出ないので、
  毎ラウンド `summary` を回すか、`draft.json` を直接見る必要があった（小さな手間）。

### 編集

- F-47 **Info の「設計の累計」はリビジョン内の合計**で、リビジョンをまたいだ累積ではない。
  4 章版でも `試行 9 回 / 修復 1 回` と出るため、rev1 の 9 と rev2 の 9 を足した 18 にはならない。
  carried 行に「元リビジョンの履歴を引き継ぎ」と出るので誤読は防げるが、累計行だけを見ると
  「増えていない」と読める。表記を「このリビジョンの設計累計」にすると誤解が消える（記録のみ）。

### 運用

- 3 作目で `doctor`・`summary` の Blocker / Warning / Observation はすべて 0。前作で出た
  ch03 の字数警告（Warning 1）は再発しなかった。
- `answers.txt` は毎ラウンド上書き、最終ラウンドだけ残す運用で問題なかった。

### 再発しなかったもの

- 字数警告（F-39 の対象）: 3 章版・4 章版とも 0 件。
- carried 設計書の履歴欠落（F-40 の対象）: 4 冊とも数字を保持。
- `--note`（F-41）は今回は `revise` を使っていないため未使用。`continue` に `--note` は無い。

## 次の一手

- F-44: `logline_elements` の依頼文に「要素は言い換えずに連結してよい」と一文足すか、
  検査側を主要語一致に緩める。次に brief を作る機会に A/B で見る。
- F-46: 章追加時に `acts` / `scenes` の章網羅を検査しているかを確かめ、していなければ
  `continue` の依頼文に「新章の act と scene を必ず含める」と明記する。
- F-47: Info の累計行の表記を「このリビジョンの設計累計」に変える（1 行の変更）。
