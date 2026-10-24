# adaptation-demo の期待値

翻案は自己完結（canon 不要）。

## `adaptation.yaml`（良好）

* 所見 0 件。4 検査すべて `pass`。権利の状態は `cleared`。
* 「翻案がうまい」の認定ではなく、「機能が翻訳されている」の確認である。

## `adaptation-bad.yaml`（不良。4 検査すべて `fail`）

| # | 検査 | 仕込み |
| --- | --- | --- |
| 1 | `functions_listed` | 種類 `mystery`。説明が空欄 |
| 2 | `mappings_assigned` | 手段・初見・既読が空欄。`fn-ghost` が機能表にない。`fn-b` の行き先がない |
| 3 | `deletions_recorded` | `fn-a` が翻訳と削除の両方。理由・代替が空欄 |
| 4 | `rights_logged` | 原作・範囲が空欄。状態 `unknown` |

テストは `tests/test_adaptation.py`。期待値の変更はこの表も更新する。
