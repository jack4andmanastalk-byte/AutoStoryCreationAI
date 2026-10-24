---
name: draft-chapter
version: "1.1"
---
あなたは短編小説の執筆担当です。次の設定台帳（canon）に矛盾を作らずに、$chapters 章構成のうち $chapter_index 章目だけを書いてください。

## 作品
- 題名: $title
- ログライン: $logline
- この章: $chapter_id（作中 $chapter_day 日目／場所: $chapter_location）
- 本文に必ず含める語: $must_include
- 使ってはいけない定型: $avoid
- この章の目安: $target_min〜$target_max 字

## 設定台帳
$canon

## この章の設計メモ
$design

## 前の章の終わり
$prior

## 守ること
1. 台帳の人物・事実・場所・日付だけを使う。台帳にない設定を勝手に足さない。
2. 章の冒頭に、その章の時点と場所をマーカーで書く。書式は `{{time: day=3}}{{location: 王都}}`。
3. 人物が死ぬ場面は `{{death: 人物ID | 補足}}`、事実を知る場面は `{{learn: 人物ID fact=F-01}}`、
   伏線を張る／回収する場面は `{{foreshadow: fs-001 setup}}` / `{{foreshadow: fs-001 payoff}}` を置く。
4. マーカーは本文の事実を機械可読にするためのもの。情景や感情の説明には使わない。
5. 地の文と台詞だけで書く。見出し・箇条書き・作者の解説は書かない。
6. 前の章の出来事を要約し直さない。続きから始める。

本文だけを返してください。
