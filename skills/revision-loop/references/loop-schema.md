# 批評・パッチ・比較の書式

## 批評ノート（`plan` の出力）

```json
{"critiques": [
  {"id": "CR-001", "source": "continuity", "severity": "high",
   "chapter": "ch02", "evidence": {"path": "ch02.md", "line": 2},
   "problem_ja": "ジロウは ch01 で死亡しているが、ch02 で発話している。",
   "fix_ja": "死亡章以降の行為を回想・遺体・代役のいずれかに変えるか、…",
   "canon_ref": "canon/characters:jirou.status", "status": "open"}
]}
```

`fix_ja` は定型の修正方針であり、診断ではない。重要度の順に並ぶ。

## パッチ（`apply` の入力）

```json
{"patches": [
  {"id": "P-001", "critique_id": "CR-001", "chapter": "ch02.md", "line": 2,
   "anchor": "置換対象の原文（正確に一致させる）",
   "replacement": "置換後の文",
   "reason": "なぜこの置換か。"}
]}
```

| 規則 | 理由 |
| --- | --- |
| `anchor` は原文と正確に一致させる | 推測で当てると、直した箇所が分からなくなる |
| `anchor` が複数箇所に一致したら `line` を必須にする | 誤った箇所の書き換えを防ぐ |
| `line` の行に `anchor` が無ければ失敗にする | 本文が変わったことを検出する |
| `reason` を必ず書く | 後から「なぜ直したか」を辿るため |

## 前後比較（`compare` の出力）

```json
{"fixed": [...], "persisting": [...], "new": [...],
 "summary": {"before": 2, "after": 0, "fixed": 2,
             "persisting": 0, "new": 0, "persisting_medium_plus": 0}}
```

同一性は（由来・種別・対象・章）で判定する。文面が変わっても対象が同じなら残存。

## 繰り返し検出

2 ラウンド以上連続で残る所見は `repeat: true` とし、
「局所修正ではなく企画・台帳に戻る」旨を `note_ja` に書く。
