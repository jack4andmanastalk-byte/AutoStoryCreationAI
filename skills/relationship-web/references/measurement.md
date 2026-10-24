# 測定仕様 — 検査項目と、判定しないこと

## 検査項目（6 検査。すべて機械的）

| 検査 | 合格条件 | 重要度 |
| --- | --- | --- |
| `pair_grounded` | 表向き・利害があり、人物が canon に実在 | medium |
| `conflict_declared` | 両立しない目的が 1 件以上ある | medium |
| `knowledge_tabled` | 状態が 3 値のいずれかで、人物・事実が実在 | medium（表自体が無い場合は low） |
| `knowledge_matches_canon` | canon で既知の事実を unknown と主張しない（canon があれば） | medium（canon 無しは skipped） |
| `change_staged` | 変化の相手が関係表にあり、契機・変化後・章がある | medium |
| `silence_meant` | 言わないことがあり、人物・章が実在 | medium |

## 照合の方向（`knowledge_matches_canon`）

設計書は canon の「先」を描いてよい。canon がまだ記録していない知識を
`knows` と計画することは許す（設計が先行するため）。
許さないのは逆向きだけ——canon が既に既知と記録したものを
`unknown` と主張すること。

## 判定しないこと（非目標）

| 問い | なぜ判定しないか | 代わりに |
| --- | --- | --- |
| 対立が面白いか | 機械的に測れない | L2/L3 |
| 対立が本当に両立しないか | 意味の判定 | 書き手の自己点検＋L2 |
| 沈黙が効いているか | 本文の判定 | L2 |
| 人物の魅力 | 別スキル | `character-core`＋L2/L3 |
| 脇役が動いているか | 本文の判定 | L2 |
