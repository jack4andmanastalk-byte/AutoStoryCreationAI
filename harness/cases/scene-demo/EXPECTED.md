# scene-demo の期待値

照合先: `harness/cases/demo/canon`（ch01～ch05、F-07・F-09、fs-001～fs-003）。

## `scenes.yaml`（良好）

* 所見 0 件。6 検査すべて `pass`。
* 「場面が面白い」の認定ではなく、「場面が設計されている」の確認である。

## `scenes-bad.yaml`（不良。6 検査すべて `fail`）

| # | 検査 | 仕込み |
| --- | --- | --- |
| 1 | `scene_purposed` | 目的・対立・変化が空欄 |
| 2 | `tension_designed` | 型 `exciting` は語彙にない |
| 3 | `knowledge_tracked` | zorro・F-00 が実在しない |
| 4 | `disclosure_planned` | F-07 が開示と保留の両方。理由が空欄 |
| 5 | `foreshadow_tagged` | fs-999 がない。fs-001 は既存 ID |
| 6 | `scenes_cover` | ch99 がない。ch01～ch05 に場面がない |

テストは `tests/test_scene_information.py`。期待値の変更はこの表も更新する。
