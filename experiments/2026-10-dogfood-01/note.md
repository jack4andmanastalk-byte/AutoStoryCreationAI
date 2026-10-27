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

- **F-22 目安字数は助言で、誰も検査しない**（記録のみ）。900字の目安に対し実測 647/668/795字
  （72〜88%）。`doctor` も `findings: 0`。`target_chars` は台帳の `target_min/target_max` と
  プロンプトの一文にしか現れず、`adapt_work_spec` では `(target, target)` に潰れる。
  今回は「短いが成立している」と判断して revise しなかった。quickstart に「長さの機械検査は
  しない。気になる章は `revise --chapter`」と明記。**警告を出す実装は未着手**。
- **F-23 検査の最小要件が依頼文に書かれていない**（記録のみ、修復2回の原因）。character の
  `speech.sample` は30字以上、scene の `foreshadows.planted` は canon にない ID のみ
  （canon の布石は `paid` に置く）。どちらも check 側にだけあり、依頼文には無い。応答を書く
  側が事前に `src/asc/*/check.py` を読んでいれば避けられるが、初見では必ず1往復増える。
  依頼文に1行足すのが素直な直し方だが、プロンプト文字列を変えると `prompt_hash` が変わり
  既存の relay 資産と衝突するため、新規作品だけに効く形を設計してから入れる。**未着手**。
- **F-24 誤字を機械は拾わない**（記録のみ）。ch01 に簡体字「开」が1箇所混入した（「すぐには
  开けなかった」）。`doctor` は pass。応答は逐語で取り込む約束なので、書き換えずに残した。
  直すなら `revise --chapter ch01` で新しい revision を作る（未実施）。

### 編集・運用

- **F-25 `Manuscript:` は既定パスしか見ない**（記録のみ）。`relay status` は
  `work/prj-mine/manuscript.md` を見て「(not written yet)」と出す。今回は experiment 直下に
  `render --out` したので、完成後も status の表示は「未書き出し」のまま。`Next:` の
  `render` をそのまま実行すれば既定パスに書けるが、置き場所を選ぶと表示が追従しない。
  `--out` の履歴を持つか、status に `--manuscript PATH` を受けるのが候補。
- **F-26 design 成果物はコミットに残らない**（運用として明記）。`runs/` は `.gitignore` 対象
  なので、世界・歴史・人物・関係・物語構造・場面・文体の実体（`runs/*-design/design/*.json`）
  はリポジトリに入らない。残るのは `relay/requests`（プロンプト）と `relay/responses`（応答の
  逐語）、`nodes/`（revision・checkpoint・artifact 参照）、`manuscript.md`。応答から
  `relay submit` で同じ設計を再取り込みできるので再現経路はあるが、成果物を直接読みたい
  読者には `responses` を開いてもらう必要がある。

## 次にやるなら（優先順）

1. **F-23**: 依頼文に検査の最小要件（文字数・ID の出所）を1行ずつ足す。修復往復が減るか、
   次の作品で数える。`prompt_hash` の影響範囲を先に確認する。
2. **F-22**: 目安字数に対する不足・超過を `submit` の報告に1行出す（fail にはしない）。
3. **F-25**: `relay status` が `--out` の出力先を知る（引数か最後に render したパス）。
4. **F-20**: 依頼プロンプトの要約版を併記するかは、まず読み込み量の実測をとってから。

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
