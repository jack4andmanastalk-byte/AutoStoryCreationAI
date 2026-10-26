# 検査の検出力: 既知の誤りを注入して、何が発火するか — t01

- 日付: 2026-10-26
- 種類: **決定論的な検出力の測定**。新しい本文は生成しない（既存 2 腕の本文に誤りを注入するだけ）。
- 位置づけ: [`../2026-10-l1-pair-t01/note.md`](../2026-10-l1-pair-t01/note.md) の「次に試すこと」2 番目。
  仕様は [`docs/two_stage_slice.md`](../../docs/two_stage_slice.md) §17。
- 結果: [`results.json`](results.json)（`schema: detection-power-v1`）

## 問い

二段階方式の検査（`check_rewrite`）は、`clean` を返したときに「誤りが無いこと」を保証しない。
では**どの誤りなら捕まえられるのか**。分かっている誤りを 1 つずつ注入し、どの検査が発火するかを見る。
同じ注入を、ログを見せずに書いた本文（直接生成）にも当て、条件の違いが検出力にどう出るかを比べる。

## 入力

| 腕 | 本文 | ログを見たか |
| --- | --- | --- |
| log-backed | `2026-10-stageb-v11-t01/relay/` の 3 章（v1.1 の出力、`clean`） | 見ている（契約下で執筆） |
| direct | `2026-10-l1-pair-t01/relay/` の 3 章（S1 draft、`pass`） | 見ていない |

- 参照するログ・canon・設計は `2026-10-stageb-v11-t01/inputs/` のもの（両腕とも同じ t01）。
- 直接生成の腕にログ依存の検査を当てるのは**反実仮想**である（その本文は契約を守るよう要求されて
  いない）。「もしログを要求していたら、どの誤りを捕まえられたか」を測るために置いている。
- `marker_sequence` は表から外す。直接生成の腕は導出マーカー列を要求されていないため、
  ベースラインで必ず落ち、内容の所見を覆い隠す。落ちること自体は別に記録する。

## 注入した誤り

| ID | 章 | 内容 |
| --- | --- | --- |
| `wrong_day_since` | ch03 | 「六日ぶり」→「四日ぶり」（離れてからの日数を誤る） |
| `dead_acts_now` | ch01 | 死者が現在時に行動する一文を足す |
| `withheld_term` | ch02 | この章で保留の事実 F-04 の語「三年前」を足す |
| `offlog_place` | ch01 | ログにない場所と船旅を足す |
| `unquantified_number` | ch02 | ログが宣言しない数量「半日」を足す |

## 結果

```bash
.venv/bin/python scripts/probe_detection_power.py \
  --game-log experiments/2026-10-stageb-v11-t01/inputs/game_log.json \
  --canon experiments/2026-10-stageb-v11-t01/inputs/canon \
  --design-dir experiments/2026-10-stageb-v11-t01/inputs/design \
  --arm log-backed=experiments/2026-10-stageb-v11-t01/relay/responses \
  --arm direct=experiments/2026-10-l1-pair-t01/relay/responses \
  --out experiments/2026-10-detect-power-t01/results.json
```

| 注入 | log-backed | direct |
| --- | --- | --- |
| `wrong_day_since` | `timeline_consistency`（`medium`） | `timeline_consistency`（`medium`） |
| `dead_acts_now` | `character_boundary`（`high`） | `character_boundary`（`high`） |
| `withheld_term` | `fact_boundary`（`medium`） | **発火せず**（ベースラインで既に発火していた） |
| `offlog_place` | 発火せず | 発火せず |
| `unquantified_number` | 発火せず | 発火せず |

ベースライン（注入前）の所見:

| 腕 | ch01 | ch02 | ch03 | `marker_sequence` |
| --- | --- | --- | --- | --- |
| log-backed | 0 | 0 | 0 | 通る |
| direct | `fact_boundary` 1（「三年前」） | `fact_boundary` 1（「三年前」） | `character_boundary` 1（ボリス） | 3 章とも落ちる |

## 読み取れること

1. **日数・死者の現在時行動・保留事実の語彙は、どちらの本文でも捕まえられる。** 3 種の注入は
   腕によらず同じ検査が発火した（`timeline_consistency` / `character_boundary` / `fact_boundary`）。
   これらは語彙と宣言の照合で決まるので、本文がどう作られたかに依存しない。
2. **直接生成の本文は、ログ契約を当てると既に 3 件の所見を持つ。** 「三年前」（F-04 の語）が ch01 と
   ch02 に早出しされ、ch03 では `present_characters` にいないボリス（鍵屋）に言及している。
   どれも `medium` で、決して検出できない類のものではない。**検査が走っていないので通っていた**。
   これは [`../2026-10-l1-pair-t01/note.md`](../2026-10-l1-pair-t01/note.md) の「差は指標ではなく
   検査可能性にある」という結論の、具体的な中身である。
3. **ログにない場所・移動と、宣言のない数量は、どちらの腕でも検出できない。**
   `offlog_place` と `unquantified_number` は 2 腕とも発火 0。既存の §13.1 M-2〜M-4
   （ログにない細部・数値）と同じ穴で、今回の追加（時系列の照合）でも塞がっていない。
   ここを塞ぐには、本文の場所名・数量を抽出してログと突き合わせる別の検査が要る（未実装）。

## 限界

- 腕ごとに 1 本文、注入ごとに 1 箇所。**発火しなかったことは、その検査の盲点の証明ではない**
  （この本文・この言い回しで捕まらなかった、という記録）。
- 直接生成の腕への適用は反実仮想であり、「この本文が不合格になるべきだった」という判定ではない。
  同じ本文を契約下で書けば、書き手は語彙を避けた可能性がある。
- 注入は手で書いた 5 種類で、試走で観測した誤り（M-1〜M-4）と既知の語彙境界から選んでいる。
  体系的な変異テスト（語彙の全走査・言い換えの網羅）ではない。
- `marker_sequence` を外した比較なので、マーカー列の一致・不一致そのものの検出力は測っていない
  （それは `scripts/probe_gamelog_contracts.py` の B 系が扱う）。
- L1 のみ。L2/L3 は `frozen_not_measured`、G5 は未達。protocol-v1 の系・指標・閾値は変えていない。

## 次に試すこと

1. 検出できなかった 2 種（ログ外の場所・移動、宣言のない数量）に対する検査の設計。場所名は canon の
   語彙で拾えるが、数量は語彙では拾えない。**L1 のまま増やせるか、L2 相当になるかを先に切り分ける。**
2. 注入の種類を増やし、同じ腕で反復する（1 本文 1 注入では、検出力と偶然を分離できない）。
3. S1 全体（plan → 8 設計 → draft）との比較。
