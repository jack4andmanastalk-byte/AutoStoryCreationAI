# 実験 2026-10-arena-replay-t03

- 実施: 2026-10-24T14:28:41Z
- 種別: **記録済み応答の offline replay**（新規生成ではない）
- 元実験: `2026-10-arena-fresh-s1-t02t03` / t03 × S1 × seed 0
- コード: `5908aecc0259c954f8d63e9f97cfbcc788a601f1`
- 集計: [`results.json`](results.json)
- 監査: [`replay-audit.json`](replay-audit.json)
- 手順: [`docs/replay.md`](../../docs/replay.md)

## 検証の問い

工程③のt03正式runについて、t02と同じreplay実装が別タスクのplan・8設計・3章を
外部providerなしで再実行できるかを確認した。source pin、request key、prompt全文、
response hash、全応答の消費、成果物一致、元runの保全をt02と同じ方法で検査した。

## 条件とrun

| 項目 | 値 |
| --- | --- |
| 元run | `20261024T141921Z-t03-s1-s0-cab323d1` |
| replay run | `20261024T142841Z-t03-s1-s0-70bd2e9a` |
| 元manifest SHA-256 | `1e2e76c265293a6e84c01cdfff131addb046c90b3718c3132c28efa733c2e1ee` |
| 元responses SHA-256 | `4b74bb22cd19b6d7f99ebb92ea79f6cf7cb94138bbb51bc730907d9229e18db7` |
| provider | `replay`（外部provider呼出し0） |
| source pin | CLIでmanifest・responsesの両方を指定 |

元runのmanifestには応答log hash欄が無かったため、CLIで両方のhashを明示した。
監査には `responses_pinned_by_source_manifest=false` と、CLI pinが有効だったことを
分けて記録している。

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
| 文字数（マーカー除く） | 3,161（元runと一致） |
| 必須語率 | 1.0（元runと一致） |
| violations / high / CED / warnings | 0 / 0 / 0.0 / 0 |

t02に続き、別タスクでも同じ12応答と42成果物の一致を確認できた。
これはreplay機能が特定のrequest key集合に固定されていないことの配線上の確認である。
request・artifactの完全なhash一覧は `replay-audit.json` に保存した。

## 限界

- 記録済み応答の一致は、モデルの独立した再生成能力やG5を示さない。
- 2タスクで replay が動いたことから、任意のrun・将来のprompt変更も再現できるとは一般化しない。
  promptが変わればreplayは意図どおり失敗する。
- L1の一致は作品品質・ジャンル適合・protocol-v1合格の証拠ではない。
- L2/L3の実証・較正・人間評定は凍結を継続し、実施していない。
- `runs/` はGit管理外のため、監査JSONとは別に元runの本文・応答・成果物の保管が必要である。
- 元の正式実験、30作品の凍結対照群、protocol-v1、baselineは変更していない。

## 次の工程

工程⑤の設計prompt契約testを追加し、replayの通常CIと合わせて全testを実行する。
構造上の不整合を検出するtestに限定し、L2/L3や人間による品質評定は行わない。
