# `plot.yaml` の書式

```yaml
logline: 灯台守の娘が鍵の真相を追い、自分の選択で灯りを守る
acts:                           # 幕。章を過不足なく覆う
  - id: setup
    chapters: [ch01, ch02]      # canon の章
    question: 鍵を追う資格は誰の手にあるか
turns:                          # 転換点。3～5 件
  - id: t1
    chapter: ch01
    choice_ja: アリアは父の命令に背き、鍵の借り手を確かめに行く
    point_of_no_return: 革袋を持ち出した時点で引き返せない  # 任意
subplots:                       # 副筋。任意
  - id: ledger
    beats: [帳面の写しの発見, 組合への届け出, 帳面の返却]
    converges: ch03 で本筋の疑いと交わる
ending:                         # 結末。型・要約・余韻
  kind: bittersweet             # resolved / bittersweet / open
  summary: 鍵は返るが、借り手の死の真相は残る
  aftertaste_ja: 守られた灯りと、残された問い
unresolved:                     # 未回収の棚卸し。任意
  - item: 借り手が鍵を借りた理由
    foreshadowing: fs-001       # canon の布石 ID
  - item: 王の病の行方
    intentional: true           # 意図的未回収の宣言
notes: 任意のメモ
```

## 欄の意味

| 欄 | 役割 |
| --- | --- |
| `acts` | 章の束と、各束が問うもの |
| `turns` | 選択の連鎖。出来事ではなく選択で書く |
| `subplots` | 副筋。節目と本筋への合流を持つ |
| `ending` | 結末の型・要約・余韻。先に決める |
| `unresolved` | 未回収。布石に結び付けるか意図的と宣言する |

## 型の使い分け

`kind` は結末の締め方。どれが優れているという序列ではない。

| 型 | 意味 |
| --- | --- |
| `resolved` | 問いが解ける |
| `bittersweet` | 解けるが代償が残る |
| `open` | 問いが残る（意図的に） |

## canon との分担

| 設計書（このスキル） | canon（`continuity-ledger`） |
| --- | --- |
| 幕・転換点・副筋・結末の設計 | 章・時点・伏線の記録 |
| 未回収の棚卸し（計画） | 伏線の回収状態（監査） |
