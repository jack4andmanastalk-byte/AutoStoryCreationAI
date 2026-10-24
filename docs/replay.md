# 記録済み応答の replay

`run_experiment.py --provider replay` は、完了した1 run の `manifest.json` と
`responses.jsonl` だけを使い、外部 provider を呼ばずに同じ pipeline を再実行します。
目的は、**記録した応答が現在の配線でも同じ成果物を作るかを監査する**ことです。

これは新規生成ではありません。また、Arena などの版を固定できないモデルが同じ文章を
再生成できること（G5）を示すものでもありません。L2/L3 の評定・較正も行いません。

## 実行

replay は1回につき **1 task × 1 system × 1 seed** に限定します。元runのセルと
protocol が CLI 指定と一致しない場合は開始前に終了します。

```bash
SOURCE=runs/<source-run-id>
MANIFEST_SHA=$(sha256sum "$SOURCE/manifest.json" | cut -d' ' -f1)
RESPONSES_SHA=$(sha256sum "$SOURCE/responses.jsonl" | cut -d' ' -f1)

.venv/bin/python scripts/run_experiment.py \
  --id 2026-10-replay-t02 --tasks t02 --systems s1 --seeds 0 \
  --provider replay --replay-from "$SOURCE" \
  --replay-manifest-sha256 "$MANIFEST_SHA" \
  --replay-responses-sha256 "$RESPONSES_SHA" \
  --runs runs/replay --out experiments/2026-10-replay-t02
```

`--replay-manifest-sha256` と `--replay-responses-sha256` は任意ですが、
古いrunを明示的に固定する場合は両方を推奨します。`--model` と `--model-version` は
指定しません。モデル名・版は元runの記録を引き継ぎ、replay が上書きしません。

既に `results.json` がある出力先は使えません。元の実験結果を上書きしないよう、
新しい `--id` / `--out` を指定してください。

## 検査するもの

| 層 | 検査 |
| --- | --- |
| 元run | `status=ok`、task/system/seed/protocol の一致 |
| source pin | manifest SHA-256、responses JSONL SHA-256、応答件数 |
| request | `system-task-seed-purpose-attempt` の request key、prompt hash、**prompt全文**、seed、temperature |
| response | 応答本文の SHA-256。新しいledgerでは各entryの `response_sha256` も照合 |
| 消費 | 元runの全応答を1回ずつ使い、未消費・重複消費がないこと |
| prompt台帳 | 元manifestと再実行ledgerの `prompt_hashes` が一致すること |
| 成果物 | plan・canon・design・draft・最終textなどの SHA-256 が一致すること |
| 元runの保全 | replay前後で元manifest・responses logのhashが変わらないこと |

`audit.json` だけは、runごとに変わる canon パスと `generated_at` を比較対象から外し、
それ以外の監査内容をJSONとして比較します。最終本文・設計書・初稿応答などは通常どおり
バイト一致です。一つでも不一致なら replay セルは失敗します。

新しいrunの `manifest.json` には `responses_sha256` と `response_count` を記録します。
各response entryには `context` と `response_sha256` も保存します。これらの追加は
記録・監査の強化であり、protocol-v1 のタスク・指標・閾値の変更ではありません。

古いledgerにはこれらのフィールドがないことがあります。その場合も、CLIで渡した
manifest/log hashを開始時に固定し、request keyは旧logの順序・operator usageから復元します。
`replay-audit.json` の `responses_pinned_by_source_manifest=false` は、元manifest自体に
log hashが無かったことを示します。CLI pinを検査していないことではありません。

## 出力

新しいrunには次が残ります。

- `replay-audit.json`: source run ID・source hash・requestごとのprompt/response hash・
  成果物ごとのsource/replay hash・未消費request・検査結果
- `cell-summary.json`: `response_provenance.counts.replay` と replay 検査の要約
- `manifest.json`: `provider=replay`、応答logのhash・件数、元のモデルメタデータ

実験の `results.json` には `replay.source` と `replay.cells` を追加し、sourceと新規runを
相互に辿れるようにします。元のresponse provenance（fresh/reused/scripted）は
`source_origin` として残しますが、replay応答を新規fresh応答として数え直しません。

`runs/` はGit管理外です。commit済みの結果とhashだけでは、失われた応答本文を復元できません。
replayを後で実行する場合は、元runの `manifest.json`・`responses.jsonl`・比較対象成果物を
ワークスペースまたは別の監査保管先に保持してください。
