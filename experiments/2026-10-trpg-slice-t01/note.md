# 二段階方式・最初の縦割り（Phase 1〜2）配線確認 — t01 / scripted / seed 0

- 日付: 2026-10-26
- 種類: **固定台本（scripted）による配線・回帰確認**。実モデルの応答は 1 件も無い。
- 設計: [`research/curation/two_stage_trpg_rewrite_direction_2026-10-26.md`](../../research/curation/two_stage_trpg_rewrite_direction_2026-10-26.md) §3 / [`docs/two_stage_slice.md`](../../docs/two_stage_slice.md)
- 決定論的要約: [`results.json`](results.json)

## 目的

Stage A（構造化ゲームログ生成 ＋ 決定論的検査）→ Stage B（検証済みログ ＋ `voice.json` による小説化リライト）という 2 段の配線が、既存の canon・設計書・マーカー文法・L1 監査と矛盾なく動くことを確認する。**「読める物語になるか」「面白いか」は測定していない。**

## バンドルの中身

```text
inputs/canon/          6 チャネル（死者 johan を含む）
inputs/design/         plot.json / scene.json / voice.json と実検査器の report
inputs/game_log.json   Stage A の固定台本応答（検証済み・3 章 3 場面）
inputs/rewrite/        Stage B の固定台本応答（ch01〜ch03）
scripted.json          上を $file で参照する固定台本（応答本文の二重管理なし）
results.json           実行に依存しない決定論的要約（コミット用）
note.md                本文書
bundle/                実行時に生成される run 出力（discard 可能・コミットしない）
```

`bundle/` は `scripts/run_twostage.py --out .../bundle` でいつでも作り直せる。生の run 出力（`responses.jsonl`、`text/`、`manifest.json`）はリポジトリの実験規約に従ってコミットしない。将来 Arena リレーを行う場合は、このバンドル内の `relay/` に応答を置き、`state.json` の `resume_command` で `--resume` する。gitignored な `runs/` / `build/` には依存しない。

## 実行方法

```bash
.venv/bin/python scripts/run_twostage.py --task t01 \
  --canon experiments/2026-10-trpg-slice-t01/inputs/canon \
  --design-dir experiments/2026-10-trpg-slice-t01/inputs/design \
  --provider scripted \
  --script experiments/2026-10-trpg-slice-t01/scripted.json \
  --out experiments/2026-10-trpg-slice-t01/bundle \
  --run-id scripted-t01-s0 \
  --results experiments/2026-10-trpg-slice-t01/results.json --report-only --quiet
```

同じ結果は `tests/test_twostage_pipeline.py` が毎回 `tmp_path` 上で再現し、2 回実行のバイト一致・修復ラウンド・fail-closed・resume を検証している。

## 結果（固定台本・1 条件）

| 項目 | 値 |
| --- | --- |
| Stage A | `clean` / 3 章・3 場面 / 8 検査すべて実行・0 所見 / 修復 0 回 |
| 確定マーカー | 19 件（`time` 3, `location` 3, `learn` 4, `use` 3, `foreshadow` 6） |
| 死者 `johan` の許容された言及 | 4 件（`record_reference` 3, `memory_mention` 1。媒体: 潮札 / 石膏手形 / 回想） |
| 死者 `johan` の現在時行動 | 0 件（`present_characters` / `action` / `dialogue` のいずれにも現れない） |
| Stage B | 3 章すべて `clean`。本文のマーカー列が導出列と完全一致。修復 0 回 |
| 既存 continuity-ledger | 6 検査すべて実行。違反 3 件はすべて `dead_character_reappears`（`name_mention`, `medium`）。`high` は 0 件 |

`dead_character_reappears` の 3 件は、`ヨハン` という名前が回想・遺物の文に現れることを既存の文字列監査が検知したものである。[`2026-10-plot-ablation-t01`](../2026-10-plot-ablation-t01/paired/note.md) で報告されたのと同じ既知の誤検出類型であり、本スライスの Stage B 検査は同じ箇所を「宣言済みの `record_reference` / `memory_mention`」として区別する。**この差を L1 の改善・効果として主張しない。** 台本は最初から整合するよう書かれており、比較対象の直接生成（S1）も実モデル応答も存在しない。

## 評価範囲と非主張

- protocol-v1 の凍結範囲を変更しない。Arena × L1 の探索的枠組みの内側で、構造・衛生の検査だけを扱う。
- `results.json` に `active_layers: [L1]`、`frozen_layers: [L2, L3]`、`G3/G4: frozen_not_measured` を記録している。
- L1 の構造検査は物語の質・面白さ・読者選好の証拠ではない。L2/L3 は `frozen_not_measured` のまま。
- 実モデルの応答、Arena リレー、L1 ペア比較（Phase 3）は**未実施**。応答・スコア・効果は一切捏造していない。
- 版を固定できない Arena 経路では G5 を主張しない。

## 既知の限界

- 1 章 1 場面・章内移動なしの最小スライス。分岐・ダイス・物語途中の死亡、1 章複数場面の語り直しは未対応。
- Stage B は前章本文を入力に受け取らない（事実の根拠を `game_log.json` に限定するため）。直接生成 S1 は前章本文を受け取るので、Phase 3 の比較では入力差を条件として明示する必要がある。
- 知識境界の語彙検査は部分文字列一致の手掛かりであり、文脈上の妥当性や比喩表現までは判定できない。
- 固定台本の本文は各章約 300 字で、タスクの標準的な章長（1,000〜1,400 字）を満たさない。長さゲートは配線確認の対象外。
