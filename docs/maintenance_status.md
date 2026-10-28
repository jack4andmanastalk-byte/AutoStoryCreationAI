# 保守状況と旧ブランチの整理（2026-10-29 更新）

> Arena.ai の GitHub 接続では、この環境から Issue のコメント更新が許可されなかった。
> **Issue の OPEN 表示だけでは最新状況を判断しない。** この文書と関連 PR を保守状況の
> 追記先とする。Issue は自動で閉じたものと見なさない。権限が使える環境で更新する場合も、
> 以下の未完項目と採否を区別する。

## 公開本文の削除完了（2026-10-29）

ユーザーの明示的な指示（なろう本文・青空本文を含む著作権上問題になるファイル類を削除、
書誌・ランキング等のメタデータのみを保持して URL から再取得できる状態を維持、
公開ワークフロー削除、`datasets` 分岐削除）に基づき実施した。削除直前にリモート先端・
Release 資産一覧を再確認したうえでの操作である。**本節が最新**。下の 2026-10-28 節の
「残っている」「変更していない」は当時の記録。

| 対象 | 実施 | 検証 |
| --- | --- | --- |
| Release `datasets-narou-commercialized` の青空本文 `aozora_texts.tar.gz`（asset id `672208519`、133,878 B） | GitHub API で削除 | 削除後の資産一覧に不在。残資産は12件（`manifest.json`、なろう書誌 JSONL 6件、ランキング MD 5件）でメタデータのみ |
| なろう本文圧縮ファイル4件（`narou_rank_*_texts.tar.gz` 等） | 2026-10-28 に削除（下節） | 同上の資産一覧で不在 |
| `datasets` 分岐（先端 `5a9f9f1861d2da85b59faac41a75dec73a794043`。`raw/narou/texts` 373件・`raw/aozora/texts` 15件・書誌 JSONL・ランキング MD） | 参照ごと GitHub API で削除 | `git ls-remote --heads` に不在。main・旧 arena 2枝・タグ `datasets-narou-commercialized`（本文なし）には本文なしを確認 |
| `.github/workflows/dataset-refresh.yml` | 本記録を含む PR で削除 | `tests/test_ci_workflows.py` がファイル不在と全ワークフローにスケジュール実行が無いことを検査 |
| `samples/texts/` の青空本文サンプル4件（`058013.txt` / `058136.txt` / `059115.txt` / `059877.txt`、旧 PDF 由来） | 同上 | main ヘッドに不在（履歴残存は下記） |

**保持したもの（メタデータ）:** Release の12資産（`text_url` 等により配信元 URL から本文を
再取得できる情報を含む書誌・ランキング）、`docs/narou_*_ranking.md`、
`data/datasets/manifest.json`、`samples/` の書誌 JSONL、main の `make pull-datasets` は
Release のメタデータ取得に切替済み。

**未完了・実行権限が無くて届かなかったもの:**

| 対象 | 状態 | 次の手 |
| --- | --- | --- |
| Actions artifacts 243件（`narou-shard-*` / `prepared-bundle`。作成は 2026-10-22〜27 の `dataset-refresh` 実行分で、本文を含み得る） | 削除 API・保持期間変更ともに 403（現环境の連携トークンに Actions 書き込み／管理権限が無い） | 権限付きトークンまたは Web UI（Settings → Actions → Artifacts and logs）で削除。既定保持（90日）なら 2027-01-20 頃から自動失効見込み。API での一括削除例: `gh api "repos/<owner>/<repo>/actions/artifacts?per_page=100" --paginate --jq '.artifacts[].id' \| while read id; do gh api -X DELETE "repos/<owner>/<repo>/actions/artifacts/$id"; done` |
| 「Debug Narou downloads」ワークフロー登録の disable | 403。ファイルは現存するどのブランチにも無く（`debug-narou.yml` 不在を確認）、最後の実行は 2026-10-22 | 起動経路は無し。登録の削除は権限のある環境で |

