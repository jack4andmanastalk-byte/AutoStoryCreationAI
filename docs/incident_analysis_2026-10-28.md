# 直近の作業・パイプライン障害調査（2026-10-28 UTC）

## 範囲と結論

調査対象は main の `ea1bcfc`、GitHub Actions の直近の実行、および未マージの `arena/9195f0c3-autostorycreationai` の失敗時点。ユーザーが意図した障害の特定情報は未提供のため、以下は確認できた事象の整理であり、すべてが同一の障害とは限らない。コード修正・再実行・公開操作は行っていない。

| 優先度 | 事象 | 状態・原因の確度 |
| --- | --- | --- |
| P0 | Stage A 実走の途中で `--resume` が失敗 | 実験記録に環境スナップショット対象外の `out/` に状態を置いたことによる中断が2回記録されている。応答は保存され、リプレイで完了 |
| P0 | 別ブランチの `research-check` 失敗 | 失敗コミットの再現で 5 テスト失敗。`add-child` の引数欠落と PDF 設定削除後のテスト不整合を確認。main とは別系統 |
| P1 | 別ブランチの `dataset-refresh` 失敗 | 全20 shard が取得ステップで失敗し publish も失敗。失敗ログにアクセスできず根本原因は未確定 |
| P1 | `clean` と品質・警告の混同 | 構造検査の合格は内容の正しさや品質を保証しない。実測上も既定の時系列警告は `clean` を妨げない |

## 1. 実走の中断と復旧

[実験記録](../experiments/2026-10-stage-a-v11-t01/note.md) では `out/` と `.venv` が Arena のスナップショットから除外され、`out/run1/state.json` が消えた結果、`--resume needs state.json`（exit 2）が2回発生。保存済み `relay/run1/responses/` を使って新規実行から再構築し、応答ハッシュの一致を記録して完了した。これはユーザー操作ではなく、保存先と実行環境の契約が食い違った運用上の問題である。

同実験の [runbook](../experiments/2026-10-stage-a-v11-t01/runbook.md) は調査時 `--out $B/out` を指していた（現在は新規 run2 向けに修正済み）。一方で [Arena 運用原則](arena_operation.md) は状態を永続化できる実験バンドルに置くよう指示しており、手順が矛盾する。仮想環境は再作成可能だが、状態・要求・応答は再作成できない可能性があるため区別する。

**対策案:** 今後の実走は `out`、`build` 等のスナップショット除外ディレクトリ名を避け、実験バンドル内の `runs/run1` 等に state・成果物・relay を置く。開始前に `git check-ignore` と実行環境のスナップショット規則を両方確認し、回答待ちの各節目で state、要求、回答を保存する。runbook と note のパスを統一し、結果ファイルの記載先も実際の `--results` と揃える。セッション横断の必要があれば機密やサイズを確認したうえでブランチに保存する。再開試験では回答待ち→環境再生成→同一設定で `--resume`→応答を重複生成せず完走を確認する。既存の `out/` が欠落した run は記録済み relay と固定された入力・プロンプトを照合してのみ再構築し、履歴を上書きしない。

## 2. CI 失敗の再現と原因

