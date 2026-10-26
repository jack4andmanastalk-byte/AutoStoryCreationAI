# 観測モード: 候補検査を「見るだけ」で走らせる — t01

- 日付: 2026-10-26
- 種類: **実装＋非干渉の測定**（候補検査は依然として契約の外）
- 前提: [`../2026-10-surface-checks-t02/note.md`](../2026-10-surface-checks-t02/note.md)
  （t02 の結論: 「未宣言の canon 地名」の枝は章の外の移動を偽陽性にするので、事例を集めるまで採らない）
- 仕様: [`docs/two_stage_slice.md`](../../docs/two_stage_slice.md) §20
- 結果: [`results.json`](results.json)（`schema: surface-observe-v1`）

## 問い

t02 で「次に集めるべきは『canon にあるが、この章で宣言されていない地名』の偽陽性の事例」と
決めた。だが事例は**実際の走りから**採るしかない。走りを回すたびに候補検査の結果も残るように
できないか。そして、残すことで**契約（合否・修復）が動いてしまわないか**。

## 作ったもの

- `check_rewrite(..., observe_surface=True)`: 報告に `observations` と `observation_summary` を足す。
  **既定は無効**で、無効ならキー自体が存在しない（既存の記録は 1 バイトも変わらない）。
- `scripts/run_twostage.py --observe-surface`: 上のフラグを走りに通す。`state.json` の config にも残す
  （ただし `CONFIG_COMPARE` には入れていない — 観測は結果を左右しないので、`--resume` の
  同一性条件に加えると、古い走りを不当に再開不能にしてしまう）。
- `render_markdown`: 観測があれば「観測（契約外・判定に使わない）」の節に出す。

観測は `findings` に**入れない**。したがって `summary` の件数・重大度・`status`・修復判定の
どれにも触れない。加えて `place_findings` の各項目に `blocks_repair: False` を明記した
（t01/t02 では `advisory: True` だけだった）。既存の `needs_repair` は
「`REPAIR_SEVERITIES` かつ `blocks_repair` が真」で判定するので、**万一 `findings` に混ぜても
修復を起こさない**。この穴は、下のテストを書いたときに実際に見つかった。

## 測定

同じ scripted バンドルを 2 回走らせた（`observe-off/run`、`observe-on/run`、本文は同一）。

| 章 | 契約側の一致 | status | findings | observations（off → on） |
| --- | --- | --- | --- | --- |
| ch01 | 一致 | clean | 0 | 無し → 0 |
| ch02 | 一致 | clean | 0 | 無し → 0 |
| ch03 | 一致 | clean | 0 | 無し → 0 |

`status`・`findings`・`checks` は 2 つの走りで同一。`observations` はオンの走りにだけ存在する。

次に、ch01 の本文へログ外の旅を注入して、その場で両方を回した。

| 腕 | status | findings | 観測した目的地 |
| --- | --- | --- | --- |
| フラグ無し | clean | 0 | —（キー無し） |
| `--observe-surface` | clean | 0 | `対岸の島` 1 件 |

**注入しても status は `clean` のまま**で、所見は 0。観測だけが 1 件増える。これが観測モードの
意味である（もし所見に混ぜていれば、medium は `REPAIR_SEVERITIES` なので修復が走っていた）。

## 分かったこと

- 観測モードは**契約を動かさずに**事例を残せる。実走りで `--observe-surface` を付ければ、
  偽陽性の候補が走りの記録に溜まる。
- 観測を「findings に混ぜるだけ」で済ませると**修復が走る**。`blocks_repair: False` の明記は
  飾りではなく、この経路を塞ぐためのもの。t02 までの実装は `advisory` フラグしか持っていなかった。

## 限界

- 測ったのは **scripted の本文**であり、実モデルの文章ではない。ここで確かめたのは配線と非干渉で、
  実本文でどんな事例が溜まるかはまだ分からない。
- 観測は事例を集めるだけで、**率を測らない**。溜まった事例は人が読む必要がある。
- 候補検査は依然として契約の外（severity は `medium` だが blocking でない・修復プロンプトに入らない）。
- L1 のみ。L2/L3 は `frozen_not_measured`、G5 は未達、protocol-v1 の系・指標・閾値は不変。

## 次に試すこと

1. 実走りで `--observe-surface` を付け、溜まった観測（特に「未宣言の canon 地名」）を読む。
2. 読んだ結果を t02 の事例表に足して、また測る。
3. S1 全体（plan → 8 設計 → draft）との比較。
