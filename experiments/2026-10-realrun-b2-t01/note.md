# バッチ B2: history プロンプト v1.1 での S1 全体 1 標本 — t01

- 日付: 2026-10-27
- 種類: 事前登録に基づく介入 1 標本（Arena Agent Mode 内で実行する）
- 状態: **完走**（2026-10-27、`sample-2`、status=`pass`）。事前登録と介入は走行前に commit `f7957c6` で固定した。
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
| `results.json` | 計測結果（B0〜B4 と H の verdict、事前登録の `sha256` を記録） |
| `relay/sample-2/` | 実行時の要求・応答の記録（prompt hash で対応が追える） |

## 結果（2026-10-27、1 標本）

`results.json` の verdict を読み替えずに引用する。

| 判定 | verdict |
| --- | --- |
| B0 条件 | `condition_ok` |
| B1 完走 | `complete_pass` |
| B2 初回所見 | `first_attempt_clean` |
| B3 長さ | `length_ok` |
| B4 監査 | `audit_no_high_all_checks_ran` |
| H（history の `canon_separated` 初回所見） | `target_findings_absent` |

- **run 全体**: status=`pass`、gates はすべて true（必須語 3/3、合計 3,311 字、high 違反なし、
  全検査実行）。コードは事前登録・介入コミット `f7957c6`、model は `arena-agent-mode` /
  `unversioned-2026-10-27`。応答は **12 件**（plan 1・設計 8・draft 3、修復・再試行なし）で、
  すべてこの Arena セッションのエージェントが生成し逐語で取り込んだ。
  `provenance.origin` は全件 `unspecified`（ingest が origin を書かないため）で、
  新規生成とは主張しない。独立性も保証されない。
- **plan / canon**: 初回で受理（attempts=1）。生成 canon は人物 4・事実 3・場所 2・章 3・伏線 2、
  checks_covered 6/6。6 ファイルの sha256 は `results.json` に記録した。
- **設計**: 8 件すべて初回で `clean`（attempts=8、repairs=0）。**初回 findings は合計 0 件**
  （最終も 0 件、`disappeared_exact=0`）。介入対象の history も初回 findings 0 件で、
  `canon_separated` は出なかった（H=`target_findings_absent`）。
- **draft**: 3 章すべて初回受理（再試行・補完マーカーなし）。字数は ch01=1,097、ch02=1,048、
  ch03=1,166 で **全章が目安内**、合計 3,311 字。
- **監査**: violations=2（すべて medium `dead_character_reappears`、ch02・ch03 での汐への言及）、
  high=0、checks_run=6 / checks_skipped=0、CED=5.672/1万字（参考値）。
  バッチ B と同じく「回想・言及の可能性」を監査器自身が注記する類であり、
  本文では死者は行為者になっていない。
- **バッチ B との記述的対照**（率にはしない）: 初回 findings は B の 5 件に対して B2 は 0 件、
  応答数は B の 14 件に対して B2 は 12 件（修復ぶんが無い）。字数は B の 3,042 字（目安内 2/3 章）
  に対して B2 は 3,311 字（3/3 章）。この差を **v1.1 の効果とは主張しない**。同一担い手が
  バッチ B で同じ指摘（history の契約、scene の新規 ID、最終章の短さ）を経験済みであり、
  プロンプト明記と担い手の学習は分離できない。H が示すのは「明記した条件で対象所見が
  出なかった」という記録までである。

## 限界

- **N=1**（本バッチ）。バッチ B（N=1）との 1 対 1 の記述的対照であり、効果量・再発率は主張しない。
- 同一担い手の学習という交絡がある。H が `target_findings_absent` でもプロンプトの効果とは言わない。
- canon が新規生成されるため、本文同士の比較にはならない。比べられるのは段ごとの所見・修復・L1 指標の出方まで。
- operator 応答では同一 seed の再現性（G5）を示せない。応答の独立性も保証されない。
- L2/L3 は `frozen_not_measured`。意味的整合や面白さは測っていない。

## 次にすること

1. 標本をさらに足す場合は B3 として走らせる前に登録する。同一担い手の学習という交絡を
   どう扱うか（条件として固定するか、別担い手を用意できるか）も登録事項にする。
2. 監査の `dead_character_reappears`（medium）は 2 バッチ連続で言及を拾っている。
   検査の意図（行為者としての再登場の検出）と実挙動（言及の検出）の切り分けが次の候補だが、
   変える場合はプロンプトか検査かを先に登録で決める。
