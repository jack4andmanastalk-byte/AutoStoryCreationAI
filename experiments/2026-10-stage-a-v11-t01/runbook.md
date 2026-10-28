# 場面フレーム（schema 1.1）の実走 手順（t01 / Stage A → Stage B）

- 目的: 1.1 の Stage A（フェイズ・結果の種別・救済・持ち越し）が、実モデルの応答で
  検査 `scene_frame` を通るか、また Stage B が 1.1 のログを小説化できるかを確かめる。
- 位置づけ: 実験経路（`run_twostage.py`）。標準フローではない。
  仕様は [`docs/two_stage_slice.md`](../../docs/two_stage_slice.md) §27。
- 入力: `inputs/canon` と `inputs/design` は [`2026-10-trpg-slice-t01`](../2026-10-trpg-slice-t01/note.md) と同一
  （複製。`game_log.json` と `rewrite/` は使わない＝ログは今回の応答から作る）。
- 依頼文（Stage A、1 回目）: [`prompts/stage-a.attempt-1.prompt.md`](prompts/stage-a.attempt-1.prompt.md)
  （`prompt_hash` = `ac3075465acb2e35`）。修復の依頼文は検査後に `runs/run2/PROMPTS.md` と
  `relay/run2/requests/` に出る。

## 0. 前提

```bash
make setup                       # .venv（初回のみ）
.venv/bin/python -m pytest tests/test_gamelog_scene_frame.py -q   # 1.1 の配線が生きていること
```

## 保存先とチェックポイント（Arena / GitHub）

過去の `run1` は完了済み。以下は新しい `run2` 用で、既存の応答を上書きしない。
`out/`・`build/` は Arena のスナップショット対象外なので使わない。次のコマンドは
**エージェントがリポジトリ内で**実行し、状態を GitHub の作業ブランチに保存する。
開始前に run と relay が存在しないこと、保存先が版管理可能なことを検査する。

```bash
B=experiments/2026-10-stage-a-v11-t01
test ! -e "$B/runs/run2" && test ! -e "$B/relay/run2" || { echo 'run2 already exists; stop' >&2; exit 1; }
python scripts/check_persistent_paths.py "$B/runs/run2" "$B/relay/run2" "$B/runs/run2-results.json"
```

- 回答待ち（exit 3）ごとに `runs/run2/` と `relay/run2/` の state・要求・応答を
  両方保存し、内容（個人情報・秘密・著作権・サイズ）を確認してから対象ファイルだけを
  `git add` / `git commit` / `git push` する。完了時は結果も同様に保存する。
  **ローカルのチェックアウトだけでは GitHub に保存されない。** commit/push に失敗したら
  保存完了と報告せず停止する。コミット前の編集や秘密情報を巻き込まない。
- 再開時は同じブランチの最新コミットを復元し、入力・プロンプト・設定を変えずに
  `--resume`。GitHub 由来の state と relay が揃うことを確認する。仮想環境は消えても再作成可能。
- 事前検査は Git の ignore と既知の Arena 除外名だけを見る。push の成功、機密性、容量、
  GitHub の権限までは保証しない。Git 管理できない大きなデータは既存の外部保存方式を使う。

## 1. 1 回目（`--resume` を付けない）

```bash
B=experiments/2026-10-stage-a-v11-t01
R=$PWD/$B/relay/run2
CMD="$PWD/.venv/bin/python scripts/chat_operator.py --dir $R"

.venv/bin/python scripts/run_twostage.py --task t01 --stage both --gamelog-schema 1.1 \
  --canon $B/inputs/canon --design-dir $B/inputs/design \
  --provider command --command "$CMD" --observe-surface --seed 0 \
  --out ${B}/runs --run-id run2 --results ${B}/runs/run2-results.json
# → exit 3（Stage A の回答待ち）。$R/requests/two-stage-t01-s0-stage_a-a1.json が出る
```

## 2. 回答を書く（オペレータの仕事）