[失敗 run 40618526069](https://github.com/jack4andmanastalk-byte/AutoStoryCreationAI/actions/runs/40618526069) は `arena/9195f0c3-autostorycreationai` の `8c385bc704c6e28284cb6bfad8cddab40f5d6b99`、`Run the test suite` で失敗。Actions ログのダウンロードはネットワーク制限により EOF となり、ログ本文は確認できなかった。代わりに同 SHA のアーカイブを別ディレクトリに展開し、Python 3.11 と main の requirements で全テストを再現したところ **5 failed / 733 passed**。CI と依存バージョンが完全に同じとは限らないので、以下はローカル再現の結果である。

- 4件: `test_cli_compose_partial_flag`、`test_run_tree_cli_and_recursive_compose`、`test_nested_cli_add_run_pending_status_and_compose`、`test_a_child_node_can_be_inspected_and_driven_and_reminds_about_adopt_child`。`--source-dataset` / `--source-work` は `init` に追加されたが、共有関数 `_work_options(args)` は `add-child` の Namespace にも存在すると仮定して直接参照する。`add-child` は `AttributeError: Namespace has no attribute source_dataset` で停止し、子作品作成や後続のツリー運用を阻害する。
- 1件: `test_ids_file_fetches_exactly_the_requested_ids` は `PathsConfig(pdf_dir=...)` を使う一方、同ブランチの PDF 設定削除後は `pdf_dir` を受け付けず `TypeError`。テストと設定 API が不整合。対象コードが正しく動くかはこの例外より先に進まないため未確認。

**対策案:** 当該ブランチを継続する場合、サブコマンドの引数契約を明示し、共有処理で任意属性を安全に扱うか両サブコマンドに必要な引数を一貫して定義する。`init` と `add-child` の両経路を source オプションの有無を含め回帰テストする。PDF 廃止の方針に合わせてテスト fixture と全参照を更新し、全テストを通す。機能を main に取り込む場合は差分を個別にレビューし、main 側の近時の成果を失わないよう統合する。調査時点で同ブランチは main と分岐しており、該当 PR は確認できなかった。

main の [直近 research-check](https://github.com/jack4andmanastalk-byte/AutoStoryCreationAI/actions/runs/40643147127) は成功。main のローカル全テストも **780 passed、3 warnings**（Python 3.11、requirements を新規 venv に導入）だった。別ブランチの失敗を main の現行障害と断定しない。

## 3. データセット更新失敗

[失敗 run 40518921973](https://github.com/jack4andmanastalk-byte/AutoStoryCreationAI/actions/runs/40518921973) は別ブランチの `da9c428bd8a6b1fe39b89ed0763951270f61b4a5` で、prepare は成功、20 shard すべてが `Fetch all episodes ...` ステップで失敗し、publish のマージ・件数検証ステップも失敗した。publish は一部 shard の失敗後もバックフィル目的で実行される設計である。全 shard に共通する設定・コード・外部サービス等が候補だが、実際の例外や HTTP 応答は未確認で原因の断定はできない。直前の [run 40092403086](https://github.com/jack4andmanastalk-byte/AutoStoryCreationAI/actions/runs/40092403086) は成功しているが、コードと実行条件が異なるため比較だけでは原因を特定できない。

**対策案:** GitHub Actions 画面等で失敗 run の shard 1件以上と publish のログを取得し、最初の例外・コマンド・HTTP status・成果物の欠落を記録する。失敗時点のワークフローとスクリプトを直前の成功 SHA と比較し、共通原因と publish 側の二次障害を分ける。外部 API エラーならレート制限・応答を検証し、コード契約エラーなら最小 fixture と CLI 回帰テストを追加する。修正後は公開先を更新しない小規模・隔離環境で検証し、欠損・件数・権利条件を確認した後、承認を得て更新する。現行 workflow は release と `datasets` ブランチへの書き込みを伴うため、調査目的で本番 run を無条件に再実行しない。

## 4. AI 出力・検査の限界

最新の [Stage A 1.1 実走](../experiments/2026-10-stage-a-v11-t01/note.md) は 1 試行で検査上 `clean` だったが、`fail_forward` / `rescue` の実応答経路は通っておらず、`carry_forward` の次場面への意味的反映は自動検査されない。応答者・回答用チャットも未記入。N=1 で品質・再現性を主張できない。

[Stage B 実験](../experiments/2026-10-stageb-v11-t01/note.md) では時系列誤りを注入しても既定では warning のまま `clean`、`--strict-timeline` では修復対象となった。したがって運用では `clean` だけでなく warning、スキップ、本文を確認し、時系列誤りを阻止したい場合は strict を明示する。次の評価では人手で持ち越しを照合し、`fail_forward` を含むケースと複数タスクを追加し、応答の由来を記録する。検査強化は誤検出率も測定したうえで判断する。

## 実施順と完了条件

1. **復旧優先:** 新規実走の保存先を安全なパスにし、途中停止から再開できることを確認。既存の証拠は保持。
2. **分岐作業の修正:** `add-child` と PDF fixture の不整合を修正し、該当ブランチで全テスト成功。main への取り込みは別途差分レビュー。
3. **データセット:** 失敗ログ取得→原因特定→隔離検証→承認後公開。ログが取得できなければ未確定のまま扱う。
4. **品質ゲート:** warning と未検査範囲を明示し、人手照合・strict 運用を検証。`clean` を品質保証と表現しない。

## 対策の実施状況（追記）

- 新規 run2 の手順を `runs/run2`・`relay/run2` に変更し、保存先の事前検査と GitHub ブランチへのチェックポイントを追加した。`scripts/check_persistent_paths.py` は Git の ignore と Arena の既知の除外ディレクトリを検出する。これは commit / push の代わりではない。
- 固定台本の回帰テストで、回答待ちの state と relay を Git にコミットし、別 checkout から `--resume` して完了することを検証した。実モデルの再現性を示すものではない。
- `source_dataset` / `pdf_dir` の失敗は現行 main に存在しない別ブランチの未統合変更に固有である。現行ブランチにその機能を取り込んでいないため、ここで存在しないコードを修正したとは主張しない。将来その差分を移植する場合は §2 の回帰対策が必要。
- データセットの失敗ログは取得できておらず、原因や修正は未確定。外部公開を行う workflow の再実行はしていない。
