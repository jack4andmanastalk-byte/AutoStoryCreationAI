# U-02 relay の一巡支援 — scripted / 1作品12ラウンド / 2026-10-27

- 日付: 2026-10-27
- 種類: **固定台本（scripted）による配線確認**。実モデルの応答は 1 件も無い。
- 決定と背景: [`docs/standard_flow.md`](../../docs/standard_flow.md) §7〜8、手順: [`docs/quickstart.md`](../../docs/quickstart.md)
- 決定論的要約: [`summary.json`](summary.json)

## 1. 何を確かめたか

U-01 の作例では、1作品が12往復し、各往復が **5操作**（`relay export` → 生成 →
`relay ingest` → `resume` → `status`）に分かれていた。どの状態でも「いま何が待っていて、
次に何をするか」が1か所で分かるようにし、往復の単位を1コマンドにした。

```text
relay status           … 状態・待っている1件・次のコマンド（生成しない）
（生成した本文を answers.txt に）
relay submit --file    … 取り込み + 再開。exit 0/3/2 がその作業単位の状態
```

| 項目 | 値 |
| --- | --- |
| 入口 | `scripts/story_project.py relay status` / `relay submit` |
| provider | `arena-relay`（`<project>/relay`） |
| 台本 | `benchmarks/protocol-v1/fixtures/project-demo.json` |
| ラウンド数 | 12（plan 1・設計 8・本文 3） |
| 1ラウンドの操作 | 3（status → 生成 → submit）。U-01 は 5 |
| 要求数 / 応答数 | 12 / 12（増えない。重複要求なし） |
| 最終状態 | `complete`、`next_command` は原稿の `render --out` |
| 完成後の再 submit | exit 0、`skipped` を返し、応答ファイル 12 件は 1 バイトも変わらない |

**主張しないこと**: 面白さ・品質は測っていない。N=1 の配線確認であり、率・再発率・
因果効果は言わない。L2/L3 は `frozen_not_measured`。台本応答はモデル出力ではない。

## 2. 摩擦ログ

| # | 分類 | 摩擦 | 今回の扱い |
| --- | --- | --- | --- |
| F-11 | 運用 | 1往復が5操作に分かれ、状態の確認と次の操作が別の場所にあった（U-01 F-6/F-10） | `relay submit`（ingest + resume）と `relay status` の1巡報告。`next_actions` も `relay export` に統一 |
| F-12 | 運用 | 終了コードが状態を表さず、スクリプトから次の判断ができなかった | `relay status` / `submit` は `0` 完了・待機なし / `3` 応答待ち / `2` 失敗 / `1` 貼り付け不正 |
| F-13 | 運用 | 完成済みの作品に `submit` すると、最後の回答が取り込まれて `resume` が「already complete」で失敗した（U-01 で実際に踏んだ） | 完成時は取り込まずに `skipped` を返し、`continue` / `revise` を案内（exit 0） |
| F-14 | 運用 | 失敗 stage で「retry は回答を再利用しない」と案内していたが、**実際は relay が prompt 単位で回答を返すため再利用される**（この作例で `--retry-failed` して確認） | 案内文を事実に合わせた（prompt が同一なら再利用、変われば再要求） |
| F-15 | 完走 | 依存の無い interpreter で走らせると design stage が `No module named 'yaml'` で `failed`。retry しても直らない | 失敗表示に「依存の問題であり回答の問題ではない」ことと `.venv/bin/python` での再実行を明示 |
| F-16 | 運用 | **往復回数そのもの（12）は減っていない**。設計8件と本文3件は前段の結果に依存するため、先にプロンプトを作れない（推測生成をしない方針） | 未解決。1応答で複数成果物を返す契約変更は検査の粒度が変わるため、U-03 の実運用で必要性が出てから扱う |
| F-17 | 編集 | 原稿に章見出しが無く、検査マーカーが本文に残る | 未解決（U-08） |

F-13 / F-14 は、案内文と実際の挙動が食い違っていた例である。どちらも「操作を減らした
結果、人が確かめずに進む経路」で見つかった。案内文は実装の事実に合わせ、テストで
固定した（完成後の再 submit が応答を変えないこと、失敗時の `--retry-failed` 誘導）。

## 3. 再現

```bash
make setup
.venv/bin/python -m pytest tests/test_relay_round.py -q   # 7 件
make quickstart-check                                    # 16 件（U-01 と併せて）
```

手で回す場合（1ラウンド）:

```bash
.venv/bin/python scripts/story_project.py --root /tmp/u02 relay status prj-u02
#  → Next request: tag <8文字> / Next: … relay submit prj-u02 --file <answers.txt>
.venv/bin/python scripts/story_project.py --root /tmp/u02 relay submit prj-u02 --file answers.txt
#  → exit 3（次の1件）/ 0（完成）/ 2（失敗）
```

## 4. 次

1. **U-03**: 実応答での dogfood。U-01/U-02 はどちらも scripted であり、**実モデルの
   導線は未確認**。摩擦の分類は「完走 / 本文 / 編集 / 運用」で続ける。
2. **U-04**: 失敗回復（F-15 の依存、設計1文書・1章単位の再試行）。
3. **U-08**: 原稿の章見出しとマーカー（F-17）。
4. F-16（12往復）は、U-03 で実害が再現したときに契約変更として扱う。
