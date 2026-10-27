# バッチ B の実行手順（Arena Agent Mode 内で実行する）

- 事前登録: [`preregistration.md`](preregistration.md) / [`preregistration.json`](preregistration.json)
  （**走らせる前に固定**。計測はこのファイルの閾値とプロンプト digest を使う）
- 目的と位置づけ: [`docs/two_stage_slice.md`](../../docs/two_stage_slice.md) §23
- 運用モデル: [`docs/arena_operation.md`](../../docs/arena_operation.md)
- 状態: **未走行**（`sample-1/run` はまだ無い）

この手順の宛先は **Arena Agent Mode のエージェント**である。利用者はローカルで
コマンドを実行しない。エージェントが sandbox 内のチェックアウトでパイプラインを駆動し、
relay の要求への応答もエージェント自身が生成して逐語で取り込む（生成と計測の担い手が
同一であること、応答の独立性を主張しないことは事前登録どおり）。利用者の役割は
開始の指示、結果の監査、マージ判断である。

**プロンプト本文は利用者へのチャットに貼らない。** パイプラインが実行時に relay 配下へ
要求ファイルとして書き出し、エージェントはそのファイルを読んで応答する。
応答はエージェントが実際に生成したテキストだけを取り込み、生成していない応答や
測っていない結果を書かない。

前提: コマンドはすべて sandbox 内のリポジトリルートで実行する。シェル状態は
ターン（コマンド呼び出し）を越えて持続しないため、変数は各ブロックの先頭で定義し直す。

## 0. 準備（エージェントが実行）

```bash
cd /home/user/AutoStoryCreationAI
test -x .venv/bin/python || make setup   # .venv が無ければ作る

BUNDLE=$PWD/experiments/2026-10-realrun-b-t01
RELAY=$BUNDLE/relay/sample-1
RUN_ROOT=$BUNDLE/sample-1
ANS_DIR=$BUNDLE/answers/sample-1
PY=.venv/bin/python
MODEL=arena-agent-mode
MODEL_VERSION=unversioned-$(date +%F)   # 初回に確定し、標本の終わりまで同じ値を記録に使う

mkdir -p "$RELAY" "$ANS_DIR"
```

実行コマンドは毎回次を使う（関数ではなく、その都度この形で実行する）。

```bash
"$PY" scripts/run_pipeline.py --task t01 --system s1 --stage all --design \
  --provider command \
  --command "$PWD/.venv/bin/python scripts/chat_operator.py --dir $RELAY --model $MODEL --model-version $MODEL_VERSION" \
  --model "$MODEL" --seed 0 --temperature 0.8 \
  --out "$RUN_ROOT" --run-id run
```

- `--canon` は付けない。付けると plan が canon を作らず、登録した S1 全体にならない。
- `--stage all` のままにする。plan で作った単一の canon を 8 設計と draft が読む。
- `scripts/run_pipeline.py` には `--resume` が無い。回答待ちで止まった未完成 run だけを
  消して同じコマンドを再実行する。relay の応答が残るので、済んだ要求は再生され、
  次の未回答要求でまた止まる。**relay は消さない。**
- `MODEL_VERSION` は Arena の版を固定できないことの記録であり、同一出力の再現（G5）は
  主張しない。初回実行時に確定した値を `note.md` に記録し、以後変えない。

## 1. 1 巡の進め方（完走または終端失敗まで繰り返す）

まず 1 回起動する。回答が無いので、通常は最初の要求（plan）で止まる。

```bash
# §0 の変数を定義し直してから §0 の実行コマンドを回す。終了直後に次を確認する。
"$PY" scripts/chat_operator.py --dir "$RELAY" --status
test -f "$RUN_ROOT/run/run-summary.json" && echo "run: complete" || echo "run: incomplete"
```

判定（`run_pipeline.py` の exit code と `pending` 件数）:

| exit | `pending` | 意味 | 次 |
| ---: | --- | --- | --- |
| 0 | - | 完走しゲート合格 | §2 の計測へ |
| 1 | - | 完走したがゲート不合格 | 再実行せず §2 の計測へ |
| 2 | 1 件以上 | 回答待ちで停止 | 下の手順で回答して再開 |
| 2 | 0 件 | 回答待ちではない失敗（修復上限・不受理・stale 等） | **run を消さず**、§2 の計測と manifest 確認へ |

### 回答待ちの場合

要求をエージェントが読める形に書き出す。プロンプトはこのファイルの中だけに現れ、
利用者へのチャットには貼らない。

```bash
"$PY" scripts/relay_prompts.py export --dir "$RELAY"
# → $RELAY/relay/PROMPTS.md（未回答ぶん）
#    $RELAY/relay/outbox/request-*.md（要求ごと）
```

