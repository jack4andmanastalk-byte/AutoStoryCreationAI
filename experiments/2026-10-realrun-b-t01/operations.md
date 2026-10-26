# バッチ B の運用手順（ハーネス側・記録用）

**読者はこれを実行しない。** 実行するのはハーネス（エージェント）で、往復は arena.ai のチャットで
行う。ここにコマンドが並んでいるのは、あとから「何をどの順で走らせたか」を再現できるようにするためで、
作業者に端末を要求するためではない。

- 事前登録: [`preregistration.json`](preregistration.json) / [`preregistration.md`](preregistration.md)
- 計測: [`results.json`](results.json)（`scripts/measure_realrun_b.py`）
- 位置づけ: [`docs/two_stage_slice.md`](../../docs/two_stage_slice.md) §23

## 役割

| 役 | すること |
| --- | --- |
| ハーネス | パイプライン実行、`relay/sample-1/PROMPTS.md` の書き出し、回答の取り込み、run、計測、コミット |
| 回答者（対話モデル） | チャットに貼られた 1 リクエストにだけ答える |
| 人 | プロンプトを貼り、回答をそのまま返す。**コマンドは叩かない** |

## 1 往復の形

1. ハーネスが `run_pipeline.py` を走らせる。回答が無い先頭の要求で止まる（exit 2,
   `NEED RESPONSE key=…`）。
2. ハーネスが `relay_prompts.py export` で `relay/sample-1/PROMPTS.md` を書き出し、
   **1 リクエストぶんをチャットに貼る**（タグ付き）。
3. 回答者が `<<<ANSWER タグ>>> … <<<END タグ>>>` を返す。
4. ハーネスがチャットの回答をそのまま `relay/sample-1/answers/round-NN.txt` に保存し、
   `relay_prompts.py ingest` で `responses/` に入れる。`provenance.origin` を記録する。
5. ハーネスが `relay/` をコミットして push する（作業環境が消えても GitHub から再開できる）。
6. 1 に戻る。**最小 11 往復**（設計 8 ＋ 本文 3）。修復が入ると増える。

`run_pipeline.py` は resume しないので、毎回**最初から**走らせて記録済みの回答を再生する
（`build/` は捨ててよい。`relay/` が状態）。

```bash
# ハーネスが実行する（読者は実行しない）
advance () {
  rm -rf build/runs/b-adv
  .venv/bin/python scripts/run_pipeline.py --task t01 --system s1 --stage all \
    --canon "$BUNDLE/inputs/canon" \
    --provider command \
    --command "$PWD/.venv/bin/python scripts/chat_operator.py --dir $RELAY" \
    --seed 0 --out build/runs --run-id b-adv --quiet
  echo "pipeline exit: $? （2 = 回答待ち。NEED RESPONSE 以外なら stderr を読む）"
  .venv/bin/python scripts/relay_prompts.py export --dir "$RELAY" --out "$RELAY"
}
```

## 記録の残し方

- `relay/sample-1/requests/` … パイプラインが実際に要求した文と `prompt_hash`（再生成できる）。
- `relay/sample-1/responses/` … 返ってきた実テキスト。**作文も修正もしない。**
  `origin` は `fresh`（このバッチのために新しく書いた）。過去の走りの本文を使った場合は
  `{"origin": "reused", "source_run_id": "…"}` に直し、標本として扱わない。
- `relay/sample-1/answers/` … チャットから受け取った原文（`ingest` の入力）。来歴の一次資料。
- `relay/sample-1/served.jsonl` … 何をいつ配ったか（`prompt_hash` つき）。

## 最終 run と計測

全回答が揃ったら、バンドルの中に 1 回だけ走らせる（ここが記録になる run）。

```bash
.venv/bin/python scripts/run_pipeline.py --task t01 --system s1 --stage all \
  --canon "$BUNDLE/inputs/canon" \
  --provider command \
  --command "$PWD/.venv/bin/python scripts/chat_operator.py --dir $RELAY" \
  --seed 0 --out "$BUNDLE/sample-1" --run-id run

.venv/bin/python scripts/measure_realrun_b.py
```

- 終了コード: **0 = ゲート通過**、**1 = 走ったがゲート未達**（これも結果）、**2 = 停止**。
- 判定は `results.json` の verdict を**そのまま引用する**（人が読み替えない）。B3 は
  `repair_erased_included` と `final_only` の両方が出る。

## つまずき

| 症状 | 対処 |
| --- | --- |
| `NEED RESPONSE key=…` | 正常。その 1 件をチャットに貼る |
| `unknown tag` | 推測しない。`--map 送った文字=正しいタグ` で明示して再取り込み |
| `STALE RESPONSE …` | プロンプトが変わった後の古い回答。その回答を消して、新しい要求に答え直す |
| 設計が `unresolved` のまま本文へ進む | S1 の仕様。そのまま記録する（B1 は `design_unresolved`） |
| 本文が 2 試行とも不合格で停止（exit 2） | run を残し、判定は `incomplete`。**消して書き直さない** |
| `condition.canon_matches_registration` が false | `inputs/canon` が変わっている。走行をやり直す |
