# `history.yaml` の書式

```yaml
eras:                        # 時代区分。任意
  - id: founding
    name: 開闢期
    begins: 1
    ends: 100
events:                      # 年表。年代順に並べる
  - id: E-01
    year: 12
    title: 最初の灯台の点火
    cause: ""                # 原因の出来事 ID。任意
    effect: 岬の航路が夜も使えるようになった。
    trace: 初代の灯芯が組合に保管されている。  # 必須
    era: founding            # 任意
sources:                     # 史料・証言・遺物
  - id: S-01
    kind: 帳面
    holder: 灯台守組合       # 誰が持ち、誰が消したか
    origin: invented         # invented / adapted / cited
    citation: ""             # cited の場合は書誌情報が必須
apocrypha: []                # 異説の出来事 ID。正史から外す
knowledge:                   # 人物が知っている歴史と知らない歴史
  aria:
    knows: [E-01, E-02]
    unknown: [E-03]
notes: 任意のメモ
```

## 由来の区分

| 由来 | 意味 | 条件 |
| --- | --- | --- |
| `invented` | 純粋な創作 | なし |
| `adapted` | 実在史料を下敷きにした創作 | 下敷きを `notes` に記録する |
| `cited` | 実在史料の引用 | `citation` に書誌情報が必須 |

創作に実在史料の権威を借りない。`cited` の体裁で創作を書かない。
