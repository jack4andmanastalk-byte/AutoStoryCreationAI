# `scenes.yaml` の書式

```yaml
scenes:
  - id: s01
    chapter: ch01              # canon の章
    purpose: 鍵の貸し借りという謎を置く
    conflict: アリアは確かめたい。父の命令は止める
    change: アリアが革袋を持ち出す
    tension: curiosity          # 6 語彙から選ぶ（下表）
    knowledge:                  # 任意。人物 × 事実の流れ
      - character: aria
        entry: []               # 入場時の既知（事実 ID）
        gained: [F-09]          # 場面で得る事実。開示計画に入れる
    disclosure:                 # 読者への開示計画
      disclosed: [F-09]
      withheld:                 # 任意
        - fact: F-07
          reason: 預かり主の死と一緒に明かす
    foreshadows:
      planted:                  # 新規 ID＋回収予定の章。任意
        - id: fs-ledger-copy
          payoff: ch03
      paid: [fs-001]            # canon の布石 ID。任意
notes: 任意のメモ
```

## 緊張の型（6 語彙）

| 型 | 意味 | 依存 |
| --- | --- | --- |
| `suspense` | 結果を待たせる | 読者が結末の候補を知る |
| `curiosity` | 欠けた過去を気にさせる | 欠けていることの提示 |
| `surprise` | 遡って意味を変える | 伏線の事前配置 |
| `irony` | 読者だけが知る | 情報の非対称 |
| `deadline` | 期限で追う | 期限の明示 |
| `quiet` | 静かな場面（型なしの宣言） | — |

「型の使い方が正しいか」は検査しない。型の宣言だけを検査する。

## canon との分担

| 設計書（このスキル） | canon（`continuity-ledger`） |
| --- | --- |
| 場面の仕事・緊張・開示の計画 | 章・時点・事実・伏線の記録 |
| 知識の流れ（予定） | 既知集合（記録） |
| 新規布石の仕掛けと回収予定 | 伏線の回収状態（監査） |
