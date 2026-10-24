# briefプロンプト v1.1 の単独A/B記録

## 目的と範囲

正式pilotでbriefだけに必要だった修復が、`design-brief` v1.1への変更後に減るかを、同じタスク・canon・seedで確認した。比較は **L1の構造検査と修復回数だけ**であり、本文生成・作品品質・ジャンル適合・L2/L3・人間評定は対象外である。正式pilotの記録と凍結対照群は変更していない。

## 変更

- `elements` の who / where / wants / obstacle に書いた文字列を、言い換えず一字一句そのままloglineへ含めるよう明示した。
- 類似作の `axis` を `structure / character / world` に限定し、differenceを10字以上にするよう明示した。
- 同じ条件をJSON schemaの説明にも記載し、テンプレートversionを1.0から1.1へ上げた。
- 実際にproviderへ渡るpromptとreportのversionを検査する回帰テストを追加した。

## 条件と手順

- タスク: `t01`、system: `s1`、seed: `0`、temperature: `0.8`、最大attempt: `2`
- 両条件とも同じplan canonを使用した。
- baseline: 正式pilotのS1 run `20261024T130502Z-t01-s1-s0-6ab9f128`
- candidate: `20261024T131059Z-t01-s1-s0-ae23abef`
- candidateには、変更後のrequestへ新規に作ったbriefを1回投入した。baselineの修復済みbriefを使い回して初回成功に見せることはしていない。
- candidateはbriefだけを実行し、他の設計書と本文stageは実行していない。
- 回答収集のための未回答停止は実験結果に含めない。比較したcandidate runのmanifestは `ok` である。

## 結果

| 指標 | v1.0 baseline | v1.1 candidate |
| --- | ---: | ---: |
| brief attempts | 2 | 1 |
| briefへのprovider request数 | 2 | 1 |
| 初回のmedium findings | 6 | 0 |
| 初回の `logline_elements` 指摘 | 3 | 0 |
| 初回の `similar_grounded` 指摘 | 3 | 0 |
| 最終status | clean（repair後） | clean（初回） |

v1.0の初回指摘は、loglineへ現れない要素3件と許可値外の類似作axis 3件だった。v1.1では新規応答が初回で構造検査を通過し、このprobeでは修復1回・request 1件の削減となった。

## 解釈と限界

今回の1件では、今回の構造指摘を対象としたプロンプト改善が機能した。ただし、candidateの新規応答はN=1であり、一般的な遵守率・成功率・再現性は推定できない。他の設計書と本文を再実行していないため、下流への効果もまだ示していない。

これは機械的な構造適合の確認であり、作品品質やジャンル適合の改善ではない。L2/L3の実証・較正・人間評定は凍結したままである。Arenaのmodel versionは `unversioned-2026-10-24` であり、G5未達も変わらない。protocol-v1の品質合格とは記録しない。
