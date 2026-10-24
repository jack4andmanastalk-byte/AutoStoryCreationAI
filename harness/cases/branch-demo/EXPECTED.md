# branch-demo の期待値

分岐は自己完結（canon 不要）。

## `branches.yaml`（良好）

* 所見 0 件。7 検査すべて `pass`。
* 「選択が面白い」の認定ではなく、「構造が辿れる」の確認である。

## `branches-bad.yaml`（不良。7 検査すべて `fail`）

| # | 検査 | 仕込み |
| --- | --- | --- |
| 1 | `graph_grounded` | via `missing_option`。to `n_ghost` |
| 2 | `paths_reachable` | `n_orphan` 到達不能。`n_trap` から結末に到達不能 |
| 3 | `endings_terminated` | `n_dead` が行き止まり。`n_end` から辺が出て内容が空欄 |
| 4 | `flags_declared` | 初期旗 `ghost_init`・条件旗 `ghost_flag` が未宣言。`has_key` の意味が空欄 |
| 5 | `conditions_sound` | `never_set` は必須だが設定されない。辺 6 は辿れない |
| 6 | `options_meaningful` | 選択肢が 1 件。`only` を使う辺がない |
| 7 | `merges_noted` | `n_merge` は 2 方向の合流だが覚え書きがない |

テストは `tests/test_interactive_branch.py`。期待値の変更はこの表も更新する。
