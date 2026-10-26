# バッチ A の実行手順（コピペ用）

- 事前登録: [`preregistration.md`](preregistration.md) / [`preregistration.json`](preregistration.json)
  （**走らせる前に固定**。計測はこのファイルの閾値だけを使う）
- 目的と位置づけ: [`docs/two_stage_slice.md`](../../docs/two_stage_slice.md) §21
- 状態: **未走行**（`sample-1`〜`sample-3` はまだ無い）

実走りは `scripts/chat_operator.py` のリレーで行う。生成は「依頼ファイルを読んで回答ファイルを書く」
オペレータ（人または対話エージェント）の仕事で、このリポジトリはモデルを呼ばない。応答は
**記録された実テキスト**であり、こちらで作文しない。

## 0. 前提

```bash
make setup   # .venv（初回のみ）

# 入力ログが clean であることを、走らせる前に再確認する
.venv/bin/python scripts/check_gamelog.py \
  --game-log experiments/2026-10-realrun-a-t01/inputs/game_log.json \
  --canon experiments/2026-10-realrun-a-t01/inputs/canon \
  --design-dir experiments/2026-10-realrun-a-t01/inputs/design --require-design
# → status: clean（所見 0）でなければ中止する
```

## 1. 1 標本の進め方（`sample-1`、`sample-2`、`sample-3` を同じ手順で）

**1 回目は `--resume` を付けない**（付けると `--resume needs state.json` で exit 2）。
2 回目以降は必ず付ける。

```bash
RELAY=$PWD/experiments/2026-10-realrun-a-t01/relay/sample-1
BUNDLE=$PWD/experiments/2026-10-realrun-a-t01

.venv/bin/python scripts/run_twostage.py --task t01 --stage b \
  --game-log $BUNDLE/inputs/game_log.json \
  --canon $BUNDLE/inputs/canon \
  --design-dir $BUNDLE/inputs/design \
  --provider command \
  --command "$PWD/.venv/bin/python scripts/chat_operator.py --dir $RELAY" \
  --observe-surface --seed 0 \
  --out $BUNDLE/sample-1 --run-id run \
  --results $BUNDLE/sample-1/results.json
```

回答が無い状態で起動すると **exit 3** で止まり、書くべきファイルを表示する。

```bash
# 何が残っているか
.venv/bin/python scripts/chat_operator.py --dir $RELAY --status
# → requests / ready / pending（`status` キーは無い）
```

`$RELAY/requests/<key>.json` を読み、`$RELAY/responses/<key>.json` に次の形で書く。

```json
{
  "text": "<本文。マーカー {{time: ...}}{{location: ...}} を含めてよい>",
  "model": "arena-agent-mode",
  "model_version": "unversioned-2026-10-26",
  "provenance": {"origin": "fresh"}
}
```

- `origin` は **`fresh`**（このバッチのために新しく書いた）。過去の走りの本文を再利用した場合は
  `{"origin": "reused", "source_run_id": "..."}` と正直に書き、標本として扱わない。
- 応答は書き終えたら `--resume` で再開する。修復が入ると新しい要求（`attempt 2`）が増える。

```bash
.venv/bin/python scripts/run_twostage.py --task t01 --stage b \
  --game-log $BUNDLE/inputs/game_log.json \
  --canon $BUNDLE/inputs/canon \
  --design-dir $BUNDLE/inputs/design \
  --provider command \
  --command "$PWD/.venv/bin/python scripts/chat_operator.py --dir $RELAY" \
  --observe-surface --seed 0 \
  --out $BUNDLE/sample-1 --run-id run \
  --results $BUNDLE/sample-1/results.json --resume
```

`sample-1` が終わったら `sample-2`（`--seed 1`、`$RELAY=.../relay/sample-2`、`--out .../sample-2`）、
`sample-3`（`--seed 2`）を同じ手順で。**リレー送信ディレクトリは標本ごとに分ける**
（同じディレクトリを使い回すと、前の標本の回答が再利用される）。

## 2. 計測（3 標本が揃ってから 1 回）

```bash
.venv/bin/python scripts/measure_realrun_a.py \
  --bundle experiments/2026-10-realrun-a-t01
# → experiments/2026-10-realrun-a-t01/results.json（schema: realrun-a-v1）
#   事前登録の sha256 を記録し、R1（地名の枝）・R2（長さ）・R3（繰り返す失敗）を判定する
```

副次指標（判定には使わない）:

```bash
.venv/bin/python scripts/compare_l1_arms.py --task t01 \
  --canon experiments/2026-10-realrun-a-t01/inputs/canon \
  --arm "sample-1=experiments/2026-10-realrun-a-t01/sample-1/run/text" \
  --arm "sample-2=experiments/2026-10-realrun-a-t01/sample-2/run/text" \
  --arm "sample-3=experiments/2026-10-realrun-a-t01/sample-3/run/text" \
  --out experiments/2026-10-realrun-a-t01/l1-metrics.json
```

（`compare_l1_arms.py` が応答ディレクトリを要求する場合は `sample-N/run/text` ではなく、
各標本の `rewrite.report.json` の数値を [`note.md`](note.md) に写すだけでもよい。CED は参考値。）

## 3. 記録すること（`note.md` を走行後に書く）

- 標本ごとの `status`、章ごとの字数・マーカー・修復回数、所見の検査名。
- 観測（`observations`）の目的地と枝（`off_log` / `undeclared`）。
- **判定は `results.json` の verdict をそのまま引用する**（人が読み替えない）。
- 独立性の限界（operator が誰か、`provenance` の `origin`）と、L2/L3・G5 を主張しない旨。

## 4. つまずき

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| exit 2 `--resume needs state.json` | 初回に `--resume` を付けた | 初回は付けない |
| exit 3 | 回答がまだ無い | `--status` を見て `responses/<key>.json` を書く |
| exit 4 `stale` | プロンプトが変わった後の古い回答 | 要求を作り直す（回答を流用しない） |
| run dir を作り直したい | 既存 run は再利用できない | `rm -rf sample-N` して**別標本として**やり直す（同じ番号を黙って上書きしない） |
| 観測が空 | `--observe-surface` 忘れ | その標本は `observations_absent` と記録され、R1 の判定に使われない |
