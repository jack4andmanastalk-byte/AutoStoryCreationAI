# `branches.yaml` の書式

```yaml
start: n_start              # 開始点の節点 ID
initial: []                 # 開始時に立つ旗
flags:                      # 旗の表
  - id: has_key
    meaning: 灯台の鍵を手に持つ
nodes:
  - id: n_start
    kind: scene             # scene / choice / ending
    summary: 灯台の朝
  - id: n_first
    kind: choice
    summary: 鍵を追うか、灯りの番に就くか
    options:                # 2 件以上
      - id: chase
        label: 鍵を追う
      - id: watch
        label: 灯りの番に就く
  - id: n_merge
    kind: scene
    summary: 夜。番小屋で落ち合う
    merge_note: 鍵の有無で会話が変わる。知識は帳面の写しで揃える
  - id: n_end_open
    kind: ending
    summary: 金庫を開ける結末
    ending: 記録が開示され、真相が残る
edges:
  - {from: n_start, to: n_first}
  - {from: n_first, to: n_chase, via: chase, sets: [has_key]}
  - {from: n_last, to: n_end_open, via: open}
```

## 辺の欄

| 欄 | 意味 |
| --- | --- |
| `from` / `to` | 節点 ID。実在必須 |
| `via` | 選択肢 ID。choice からの辺に必須、それ以外は禁止 |
| `requires` | 通過条件の旗。宣言必須 |
| `sets` | 通過時に立てる旗。宣言必須 |

選択肢自体にも `requires` を書ける（表示条件）。辺の `requires` と
選択肢の `requires` の両方が満たされたときだけ辿れる。

## 合流の規則

2 方向以上から入る節点（自己辺を除く）は合流点。
`merge_note` に知識・状態の扱いを書く。
書けない合流は設計ミス（分岐を戻すか、節点を分ける）。
