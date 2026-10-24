# 設計prompt契約testの拡張（2026-10-24）

- 工程: ⑤ brief以外の7設計promptの契約test拡張
- コード: `44a87923f97ec5cc4e97fca53e83d77295b5936d`
- test: [`tests/test_design_prompt_contracts.py`](../../tests/test_design_prompt_contracts.py)
- 機械集計: [`results.json`](results.json)
- 範囲: **L1の構造・canon参照契約**。新規モデル応答・作品品質評価なし

## 目的

world・history・character・relation・plot・scene・voice の各promptについて、
正常な台本が通ることだけでなく、promptが明示する契約と、不正応答をrepairへ回して
記録する挙動を固定する。standalone checkerのYAML demoではなく、実際の `build_design`
境界で検証した。

## 追加した29件

| 区分 | 件数 | 確認内容 |
| --- | ---: | --- |
| prompt契約 | 7 | canon・先行設計・JSON-only・各文書固有の機械条件がpromptにある |
| 正常JSON | 7 | 各文書が1 attempt・findings 0・`clean` |
| 構造・canon参照の失敗 | 7 | 2 attempts後に`unresolved`、初回/最終findingsとrepair promptへ記録 |
| nested JSON型違い | 7 | pipeline例外ではなく`schema`所見として扱う |
| 開示/保留の正常形 | 1 | 獲得事実を理由付きで保留できる |

失敗caseの主な対象:

| 文書 | 検査する不整合 | 型違いcase |
| --- | --- | --- |
| world | canonにない地理・存在しない開示章 | rulesを文字列化 |
| history | 年代逆順・不明な原因・不明な人物/出来事の知識 | 出来事yearを文字列化 |
| character | WANT=NEED・予測不足・不明な人物ID | speechを文字列化 |
| relation | canon既知をunknown化・関係表にない変化 | 変化pairを文字列化 |
| plot | 幕の章不整合・転換点不足・不明な伏線ID | endingを文字列化 |
| scene | 獲得事実の開示漏れ・早すぎる回収・不明な伏線ID | disclosureを文字列化 |
| voice | 一人称の自称欠落・固定sample欠落・禁止理由欠落 | viewpointを文字列化 |

ここで「失敗」はL1の構造・参照不整合であり、L2の意味評価や作品の良し悪しではない。
`unresolved` は設計段階のfail-open仕様どおり記録される状態であり、`clean`と混同しない。

## test中に確認・修正した契約差

1. **sceneの獲得事実の保留**  
   promptは「開示か保留のどちらか」とする一方、checkerは`disclosed`に無い獲得事実を
   一律に拒否していた。`scene/check.py`を修正し、理由付き`withheld`も受け付けるようにした。
   開示と保留の両方に同じ事実を置く従来の禁止は変更していない。

2. **voiceの設計時必須条件**  
   原稿が無い設計段階では読み込みだけで通っていた。`pipeline/design.py`に、
   一人称の`pronouns`、固定`sample`、禁止表現の`message_ja`を検査するfindingを追加した。
   原稿に対する文体検査は従来どおり後段へ残す。standaloneの文体demoは変更していない。

7種のprompt本文とversion 1.0、brief v1.1、protocol-v1は変更していない。

## 検証結果

- 新規契約test: **29 collected / 29 passed**
- 関連test: **61 passed**（新規契約・pipeline design・scene・voice）
- 全CI: **423 passed, 3 warnings**
- research catalog: up to date
- continuity demo・evaluation fixture: 実行成功（evaluationは凍結資産の固定fixture）

設計契約の変更後、同じcommit `44a8792` で工程③の2 runを再度replayした。

| タスク | replay run | 応答 | 成果物一致 | 元run |
| --- | --- | ---: | ---: | --- |
| t02 | `20261024T143333Z-t02-s1-s0-b1e64fa7` | 12 / 12 | 42 / 42 | hash不変 |
| t03 | `20261024T143333Z-t03-s1-s0-2d849daf` | 12 / 12 | 42 / 42 | hash不変 |

したがって、今回の契約強化は少なくともこの2つの正式runの記録応答と成果物を変えなかった。
ただし、これは全ての将来の設計応答がcleanになるという意味ではない。

## 限界と終了条件

- 台本による選択的な異常caseであり、網羅的なfuzzingやモデル性能評価ではない。
- 正常契約への適合は、作品品質・ジャンル適合・protocol-v1合格を示さない。
- replayは記録済み応答の再実行であり、G5のモデル再現性を示さない。
- 新規のArena応答、人間評定、L2/L3の実証・較正は行っていない。L2/L3凍結を維持する。
- 30作品の凍結対照群、正式な生成/replay結果、旧baselineは上書きしていない。

これで、全新規S1 N=3、標準集計、複数タスク展開、監査可能なreplay、設計prompt契約testの
工程①〜⑤がそろった。今後もL2/L3を再開する場合は、利用者の明示的な決定と別条件が必要である。
