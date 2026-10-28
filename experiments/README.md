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
* 例外: [`2026-10-trpg-slice-t01/inputs/`](2026-10-trpg-slice-t01/inputs/) は
  **固定台本（`scripted`）の入力**（canon・設計書・`game_log.json`・リライト本文）であり、
  run 出力ではありません。二段階方式の配線をセッションを越えて再現するために必要なので
  コミットします。実行時にできる `bundle/` は run 出力なのでコミットしません。
  将来 Arena リレーで実応答を保存する場合は、同じ `experiments/<id>/` の `relay/` に
  置き、gitignored な `runs/` / `build/` に依存させないでください。
* 例外: [`2026-10-dogfood-01/`](2026-10-dogfood-01/) は標準フロー
  （`scripts/story_project.py`）を**実応答**で1作品ぶん回した dogfood です。作品ディレクトリ
  `work/prj-mine/`（`project.json`・`nodes/`・`relay/`）と `manuscript.md` をコミットし、
  `runs/` は gitignore のままにします。応答は `work/prj-mine/relay/responses/` に逐語で残り、
  `runs/` に依存しません。台本（`scripted`）ではないので、`note.md` の「限界」に
  品質を主張しない旨を明記しています。
* 同じ `id` を再利用しないでください。条件を変えたら新しい `id` にします
  （例: `2026-10-s1-vs-s0-a`、`2026-10-s1-vs-s0-b`）。

## 実験インデックス

以下は `experiments/` 配下の全実験一覧です。類似実験グループの中で「最新の正」とみなされるものは **★最新** でマークし、後続実験に譲ったものは △非推奨 でマークします。

| 実験ID | 日付 | 種類 | 状態 | 位置づけ | タグ |
|---|---|---|---|---|---|
| `2026-10-arena-brief-v11` | 2026-10 | brief 契約検証 | 完了 | design-brief v1.1 の構造適合 | △非推奨 |
| `2026-10-arena-brief-v11-s1` | 2026-10 | brief × S1 | 完了 | design-brief v1.1 × S1 | △非推奨 |
| `2026-10-arena-fresh-s1-n3` | 2026-10-24 | S1 新規応答 N=3 | 完了 | t01 の plan/design/draft 36応答 | ★最新（t01 用） |
| `2026-10-arena-fresh-s1-t02t03` | 2026-10-24 | S1 新規応答 t02/t03 | 完了 | t02/t03 の plan/design/draft | ★最新（t02/t03 用） |
| `2026-10-arena-l1-t01` | 2026-10 | Arena × L1 パイロット | 完了 | t01 × S0–S3 × seed 0 | △非推奨 |
| `2026-10-arena-replay-t02` | 2026-10-24 | offline replay | 完了 | fresh-s1-t02t03 / t02 の replay 検証 | ★最新（replay 用） |
| `2026-10-arena-replay-t03` | 2026-10-24 | offline replay | 完了 | fresh-s1-t02t03 / t03 の replay 検証 | ★最新（replay 用） |
| `2026-10-design-prompt-contracts` | 2026-10 | 設計書プロンプト契約 | 完了 | 8種設計書のプロンプト契約 | △非推奨 |
| `2026-10-detect-power-t01` | 2026-10 | 検出力測定 | 完了 | 2種の検出穴への対応 | △非推奨 |
| `2026-10-dogfood-01` | 2026-10 | dogfood 実応答 | 完了 | 標準フロー 1作品ぶん | ★最新（dogfood 用） |
| `2026-10-full-t01` | 2026-10 | フル走行 | 完了 | t01 フルパイプライン | △非推奨 |
| `2026-10-l1-pair-t01` | 2026-10 | L1 ペア比較 | 完了 | t01 の L1 ペア比較 | △非推奨 |
| `2026-10-pilot-t01-s0s1` | 2026-10 | パイロット S0/S1 | 完了 | t01 × S0/S1 比較 | △非推奨 |
| `2026-10-plot-ablation-t01` | 2026-10 | プロット除去 | 完了 | Plot メモオフの ablation | △非推奨 |
| `2026-10-realrun-a-t01` | 2026-10-26 | 実走り Stage B | 走行済み | Stage B のみ、3標本・9章 clean | △非推奨（b2 へ譲る） |
| `2026-10-realrun-b-t01` | 2026-10-27 | 実走り S1 全体 | 完走 | S1 全体 1標本、pass | △非推奨（b2 へ譲る） |
| `2026-10-realrun-b2-t01` | 2026-10-27 | 実走り S1 全体 history v1.1 | 完走 | S1 全体 1標本、history プロンプト v1.1 | ★最新（S1 全体） |
| `2026-10-relay-t01-s0s1` | 2026-10 | relay 往復 | 完了 | t01 × S0/S1 relay | △非推奨 |
| `2026-10-stageb-solo-t01` | 2026-10 | Stage B 単独 | 完了 | Stage B のみ t01 | △非推奨 |
| `2026-10-stageb-v11-t01` | 2026-10 | Stage B v1.1 | 完了 | Stage B v1.1 t01 | △非推奨 |
| `2026-10-surface-checks-t01` | 2026-10-26 | 表面検査試作 | 測定完了 | 地名移動・数字報告の候補 | △非推奨（t02 へ譲る） |
| `2026-10-surface-checks-t02` | 2026-10-26 | 表面検査校正 | 測定完了 | t01 の言い換え校正、9章・18事例 | ★最新（surface 用） |
| `2026-10-surface-observe-t01` | 2026-10 | surface observe | 完了 | --observe-surface 検証 | △非推奨 |
| `2026-10-trpg-slice-t01` | 2026-10 | TRPG スライス | 完了 | 固定台本入力（canon・設計書・ゲームログ等） | ★最新（TRPG 用） |
| `2026-10-u01-standard-flow-t01` | 2026-10 | U-01 標準フロー | 完了 | 標準フロー t01 | △非推奨 |
| `2026-10-u02-relay-round-t01` | 2026-10 | U-02 relay 往復 | 完了 | relay 往復 t01 | △非推奨 |

### 類似実験グループと「最新の正」

| グループ | 実験 | 最新の正 | 理由 |
|---|---|---|---|
| realrun | a-t01 → b-t01 → b2-t01 | `2026-10-realrun-b2-t01` | history プロンプト v1.1 を適用した S1 全体の最新走行 |
| surface-checks | t01 → t02 | `2026-10-surface-checks-t02` | t01 の言い換え校正を反映、9章・18事例で測定 |
| arena-fresh | s1-n3 / s1-t02t03 | 両方★最新 | t01 用と t02/t03 用で用途が異なるため両方保持 |
| arena-replay | replay-t02 / replay-t03 | 両方★最新 | t02/t03 それぞれの replay 検証用 |

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
