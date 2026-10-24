# 実験 2026-10-arena-replay-t02

- 実施: 2026-10-24T14:28:41Z
- 種別: **記録済み応答の offline replay**（新規生成ではない）
- 元実験: `2026-10-arena-fresh-s1-t02t03` / t02 × S1 × seed 0
- コード: `5908aecc0259c954f8d63e9f97cfbcc788a601f1`
- 集計: [`results.json`](results.json)
- 監査: [`replay-audit.json`](replay-audit.json)
- 手順: [`docs/replay.md`](../../docs/replay.md)

## 検証の問い

工程③のt02正式runについて、外部providerを呼ばず、source manifest・responses logを
SHA-256で固定したまま、同じ12応答を現在のS1配線へ再投入できるか。
また、request key・prompt全文・response hash・最終成果物が一致し、元runが変更されないことを
機械的に確認できるかを検証した。

## 条件とrun

| 項目 | 値 |
| --- | --- |
| 元run | `20261024T141921Z-t02-s1-s0-39192327` |
| replay run | `20261024T142841Z-t02-s1-s0-5e64bf29` |
| 元manifest SHA-256 | `19fa6546754d4cbf5e84985d29a9a97de1d0d93706df39d42cfd7b5b571d10f0` |
| 元responses SHA-256 | `3a316be4dda08b58bcac855e30f8675fe8d6b624cc5bf7ba41d2fa5b0c5870eb` |
| provider | `replay`（外部provider呼出し0） |
| source pin | CLIでmanifest・responsesの両方を指定 |

元runは新しい `responses_sha256` manifest欄の導入前に作られたため、
`responses_pinned_by_source_manifest=false` である。今回はCLIの両hash pinで固定し、
監査にも `manifest_pin_provided=true`・`responses_pin_provided=true` と記録した。

## 結果

| 検査 | 結果 |
| --- | ---: |
| replayセル / 失敗 | 1 / 0 |
| 消費した記録応答 | 12 / 12 |
| request key・prompt全文・prompt hashの一致 | 12 / 12 |
| 未消費・重複消費 | 0 |
| manifest `prompt_hashes` | 一致 |
| 最終成果物の一致 | 42 / 42 |
| replay前後の元manifest・responses hash | 不変 |
| response provenance | replay 12、fresh 0 |
| 文字数（マーカー除く） | 3,141（元runと一致） |
| 必須語率 | 1.0（元runと一致） |
| violations / high / CED / warnings | 0 / 0 / 0.0 / 0 |

plan・canon・design・draft・最終textはバイト一致だった。`audit.json` はrun固有の
canonパスと `generated_at` だけを比較から外し、その他の監査内容が一致した。
requestごとのsource request key・prompt/response hash、42成果物のsource/replay hashは
`replay-audit.json` に保存した。

## 故障検出の回帰test

`tests/test_replay.py` では、正常runに加えて次を検証した。

- design briefの初回失敗とrepairを含む13応答でも、`design-brief-a1` と
  `design-brief-repair-a2` を区別して全応答を再生できる。
- promptを変更したrequest、存在しないtaskのrequest keyを拒否する。
- manifestの `responses_sha256` と異なる応答logを拒否する。
- 応答が同じでも最終text成果物が異なればreplayを失敗にする。
- CLIがsource pin・replay provenance・G5非主張を結果へ残す。

実装commit時のCIは **394 passed, 3 warnings** だった。

## 限界

- これは**記録済みテキストの配線再現**であり、Arenaが同じ文章を再生成できる証拠ではない。
  G5のモデル再現性は引き続き未達として扱う。
- L1の数値が元runと一致したことは、作品品質・ジャンル適合・protocol-v1合格を意味しない。
- L2/L3の実証・較正・人間評定は凍結を継続し、実施していない。
- 1タスク・1セルのreplayである。t03は別実験として記録し、一般的な成功率は主張しない。
- `runs/` はGit管理外。監査JSONはcommitするが、再実行に必要な元応答本文と成果物は
  ワークスペース等に保持する必要がある。
- 元の正式実験、30作品の凍結対照群、protocol-v1、baselineは変更していない。

## 次の工程

工程⑤として、brief以外の7種の設計promptについて、正常形だけでなく欠落・型違い・
参照不整合・知識状態・開示/伏線順序などの契約testを追加する。L1の構造検査に限定し、
意味的な作品評価やL2/L3の再開は行わない。
