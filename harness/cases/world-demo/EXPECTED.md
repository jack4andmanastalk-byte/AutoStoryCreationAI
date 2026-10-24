# world-demo の期待値

照合先: `harness/cases/demo/canon`（場所=灯台・王都・港、章=ch01〜ch05）。

## `world.yaml`（良好）

* 所見 0 件。5 検査すべて `pass`。
* これは「良い世界」の認定ではなく、「制約として書かれた」ことの確認である。

## `world-bad.yaml`（不良。5 検査すべて `fail`）

| # | 検査 | 仕込み |
| --- | --- | --- |
| 1 | `axiom_declared` | 公理が空。変えてはいけない前提がない |
| 2 | `rule_has_cost` | R-01 にコストが無い（代償なき力） |
| 3 | `exception_bounded` | R-02 の例外に条件が無い（無条件の抜け道） |
| 4 | `geography_grounded` | 「雲の都」が canon の場所にない |
| 5 | `disclosure_ordered` | 開示が「灯り」（短い）で、開示先 ch09 が年表にない |

テストは `tests/test_world_rules.py`。期待値の変更はこの表も更新する。
