# experiments — 実験ノート

1 つの実験 = 1 ディレクトリ。**結果と限界を書いたものだけ**をコミットします。

> 新規実験の範囲は **Arena.ai × L1** です。L2/L3 は 2026-10-24 に運用凍結したため、
> G3/G4 は測定せず、版を固定できない Arena run では G5 も主張しません。すべて探索的な
> 参考値として記録します（[`../docs/evaluation_scope.md`](../docs/evaluation_scope.md)）。
> `run_experiment.py` はこの範囲を `results.json` と `note.md` に自動記録します。

```
experiments/<id>/
├── results.json   # 自動生成（scripts/run_experiment.py）
└── note.md        # 仮説・条件・N・結果・限界・次に試すこと
```

## 保存・公開の規約

* `note.md` には条件、結果、限界、次に試すことを残します。`scripted` は配線検証であり、
  作品の品質やモデル性能の証拠ではありません。
* ルート直下の `/runs/` は Git 管理外です。一方、作品内の `runs/` はこのルールでは
  除外されません。`experiments/<id>/work/<project>/runs/` のような内部 `runs/` は、
  実際に追跡されることがあります。以前の「すべての `runs/` が gitignore 対象」という
  記述は正しくありません。
* 中断・復元・監査が必要な作品は、`project.json`、`nodes/`、`relay/`、作品内の
  `runs/` を含む必要な状態を一緒に保全します。relay 応答だけや結果のハッシュだけでは
  再開・再現を保証できません。保存前に機密・個人情報・権利・容量を確認し、外部由来の
  大量データを無条件に Git に入れないでください。
* Arena のスナップショットでは、どの階層でも `out/` や `build/` 等は対象外です。
  `scripts/check_persistent_paths.py` で保存先を確認し、節目で内容を点検した上で
  作業ブランチに commit / push します。検査の成功自体は保存を保証しません。
* [`2026-10-trpg-slice-t01/inputs/`](2026-10-trpg-slice-t01/inputs/) は固定台本の
  入力です。[`2026-10-dogfood-01/`](2026-10-dogfood-01/) 等には標準フローの
  実応答・作品状態を保存しています。既存の実験記録を上書きしないでください。
* 同じ `id` を再利用せず、条件を変えたら新しい `id` にします。

## 過去ブランチの履歴資料

[`archives/legacy-fixed-canon-b-2026-10-27/`](archives/legacy-fixed-canon-b-2026-10-27/README.md)
には、未完の旧 Batch B（固定 canon）の差分を保全しています。現行の同名実験とは条件が
異なり、完走結果ではありません。通常の実験バンドルではなく復元・比較用の履歴資料です。

## 使い方

```bash
# 台本で配線を確認（結果は build/ に出る。コミットしない）
make experiment

# Arena × L1: t01 × S0–S3 × seed 0 のパイロット
python3 scripts/run_experiment.py --id 2026-10-arena-l1-t01 \
  --tasks t01 --systems s0 s1 s2 s3 --seeds 0 \
  --provider command --model arena-agent-mode --model-version unversioned-2026-10-24 \
  --command "python3 scripts/chat_operator.py --dir runs/operator/arena-l1-t01" \
  --runs runs/arena-l1-t01 --out build/experiments/2026-10-arena-l1-t01
# 未回答のプロンプトを書き出す（初回は4件。回答がない間の失敗・exit 1は実験結果ではない）
python3 scripts/relay_prompts.py export --dir runs/operator/arena-l1-t01
# Arena で回答後: relay_prompts.py ingest → 同じ run_experiment を再実行
# 全セル完了後にだけ --out experiments/2026-10-arena-l1-t01 へ変え、結果を保存する
```

`--provider command` のアダプタは、標準入力の JSON（`GenerationRequest`）に対して
標準出力に `{"text": "..."}` を返すものです。`scripts/judge_adapter.py` を使う L2 判定は
凍結中なので、新規実験には接続しません。

完了runの記録済み応答を外部providerなしで再実行する場合は `--provider replay` を使います。
source hash、request key、prompt全文、response hash、成果物一致を検査する手順は
[`../docs/replay.md`](../docs/replay.md) を参照してください。replayは新規生成やG5の
モデル再現性の証拠ではなく、既存の実験結果を上書きしないよう新しい出力先が必要です。
