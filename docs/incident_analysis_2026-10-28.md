# 実走中断の調査と対策（2026-10-28）

## 確認した事象

[Stage A 1.1 実走の記録](../experiments/2026-10-stage-a-v11-t01/note.md)では、Arena のスナップショット対象外である `out/` に再開用の `state.json` を置いた結果、途中の再開に2回失敗した。保存済みの relay 応答を使って run を再構築し、応答ハッシュを照合して完了した。

原因は、状態の保存先と実行環境の保存規則との不一致だった。仮想環境は再作成できるが、run の状態や回答は再作成できない可能性がある。

## 実施した対策

- 新規実走の保存先を実験バンドル内の `runs/run2` と `relay/run2` に変更し、既存の run1 を上書きしない手順にした。[runbook](../experiments/2026-10-stage-a-v11-t01/runbook.md)
- `scripts/check_persistent_paths.py` で、Git の ignore と既知の Arena スナップショット除外ディレクトリを事前検査できるようにした。検査の成功は commit や push の代わりにはならない。
- 回答待ちや完了の節目で state、要求、応答と成果物を点検し、GitHub の作業ブランチに commit / push する運用を明記した。[運用手順](arena_operation.md)
- 固定台本のテストで、回答待ちの状態と relay を Git にコミットし、別のチェックアウトから再開して完了できることを確認した。実モデルの再現性を示すテストではない。

## 確認結果

修正後の全テストは Python 3.11 で **784 passed、3 warnings**。検査結果の `clean` は検査範囲内の状態を示し、物語の質や意味的な整合性を保証しない。

次の作業は[再開プラン](work_resumption_plan.md)を参照する。
