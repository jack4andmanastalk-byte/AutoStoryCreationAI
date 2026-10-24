# brief-demo の期待値

## `brief.yaml`（良好）

* 所見 0 件。6 検査すべて `pass`。
* これは「良い企画」の認定ではなく、「検証可能な形」の確認である。

## `brief-bad.yaml`（不良。6 検査すべて `fail`）

| # | 検査 | 仕込み |
| --- | --- | --- |
| 1 | `logline_form` | 4 文ある（「灯台の話。娘が…」）。一文に圧縮していない |
| 2 | `logline_elements` | `where` が空欄、`wants`（宝を探す）がログラインに無い |
| 3 | `theme_contrast` | 「家族の絆は大切だ」は教訓で、対立命題の形をしていない |
| 4 | `similar_grounded` | 1 件のみ。軸が `feeling`（不正）、差分が「似てる。」（短い） |
| 5 | `prohibition_testable` | 確認方法が「頑張る。」（判定不能） |
| 6 | `question_form` | 「面白くすること」は問いの形をしていない |

テストは `tests/test_premise_brief.py`。期待値の変更はこの表も更新する。