1. エージェントが `$RELAY/relay/PROMPTS.md`（または `outbox/request-*.md`）を読み、
   未回答の要求に対して応答を生成する。通常は依存順に 1 件ずつ現れる。
   修復／再試行が入ると要求が増える。
2. 生成した `<<<ANSWER タグ>>>` … `<<<END タグ>>>` のブロックを、**新しい**
   回答ファイルへ逐語で保存する。前巡の回答ファイルは上書きしない。
   利用者が別の担い手の応答を持ち込む場合は、その応答を逐語で保存し、
   出所を `note.md` に記録する（エージェント生成と混ぜない）。

```bash
ANS=$ANS_DIR/answers-001.txt   # 巡ごとに 002, 003, ... と増やす
# ここで $ANS に、生成した ANSWER ブロックを保存する

"$PY" scripts/relay_prompts.py ingest --dir "$RELAY" --file "$ANS" \
  --model "$MODEL" --model-version "$MODEL_VERSION"
"$PY" scripts/chat_operator.py --dir "$RELAY" --status
```

3. 回答した要求が `pending` から消えたことを確かめてから、**回答待ちだった
   未完成 run だけ**を消して再実行する。

```bash
test -f "$RUN_ROOT/run/run-summary.json" && echo "complete: do not delete" || rm -rf "$RUN_ROOT/run"
# §0 の実行コマンドを再実行し、exit code と pending を確認する
```

`pending` が出る間は同じ巡を繰り返す。修復が無ければ要求は最低 12 件
（plan 1・設計 8・draft 3）。plan 修復、設計修復、draft 再試行で増えることがある。

注意:

- 過去の run の応答を流用しない。流用する場合は取り込まずに止め、別バッチとして扱う。
- `relay_prompts.py ingest` は現状 `provenance.origin` を書かないため、台帳上は
  `unspecified` になる。**後から `fresh` と書き換えない。**
- タグは表示された 4 文字を正確に使う。`--map` で付け替えた場合は、その事実を
  `note.md` に記録する（推測で付け替えない）。

## 2. 計測（完走または終端失敗の後に 1 回、エージェントが実行）

```bash
"$PY" scripts/measure_realrun_b.py \
  --bundle experiments/2026-10-realrun-b-t01
# → experiments/2026-10-realrun-b-t01/results.json（schema: realrun-b-v1）
#   事前登録の sha256 を記録し、B0 条件・B1 完走・B2 初回所見
#   （修復で消えたものも数える）・B3 長さ・B4 監査を判定する
```

`results.json` にプロンプト本文・応答本文は入れていない（件数・検査名・hash のみ）。

## 3. 記録と GitHub への反映

- `results.json` の verdict を**読み替えずに引用**して `note.md` に書く。
- 段ごと: plan attempts／初回失敗、canon の件数と sha256、設計書ごとの
  status・attempts・初回 findings・最終 findings、章ごとの字数・試行・
  初回 issues・補完マーカー、監査の内訳。
- 応答数と `provenance.origin` の内訳、operator が誰か（独立性の限界）。
- L2/L3 が `frozen_not_measured`、G5 未達である旨。N=1 で率を主張しない旨。
- 完了したら、バンドルの成果物（`relay/`・`sample-1/run`・`results.json`・`note.md`）を
  セッションブランチへ commit / push し、PR の CI（`research-check`）で再検証する。
  **マージは利用者の指示があるときだけ行う。**

## 4. つまずき

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| `run already exists` | 同じ `--run-id run` が残っている | `run-summary.json` があれば完走済みとして計測。回答待ちの未完成 run だけ §1 の手順で消す |
| exit 2 で `pending` が空 | 修復上限・本文不受理・stale 等の終端失敗 | run を消さず、stderr と `$RUN_ROOT/run/manifest.json` を見て計測する |
| `STALE RESPONSE` | 応答を書いた後にプロンプトが変わった | 条件のずれとして止める。黙って応答を差し替えない |
| ingest で `unknown tag` | タグの転記違い | 表示タグを確認する。`--map` は明示した場合だけ使い、記録する |
| 計測で `condition_violation` | `--canon` 使用、plan 欠落、プロンプト digest 不一致など | 登録を後から直さない。その走りは本バッチの標本として数えない |
| 台本で試したい | 配線確認は tests が担う | scripted の出力を `sample-1` に入れない。実応答として扱わない |
| セッションが切れた | sandbox の状態は揮発しうる | GitHub に上げた節目のコミットから復元する。relay をバンドル内に置くのはこのため |
