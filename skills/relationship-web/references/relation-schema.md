# `relations.yaml` の書式

```yaml
pairs:                        # 関係。1 件以上
  - a: aria
    b: boris                  # 人物は canon の ID
    public: 依頼人と無愛想な鍵屋  # 表向き。空欄不可
    stakes: 鍵の返却を巡る駆け引き  # 実際の利害。空欄不可
    conflict: |               # 両立しない目的。全体で 1 件以上
      アリアは鍵を今すぐ取り返したい。
      ボリスは帳面の筋を通すまで返さない。両立しない
knowledge:                    # 知識表。人物 × 事実
  - character: boris
    fact: F-07                # canon の事実 ID
    state: knows              # knows / unknown / suspects
changes:                      # 関係の変化。章・契機・変化後
  - pair: [aria, boris]       # 関係表にある相手
    chapter: ch03             # canon の章
    trigger: ボリスが帳面の一頁を見せる
    after: 依頼人と鍵屋から、記録を共有する共犯へ
silences:                     # 沈黙・言い淀み
  - chapter: ch02
    who: boris
    unsaid_ja: 預かり主が死んだことを、まだアリアに言わない
notes: 任意のメモ
```

## 欄の意味

| 欄 | 役割 |
| --- | --- |
| `public` / `stakes` | 表向きと利害の分離。同じ文は避ける |
| `conflict` | 両立しない目的。「誤解を解けば終わる」は不可 |
| `knowledge` | 誰が何を知るか。推理・サスペンスの土台 |
| `changes` | 変化の設計。契機は選択と行動で書く |
| `silences` | 沈黙の意味。言わないことを書く |

## canon との分担

| 設計書（このスキル） | canon（`continuity-ledger`） |
| --- | --- |
| どう衝突し、何が変わるか | いまどういう状態か |
| 誰が何を知る「予定」か | 誰が何を既知か（記録） |
| 沈黙の意味 | 変化のマーカー（いつ変わったか） |
