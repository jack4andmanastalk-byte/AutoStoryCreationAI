# 依拠した技法と、本実装で補った条件

seed-10 が引く 16 件のうち、本実装が直接使う 12 件を記録する。
実行可能度は `executable` 3 件、`partial` 9 件。
残り 4 件（T112・T113・P16・F07）は制作体制の背景知識であり、手順に落とさなかった。

| 技法 ID | 名称 | 実行可能度 | 採ったもの | 補った条件 |
| --- | --- | --- | --- | --- |
| `narrative/japan_2026:T107` | 構成の並替え | partial | 構造の可視化 | 批評を重要度順に並べる手順にした |
| `narrative/japan_2026:T108` | 段階化 | executable | 段階を分ける | plan→apply→compare の分離にした |
| `narrative/japan_2026:T109` | 局所修正が詰まったら戻る | executable | 戻る条件 | 繰り返し検出（2 回連続で設計に戻る）にした |
| `narrative/japan_2026:T110` | 他者による理解点検 | partial | 他者の目 | パッチの `reason` 必須（第三者が辿れる）にした |
| `narrative/japan_2026:T111` | 時間を置く自己推敲 | partial | 時間を置く | ラウンドの区切り（前後レポートの分離）にした |
| `narrative/us_2026:T142` | 意図と受容の差に基づく改稿 | partial | 受容からの批評 | 新規所見の計数（改稿の副作用の検出）にした |
| `production/game_narrative_us:P27` | 理解の照合 | partial | 照合 | 再監査の必須化にした |
| `production/game_narrative_us:P28` | 高コスト化前のレビュー | partial | 早期の検査 | 決定論的所見を先に潰す順序にした |
| `production/game_narrative_us:P30` | 自動試験と人間の併用 | partial | 層の分離 | 機械（所見）と人間（判断）の分担にした |
| `production/game_narrative_us:P36` | 依存資産の見える化 | partial | 影響範囲 | `canon_ref` の批評への引継ぎにした |
| `production/game_narrative_us:P40` | ポストモーテム | partial | 振り返り | 前後比較レポートの保存にした |
| `production/game_narrative_us:P42` | 複数基準で判断 | executable | 単一基準の否定 | 解消・残存・新規の三数併記にした |

## 採らなかったもの

* **質の向上の判定**。所見の数は質ではない。L2/L3 に回した。
* **改稿の自動停止条件**。回数の規定はしない。残存 0 か理由の記録で止める。
* **自己評価バイアスの除去**。運用（生成者と批評者の分離）で扱い、検査にしない。