1. `prompts/stage-a.attempt-1.prompt.md` の内容を Arena のチャットに貼る。
2. 返ってきた **JSON だけ**（説明文なし。コードフェンスは可）を次の形で保存する。

```bash
B=experiments/2026-10-stage-a-v11-t01
R=$PWD/$B/relay/run2
mkdir -p "$R/responses"
# $R/responses/two-stage-t01-s0-stage_a-a1.json の中身:
# {
#   "text": "<ゲームログの JSON 本文>",
#   "model": "arena-agent-mode",
#   "model_version": "unversioned-2026-10-28",
#   "provenance": {"origin": "fresh"}
# }
```

- `origin` は `fresh`（この実走のために新しく得た応答）。過去の応答の再利用は
  `{"origin": "reused", "source_run_id": "..."}` と書き、標本として扱わない。
- 応答者（人か、どのチャットか）を新しい run の記録に書く。

## 3. 再開（応答を書くたびに同じ command に `--resume` を付けて実行）

```bash
B=experiments/2026-10-stage-a-v11-t01
R=$PWD/$B/relay/run2
CMD="$PWD/.venv/bin/python scripts/chat_operator.py --dir $R"
.venv/bin/python scripts/run_twostage.py --task t01 --stage both --gamelog-schema 1.1 \
  --canon $B/inputs/canon --design-dir $B/inputs/design \
  --provider command --command "$CMD" --observe-surface --seed 0 \
  --out ${B}/runs --run-id run2 --results ${B}/runs/run2-results.json --resume
```

- `--gamelog-schema 1.1` は**毎回**付ける（付けないと設定の不一致で拒否される）。
- 状況確認: `.venv/bin/python scripts/chat_operator.py --dir $R --status`
- exit 3 = 次の回答待ち（書くべきファイルが表示される）/ 0 = 完了 / 2 = 失敗。
- 検査に落ちた場合は修復の依頼（`stage_a:repair`）が 1 回出る。修復の依頼文は
  `$B/runs/run2/PROMPTS.md` に出るので、同じ手順で答える。
- 回答を流用したい場合は必ず `status` を見る。内容が変わった要求には古い回答を使わない（exit 4 `stale`）。

## 4. 記録（走行後に新しい run の記録を書く。既存 `note.md` は上書きしない）

見る場所:

| 見たいもの | 場所 |
| --- | --- |
| Stage A の検査結果（`scene_frame` を含む 9 検査） | `$B/runs/run2/game_log.report.json` |
| 試行・修復の回数 | 同上の `attempts` / `repairs` / `first_attempt_findings` |
| 1.1 のログ本体 | `$B/runs/run2/game_log.json` |
| 本文（Stage B） | `$B/runs/run2/text/ch0*.md` と `rewrite.report.json` |
| 判定の要約 | `${B}/runs/run2-results.json` |

新しい run の記録に残すこと:

- 応答者と `origin`、応答の回数、修復の回数、ステータス（`clean` / `unresolved`）。
- `scene_frame` の所見（重大度と文言）と、人が見て妥当だったか。
- 救済（`rescue`）と持ち越し（`carry_forward`）が、本文に実際に反映されたか（人が読んで確認。検査はしない）。
- 1.0 の凍結実験（`2026-10-trpg-slice-t01`、`full-t01`）との比較は、件数の参考値にとどめる。
- 限界: L1 は構造・衛生の検査であり、物語の質の証拠ではない。G5（同条件での再現）は主張しない。
  L2/L3 は凍結中。`clean` は意味的な整合性を保証しない。

## 5. 中止・やり直し

- run dir は再利用できない。やり直すときは `runs/run2/` と `relay/run2/` を消すのではなく、
  `run3` のような新しい名前にする（同じ番号を黙って上書きしない）。
- 1.1 の結果が悪くても、判定基準（`scene_frame` の所見件数と本文の確認）を後から変えない。
  変えるなら新しい run の記録に理由と版を残す。
