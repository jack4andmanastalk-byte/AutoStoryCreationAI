# クイックスタート — 題材から3章の原稿まで

- 日付: 2026-10-27
- 対象: Arena Agent Mode のセッション内（ローカル実行を前提にしない）
- 決定と背景: [`standard_flow.md`](standard_flow.md)
- 使う入口: `scripts/story_project.py` だけ

この手順は、題材と条件を決めてから、`plan → 8設計 → 3章の本文` を経て、
読める原稿（`manuscript.md`）と状態（`status` / `doctor`）を得るまでを通す。
本文を代筆したり、成果物を手作業で別の場所へ運んだりはしない。生成の各段は
Arena のAI（または接続したモデル）が行い、人間は題材の指定・開始・採用判断・読後
フィードバックを担う。

## 0. 準備（セッションの最初に1回）

```bash
make setup                      # .venv を作り、requirements.txt を入れる
.venv/bin/python scripts/story_project.py --help
```

`.venv/bin/python` は依存（PyYAML 等）を含む。システムの `python3` を直接使う場合は、
同じ依存が入っていることを先に確かめる。Arena の sandbox では `.venv` を作り直せば
同じ状態に戻る（`runs/` は git 管理外なので、作品は `works/` に置く）。

## 1. 題材と条件を決める

決めるのは、題名・premise（題材と制約）・章数・目標字数だけである。

```bash
.venv/bin/python scripts/story_project.py --root works init \
  --project-id prj-seaside \
  --title "潮の記録者" \
  --premise "港町で失われた潮位記録を追う。記録を守る者と、書き換えたい者がいる。" \
  --chapters 3 --target-chars 1200
```

- `--root works` はリポジトリ内の版管理された保存先。実験として登録する走りは
  `--root experiments/<id>/work` にする。既定の `runs/projects` は git 管理外。
- premise はファイルから読むこともできる（`--premise-file premise.txt`）。
- 出力の `Current revision` が、この作品の版のIDである。

## 2. 生成を開始する（plan）

```bash
.venv/bin/python scripts/story_project.py --root works run prj-seaside
```

- provider を省略すると **Arena relay**（`works/prj-seaside/relay/`）になる。
- 応答がまだ無いので **exit 3** で止まり、次を表示する。

```text
pending: plan is waiting for operator response <key>
response: works/prj-seaside/relay/responses/<key>.json
prompts: 1 pending / 0 answered
  works/prj-seaside/relay/PROMPTS.md
ingest the answers: python3 scripts/story_project.py relay ingest prj-seaside --file <answers.txt>
resume after writing the response: story_project.py resume prj-seaside
```

## 3. 待っている1件に答えて、1コマンドで続ける

1ラウンドは「①次の1件を知る → ②答える → ③submit」で完結する。

```bash
# ① 何が待っているか（生成しない）。run が exit 3 のときは自動で書き出されている
.venv/bin/python scripts/story_project.py --root works relay status prj-seaside
#    → Next request: tag 1F3A9C2D (design: brief)
#    → works/prj-seaside/relay/PROMPTS.md / outbox/request-01-1F3A9C2D.md

# ② 生成した本文を answers.txt に書く（タグは PROMPTS.md の8文字をそのまま）
#    <<<ANSWER 1F3A9C2D>>>
#    …本文…
#    <<<END 1F3A9C2D>>>

# ③ 取り込んで、そのまま続ける
.venv/bin/python scripts/story_project.py --root works relay submit prj-seaside --file answers.txt
```

`relay submit` は次のどれかを同じ書式で報告し、その終了コードを返す。

| exit | 意味 | 次にすること |
| --- | --- | --- |
| `3` | 次の1件が待っている | `relay status` で示されたタグに答えて、また `relay submit` |
| `0` | 完成。待機なし | `Next:` の `render --out` で原稿を書き出す（手順5） |
| `2` | stage が失敗 | `Next:` の `resume --retry-failed`（新しい attempt。失敗 run は残る） |
| `1` | 貼り付けが不正（未知タグ・空・タグ重複） | `index.json` のタグを確認して書き直す（何も生成されない） |

`relay export` と `relay ingest` は③を分割した下位コマンドで、書き出しだけ・取り込み
だけを行いたいときに使う。取り込んだあと `resume` するのは `submit` と同じ経路。

- 応答は必ず `<<<ANSWER タグ>>>` … `<<<END タグ>>>` で囲む。タグは `PROMPTS.md` の
  8文字をそのまま使う（推測・使い回しをしない）。
- `ingest` はタグ→request key を台帳で引き、`prompt_hash` を固定して保存する。
  未知のタグは `unknown tag` として拒否し、勝手に別の request へ付けない。
- 応答を捏造しない。生成した本文だけを逐語で入れる。生成できなかった場合は
  `<<<ERROR タグ>>>` を使い、理由を1行書く。
- 手順3は **1件ごとに繰り返す**。1作品（3章）で12ラウンド（plan 1・設計 8・本文 3）。
  各ラウンドの `submit` は記録済み応答を再生成せず、次の未回答から続ける。
- 待っている要求はパイプライン順（plan → design → draft）に1件だけ示される。先の要求は
  前段の結果に依存するため、プロンプトを先に作らない（推測生成をしない）。
- 完成済み・失敗済みの作品への `submit` は取り込まない。完成なら `continue` / `revise`、
  失敗なら `--retry-failed` を案内する。

