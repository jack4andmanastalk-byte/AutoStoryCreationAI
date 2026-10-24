# relation-demo の期待値

照合先: `harness/cases/demo/canon`（人物 aria・boris・celia、事実 F-07・F-09、ch01～ch05）。

## `relations.yaml`（良好）

* 所見 0 件。6 検査すべて `pass`。
* 「衝突が面白い」の認定ではなく、「衝突が設計されている」の確認である。

## `relations-bad.yaml`（不良。6 検査すべて `fail`）

| # | 検査 | 仕込み |
| --- | --- | --- |
| 1 | `pair_grounded` | 表向き・利害が空欄。zorro が canon にいない |
| 2 | `conflict_declared` | 衝突の記載が一件もない |
| 3 | `knowledge_tabled` | 状態 `maybe`。zorro・F-00 が実在しない |
| 4 | `knowledge_matches_canon` | boris は canon で F-07 を既知なのに unknown と主張 |
| 5 | `change_staged` | aria-celia は関係表にない。契機・変化後が空欄。ch99 がない |
| 6 | `silence_meant` | 言わないことが空欄。zorro・ch99 が実在しない |

テストは `tests/test_relationship_web.py`。期待値の変更はこの表も更新する。
