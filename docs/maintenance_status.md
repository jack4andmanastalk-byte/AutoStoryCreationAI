# 保守状況と旧ブランチの整理（2026-10-28）

> Arena.ai の GitHub 接続では、この環境から Issue のコメント更新が許可されなかった。
> **Issue の OPEN 表示だけでは最新状況を判断しない。** この文書と関連 PR を保守状況の
> 追記先とする。Issue は自動で閉じたものと見なさない。権限が使える環境で更新する場合も、
> 以下の未完項目と採否を区別する。

## 残作業

| 対象 | 完了・判明したこと | 未完・次の判断 |
| --- | --- | --- |
| [#57](https://github.com/jack4andmanastalk-byte/AutoStoryCreationAI/issues/57) / `9195f0c3` | [PR #59](https://github.com/jack4andmanastalk-byte/AutoStoryCreationAI/pull/59) で PDF 削除の安全性、R15・PDF の説明、doctor の回帰テストを統合。旧枝の doctor は不完全 index により偽陰性になり得る。旧枝の dataset 参照は plan prompt に伝わらない。詳細は [分解記録](branch_reconciliation_2026-10-28.md)。 | 旧枝の一括マージはしない。dataset の明示的な入力・権利・prompt・再開時の再現性を設計するまで接続を採用しない。skill registry は実需確認待ち（R-04）、index 差分検査は性能と正確性の検証待ち（R-05）。実験索引の独自差分も未確認。旧枝は保持。 |
| [#58](https://github.com/jack4andmanastalk-byte/AutoStoryCreationAI/issues/58) / 過去の dataset-refresh 失敗 | 失敗 job の一部は特定したがログ取得は EOF、根本原因は未確認。PR #59 で push / PR 起動を廃止し、公開を main に限定。 | 詳細ログなどの証拠が得られた場合に原因を切り分ける。main の月次・手動実行は引き続き共有データを公開する。データの取得・再公開はこの調査では実行しない。 |
| #58 / `f3ec8a91` | 先端 `fab7e5cf5c7039e7ed31365d5b20874acc1c8615` は、固定 canon・plan 不実行の事前登録（`preregistration.json` SHA-256 `ecaccfe468b7ca926ff5fe5171d07f3a6ffb87348961b796dc67482f97701b2f`）と回答待ち状態を持つ。main の同名実験は plan 実行を含む別条件・別登録（現在の登録 SHA-256 `d4784d1fbf539ac97852145233d1da9e4f256bd223377e6e83a900d4230624e9`）で完走済み。固定 canon での監査失敗と記録欠落を別途修正・回帰検査。 | 両者を同じ実験と見なしたり、main の事前登録・結果に上書きしたりしない。独自の未完実験記録と他の差分の保全・採否を確認するまで旧枝を保持。 |
| #58 / `7d70c8c2` | 先端 `a9715d1a94f048b22a11f86ef3ef61cb9ee60025` は Apple Books 検証と 201〜300 位の取得関連変更を含む。main の `1ae36d8` には同枝と同一の `media_verify.py`・`narou.py`・対応テストがあるが、workflow・データ生成手順はその後も大きく変わっている。 | 残る差分の機能・契約・公開への影響を比較する。部分一致だけで統合済みと判断しない。旧枝は保持。 |

## ブランチ整理の安全条件

- 対象と現在の先端 SHA を再確認し、独自コミットを機能・実験・履歴としてすべて採用、
  保全または明示的に不要と判断する。差分がテキスト上マージ可能というだけでは不十分。
- 必要な成果物が main または別の永続的な Git 管理場所にあること、同名の実験記録を
  上書きしないこと、他の人の進行中作業や open PR がないことを確認する。
- 削除する前に記録を main に統合する。直前にリモート先端を再確認し、変化したら中止。
  削除後は参照リンクが切れるため、名前・先端 SHA・統合先・判断をこの文書に残す。
- `datasets` は公開用の独立ブランチであり、旧作業枝の整理対象ではない。

### 整理候補: 保存・復元対策 `b843f5a4`

旧枝先端 `ced6b9432531be573a64dd1a2ee0dd0e1b9fa652` の独自 3 コミット
`1f7c7dd` / `f099065` / `ced6b94` は、`git cherry -v origin/main` で全て `-`
（同一パッチが main 側に存在）と確認。対応する main のコミットは
`a8142b9` / `d1303c0` / `f3f2d22`、[PR #56](https://github.com/jack4andmanastalk-byte/AutoStoryCreationAI/pull/56)
で統合済み。確認時点で旧枝を head とする PR はなかった。削除操作はこの記録の統合後、
リモート先端を再確認してから行う。削除できたかどうかはリモートのブランチ一覧で確認する。