## 4. 完成と状態を確認する

```bash
.venv/bin/python scripts/story_project.py --root works relay status prj-seaside   # 1巡の報告
.venv/bin/python scripts/story_project.py --root works status prj-seaside         # 工程と原稿
.venv/bin/python scripts/story_project.py --root works doctor prj-seaside         # 横断整合性
```

`status` は `Relay: N answered / M pending` の1行を出し、待機中なら `next_actions` に
`relay export`（＝手順3）、完成なら `Manuscript:` と書き出しコマンドを出す。

`status` は工程（plan / design / draft）、未回答件数、次の操作、そして完成時には
`Manuscript:` と書き出しコマンドを表示する。`doctor` は project・node・revision・
artifact・pending を横断して確認する。`doctor` の終了コードは 0（ok）/ 1（error）。

`clean` / `pass` は「検査した範囲で進める」という意味で、面白さの保証ではない。

## 5. 原稿を読む

```bash
.venv/bin/python scripts/story_project.py --root works render prj-seaside \
  --out works/prj-seaside/manuscript.md
```

- 出力は章見出し・作品情報・検査用マーカーを含む結合 markdown。ここが最終成果物。
- `--json` を付けると、原稿本文とハッシュを機械可読な形でも返す。
- 読後の感想（長さ、説明過多、反復、会話、場面転換、伏線回収、文体）は、
  次の改善の材料として残す。U-03 の摩擦ログで分類する。

## 6. 続き・改訂・分岐・編纂へ進む

```bash
# 章を足す（新しい revision を作る。旧版は残る）
.venv/bin/python scripts/story_project.py --root works continue prj-seaside --add-chapters 1

# 特定の章だけを書き直す（他の章はバイト単位でコピーされる）
.venv/bin/python scripts/story_project.py --root works revise prj-seaside --chapter ch02

# 完成版から分岐して別案の node を作る
.venv/bin/python scripts/story_project.py --root works branch prj-seaside --node-id node-alt

# 子作品をまとめて編纂する
.venv/bin/python scripts/story_project.py --root works compose prj-seaside --out works/prj-seaside/collection.md
```

これらも provider を省略すれば relay になる。応答が足りない場合は手順3と同じく
`relay export` → 生成 → `relay ingest` → `resume` を回す。

## 7. セッションの外に状態を残す

```bash
.venv/bin/python scripts/story_project.py --root works bundle export prj-seaside \
  --out experiments/<id>/bundle
```

- `works/` をセッションブランチに commit / push すれば、sandbox が消えても再開できる。
- `bundle export` は relay と run をハッシュ付きでまとめる。`bundle verify` で照合できる。

## 8. 導線だけを確認する（生成なし）

実応答を使わず、固定台本で同じ導線を確認できる。CI と同じ回帰である。

```bash
make quickstart-check
```

`tests/test_standard_flow.py` が、premise → init → run → relay export → ingest →
resume → render を回し、`status` と `doctor` の表示、8文字タグ、未知タグの拒否を
固定する。`tests/test_relay_round.py` が、1ラウンド（status → submit → 次の1件）と
終了コード、完成後の再 submit が何も変えないこと、失敗時の `--retry-failed` 誘導を
固定する。台本の応答はモデル出力ではなく、品質の主張には使わない。

## この手順を使わない場合（研究用の固定経路）

過去の実験条件を再実行するときは、標準フローではなく凍結した経路を使う。

- `scripts/run_pipeline.py`: 固定タスク `t01` を protocol-v1 で回す研究用ハーネス。
- `scripts/run_twostage.py`: 固定 canon / 固定 design からの二段階方式スライス。

どちらも題材は固定で、作品を続き・改訂へ進める状態モデルを持たない。新しい作品を
作るときは、このページの `scripts/story_project.py` を使う
（[`standard_flow.md`](standard_flow.md) §1）。

## 失敗したとき

| 症状 | 意味 | 次にすること |
| --- | --- | --- |
| exit 3 + `pending:` | 応答待ち | `Next:` の `relay submit`（手順3） |
| exit 3 + `Skipped: the answer file had no block…` | 回答が入っていない/タグ違い | `relay status` のタグで書き直す |
| exit 3 + `response is still missing` | 応答ファイルがまだ無い | `relay export` で未回答を確認し、`submit` |
| exit 2 + `provider exited 4` | プロンプトが変わった応答（stale） | その応答は捨て、新しい `PROMPTS.md` のタグで生成し直す |
| exit 2 + `Failed: ... stage failed:` | 生成textが検査を通らない | `Next:` の `resume --retry-failed`（新しい attempt。失敗 run は残る） |
| exit 1 + `rejected (tag …): unknown tag` | タグの貼り間違い | `index.json` のタグを確認。`--map FROM=TO` は明示した場合だけ使う |
| `No module named ...` | 依存の無い python | `make setup` の `.venv/bin/python` を使う |

## してはいけないこと

- 生成していない応答を `responses/` に置くこと（provenance を偽ることになる）。
- 完了した run・relay・事前登録・`results.json` を書き換えること。
- 品質・面白さ・率・再発率・因果効果を主張すること（L2/L3 は `frozen_not_measured`）。
- プロンプト本文をチャットへ貼ること（relay は `<project>/relay` の中で完結させる）。
