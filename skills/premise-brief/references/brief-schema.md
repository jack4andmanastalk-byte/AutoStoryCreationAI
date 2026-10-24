# `brief.yaml` の書式

企画核は 1 ファイル（YAML または JSON）にまとめる。後工程はこのファイルを読む。

```yaml
logline: 嵐の夜、灯台守の娘が、灯りを消すために貸した鍵の行方を追う。
elements:           # ログラインに現れる四要素。未定は「未定」と書く
  who: 灯台守の娘
  where: 嵐の夜
  wants: 鍵の行方を追う
  obstacle: 灯りを消すため
premise: 死んだはずの人物の手に鍵が渡っていた。娘は灯りを守るか追跡かを選ぶ。
theme: 灯りを守る義務対鍵を追う好奇心
similar:            # 3 件以上。差分の軸は structure / character / world
  - title: 灯台守の恋
    axis: structure
    difference: 恋愛ではなく選択の物語で、結末が未解決に寄る。
prohibitions:       # やらないこと。確認方法を必ず書く
  - rule: 選ばれし者の血統を使わない
    check_ja: 本文に「選ばれ」「血統」「予言」が出たら違反。
failure_questions:  # 失敗仮説。問いの形で書く
  - 鍵の謎が序盤で解けてしまわないか？
genre: 幻想
audience: 短編を読む成人
```

## 欄の意味

| 欄 | 役割 |
| --- | --- |
| `logline` | 一文。企画の核。声に出して読める長さ |
| `elements` | 四要素。ログラインの部品表。未定は「未定」と明示する |
| `premise` | 状況と変化の可能性。ログラインに入りきらない因果を書く |
| `theme` | 対立命題。結論ではなく問いとして残す |
| `similar` | 類似作。題名ではなく**差分の説明**が本体 |
| `prohibitions` | 禁止条件。`check_ja` が無い禁止は守れない |
| `failure_questions` | 失敗仮説。検証可能な問いの形にする |

## 書かないこと

* 登場人物の一覧（canon の `characters` が担当）
* 世界の規則（`world-rules` が担当）
* 年表（`history-timeline` が担当）

企画核は**仮説**であり、設計ではない。設計は各スキルに委ねる。
