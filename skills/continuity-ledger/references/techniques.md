# 依拠した技法と、本実装で補った条件

`research/catalog/techniques.jsonl` から 14 件を参照している。
**元カタログには処方の文章しかなく、判定条件が無いものが多い**（実行可能度で
`partial` が 9 件）。ここでは、各技法から何を採り、何を補ったかを記録する。
補った条件はすべて編集上の判断であり、原典の主張ではない。

| 技法 ID | 名称 | 実行可能度 | 採ったもの | 補った条件 |
| --- | --- | --- | --- | --- |
| `production/game_narrative_us:P13` | カノン変更を方針・範囲・版で扱う | partial | 変更を範囲と版で記録する考え方 | 台帳の出力に `canon` パスを含め、版は git に委ねる |
| `production/game_narrative_us:P19` | 条件・既読・関係性を明示した状態モデル | partial | 「条件・既読・更新」の三つ組 | 人物の `status` / `location` / `known_facts` として実装 |
| `production/game_narrative_us:P22` | 環境の痕跡を因果連鎖として配置する | partial | 場所と時間を手掛かりにする発想 | 移動日数の表として実装（因果ではなく物理制約に限定） |
| `production/game_narrative_us:P33` | 本文から独立した安定した line ID | partial | 本文と ID を分ける原則 | マーカーは本文中に置くが、台帳は ID で参照する |
| `production/game_narrative_us:P36` | 改稿の依存資産と再作業範囲 | partial | 変更の影響範囲を一覧化する | 違反レポートに `canon_ref` を付けて影響先を示す |
| `production/game_narrative_us:P38` | 物語パッチを preview・正式版で扱う | partial | 改訂を段階的に扱う | `--fail-on high` の段階導入（まず high だけ止める） |
| `narrative/japan_2026:T033` | 一対一の張りと回収 | partial | 初出と回収の位置を記録する | 「回収章 ≥ 設置章」を検査条件にした |
| `narrative/japan_2026:T034` | 複数の張りを一つの回収へ集約 | executable | 複数の手掛かりを同じ真相へ | **未実装**（回収先の同一性は意味判定が要る） |
| `narrative/japan_2026:T035` | 張り・回収を交互につなぐ | partial | 段階的な理解更新 | 未回収の検出のみ。交互配置の良し悪しは見ない |
| `narrative/japan_2026:T036` | 回収を分岐させる | partial | 一つの提示が複数の回収に接続する | 未実装（構造が DAG になるため別検査） |
| `narrative/japan_2026:T037` | 結末から遡って伏線を補う | executable | 後から前段に前振りを足す | 追加後の再監査を手順に含めた |
| `narrative/japan_2026:T112` | フラグ・場面遷移の図式化とチーム点検 | executable | 図と台帳で依存を共有する | 台帳を JSON で出力し、レビューで使える形にした |
| `narrative/us_2026:T012` | 伏線・反復・ペイオフ | executable | 初出と再使用を記録する | 設置・回収の章を機械可読にした |
| `narrative/us_2026:T116` | 継続設定と協調的な執筆 | executable | 年表・語彙・既知情報・未確定事項の台帳 | 未確定事項は `notes` に残し、検査対象外と明示 |

## 採らなかったもの

* **意味的な整合性の判定**（T034 / T036）。回収先が同じかを機械的に決めるには、
  出来事の同一性判定が要る。L1 では扱わず、`evaluation-harness` の L2 に回した。
* **自動抽出**（本文から状態変化を NLP で抜く）。日本語の人称・省略のため誤りが多く、
  誤検出が台帳への信頼を壊す。マーカーを明示的に書く方式にした。

## 実行可能度との関係

`research/catalog/executability.jsonl` の判定では、seed-08 が引く 14 件のうち
`executable` は 5 件、`partial` は 9 件だった。このスキルの実装で、`partial` の 9 件に
**判定条件を 1 対 1 で対応させた**（上の表の「補った条件」）。
つまり `executability_report.md` が「足すべき」と指摘した層を、ここで補ったことになる。
