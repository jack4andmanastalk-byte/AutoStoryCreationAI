# CI — 実行枠の設計

## 0. 現在の状態（2026-10-23、公開リポジトリ化後）

**分数の問題は解消した。** リポジトリを公開にしたことで、標準の GitHub ホステッドランナーは
課金対象外になった。実際に確認した結果は次のとおり。

| 確認 | 結果 |
| --- | --- |
| リポジトリの公開設定 | `private: false`（public） |
| 公開後の CI 実行 | `research-check` **17 秒・全 9 ステップ成功** |
| 以前の失敗 | 同じワークフローが「job not started（billing）」で 2〜3 秒で失敗していた |
| 実行枠（同時実行数） | **変わらず 20**（Free プラン）。`max-parallel: 12` は維持する |

分数は無料になったが、**同時実行数の上限は残る**。データ生成が 20 シャードを同時に走らせると、
CI は依然としてその後ろで待たされる。`docs/ci.md` の 1〜3 節（枠の予約）はそのため有効。

**未確認**: `dataset-refresh` は公開後に一度も走らせていない（70 分かかるため）。
請求ブロックはアカウント単位だったので解消していると見込まれるが、次回の手動実行か
月次スケジュールで確認する。動かす前に確認したい場合は、`prepare` ジョブの開始だけを見て
中止すればよい。

## 1. 何が起きていたか（公開前の記録）

このリポジトリは**プライベート**で、GitHub ホステッドランナーの同時実行数には
アカウント単位の上限がある（Free: 20 ジョブ）。`dataset-refresh` は
`prepare` 1 + シャード 20 + `publish` 1 を同時に起動するため、上限を埋め尽くしていた。

その結果、15 秒で終わるはずの `research-check` が、30〜60 分の PDF ビルドの後ろで
数十分待たされた。テストが遅いのではなく、**順番待ちが遅い**。

```
修正前:  dataset-refresh   [prepare][shard x20] ......... 35-60 min
         research-check                          [check]   ← 15 秒の処理に 20 分待つ
```

## 2. どう直したか

| 変更 | ファイル | 効果 |
| --- | --- | --- |
| シャードの同時実行を **12** に制限（`DATASET_MAX_PARALLEL` で変更可） | `dataset-refresh.yml` | 常に 6 スロット以上を空ける。2 ウェーブ（約 70 分）で完了 |
| `prepare` / `render-narou` に**ジョブ単位の concurrency** | 同上 | 同一 ref の古いビルドを打ち切る。3 本が積み上がらない |
| `publish` はキャンセルされた実行から**公開しない** | 同上 | 部分的な成果物で `datasets` ブランチを上書きしない |
| `research-check` に**専用の concurrency**（`cancel-in-progress: true`） | `research-check.yml` | 古いコミットのチェックが自分自身の後ろに並ばない |
| `runs-on: ${{ vars.CI_RUNNER_LABEL \|\| 'ubuntu-latest' }}` | 同上 | セルフホストランナーを登録すれば、コード変更なしで CI を共有枠から外せる |
| トリガーを**全 push / 全 PR** に変更（path フィルタ廃止） | 同上 | 「テスト対象のファイルを列挙し忘れて CI が走らない」事故をなくす |
| `datasets` ブランチだけ除外（`branches: ["**", "!datasets"]`） | 同上 | データ公開のバッチ push はコードを変えない。1 回の公開で 10 本近い CI を走らせない |
| テストを**手書きの一覧ではなく `pytest tests`** に | 同上 | 新しいテストファイルを追加するたびに CI を直す必要がなくなる |

```
修正後:  dataset-refresh   [prepare][shard x12] ......        ← 6 枠を常に空ける
         research-check        [check] 15 s                   ← 待たずに走る
```

## 3. 「別ランナー」について

プライベートリポジトリでは、ホステッドランナーの**ラベルを分けても実行枠は共有**される
（`ubuntu-latest` と `ubuntu-slim` は同じ予算。`ubuntu-slim` は公開リポジトリ限定）。
したがって「別ランナー」は次のどちらかで実現する。

1. **枠の予約**（今回の既定）: 重いワークフローの並列度を下げる。追加費用なしで、
   CI はほぼ待たずに走る。
2. **セルフホストランナー**: リポジトリ変数 `CI_RUNNER_LABEL` にラベルを設定すると、
   `research-check` はそのランナーで動く。共有枠を使わないので、データセットの再生成と
   完全に独立する。ランナーの登録は Settings → Actions → Runners。

```bash
# 設定（すべて任意）
gh variable set DATASET_MAX_PARALLEL --body 8        # データ生成の並列度を下げる
gh variable set CI_RUNNER_LABEL --body self-hosted   # CI をセルフホストへ
gh variable set DATASET_RUNNER_LABEL --body self-hosted  # データ生成もセルフホストへ
```

## 4. コスト（分数）— 公開前の制約（現在は解消）

> **公開後**: 標準ホステッドランナーは公開リポジトリでは課金対象外。以下の見積もりは
> 「なぜ止まっていたか」の記録として残す。セルフホストへの移行口（`*_RUNNER_LABEL`）は、
> 実行枠を完全に分離したい場合のために引き続き有効。

2026-10-23 に、**両ワークフローが 2 秒で「開始されず」に失敗**した。ログの注記は次のとおり。

```
The job was not started because recent account payments have failed
or your spending limit needs to be increased.
```

つまり枠（同時実行数）ではなく、**分数の上限または支払い**で止まっていた。見積もりは次のとおり。

