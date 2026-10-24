---
name: premise-brief
description: 企画の核（一文ログライン・前提・主題・差分・禁止条件）を、後続の設計と評価が検証できる形に圧縮する。文章を書き始める前に何を面白がらせるのかを仮説として固定したいとき、企画が検証可能な形か確かめたいときに使う。面白さ自体は判定しない。
license: MIT
compatibility: Python 3.11+; PyYAML 6+; ネットワーク不要
metadata:
  seed: seed-01-premise-brief
  version: "0.1"
  catalog: research/catalog/techniques.jsonl
  executability: research/catalog/executability.jsonl
---

# 企画核・ログライン・主題の確定

書き始める前に、**検証できる形で**企画を固定する。このスキルの要点は
「良い企画を作る」ことではなく、**企画の良し悪しを後から判定できる材料を残す**ことにある。

## いつ使うか

* 新しい企画を立て、後工程（世界・人物・本文）に渡す核を作りたい。
* 企画書が感想文になり、「何が検証できるのか」が分からなくなった。
* 類似作との差分を、構造・人物・世界のいずれかで説明したい。

使わない場面: 既に本文がある作品の改稿（[`revision-loop`](../revision-loop/SKILL.md)）。
面白さの判定は [`evaluation-harness`](../evaluation-harness/SKILL.md) の L2/L3 の担当。

## 入力

| 入力 | 必須 | 形式 |
| --- | --- | --- |
| 素材メモ | 任意 | 箇条書きでよい |
| 制約 | 任意 | ジャンル・媒体・長さ・想定読者・レーティング |

## 手順

1. **四要素を書く。** 誰が・どこで・何を望み・何が妨げるか。分からなければ「未定」と書く。
2. **一文に圧縮する。** 四要素を一文のログラインにする。二文になったら要素が多すぎる。
3. **主題を対立命題にする。** 『A対B』の形にし、どちらへの結論も先取りしない。
4. **類似作を 3 件挙げる。** 差分を構造・人物・世界のいずれかで説明する。
5. **禁止条件を書く。** 「やらないこと」と、その確認方法（後工程が判定できる書き方）を残す。
6. **失敗仮説を問いの形にする。** 「失敗するとしたら何が原因か」を検証可能な問いにする。
7. **検査を実行する。**

   ```bash
   python3 scripts/check_brief.py --brief brief.yaml
   ```

書式は [`references/brief-schema.md`](references/brief-schema.md)。

## 出力

| 出力 | 内容 |
| --- | --- |
| `brief.yaml` | ログライン・四要素・前提・主題・類似作・禁止条件・失敗仮説 |
| 検査レポート | 構造上の所見（形式・要素・対立形・根拠・検証可能性） |

## 合格条件（このスキル自体の検証）

| 条件 | 判定方法 |
| --- | --- |
| 形式の欠陥を検出できる | `harness/cases/brief-demo/brief-bad.yaml` の 6 検査すべてを fail にする（`tests/test_premise_brief.py`） |
| 良好な企画核を通す | `brief-demo/brief.yaml` が所見 0 件になる |
| 壊れた入力で落ちない | 必須欄の欠落は `BriefError` で、検査不能ではなく入力異常として返す |
| 面白さを判定しない | 検査項目に質の判断が含まれない（`references/measurement.md` の非目標表） |
| CI で使える | `--fail-on medium` で終了コードが 1 になる |

**この 5 条件は本リポジトリが書いた編集上の基準であり、原典の主張ではない。**

## しないこと

* ログラインの巧さを作品の質と混同しない（巧い一文と良い作品は別）。
* 主題を単一の教訓に還元しない（多声的な作品を作れなくなる）。
* 類似作 3 件を「影響の告白」にしない（差分の説明が本体。題名だけでは不足）。
* 所見 0 件を「良い企画」と表現しない。**検証可能な形になった**という意味でしかない。

## うまくいかないとき

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| ログラインが二文になる | 要素が多い | 副次的な要素を premise に移す |
| 主題が教訓になる | 対立がない | 反対側の立場の人物を一人置く |
| 禁止条件が書けない | 企画が固まっていない | 類似作の「やっていること」を裏返す |

## 参照

* [`references/brief-schema.md`](references/brief-schema.md) — `brief.yaml` の書式
* [`references/measurement.md`](references/measurement.md) — 各検査の合格条件と、判定しないこと
* [`references/techniques.md`](references/techniques.md) — 依拠した技法と、本実装で補った条件
* `research/catalog/executability.jsonl` — 依拠した技法の実行可能度
