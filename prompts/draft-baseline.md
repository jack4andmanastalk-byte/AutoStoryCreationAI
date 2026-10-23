---
name: draft-baseline
version: "1.0"
---
次の前提で、$chapters 章構成の短編小説の $chapter_index 章目を書いてください。

- 題名: $title
- ログライン: $logline
- この章: $chapter_id
- 本文に必ず含める語: $must_include
- 使ってはいけない定型: $avoid
- この章の目安: $target_min〜$target_max 字

## 前の章の終わり
$prior

地の文と台詞だけで、続きを書いてください。見出し・箇条書き・解説は書かないでください。
これは手順を足さない基準（S0）のための生成であり、設定台帳は渡されません。
本文だけを返してください。