**削除の限界（記録）:** `samples/texts/` は main のヘッドから削除したが、**過去コミットの
履歴には blob が残る**（例: `f155b98`）。完全除去には main の履歴書き換えが必要で、
参照切れ・再 clone への影響が伴うため今回実施していない（要別途明示的承認）。`datasets`
分岐は参照ごと削除したが、Git バックエンドのオブジェクト除去・キャッシュ・第三者の複製の
消去は保証できない。本文の再取得・独立ハッシュ計算は行っていない（メタデータのみ保持の
方針に変更されたため、4圧縮ファイルの網羅性検証は対象外）。非公開保管先へはこの環境から
アクセスできず（可視リポジトリは公開2件のみ）、保管先側の実物検証は未実施のまま。

## 公開データと非公開研究の設計（2026-10-28）

作品本文の再配布許諾は未確認。設計作成時には、ユーザーの選択により
[設計・注意書き](private_research_design.md) のみを追加し、公開物等は変更しなかった。

その後、ユーザーが `dataset-refresh` を GitHub 上で手動停止し、確認時の状態は
`disabled_manually`。workflow のコードは変更されておらず、再有効化すれば再公開し得る。
ユーザーから非公開側 Release の4つのなろう本文圧縮ファイルについて、公開側とサイズ・
GitHub メタデータの SHA-256 が一致するとの確認を受け、明示的な承認のもと公開 Release の
該当4資産のみを削除し、不在を確認した。本文の再取得・独立ハッシュ計算は行っていない。

公開 `datasets` ブランチ（確認時 `5a9f9f1861d2da85b59faac41a75dec73a794043`）と
Actions 成果物は変更していない。`raw/narou/texts` には確認時373件があり、期限付きの
shard artifact にも本文が含まれる。4圧縮ファイルがそれら全件を網羅するか未検証。
公開 Release の他資産・青空本文も残る。削除後も第三者のコピーの消去は保証できない。
今後の対応は権利、保全範囲・復元先、公開範囲と影響を確認して別途判断する。

## 残作業

