# 依拠した技法と、本実装で補った条件

seed-04 が引く 15 件のうち、本実装が直接使う 12 件を記録する。
実行可能度は `executable` 5 件、`partial` 7 件。
`T024`（サブテクスト）は `relationship-web` 側に、
`C02`（理想像の合成）は類型論の参考に留めた。

| 技法 ID | 名称 | 実行可能度 | 採ったもの | 補った条件 |
| --- | --- | --- | --- | --- |
| `narrative/us_2026:T017` | 人物の局所目標と主体性 | partial | 局所目標 | 予測の状況の具体化を条件にした |
| `narrative/us_2026:T018` | 相反する欲求・忠誠・役割 | partial | 欲求の対立 | WANT と NEED の分離を検査条件にした |
| `narrative/us_2026:T019` | 圧力下の選択で人物を示す | partial | 圧力下の選択 | 予測 3 件を検査条件にした |
| `narrative/us_2026:T020` | 変化する人物・変わらない人物 | partial | 変化と不変 | changed/unchanged の両記を条件にした |
| `narrative/us_2026:T021` | 行為・外見・環境による間接造形 | executable | 間接造形 | 説明ではなく選択で書く方針にした |
| `narrative/us_2026:T022` | 自己像・他者像・行動の不一致 | partial | 像の不一致 | self/others の分離を検査条件にした |
| `narrative/us_2026:T023` | 対話を行為として組む | partial | 対話の行為化 | 口調サンプルの書き写しを条件にした |
| `narrative/japan_2026:T021` | 欲望と反対ベクトルの可視化 | partial | ベクトルの可視化 | 恐れ・傷の欄を書式にした |
| `narrative/japan_2026:T022` | 行為項による役割配分 | executable | 役割の配分 | 人物 ID と canon の対応を検査条件にした |
| `narrative/japan_2026:T023` | WANT／NEED のずれ | partial | ずれ | 同一文の禁止を検査条件にした |
| `narrative/japan_2026:T024` | アーク設計 | executable | 終点の決定 | 終点の必須化を検査条件にした |
| `production/game_narrative_us:P07` | 役割・関係性・声の対照化 | executable | 声の対照化 | 語彙・回避の規則を検査条件にした |

## 採らなかったもの

* **本文中の人物造形の判定**。設計書だけでは閉じない。L2 に回した。
* **診断ツールの使用**。seed の `risks_ja` に従い、類型ラベルは検査に使わない。
* **理想像の合成（C02）**。類型論であり、手順に落とせる形ではなかった。
