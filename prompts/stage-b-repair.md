---
name: stage-b-repair
version: "1.0"
---
# Stage B: リライト本文の修復

前の本文は決定論的検査器で不合格でした。**指摘された項目だけ**を直し、$chapter_id の章本文をもう一度返してください。返答は本文のみ。新しい事実や人物行動を足してはいけません。

## 検査器の指摘

$findings

## 文体・視点（voice.json）
$voice

## 確定マーカー列（この順番で、文字列を変えずに含める）
$markers

## 前の本文

$previous
