# plot-demo の期待値

照合先: `harness/cases/demo/canon`（ch01～ch05、fs-001～fs-003）。

## `plot.yaml`（良好）

* 所見 0 件。5 検査すべて `pass`。
* 「筋が面白い」の認定ではなく、「筋が設計されている」の確認である。

## `plot-bad.yaml`（不良。5 検査すべて `fail`）

| # | 検査 | 仕込み |
| --- | --- | --- |
| 1 | `acts_cover` | 幕の問いが空欄。ch99 が canon にない |
| 2 | `turns_placed` | 転換点が 1 件。選択が空欄。ch99 がない |
| 3 | `subplots_allocated` | 節目・合流が空欄 |
| 4 | `ending_designed` | 型 `happy`。要約・余韻が空欄 |
| 5 | `debts_listed` | fs-999 が canon の伏線表にない |

テストは `tests/test_plot_architecture.py`。期待値の変更はこの表も更新する。