| 対象 | 完了・判明したこと | 未完・次の判断 |
| --- | --- | --- |
| [#57](https://github.com/jack4andmanastalk-byte/AutoStoryCreationAI/issues/57) / `9195f0c3` | [PR #59](https://github.com/jack4andmanastalk-byte/AutoStoryCreationAI/pull/59) で PDF 削除の安全性、R15・PDF の説明、doctor の回帰テストを統合。旧枝の doctor は不完全 index により偽陰性になり得る。旧枝の dataset 参照は plan prompt に伝わらない。詳細は [分解記録](branch_reconciliation_2026-10-28.md)。 | 旧枝の一括マージはしない。dataset の明示的な入力・権利・prompt・再開時の再現性を設計するまで接続を採用しない。skill registry は実需と関係の契約確認待ち（R-04）、index 差分検査は性能と正確性の検証待ち（R-05）。旧索引の比較を終え、現行の [実験索引](../experiments/INDEX.md) を追加。旧枝は保持。 |
| [#58](https://github.com/jack4andmanastalk-byte/AutoStoryCreationAI/issues/58) / 過去の dataset-refresh 失敗 | 失敗 job の一部は特定したがログ取得は EOF、根本原因は未確認。PR #59 で push / PR 起動を廃止し、公開を main に限定。 | 詳細ログなどの証拠が得られた場合に原因を切り分ける。workflow は GitHub 上で手動停止中。再有効化すると main の月次・手動実行で共有データを再公開し得る。 |
| #58 / `f3ec8a91` | 先端 `fab7e5cf5c7039e7ed31365d5b20874acc1c8615` は、固定 canon・plan 不実行の事前登録（`preregistration.json` SHA-256 `ecaccfe468b7ca926ff5fe5171d07f3a6ffb87348961b796dc67482f97701b2f`）と回答待ち状態を持つ。main の同名実験は plan 実行を含む別条件・別登録（現在の登録 SHA-256 `d4784d1fbf539ac97852145233d1da9e4f256bd223377e6e83a900d4230624e9`）で完走済み。固定 canon での監査失敗と記録欠落を別途修正・回帰検査。旧先端の全21ファイル差分を[履歴資料](../experiments/archives/legacy-fixed-canon-b-2026-10-27/README.md)に保全し、親からの再構成・バイト一致を確認。 | 両者を同じ実験と見なしたり、main の事前登録・結果に上書きしたりしない。旧実験は未完・未再開であり、今後の扱いを判断するまで旧枝は保持。 |
| #58 / `7d70c8c2` | 先端 `a9715d1a94f048b22a11f86ef3ef61cb9ee60025` の7ファイルを機能別に比較し、主機能は main 側にあり、旧 PDF 公開フローは戻さないと判断。詳細は下記。2026-10-28 にリモート一覧から旧枝が見えなくなったことを確認（本作業で削除しておらず、理由・日時は未確認）。 | 旧コミット自体は確認時に GitHub API で参照できた。公開物の権利とデータ取得の正常性は未確認。 |

## ブランチ整理の安全条件

- 対象と現在の先端 SHA を再確認し、独自コミットを機能・実験・履歴としてすべて採用、
  保全または明示的に不要と判断する。差分がテキスト上マージ可能というだけでは不十分。
- 必要な成果物が main または別の永続的な Git 管理場所にあること、同名の実験記録を
  上書きしないこと、他の人の進行中作業や open PR がないことを確認する。
- 削除する前に記録を main に統合する。直前にリモート先端を再確認し、変化したら中止。
  削除後は参照リンクが切れるため、名前・先端 SHA・統合先・判断をこの文書に残す。
- `datasets` は公開用の独立ブランチであり、旧作業枝の整理対象ではない。

### 整理済み: 保存・復元対策 `b843f5a4`

旧枝先端 `ced6b9432531be573a64dd1a2ee0dd0e1b9fa652` の独自 3 コミット
`1f7c7dd` / `f099065` / `ced6b94` は、`git cherry -v origin/main` で全て `-`
（同一パッチが main 側に存在）と確認。対応する main のコミットは
`a8142b9` / `d1303c0` / `f3f2d22`、[PR #56](https://github.com/jack4andmanastalk-byte/AutoStoryCreationAI/pull/56)
で統合済み。確認時点で旧枝を head とする open PR はなかった。この記録を
[PR #60](https://github.com/jack4andmanastalk-byte/AutoStoryCreationAI/pull/60) で統合し、
リモート先端が上記 SHA のままであることを再確認した後、2026-10-28 に旧枝を削除。
`git ls-remote --heads` で旧枝が存在しないことを確認した。他の未評価枝は保持する。

### `7d70c8c2` の追加比較（2026-10-28）

共通祖先 `4ed2ec9` から先端 `a9715d1` までの独自差分は 1 コミット・7 ファイル。
以下は Git の差分比較であり、データ取得や公開の実行結果ではない。

| 範囲 | 旧枝の内容 | 現行側の確認と判断 |
| --- | --- | --- |
| `media_verify.py` / `narou.py` / `test_media_verify.py` | Apple Books の照合、ランキング評価、取得件数制御、テスト | main にある `1ae36d8` と旧枝先端では3ファイルがバイト一致。その後も main で維持・変更されている。旧枝を丸ごと適用する必要はない。 |
| `configs/dataset.yaml` | 既定取得数 300 と Apple Books の説明 | `1ae36d8` の同ファイルとバイト一致。現行でも取得数 300。 |
| `setup_dataset.py` | 100件単位のスライス、検証済み情報の再利用、scan 範囲と CLI 既定値 | `1ae36d8` に同機能があり、後続で再利用等が発展。旧枝を適用すると現行の変更を戻すため採用しない。検証済みフラグの再利用は作品の再配布許諾確認とは異なる。 |
| `Makefile` | 取得ページ数増加、上位300件・PDF 生成 | `1ae36d8` に同じ data コマンドが存在。現行の通常経路はテキスト中心に変更済み。旧枝の PDF 強制生成へ戻さない。 |
| `dataset-refresh.yml` | 300件化、過去の検証・PDFを再利用、公開分割、PDF Release の更新 | 300件化・分割等は後続側で発展。現行ではテキスト中心、公開のタイミング・キャンセル制御も異なる。旧枝の PDF 公開と公開上書きロジックは採用しない。本文公開の許諾は別途未確認（[設計・注意書き](private_research_design.md)）。 |

この比較は旧枝に現行側と異なる振る舞いがないこと、公開済みデータの権利、または
データ取得の正常性を保証しない。枝の削除や公開物の変更はこの比較時には行っていない。
その後のリモート一覧確認では、旧枝は既に存在しなかった。
