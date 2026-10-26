# 評価レポート

対象: `/home/user/AutoStoryCreationAI/experiments/2026-10-plot-ablation-t01/paired/attempts/t01-s1-seed0/with_plot/t01-s1-seed0-with_plot-try14/text`

**状態: PASS**

| ゲート | 状態 | 条件 |
| --- | --- | --- |
| `no_high_severity_continuity` | pass | high の整合性違反が 0 件であること。 |
| `all_verdicts_evidenced` | skipped | L2 の全判定に根拠（引用または位置）が付いていること。 |
| `no_regression` | skipped | ベースラインと比べて悪化した指標がないこと。 |

## L1 決定論的検査

* 文字数 4,017 / 段落 26 / 会話率 23%
* 違反密度（CED 相当）: 12.447 / 1万文字、禁止パターン 0.0 / 1万文字
* 継続性違反 5 件（high 0 / medium 5 / low 0）
* 監査カバレッジ: 3/3 章にマーカーあり（低い場合、0 件は「矛盾なし」ではなく「未検査」）

## L2 モデル判定

スキップ: judge が設定されていない

## L3 人間評価

スキップ: 人間ラベルが指定されていない

## 改善チケット

| 担当 | 分類 | 件数 | 次の一手 |
| --- | --- | ---: | --- |
| `skills/continuity-ledger` | 整合性 / 人物状態 | 5 | 死亡章以降の参照を削除するか、suppressions.yaml に理由つきで登録する。 |

## この評価で分からないこと

* L1 は整合性の一部（台帳にある項目）しか見ない。意味の破綻は対象外。
* L2 の点数は判定器に依存する。判定器名・版・設定を記録しない比較は無効。
* L3 が無い場合、L2 の妥当性は測れていない。
* 単一の総合点は出さない。次元ごとの差を見る。