| ワークフロー | 1 回の消費 | 頻度（変更前） | 月あたり |
| --- | ---: | --- | ---: |
| `dataset-refresh` | 約 **700 分**（20 シャード × 約 35 分 ＋ prepare/publish） | 週次 | 約 3,000 分 |
| `research-check` | 約 1 分 | push ごと（数十回/日） | 数十分 |

Free プランのプライベートリポジトリは **2,000 分/月**。データ生成だけで超過する。
そこで次の 3 つを入れた。

1. **定期実行を週次 → 月次**（`cron: "0 3 1 * *"`）。必要なら `workflow_dispatch` で随時実行する。
2. **セルフホストランナーへの移行口**を両方に用意した（`CI_RUNNER_LABEL` / `DATASET_RUNNER_LABEL`）。
   セルフホストは分数を消費しないため、これがいちばん確実な解決策になる。
3. `research-check` の path フィルタ廃止（全 push）は**コスト的にも安全**。1 回 1 分未満で、
   古いコミットの実行は `cancel-in-progress` で打ち切られる。

> **注意**: 請求が止まっている間は、どのワークフローも開始されない。
> ローカルでは `make ci` が同じ検査を行うので、マージ判断はそれで行える。

## 5. データ公開（Release）の失敗と再発防止 — 2026-10-23

`dataset-refresh` は 20 シャードすべて成功し、`datasets` ブランチへの反映も成功したのに、
**Release への添付だけが失敗**して PDF バンドル（`narou_rank_*_pdfs.tar.gz`）が消えた。

| 項目 | 内容 |
| --- | --- |
| 原因 | アセット一覧に同じファイルを 2 回入れていた。`narou_commercialized_rank[0-9]*` は正しいが、当時は `rank*` で、`narou_commercialized_ranked.jsonl` にも一致した |
| なぜ消えたか | `gh release upload` は重複名で HTTP 422 を返して**全体を中断**する。`--clobber` は**先に旧アセットを削除**するため、中断時点で旧 tarball も新しい tarball も無い状態になった |
| 二次被害 | このワークフローは Release の tarball をキャッシュに使う。空になったため、次の実行では全シャードが一から取得し直し、シャード 7 が 46 分・シャード 5 が 26 分かかった |

再発防止として、公開ステップを次のように変えた。

1. **重複排除**（`awk '!seen[$0]++'`）と、glob を `rank[0-9]*` に限定
2. **事前検査**: サイズが 0 以下・2 GiB 以上・`gzip -t` に失敗するファイルは、**何も削除する前に**停止
3. **1 アセットずつ・3 回リトライ**（1 件の失敗で残りを巻き添えにしない）
4. **公開後の照合**: アセット名とサイズを API で突き合わせ、欠けていれば `::error::` で失敗
5. シード実行 ID が期限切れ（アーティファクトは 7 日）でも、直近の成功実行から取り直す

これらは `tests/test_ci_workflows.py` で固定している（glob が `ranked.jsonl` に一致しないこと、
一括アップロードをしていないこと、検証と `gzip -t` があること、Bash 構文が通ること）。

## 6. ローカルで同じことをする

```bash
make ci    # カタログ整合 → 全テスト → デモ監査 → デモ評価（CI と同じ順序）
```

## 7. 現在のジョブ構成

| ワークフロー | トリガー | 時間 | 役割 |
| --- | --- | --- | --- |
| `research-check` | 全 push・全 PR・手動 | 30〜60 秒 | カタログ整合、全テスト、デモ監査、デモ評価 |
| `dataset-refresh` | 月次・手動（push / PR では起動しない） | 10〜90 分（キャッシュ再利用時 ~7 分） | メタデータ取得、5ジャンル並列検証、プレーンテキスト化・PDF完全削除、orphan `datasets` ブランチと Release (`*_texts.tar.gz`) への公開 |

`dataset-refresh` は現在 GitHub 上で手動停止されている（[保守状況](maintenance_status.md)）。
以下は再有効化した場合のコードの挙動であり、再開の許可ではない。`publish` は **main の
実行時のみ** `datasets` と Release を更新する。手動で作業ブランチを指定するとビルド確認は
できるが公開ジョブは実行されない。通常の push / PR では外部データ取得・上書きは始まらない。
main の手動・月次実行では再公開されるため、再開前に権利・対象・容量を確認する。

`research-check` は**デモの監査と評価も実行**する。テストが緑でも、デモの期待値が
ずれていれば落ちる（`harness/cases/demo/EXPECTED.md` が契約）。

## 8. 触るときの注意

* `dataset-refresh` のシャード数を増やすなら `max-parallel` も見直す。
  `シャード数 - max-parallel + 2` が常時使う枠。**8 以上は空ける**こと。
* `publish` の `if` は main 限定と `(!cancelled()) && needs.prepare.result == 'success' && needs.render-narou.result != 'cancelled'` を維持する（`always()` を使うと Web UI の Cancel が効かなくなるため `!cancelled()` とする）。
  キャンセルされた実行の部分的な PDF で `datasets` ブランチを上書きしてしまう。
* `dataset-refresh` の頻度を週次に戻すなら、分数を計算し直すこと（1 回 700 分）。
* `research-check` に path フィルタを戻さない。**列挙漏れで CI が走らない**のが
  いちばん危ない失敗の仕方だから。実行時間は 1 分未満なので、絞る理由がない。
* ランナーの上限はプランで変わる（Free 20 / Pro 40 / Team 60）。数字を直すときは
  `tests/test_ci_workflows.py` の前提も更新する。
