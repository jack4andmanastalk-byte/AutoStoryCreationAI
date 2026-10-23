# 実行可能度の集計（自動生成）

`research/catalog/executability.jsonl` の要約です。`python3 scripts/build_research_catalog.py` で再生成されます。
この数字は**レコードの書き方**を測ったもので、引用元の研究の質や技法の有効性を示すものではありません。

## 判定基準（4 項目・各 1 点）

| 項目 | 条件 | 意味 |
| --- | --- | --- |
| 手順 | `operation_ja` が 30 文字以上 | 何をするかが書かれている |
| 合格条件 | 手順・機能・仕組み・要約のいずれかに判定語（確認・検証・測定・基準・判定・チェック・照合・逸脱・満たす・比較・テスト・記録）を含む | 出来を判定できる語がある |
| 失敗条件 | `limitations_ja` が 20 文字以上 | 成立しない場合が書かれている |
| 例 | 具体例が 1 件以上 | 抽象語だけではない |

| 区分 | 条件 |
| --- | --- |
| `executable` | 手順と合格条件の両方があり、他の項目も概ね揃う |
| `partial` | 手順か合格条件のどちらかが欠ける（2 点以上） |
| `reference_only` | 0–1 点 |

## 全体

対象: **488 件**（`techniques.jsonl` の全レコード）

| 区分 | 件数 | 比率 | 読み方 |
| --- | ---: | ---: | --- |
| `executable` | 115 | 24% | そのままスキル化できる |
| `partial` | 290 | 59% | 条件を補えば使える |
| `reference_only` | 83 | 17% | 分類・評価の語彙として使う |

| 項目 | 該当件数 | 比率 |
| --- | ---: | ---: |
| procedure | 405 | 83% |
| acceptance | 124 | 25% |
| failure_condition | 386 | 79% |
| example | 103 | 21% |

手順の出所: `mechanism_derived` 84 件、`none` 83 件、`stated` 321 件。`mechanism_derived` は、原カタログが `mechanism` 欄に書いた手順を`operation_ja` として公開したものです（原文は `mechanism_ja` に残しています）。

## 成果物別

| 成果物 | 件数 | executable | partial | reference_only | 手順 | 合格条件 | 失敗条件 | 例 | 平均点 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `history_myth/comparative_mythology`<br>比較神話 | 19 | 1 | 18 | 0 | 19 | 1 | 0 | 19 | 2.05 |
| `narrative/china_2026`<br>中国 技法カタログ | 84 | 12 | 72 | 0 | 84 | 12 | 84 | 84 | 3.14 |
| `narrative/japan_2026`<br>日本 技法カタログ | 116 | 40 | 76 | 0 | 116 | 40 | 116 | 0 | 2.34 |
| `narrative/us_2025`<br>米国 パラダイム索引 | 83 | 0 | 0 | 83 | 0 | 9 | 0 | 0 | 0.11 |
| `narrative/us_2026`<br>米国 技法カタログ | 144 | 56 | 88 | 0 | 144 | 56 | 144 | 0 | 2.39 |
| `production/game_narrative_us`<br>米国 ゲーム制作実務 | 42 | 6 | 36 | 0 | 42 | 6 | 42 | 0 | 2.14 |

## そのままスキル化できる候補（先頭 20 件）

| ID | タイトル | 点 | 領域 |
| --- | --- | ---: | --- |
| `narrative/china_2026:B05` | 地図・位面の更新による連載の再起動 | 4 | story, world |
| `narrative/china_2026:C02` | 理想化された人物像の要素合成 | 4 | character, story |
| `narrative/china_2026:C06` | 口の動きと吹替をずらす二重の台詞 | 4 | character, story |
| `narrative/china_2026:D06` | 歴史的人物に現代の統治・倫理問題を担わせる | 4 | story, style |
| `narrative/china_2026:G07` | 翻案・フランチャイズとトランスメディア展開の区別 | 4 | interaction |
| `narrative/china_2026:I01` | 現場に居合わせる撮影と偶発性の受入れ | 4 | history, meta |
| `narrative/china_2026:I03` | 異種の記録を並べて証言を補強・複雑化する | 4 | history, meta |
| `narrative/china_2026:I04` | 記録映像と演技を混ぜ、写実の条件を問う | 4 | history, meta |
| `narrative/china_2026:I05` | 共有された非知・見ないことの公共性 | 4 | history, meta |
| `narrative/china_2026:I06` | 日記・生活記録を集合的記憶へ編成する | 4 | history, meta |
| `narrative/china_2026:J06` | 上演後討議を語りの継続にする | 4 | interaction, story |
| `narrative/china_2026:L07` | 「参加型」という表示と編集権の区別 | 4 | meta |
| `history_myth/comparative_mythology:CM-HIST-03` | ローラシア神話群の通史構造 (Laurasian Narrative Arc: Primeval Chronicle) | 3 | history, world |
| `narrative/japan_2026:T001` | 着想の外部記録（ネタ帳） | 3 | production, story |
| `narrative/japan_2026:T006` | テーマを行為の帰結で検討する | 3 | production, story |
| `narrative/japan_2026:T009` | 三幕構成と幕間の転換 | 3 | story |
| `narrative/japan_2026:T016` | 物語機能の分解・再構成 | 3 | story |
| `narrative/japan_2026:T018` | 一話完結と長期アークの二重化 | 3 | story |
| `narrative/japan_2026:T022` | 行為項による役割配分 | 3 | character |
| `narrative/japan_2026:T024` | 変化・不変・悪化を選ぶアーク設計 | 3 | character |

## `partial` を `executable` にするために足すもの

| 足すもの | 件数 | 備考 |
| --- | ---: | --- |
| 合格条件（判定語・基準） | 290 | 手順はあるが、出来を判定する語がない |
| 手順 | 0 | 定義・分類しかない |
| 失敗条件 | 18 | 成立しない場合が書かれていない |
| 例 | 200 | 抽象語だけで具体例がない |

## `reference_only` の内訳

| 欠けている項目 | 件数 |
| --- | ---: |
| procedure | 83 |
| acceptance | 74 |
| failure_condition | 83 |
| example | 83 |

## スキル種（13 件）が参照する技法の内訳

`research/program/skill_seeds.jsonl` が引く技法 ID は 164 件（解決 164 件）。

| 区分 | 件数 |
| --- | ---: |
| `executable` | 48 |
| `partial` | 100 |
| `reference_only` | 16 |

## この集計で分からないこと

* 手順が**正しいか**、**効くか**は分かりません。文章が揃っているかだけを見ています。
* 合格条件は語彙の有無で判定しているため、「基準」という語を含むだけの項目も該当します（過大評価の可能性）。
* 中国カタログの手順は `mechanism` からの導出なので、原典が手順として書いたとは限りません。
* 成果物ごとに記述の詳しさが違うため、`mean_score` の横比較は「そのカタログの書き方」の比較であって、内容の比較ではありません。

