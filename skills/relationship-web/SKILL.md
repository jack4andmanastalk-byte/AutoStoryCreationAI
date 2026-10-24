---
name: relationship-web
description: 関係を属性の組合せではなく両立しない目的・知識状態・沈黙の設計として書く。場面を動かす圧力を作り、設計書として検査できる。都合のよい和解や寝返り（準備のない変化）を防ぎたいときに使う。関係の面白さは判定しない。
license: MIT
compatibility: Python 3.11+; PyYAML 6+; ネットワーク不要
metadata:
  seed: seed-05-relationship-web
  version: "0.1"
  catalog: research/catalog/techniques.jsonl
  executability: research/catalog/executability.jsonl
---

# 関係網・対立・変化点の設計

関係を**属性の組合せではなく力の設計**として書く。
このスキルの要点は「誰と誰が何で衝突し、何を知り、何が変わるか」を
場面が始まる前に決めることにある。

## いつ使うか

* 対立が「誤解を解けば終わる」水準に堕していないか確かめたい。
* 寝返り・和解・裏切りが準備なしに起きていないか潰したい。
* 「誰が何を知っているか」の表を作品全体で持ちたい。
* 沈黙・言い淀みに意味を持たせたい。

使わない場面: 本文中の関係の動きの判定（L2 の担当）。
人物単体の核は [`character-core`](../character-core/SKILL.md)。

## 入力

| 入力 | 必須 | 形式 |
| --- | --- | --- |
| 登場人物 | 任意 | ID の一覧でよい |
| canon | 照合時に必須 | `check_relation --canon` に渡す |

## 手順

1. **表向きと利害を分けて書く。** 周囲に見える関係と、実際の力関係は別物。
2. **両立しない目的を 1 件以上書く。** 誤解レベルの対立と区別する。
3. **知識状態を表にする。** 人物 × 事実の `knows` / `unknown` / `suspects`。
4. **変化を章・契機・変化後で設計する。** 変化は選択と行動で起きる。
5. **沈黙を用意する。** 言わないことを書かない沈黙は、ただの空白。
6. **検査を実行する。**

   ```bash
   python3 scripts/check_relation.py --relations relations.yaml --canon canon/
   ```

書式は [`references/relation-schema.md`](references/relation-schema.md)。

## 出力

| 出力 | 内容 |
| --- | --- |
| `relations.yaml` | 関係・知識表・変化・沈黙 |
| 検査レポート | 構造上の所見（関係・衝突・知識・変化・沈黙・canon 照合） |

## 合格条件（このスキル自体の検証）

| 条件 | 判定方法 |
| --- | --- |
| 形式の欠陥を検出できる | `harness/cases/relation-demo/relations-bad.yaml` の 6 検査すべてを fail にする（`tests/test_relationship_web.py`） |
| 良好な関係網を通す | `relation-demo/relations.yaml` が所見 0 件になる |
| canon が無くても落ちない | 照合が弱くなり、理由がレポートに出る |
| 面白さを判定しない | 検査項目に質の判断が含まれない（`references/measurement.md` の非目標表） |
| CI で使える | `--fail-on medium` で終了コードが 1 になる |

**この 5 条件は本リポジトリが書いた編集上の基準であり、原典の主張ではない。**

## しないこと

* 属性の組合せで関係を済ませない。
* 「誤解が解けるだけ」の対立を両立しない目的と呼ばない。
* 変化の契機を「時間が経った」「なんとなく」にしない。
* 所見 0 件を「良い関係」と表現しない。

## うまくいかないとき

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| 衝突が書けない | 目的が誤解レベル | 互いの方針が同時に成立しない形に掘る |
| 知識表が真っ白になる | 事実の整理不足 | `continuity-ledger` の事実台帳を先に作る |
| 変化が唐突だと言われる | 契機の不足 | index(兆候)→予兆→発現の順に場面を置く |

## 参照

* [`references/relation-schema.md`](references/relation-schema.md) — `relations.yaml` の書式
* [`references/measurement.md`](references/measurement.md) — 各検査の合格条件と、判定しないこと
* [`references/techniques.md`](references/techniques.md) — 依拠した技法と、本実装で補った条件
* `research/catalog/executability.jsonl` — 依拠した技法の実行可能度
