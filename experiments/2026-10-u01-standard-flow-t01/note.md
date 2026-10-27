# U-01 標準フローの導線確認 — scripted / 3章 / 2026-10-27

- 日付: 2026-10-27
- 種類: **固定台本（scripted）による配線確認**。実モデルの応答は 1 件も無い。
- 決定: [`docs/standard_flow.md`](../../docs/standard_flow.md) / 手順: [`docs/quickstart.md`](../../docs/quickstart.md)
- 決定論的要約: [`summary.json`](summary.json)
- 出力した原稿: [`manuscript.md`](manuscript.md)（台本の本文であり、作品としての評価はしない）

## 1. 何を確かめたか

roadmap U-01 の完了の目安は「題材と条件から3章の原稿まで、Arenaセッション内で迷わず
進められ、最終成果物と状態が分かる」こと。ここでは、その導線が**1つの入口と1つの
往復手順**で最後まで通ることを確認した。

```text
init --root /tmp/u01（題材・3章・1200字）
  → run（既定 provider = arena relay）            exit 3
  → relay export → 台本応答を tag 付きで ingest → resume   ×12
  → complete（plan / design / draft すべて done）
  → render --out manuscript.md
  → status / doctor（findings 0）
```

| 項目 | 値 |
| --- | --- |
| 入口 | `scripts/story_project.py` のみ |
| provider | `arena-relay`（`<project>/relay` の `chat_operator.py`） |
| 台本 | `benchmarks/protocol-v1/fixtures/project-demo.json` |
| relay | 12 requests / 12 responses / pending 0 |
| resume 回数 | 12（1リクエストごとに1回） |
| run | 15（plan 1・design 8・draft 3・ほか resume 記録） |
| 状態 | `complete`、`doctor` findings 0 |
| 原稿 | 2,625 文字、`{{...}}` マーカー 11 個 |

**主張しないこと**: 面白さ・品質は測っていない。N=1 の配線確認であり、率・再発率・
因果効果は言わない。L2/L3 は `frozen_not_measured`。台本応答はモデル出力ではない。

## 2. 摩擦ログ（見つけた順）

分類は roadmap §2 の「完走 / 本文 / 編集 / 運用」に合わせた。

| # | 分類 | 摩擦 | 実害 | 今回の扱い |
| --- | --- | --- | --- | --- |
| F-1 | 運用 | **relay タグが 4 hex で衝突した**。同一 node では request key が `purpose` しか違わず、`design:history` と `plan` の先頭4文字が同じ `D982` になった。`ingest` は「成功」と表示しながら、回答を**すでに回答済みの plan リクエスト**へ保存した | 応答が別 request に付いたまま進む。静かに壊れる | `TAG_LENGTH = 8` に変更。衝突していた実キー対を回帰テストに固定（`tests/test_relay_prompts.py`） |
| F-2 | 運用 | 入口が `run_pipeline.py` / `run_twostage.py` / 創作projectに分かれ、標準がどれか決まっていない | 開始前に毎回判断が要る | `story_project.py` を標準と決定（`docs/standard_flow.md`） |
| F-3 | 運用 | relay を使うたび `--provider command --command "python3 scripts/chat_operator.py --dir ..."` を書く必要があった | コマンドが長く、`--dir` の綴り間違いが実行時まで分からない | `--provider arena` を追加し、**省略時の既定**にした。relay ディレクトリは `<project>/relay` に固定 |
| F-4 | 運用 | 応答待ちの表示が `response:` のパスだけで、次に開く `PROMPTS.md` と次のコマンドが分からなかった | 都度 `relay_prompts.py --dir ...` を思い出す必要 | exit 3 時に PROMPTS.md を自動更新し、ingest と resume の次コマンドを表示 |
| F-5 | 運用 | 完成後の `status` の `Next:` が空で、原稿の場所が出なかった | 原稿に辿り着けない（JSON を開く必要） | 完成時に `Manuscript:` と `render --out` を表示 |
| F-6 | 運用 | 1作品で **12往復**（plan 1・設計 8・本文 3）。`chat_operator` は最初の未回答で止まるため、未回答をまとめて書き出せない | セッションのターン数が嵩む | **未解決**。`relay export` の一括化と、`status` の pending 文言を relay 手順へ寄せるのは U-02 |
| F-7 | 完走 | 依存の無い `python3` で design stage が `No module named 'yaml'` で `failed`（exit 2） | 初回で原因が分かりにくい | quickstart の準備手順と失敗表に明記（`.venv/bin/python`） |
| F-8 | 本文 | `render` の出力に章見出しが無く、検査用マーカー（`{{time: ...}}`）が本文に残る | 読むための原稿としては粗糙。どこが章か分からない | **未解決**。U-08（原稿出力を読める形にそろえる） |
| F-9 | 編集 | `render --out` を別パスへ出しても `status` は `<project>/manuscript.md` しか見ないため「not written yet」のまま | 表示と実体が食い違う | **未解決**。U-08 で出力先の既定を1つに決める |
| F-10 | 運用 | `status` の next action が `pending <project>` のままで、relay の export/ingest を指さない | 2つ目の手順書があるように見える | **未解決**。U-02 |

F-1 は「1作品で見つかった実害」の例として、率を主張せずに修正したもの。修正は
タグ長の定数化と、衝突していたキー対の回帰テストだけで、relay の他の契約
（タグ→key の台帳、prompt_hash の固定、未知タグの拒否）は変えていない。過去の
experiments の relay ディレクトリと回答ファイルは書き換えていない。

## 3. 再現

実応答を使わずに同じ導線を回す（`make quickstart-check` と同じテスト）。

```bash
make setup
.venv/bin/python -m pytest tests/test_standard_flow.py -q
```

手で回す場合:

```bash
.venv/bin/python scripts/story_project.py --root /tmp/u01 init \
  --project-id prj-u01-flow --title "潮の記録者" \
  --premise "港町で失われた潮位記録を追う。記録を守る者と、書き換えたい者がいる。" \
  --chapters 3 --target-chars 1200
.venv/bin/python scripts/story_project.py --root /tmp/u01 run prj-u01-flow   # exit 3
# relay export → index.json の purpose に対応する台本応答を tag 付きで ingest → resume を12回
.venv/bin/python scripts/story_project.py --root /tmp/u01 render prj-u01-flow \
  --out experiments/2026-10-u01-standard-flow-t01/manuscript.md
```

台本応答は purpose（`plan` / `design:brief` … / `draft:ch01`）で引いた。本番の
Arena セッションでは、ここを実際に生成した応答に置き換える（捏造・代筆はしない）。

## 4. 次

1. **U-02**: F-6 / F-10。1回の `relay export` で stage の未回答をまとめて出し、
   `status` の pending を relay 手順へ寄せ、取り込み後の次操作を1か所にまとめる。
   完了済み応答を再生成しないことは既存の `resume` が担保している。
2. **U-03**: 実応答での dogfood。今回は scripted のみで、実モデルの導線は未確認。
3. **U-08**: F-8 / F-9。章見出しとマーカーの扱い、原稿の置き場所。
