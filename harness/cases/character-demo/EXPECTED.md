# character-demo の期待値

ID の照合先: `harness/cases/demo/canon`（aria・boris・celia）。

## `characters.yaml`（良好）

* 所見 0 件。6 検査すべて `pass`。
* これは「良い人物」の認定ではなく、「選択が説明できる形」の確認である。

## `characters-bad.yaml`（不良。6 検査すべて `fail`）

| # | 検査 | 仕込み |
| --- | --- | --- |
| 1 | `core_declared` | WANT と NEED が同一文。恐れ・行動原理が空欄 |
| 2 | `views_separated` | 自己像・他者像が空欄 |
| 3 | `choices_predicted` | 予測が 1 件（3 件必要） |
| 4 | `voice_fixed` | サンプルが「短い。」、語彙規則が空欄 |
| 5 | `arc_decided` | 終点・変わる選択・変わらない選択が空欄 |
| 6 | `canon_grounded` | zorro が canon にいない |

テストは `tests/test_character_core.py`。期待値の変更はこの表も更新する。
