# バッチ B2: history プロンプト v1.1 での S1 全体 1 標本 — t01

- 日付: 2026-10-27
- 種類: 事前登録に基づく介入 1 標本（Arena Agent Mode 内で実行する）
- 状態: **未走行**（`results.json` は `not_run` の予定）
- 事前登録: [`preregistration.md`](preregistration.md) / [`preregistration.json`](preregistration.json)
- 手順: [`runbook.md`](runbook.md)
- 計測: [`results.json`](results.json)（`schema: realrun-b-v1`、事前登録の `sha256` を記録）
- 運用モデル: [`docs/arena_operation.md`](../../docs/arena_operation.md)
- 位置づけ: [`docs/two_stage_slice.md`](../../docs/two_stage_slice.md) §24
- 先行バッチ: [`experiments/2026-10-realrun-b-t01/`](../2026-10-realrun-b-t01/note.md)

## なぜこのバッチがあるか

バッチ B（§23.1）では S1 全体が初めて通った一方、設計の初回所見が 5 件あった。
そのうち history の `canon_separated` 3 件は、プロンプトに書かれていない制約によるもので、
「検査だけが知っている規則で書き手が減点される」構造（§22 で是正したのと同型）が残っていた。

B2 は、その制約をプロンプトに明記した `design-history` v1.1 で同じ S1 経路をもう一度だけ通し、
対象所見が初回に出るかどうかを、走らせる前に固定した判定（H）で記録するバッチである。
検証の狙いは「直ったことの証明」ではなく、明記後もなお出るかどうかを後から読み替えずに
残すことにある。

## 何を固定したか（走らせる前）

1. **条件**: t01、S1、`--stage all`、seed 0、temperature 0.8、1 標本（`sample-2`）。
2. **変更は 1 点だけ**: `design-history` プロンプト 1.0 → 1.1。
   history 検査（`canon_separated` / `trace_exists` / `knowledge_consistent`）だけが
   知っていた未記載の制約を、検査と同じ意味になるようプロンプトに明記した。
   検査そのもの（閾値・重大度）は変えていない。
3. **canon 方針はバッチ B と同じ**: 同一 run の plan が一度だけ作った単一 canon を
   8 設計と draft が読む（`--canon` は付けない）。
4. **判定**: B0〜B4 はバッチ B の定義を継承。加えて H（history の `canon_separated`
   初回所見の有無）を置く。数え方は初回所見を主とし、修復で消えたものも数える。
5. **交絡の明記**: 生成担い手はバッチ B と同一の Arena エージェントであり、同じ指摘を
   経験済みである。増減をプロンプト変更だけに帰因しない。

## 現在の中身

| パス | 内容 |
| --- | --- |
| `preregistration.json` / `preregistration.md` | 走らせる前に固定した条件・判定・prompt digest |
| `runbook.md` | Arena 内でエージェントが relay を使って回す 1 標本の手順 |
| `results.json` | 計測スクリプトの空の出力（未走行） |
| `relay/sample-2/.gitkeep` | 実行時に要求・応答が入る場所。現時点では空 |

## 結果（走行後にここへ書く）

まだ無い。走行したら `results.json` の verdict を読み替えずに引用し、次を書く。

- B0〜B4 と H の verdict、run の status と gates。
- history の初回 findings（check 別。特に対象 `canon_separated`）と最終 findings。
- 他の 7 設計も含めた初回・最終 findings、修復で消えた件数。
- 章ごとの字数、attempts、補完マーカー、必須語率。
- 監査の内訳と CED（参考値）。
- バッチ B との記述的対照（合算した率は出さない）。

## 限界

- **N=1**（本バッチ）。バッチ B（N=1）との 1 対 1 の記述的対照であり、効果量・再発率は主張しない。
- 同一担い手の学習という交絡がある。H が `target_findings_absent` でもプロンプトの効果とは言わない。
- canon が新規生成されるため、本文同士の比較にはならない。比べられるのは段ごとの所見・修復・L1 指標の出方まで。
- operator 応答では同一 seed の再現性（G5）を示せない。応答の独立性も保証されない。
- L2/L3 は `frozen_not_measured`。意味的整合や面白さは測っていない。

## 次にすること

1. [runbook.md](runbook.md) の手順で sample-2 を Arena 内で回す。
2. 完走または終端失敗後に `scripts/measure_realrun_b.py --bundle experiments/2026-10-realrun-b2-t01` で測る。
3. verdict をこのノートへ引用し、初回所見の出方を記録する。
4. さらに足す場合は B3 として走らせる前に登録する。
