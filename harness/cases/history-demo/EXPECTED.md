# history-demo の期待値

知識地図の照合先: `harness/cases/demo/canon`（人物=aria・boris・celia）。

## `history.yaml`（良好）

* 所見 0 件。5 検査すべて `pass`。

## `history-bad.yaml`（不良。5 検査すべて `fail`）

| # | 検査 | 仕込み |
| --- | --- | --- |
| 1 | `chronology_ordered` | 年表が 150→12 年の逆順。時代 chaos の終わりが始まりより前 |
| 2 | `causality_linked` | E-02 の原因 E-09 が年表にない |
| 3 | `trace_exists` | E-02 の痕跡が「帳面。」（短い）、E-01 の痕跡が空 |
| 4 | `canon_separated` | 異説 E-07 が年表にない。S-01 は `cited` だが citation が無い |
| 5 | `knowledge_consistent` | 人物 zorro が canon にいない。E-05 が年表にない。E-01 が既知と未知の両方にある |

テストは `tests/test_history_timeline.py`。期待値の変更はこの表も更新する。
