# canon とマーカーの書式

canon は**作品の外にある正解**である。本文から推測せず、ここに書かれたことだけを根拠にする。
全ファイルが任意で、YAML と JSON のどちらでもよい。1 つの `canon.yaml` にまとめてもよい。

```
canon/
├── characters.yaml   # 人物の状態
├── facts.yaml        # 作品世界の事実
├── locations.yaml    # 場所と移動日数
├── timeline.yaml     # 章ごとの日付・場所
├── foreshadowing.yaml# 伏線の設置・回収
└── suppressions.yaml # 意図的な矛盾（除外リスト）
```

## characters

```yaml
characters:
  - id: aria                 # 必須。マーカーと台帳のキー
    name: アリア              # 本文中の表記
    aliases: ["アリア姫"]      # 別表記（姓・肩書・愛称）
    status: alive            # alive / dead / missing / unknown
    status_since: ch02       # その状態になった章（死亡章の判定に使う）
    location: 灯台
    age_at_start: 24
    birthday_day: 120        # 通日。年齢の自動検査に使う
    knows: ["F-07"]          # 物語開始時に知っている事実 ID
    notes: 灯台守の娘
```

`status_since` を省くと、死亡は本文の `{{death}}` マーカーだけが根拠になる。
どちらも無い場合、死亡した人物の検査は行われない（`skipped`）。

## facts

```yaml
facts:
  - id: F-07
    summary: 王の病は治らない
    terms: ["王の病", "咳"]    # 台詞中の語彙手掛かり（任意）
    setup: ch03               # 事実が明かされる章（任意）
```

`terms` を書くと、学習前の台詞にその語が出たときに medium で報告する。
書かなければ、`{{use}}` マーカーによる検査だけになる。

## locations

```yaml
locations:
  - id: 灯台
    travel_days:
      王都: 3      # 灯台 → 王都 に 3 日
      港: 1
```

逆向きは自動で使われる（`王都 → 灯台` は 3 日）。定義のない組は**判定しない**。
移動日数は作者が決めるもので、現実の地理と一致する必要はない。

## timeline

```yaml
chapters:
  - id: ch01
    day: 1        # 通日。章の順序と経過日数の基準
    year: 1024    # 任意
    location: 灯台
```

`day` が無い章は移動時間の検査から外れる。

## foreshadowing

```yaml
foreshadowing:
  - id: fs-001
    description: 灯台の鍵
    setup: ch01
    payoff: ch04   # 未回収なら書かない
```

ここに書いた `setup` は「設置済み」として扱われる。本文のマーカーと食い違うと low で報告される。

## suppressions（意図的な矛盾）

```yaml
suppressions:
  - check: dead_character_reappears   # 検査 ID（* で全検査）
    subject: boris                    # 人物 ID・伏線 ID（* で全部）
    scope: [ch05]                     # 章を限定（省略すると全章）
    reason: アリアの夢の中の回想。故人が発話するのは意図どおり。
```

`reason` は必須の運用とする。空の除外は、後から「なぜ許したか」が分からなくなる。

## 本文マーカー

本文中に `{{種別: 引数}}` の形で書く。描画時は除去する。

| マーカー | 意味 | 例 |
| --- | --- | --- |
| `{{death: 人物 \| 補足}}` | 死亡 | `{{death: boris \| 崩落}}` |
| `{{state: 人物 key=value}}` | 状態変化 | `{{state: aria location=王都}}` |
| `{{learn: 人物 fact=ID}}` | 事実を知る | `{{learn: aria fact=F-07}}` |
| `{{use: 人物 fact=ID}}` | 事実を利用する | `{{use: aria fact=F-07}}` |
| `{{time: day=N}}` | 章の時点 | `{{time: day=11}}` |
| `{{location: 場所}}` | 章の場所 | `{{location: 王都}}` |
| `{{foreshadow: fs-ID setup\|payoff}}` | 伏線 | `{{foreshadow: fs-001 payoff}}` |
| `{{age: 人物 N}}` | 年齢の明示 | `{{age: aria 24}}` |

マーカーは**本文の事実を機械可読にする**ためのもの。マーカーが無い章は、
名前の言及による検査だけが行われる（重要度は下がる）。

## 最小構成

```yaml
# canon/characters.yaml
characters:
  - id: aria
    name: アリア
    status: alive
```

```yaml
# canon/timeline.yaml
chapters:
  - id: ch01
    day: 1
    location: 灯台
```

これだけでも、名前の言及・死亡・時系列の一部は検査できる。空の canon では
全検査が `skipped` になり、レポートにその理由が出る。
