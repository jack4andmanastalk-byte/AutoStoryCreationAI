# `adaptation.yaml` の書式

```yaml
source_title: 灯台の鍵（架空の短編）
target_medium: 舞台
functions:                      # 機能。1 件以上
  - id: fn-key-mystery
    kind: info                  # info / emotion / relation / tempo
    description: 鍵の貸し借りという謎の提示
mappings:                       # 翻訳。機能ごとに手段＋両者への対応
  - function: fn-key-mystery
    means: 客席に鍵の束を見せる発端の身振り
    newcomer: 台詞で貸し借りの関係を説明する
    existing: 原作の革袋の描写を小道具で再現する
deletions:                      # 削除。理由＋代替
  - function: fn-night-watch
    reason: 上演時間に夜番の長さを収められない
    substitute: 番の交代の所作が時間の経過を担う
rights:
  source: 灯台の鍵（著作者の許諾済みと想定）
  scope: 舞台上演・配信
  status: cleared               # cleared / pending / na
notes: 任意のメモ
```

## 機能の種類（4 語彙）

| 種類 | 担うもの |
| --- | --- |
| `info` | 情報（謎・事実・設定）の提示 |
| `emotion` | 感情の動き |
| `relation` | 関係の変化 |
| `tempo` | 緩急・時間の配分 |

## 行き先の規則

各機能は翻訳（`mappings`）か削除（`deletions`）のどちらかに属する。
両方・どちらでもないは所見。削る機能の働きは `substitute` に書く。
