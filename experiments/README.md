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

## 規約

* `note.md` はテンプレートに数値が入った状態で生成されます。**「限界」と「次に試すこと」は
  必ず人が書いてからコミット**してください。書かれていない実験は、後から読む人にとって
  「良くなった」という主張だけが残ります。
* 生の run 出力（`runs/`、章テキスト、応答ログ）は**コミットしません**。再現に必要なのは
  `manifest.json` の `git_commit`・`prompt_hashes`・モデル設定で、それらは `results.json` に
  転記されます。
* プロバイダが `scripted` の実験（台本）は**配線検証**です。性能の主張には使えません。
  `note.md` の「限界」にその旨が自動で入ります。
* 本文は `runs/` にしかありません（git 管理外）。`runs/` は残らないものとして扱います。
  L2/L3 凍結中は新しい評定用の盲検ペアを作らず、`make_blind_pairs.py` は既存資産の
  再現が必要な場合にだけ使います。
* 同じ `id` を再利用しないでください。条件を変えたら新しい `id` にします
  （例: `2026-10-s1-vs-s0-a`、`2026-10-s1-vs-s0-b`）。

## 使い方

```bash
# 台本で配線を確認（結果は build/ に出る。コミットしない）
make experiment

# Arena × L1: t01 × S0–S3 × seed 0 のパイロット
python3 scripts/run_experiment.py --id 2026-10-arena-l1-t01 \
  --tasks t01 --systems s0 s1 s2 s3 --seeds 0 \
  --provider command --model arena-agent-mode --model-version unversioned-2026-10-24 \
  --command "python3 scripts/chat_operator.py --dir runs/operator/arena-l1-t01"
# 未回答のプロンプトを書き出す（NEED RESPONSE で止まった後に実行）
python3 scripts/relay_prompts.py export --dir runs/operator/arena-l1-t01
# Arena で回答後: relay_prompts.py ingest → 同じ run_experiment を再実行
```

`--provider command` のアダプタは、標準入力の JSON（`GenerationRequest`）に対して
標準出力に `{"text": "..."}` を返すものです。`scripts/judge_adapter.py` を使う L2 判定は
凍結中なので、新規実験には接続しません。
