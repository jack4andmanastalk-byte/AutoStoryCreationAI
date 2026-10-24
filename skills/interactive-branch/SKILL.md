---
name: interactive-branch
description: 分岐を節点と辺の構造として設計し、到達不能・行き止まり・罠・辿れない条件・覚え書きのない合流を機械的に検査する。分岐ゲーム・選択肢のある物語・マルチエンディングの構造監査に使う。選択の面白さは判定しない。
license: MIT
compatibility: Python 3.11+; PyYAML 6+; ネットワーク不要
metadata:
  seed: seed-11-interactive-branch
  version: "0.1"
  catalog: research/catalog/techniques.jsonl
  executability: research/catalog/executability.jsonl
---

# 分岐・状態・合流の設計

分岐を**フローチャートの絵ではなく検査できる構造**として書く。
このスキルの要点は、全節点が開始点から到達でき、全節点から結末に
到達でき、条件が実際に成立し、合流点の扱いが書かれていることにある。

## いつ使うか

* 分岐の行き止まり・到達不能・無限回遊を潰したい。
* 条件分岐（旗・状態変数）が実際に成立するか確かめたい。
* 合流点で知識・状態が食い違っていないか確かめたい。
* 選択肢が形だけ（1 件・表示の重複・辺のない選択肢）になっていないか確かめたい。

使わない場面: 線形の物語の設計（`plot-architecture`、`scene-information`）。
選択の意味の評価は L2/L3。

## 入力

| 入力 | 必須 | 形式 |
| --- | --- | --- |
| 節点と辺 | 必須 | `branches.yaml` の書式で |

分岐は自己完結。canon は要らない。

## 手順

1. **節点を書く。** scene（場面）/ choice（選択）/ ending（結末）。
2. **辺を書く。** 選択肢からの辺には `via`、条件には `requires`、更新には `sets`。
3. **旗を表にする。** 意味を書き、初期値を決める。
4. **合流点に覚え書きを書く。** 2 方向以上から入る節点は知識・状態の扱いを書く。
5. **検査を実行する。**

   ```bash
   python3 scripts/check_branch.py --branches branches.yaml
   ```

書式は [`references/branch-schema.md`](references/branch-schema.md)。

## 出力

| 出力 | 内容 |
| --- | --- |
| `branches.yaml` | 節点・辺・旗・開始点 |
| 検査レポート | 構造上の所見（参照・到達・終端・旗・条件・選択肢・合流） |

## 合格条件（このスキル自体の検証）

| 条件 | 判定方法 |
| --- | --- |
| 形式の欠陥を検出できる | `harness/cases/branch-demo/branches-bad.yaml` の 7 検査すべてを fail にする（`tests/test_interactive_branch.py`） |
| 良好な分岐を通す | `branch-demo/branches.yaml` が所見 0 件になる |
| 条件の検査が有界である | 状態空間の上限を超えたら省略を low で報告し、推測しない |
| 面白さを判定しない | 検査項目に質の判断が含まれない（`references/measurement.md` の非目標表） |
| CI で使える | `--fail-on medium` で終了コードが 1 になる |

**この 5 条件は本リポジトリが書いた編集上の基準であり、原典の主張ではない。**

## しないこと

* 1 件の選択肢を選択肢と呼ばない。
* 辺のない選択肢を残さない。
* 合流点の扱いを書かずに合流させない。
* 所見 0 件を「面白い分岐」と表現しない。

## うまくいかないとき

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| 到達不能が消えない | 辺の不足か、削り忘れ | 足すか削るか決める |
| 条件が辿れない | 旗の設定漏れ | 設定する辺を足すか、条件を緩める |
| 状態空間の上限に達する | 旗の組合せ爆発 | 分岐を分割して再検査する |

## 参照

* [`references/branch-schema.md`](references/branch-schema.md) — `branches.yaml` の書式
* [`references/measurement.md`](references/measurement.md) — 各検査の合格条件と、判定しないこと
* [`references/techniques.md`](references/techniques.md) — 依拠した技法と、本実装で補った条件
* `research/catalog/executability.jsonl` — 依拠した技法の実行可能度
