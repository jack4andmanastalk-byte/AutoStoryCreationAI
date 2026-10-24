# brief v1.1 のS1下流統合検査

## 目的と範囲

単独A/Bで初回通過した `design-brief` v1.1のbriefを、S1の残りの設計・初稿・監査へ接続し、新たな構造不良や修復なしに完走できるかを確認した。これは **運用者応答を統制したL1統合回帰検査**であり、新規のend-to-end生成試行、作品品質評価、L2/L3、人間評定ではない。

正式pilot `experiments/2026-10-arena-l1-t01/`、単独A/B `experiments/2026-10-arena-brief-v11/`、凍結対照群は変更していない。

## 条件と応答の由来

- タスク: `t01`、system: `s1`、seed: `0`、temperature: `0.8`
- baseline run: `20261024T130502Z-t01-s1-s0-6ab9f128`
- candidate run: `20261024T131956Z-t01-s1-s0-ad75f5a8`
- candidateのbriefは、単独A/Bでv1.1へ新規に作成して初回通過したものを使用した。
- planはbaselineの応答を再利用した。
- brief以外の7設計書と3章の初稿は、baselineで運用者が作成した応答を維持した。新しいbriefとの統合を検査するための統制再利用であり、新規の下流モデル応答ではない。
- candidateの全12 requestが回答済みで、operator pendingは0、対象runのmanifestは `ok` である。回答収集のための未回答停止は結果に含めない。

## 結果

| 指標 | v1.0 baseline | v1.1 candidate |
| --- | ---: | ---: |
| provider requests | 13 | 12 |
| design attempts合計 | 9 | 8 |
| brief attempts | 2 | 1 |
| design findings（最終） | 0 | 0 |
| design unresolved / missing | 0 / 0 | 0 / 0 |
| violations / high | 0 / 0 | 0 / 0 |
| checks skipped | 0 | 0 |
| CED / 1万字 | 0.0 | 0.0 |
| must_include_rate | 1.0 | 1.0 |
| warnings / injected markers | 0 / 0 | 0 / 0 |
| 本文文字数 | 3,263 | 3,263 |

candidateでは全8設計書が1 attemptで通過し、S1が完走した。requestとdesign attemptの1件減は、単独A/Bで確認したbrief修復の除去と一致する。

## 統制条件の確認

- canonのJSONは両runで一致した。
- brief以外の7設計書は両runでバイト一致した。
- candidateのbriefは単独A/Bのbriefとバイト一致した。
- 初稿応答を再利用したため、最終3章も両runでバイト一致した。結合本文のSHA-256は `8f630f787125b8b41695ee5d3f9dd1407ec1f61a3b5d31720862e9a9b04e0963` である。

したがって、本文が同じであることはプロンプトの効果がないという証拠ではなく、初稿応答を統制した結果である。

## 解釈と限界

この統合条件では、v1.1 briefの接続によって新たな構造検査不合格・未解決設計・追加修復は観測されなかった。一方、N=1で下流応答を再利用しているため、新規生成時の下流挙動、一般的な修復削減率、再現性は推定できない。

本記録はL1の探索的参考結果である。作品品質・ジャンル適合・人間評価・protocol-v1の品質合格は主張しない。L2/L3の実証・較正・人間評定は凍結したままで、Arenaのmodel versionが `unversioned-2026-10-24` のためG5未達も変わらない。
