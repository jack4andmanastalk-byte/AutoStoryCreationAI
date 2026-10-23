# experiments — 実験ノート

1 つの実験 = 1 ディレクトリ。**結果と限界を書いたものだけ**をコミットします。

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
* 同じ `id` を再利用しないでください。条件を変えたら新しい `id` にします
  （例: `2026-10-s1-vs-s0-a`、`2026-10-s1-vs-s0-b`）。

## 使い方

```bash
# 台本で配線を確認（結果は build/ に出る。コミットしない）
make experiment

# 実モデルで 1 タスク × 3 seed
python3 scripts/run_experiment.py --id 2026-10-lighthouse \\
  --tasks t01 --systems s0 s1 --seeds 0 1 2 \
  --provider command --command "python3 my_model_adapter.py"
```

`--provider command` のアダプタは、標準入力の JSON（`GenerationRequest`）に対して
標準出力に `{"text": "..."}` を返すものです。判定器は `scripts/judge_adapter.py` を使ってください。
