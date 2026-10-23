# `voice.yaml` の書式

```yaml
viewpoint:
  person: first            # first（一人称）/ third（三人称）
  character: 凪             # 視点人物。本文中の表記
  aliases: [なぎ]           # 別表記
  pronouns: [私]            # 一人称のみ。自称の宣言
narrator:
  knows_ja: 凪が見聞きしたことだけを地の文で書く。他者の心中は断定しない。
sample: |                  # 300 字程度の照合基準。本文から採る
  雨が灯台の窓を叩いた。私は鍵を握りしめた。……
banned:                    # 文体固有の禁止表現（正規表現）
  - id: emotion_naming
    pattern: "(悲しかった|嬉しかった)。"
    message_ja: 感情の直接命名。所作か知覚で示す。
notes: 任意のメモ
```

## 欄の意味

| 欄 | 役割 | 無い場合 |
| --- | --- | --- |
| `viewpoint` | 誰の視点か | 必須（無いと読込異常） |
| `narrator.knows_ja` | 語り手の知識範囲 | 必須（無いと読込異常） |
| `sample` | 照合基準の本文 | `sample_drift` が `skipped` |
| `banned` | 禁止表現 | `banned_voice` が `skipped` |
| `pronouns` | 自称の宣言 | `pronoun_drift` が `skipped`（一人称のみ検査） |

## 全知視点の扱い

全知視点の作品では `person: third` にし、視点人物を「語り手」と書く。
`viewpoint_slip` は視点外断定の検出には使えないため、結果は参考扱いにする。
禁止表現と乖離の検査はそのまま使える。
