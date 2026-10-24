# 依拠した技法と、本実装で補った条件

seed-03 が引く 12 件のうち、本実装が直接使う 10 件を記録する。
実行可能度は `executable` 2 件、`partial` 8 件。
`T005`（制度設計）は `world-rules` 側に、`T053`（反実仮想）は知識地図の根拠に回した。

| 技法 ID | 名称 | 実行可能度 | 採ったもの | 補った条件 |
| --- | --- | --- | --- | --- |
| `production/game_narrative_us:P11` | 資料調査と考証の分離 | partial | 調査と考証を分ける | 由来区分（invented/adapted/cited）を書式にした |
| `production/game_narrative_us:P12` | ロアの照会・出典・履歴の管理 | partial | 出典の管理 | 原因参照の存在と前後関係を検査条件にした |
| `production/game_narrative_us:P13` | カノン変更の方針・範囲・版 | partial | 変更の版管理 | 正史と異説の分離（apocrypha）を書式にした |
| `production/game_narrative_us:P24` | 作中史の接続 | partial | 遺物・地名への接続 | 痕跡必須（5 字以上）を検査条件にした |
| `production/game_narrative_us:P39` | 設定の引継ぎ | executable | 引継ぎ | 知識地図（knows/unknown）を書式にした |
| `history_myth/comparative_mythology:CM-HIST-01` | 三機能体系論 | partial | 時代区分の見方 | 時代の前後関係を検査条件にした |
| `history_myth/comparative_mythology:CM-HIST-02` | 永遠回帰と循環史観 | partial | 史観の自覚 | 年代順の検査（循環史観は対象外と明示）にした |
| `history_myth/comparative_mythology:CM-HIST-03` | ローラシア通史構造 | executable | 通史の構造 | 出来事の題・年・痕跡の三つ組を書式にした |
| `history_myth/comparative_mythology:CM-HIST-04` | 五時代論と衰退史観 | partial | 史観の類型 | 保持者（holder）の記録を条件にした |
| `history_myth/comparative_mythology:CM-HIST-05` | 大洪水・災害神話 | partial | 災害の記憶 | 痕跡を「物語で触れられる物」に限定した |

## 採らなかったもの

* **循環史観の年表**。年代順の検査と相容れない。直線史観に限定し、循環は対象外と明示した。
* **実在史の考証**。範囲外。混交の防止（由来区分と引用の検査）に留めた。
* **神話の比較の結論**。地域的な偏りがあるため、類型論は書式の参考に留めた。
