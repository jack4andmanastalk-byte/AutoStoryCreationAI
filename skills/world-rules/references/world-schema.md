# `world.yaml` の書式

```yaml
axioms:                    # 変えてはいけない前提。1 件以上
  - 灯りの火は絶やしてはならない。
rules:                     # 規則。コストは必須
  - id: R-01
    statement: 灯りを分けるには、分け手の火を半分にする。
    cost: 照射範囲が半減し、嵐の夜は船が見えなくなる。
    constraint: 分け火は一夜しか保たない。      # 任意
    exception: 港長が認めた緊急時のみ全量で分けられる。  # 任意
    exception_condition: 署名入り命令書があり、翌朝までに返すこと。  # 例外には必須
institutions:              # 制度・勢力。任意
  - name: 灯台守組合
    role: 鍵の貸借の立会いと帳面の保管。
geography: [灯台, 王都, 港]  # canon の場所 ID と一致させる
disclosure:                # 開示計画。任意
  - info: 灯りを絶やしてはいけない掟
    chapter: ch01
notes: 任意のメモ
```

## 欄の意味

| 欄 | 役割 |
| --- | --- |
| `axioms` | 世界の公理。ここを変えたら別世界になる前提 |
| `rules` | 規則とコスト。人物の選択を拘束する |
| `institutions` | 制度・インフラ・勢力。規則が及ぶ先 |
| `geography` | 地名。canon の場所と対応させる |
| `disclosure` | 開示順序。必要な情報を必要な章に |

## 変更の記録

規則の追加・撤回は version として残す（git の履歴でよい）。
黙って変えた規則は、検査も物語も壊す。
