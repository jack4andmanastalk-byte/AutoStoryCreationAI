---
name: character-core
description: 性格の形容詞ではなく圧力下の選択が一貫して説明できる人物モデル（WANT/NEED・恐れ・行動原理・口調・アーク）を作り、設計書として検証できる形か検査する。都合のよい性格変化を防ぎたいとき、脇役が引き立て役に堕していないか確かめたいときに使う。人物の魅力は判定しない。
license: MIT
compatibility: Python 3.11+; PyYAML 6+; ネットワーク不要
metadata:
  seed: seed-04-character-core
  version: "0.1"
  catalog: research/catalog/techniques.jsonl
  executability: research/catalog/executability.jsonl
---

# 人物の核・欲望・変化の設計

人物を**形容詞の羅列ではなく選択のモデル**として書く。
このスキルの要点は魅力的な人物を作ることではなく、
**圧力下の選択が一貫して説明できること**にある。

## いつ使うか

* 新しい人物の核（WANT/NEED・恐れ・行動原理）を固定したい。
* 都合のよい性格変化が起きていないか設計段階で潰したい。
* 脇役が主人公の引き立て役だけになっていないか確かめたい。
* 口調を章をまたいで一貫させたい。

使わない場面: 本文中の人物の振る舞いの判定（L2 の `character_consistency` の担当）。
canon の状態管理（生死・所在・既知事実）は [`continuity-ledger`](../continuity-ledger/SKILL.md)。

## 入力

| 入力 | 必須 | 形式 |
| --- | --- | --- |
| 物語の前提 | 任意 | ログラインでよい |
| 人物の役割 | 任意 | 主人公・対立者・脇役など |
| canon | 照合時に必須 | `check_character --canon` に渡す |

## 手順

1. **WANT と NEED を分けて書く。** 失いたくないものと、本当に必要なものは別物。
2. **自己像と他者像を分ける。** 本人の思い込みと、他者からの見え方のずれが人物を作る。
3. **状況を変えた選択を 3 つ予測する。** 同じ核から違う選択が出ることを確かめる。
4. **口調を固定する。** 会話サンプルを書き写し、使う語と避ける語を決める。
5. **アークの終点を決める。** 変わる選択と変わらない選択の両方を書く。
6. **検査を実行する。**

   ```bash
   python3 scripts/check_character.py --characters characters.yaml --canon canon/
   ```

書式は [`references/character-schema.md`](references/character-schema.md)。

## 出力

| 出力 | 内容 |
| --- | --- |
| `characters.yaml` | 人物ごとの核・視点・予測・口調・アーク・禁止行動 |
| 検査レポート | 構造上の所見（核・視点・予測・口調・アーク・canon 対応） |

## 合格条件（このスキル自体の検証）

| 条件 | 判定方法 |
| --- | --- |
| 形式の欠陥を検出できる | `harness/cases/character-demo/characters-bad.yaml` の 6 検査すべてを fail にする（`tests/test_character_core.py`） |
| 良好な人物核を通す | `character-demo/characters.yaml` が所見 0 件になる |
| canon が無くても落ちない | ID の照合が `skipped` になり、理由がレポートに出る |
| 魅力を判定しない | 検査項目に質の判断が含まれない（`references/measurement.md` の非目標表） |
| CI で使える | `--fail-on medium` で終了コードが 1 になる |

**この 5 条件は本リポジトリが書いた編集上の基準であり、原典の主張ではない。**

## しないこと

* 診断ツール（MBTI 等）を実在性の保証にしない。
* 属性の組合せで人物を済ませない（関係性は属性から生まれない）。
* 主人公以外の人物を主人公の都合だけで動かさない（全員に WANT/NEED を書く）。
* 所見 0 件を「良い人物」と表現しない。

## うまくいかないとき

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| WANT と NEED が同じになる | 欲望の掘り下げ不足 | 「失いたくないもの」と「変わるために要るもの」を分ける |
| 予測が 3 つ書けない | 核が薄い | 恐れと傷を具体化してから戻る |
| 口調が決まらない | サンプル不足 | 既存の会話場面を 30 字以上書き写す |

## 参照

* [`references/character-schema.md`](references/character-schema.md) — `characters.yaml` の書式
* [`references/measurement.md`](references/measurement.md) — 各検査の合格条件と、判定しないこと
* [`references/techniques.md`](references/techniques.md) — 依拠した技法と、本実装で補った条件
* `research/catalog/executability.jsonl` — 依拠した技法の実行可能度
