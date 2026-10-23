# revision-demo の期待値

2 章の小品。初稿に 2 件の所見があり、パッチで解消する。

## 初稿の所見（`plan` の入力）

| # | 批評 | 由来 | 重要度 |
| --- | --- | --- | --- |
| CR-001 | ジロウは ch01 で死亡しているが、ch02 で発話している | continuity `dead_character_reappears` | high |
| CR-002 | fs-001 が ch01 で設置され、回収がない | continuity `unresolved_foreshadow` | medium |

## パッチ（`patch.json`）

| # | 対応 | 内容 |
| --- | --- | --- |
| P-001 | CR-001 | ch02 L2 の発話行を除去し、風の音の行に置換 |
| P-002 | CR-002 | ch02 L3 に `{{foreshadow: fs-001 payoff}}` を追加 |

P-001 は「削除」を選んだ。回想として残す場合は `suppressions.yaml` への
理由つき登録が別解であり、どちらが良いかは人間が決める。

## 改稿後の比較（`compare`）

* `before: 2 → after: 0`（解消 2／残存 0／新規 0）。終了コード 0。
* これは「所見の解消」であり、質の向上の証明ではない。

テストは `tests/test_revision_loop.py`。期待値の変更はこの表も更新する。
