# 設計変更の記録（2026-10 p4。S1 への設計ステージ接続）

S1 を plan → draft から plan → **design** → draft に変更した。
11/13 スキルが S1 に接続されたことになる（下表）。

## 接続表

| スキル | 接続先 | 備考 |
| --- | --- | --- |
| premise-brief / world-rules / history-timeline | design ステージ | 設計書として生成・検証 |
| character-core / relationship-web / plot-architecture / scene-information | design ステージ | 同上。canon と照合 |
| voice-style | design ステージ → S3 の voice pass | 設計時は構造のみ。本文の検査は後工程 |
| continuity-ledger | audit | 従来どおり |
| revision-loop | S2 | 従来どおり |
| evaluation-harness | run_evaluation | 従来どおり |
| interactive-branch / adaptation | 対象外 | 線形短編のパイプラインではなく、ゲームブック・翻案のパイプラインの技能 |

## 決定

* **fail-open（記録して続行）。** 修復上限（2 試行）を超えた設計書は
  `unresolved`（解析不能は `missing`）として記録し、run を続ける。
  理由。設計書 1 件の不備で全生成を潰すのは費用対効果が悪く、
  分析は設計報告を条件に使える。
* **ゲートに入れない。** 未解決があっても有効な S1 run である。
  S1 の定義の一部だからであり、品質の合否ではない。
* **版上げなし。** §9 の「系の構成変更」に当たるが、本実験の結果が
  存在しないため無効化するものがない。以後の S1 の構成変更は v2。
* **`draft-chapter` 1.1（`$design` 追加）。** 章ごとの場面メモと文体行を渡す。
  設計なしの場合は「（設計メモなし）」と明示し、ablation を正直にする。
* **S3 の voice pass は設計 `voice.json` を既定に。** 明示の `--voice` が優先。
  どちらを使ったかは `voice.json` の `guide_from_spec` に残る。
* **`--no-design` は ablation・デバッグ専用。** 本実験では使わない。
  使った場合は実験ノートに記録し、警告を出す。
* **費用。** 1 run あたり約 8 モデル呼び出し増。`manifest.json` の `usage` に残る。

## 次の検討（今回はやらない）

* 設計書を canon 生成に使う順序（design-first）。今回は plan → design で、
  canon は設計書に制約されない。canon を設計書から組み立てる変更は、
  `plan-canon` プロンプトの作り替えを伴うため別件にした。
