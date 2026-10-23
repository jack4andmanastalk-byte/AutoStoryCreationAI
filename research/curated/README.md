# research/curated — 選別済みコーパス

ここには、添付アーカイブ `StoryAutomation.zip` から**採録した 88 ファイル**だけを置いています
（この README、`MANIFEST.json`、互換用シンボリックリンク 4 本を除く）。
すべて元ファイルの**バイト単位のコピー**で、内容の改変はしていません。
各ファイルの元パスと SHA-256 は [`MANIFEST.json`](MANIFEST.json) に記録しています。

## 何を残したか

| 判定 | 内容 | このディレクトリでの扱い |
| --- | --- | --- |
| adopt（9） | 構造化データ・スキーマ・検証ログが揃う成果物 | 統一カタログ（[`../catalog/`](../catalog/)）へ正規化。 |
| reference（21） | 報告書・出典リスト。正規化はしていない | 比較・深掘り用に保存。 |

判定の理由は [`../curation/selection_report.md`](../curation/selection_report.md) を参照。

## 保存しなかったもの

* 第三者本文・PDF 抽出テキスト（`us_story2/evidence/`、290 ファイル）
* clone 済みリポジトリ・検索生ログ（3,444 ファイル、約 17 MB）
* CNKI・万方の HTML/PDF（22 ファイル）
* 展開済みと重複する入れ子 ZIP（18 本）
* 検証スクリプト、チェックサム、取得監査ログ（成果物本体ではないため）

そのため、元の報告書に含まれる一部の相対リンク（`validate.py`、`checksums.sha256`、
`retrieval_audit.jsonl`、`SHA256SUMS.txt` など）は、このリポジトリでは解決できません。
**内容の欠落ではなく、意図的な非収録**です。

## ファイル名の正規化

可読性のため、次のファイルは名前を変えて保存しています。元の名前は `MANIFEST.json` の
`source_path` から確認できます。参照の多いものには互換用のシンボリックリンクも置いています
（Windows では通常のテキストファイルとして展開される場合があります）。

| 保存名 | 元のファイル名 | bytes |
| --- | --- | ---: |
| `ai_creation/pipeline_catalog/report.md` | `creative_pipeline_catalog_report.md` | 45,803 |
| `ai_creation/pipeline_catalog/tools.jsonl` | `creative_narrative_tools_metadata.jsonl` | 21,461 |
| `ai_creation/skills_catalog/report.md` | `creative_building_ai_skills_catalog_report.md` | 124,262 |
| `character/europe/report.md` | `character_research_report_ja.md` | 19,730 |
| `character/europe/sources.jsonl` | `character_sources.jsonl` | 77,956 |
| `character/japan/report.md` | `character_creation_japan_report.md` | 66,237 |
| `character/japan/sources.jsonl` | `character_creation_japan_catalog_metadata.jsonl` | 128,413 |
| `history_myth/comparative_mythology/report.md` | `comparative_mythology_creative_catalog.md` | 76,006 |
| `history_myth/comparative_mythology/sources.jsonl` | `comparative_mythology_catalog_sources.jsonl` | 55,256 |
| `narrative/china_2026/report_ja.md` | `china_storytelling_report_ja.md` | 178,297 |
| `narrative/europe_craft/report.md` | `catalog_report.md` | 41,971 |
| `narrative/europe_storytelling/report.md` | `現代ヨーロッパ_ストーリーテリング技法カタログ.md` | 33,526 |
| `narrative/europe_storytelling/sources.jsonl` | `現代ヨーロッパ_ストーリーテリング_情報源.jsonl` | 23,722 |
| `narrative/japan_2026/report.md` | `japan_narrative_techniques_report.md` | 171,766 |
| `narrative/japan_entertainment/report.md` | `japanese_entertainment_scenario_techniques.md` | 77,325 |
| `narrative/japan_entertainment/sources.jsonl` | `scenario_sources_metadata.jsonl` | 42,707 |
| `narrative/japan_film/report.md` | `scenario_techniques_report.md` | 89,509 |
| `narrative/japan_film/sources.jsonl` | `scenario_techniques_metadata.jsonl` | 26,526 |
| `narrative/japan_games/report.md` | `scenario_techniques_japan_games.md` | 15,210 |
| `narrative/japan_games/sources.jsonl` | `scenario_sources.jsonl` | 7,321 |
| `narrative/japan_literary/report.md` | `literary_scenario_techniques_japan.md` | 17,799 |
| `narrative/japan_literary/sources.jsonl` | `literary_scenario_sources.jsonl` | 13,209 |
| `narrative/japan_storytelling_50/report.md` | `japanese_storytelling_techniques_catalog.md` | 122,843 |
| `narrative/japan_storytelling_50/sources.jsonl` | `storytelling_sources.jsonl` | 25,623 |
| `narrative/japan_storytelling_report/report.md` | `storytelling_japan_report.md` | 22,991 |
| `narrative/japan_storytelling_report/sources.jsonl` | `storytelling_japan_sources.jsonl` | 7,869 |
| `narrative/japan_trpg/report.md` | `trpg_scenario_catalog.md` | 18,892 |
| `narrative/japan_trpg/sources.jsonl` | `trpg_scenario_sources.jsonl` | 10,247 |
| `production/game_narrative_china/report.md` | `2026-10-23_china-game-narrative-pipeline_report_ja.md` | 58,014 |
| `production/game_narrative_china/sources.jsonl` | `2026-10-23_china-game-narrative-sources.jsonl` | 26,430 |
| `production/game_narrative_europe/report.md` | `european_game_narrative_pipeline_report.md` | 32,617 |
| `production/game_narrative_europe/sources.jsonl` | `european_game_narrative_sources.jsonl` | 25,606 |
| `worldbuilding/china/report.md` | `worldbuilding_techniques_china_ja.md` | 38,840 |
| `worldbuilding/china/sources.jsonl` | `sources_ja.jsonl` | 33,618 |
| `worldbuilding/europe/report.md` | `worldbuilding_catalogue_report.md` | 45,611 |
| `worldbuilding/europe/sources.jsonl` | `2_worldbuilding_sources.jsonl` | 17,491 |
| `worldbuilding/japan/report.md` | `worldbuilding_techniques_japan.md` | 117,331 |
| `worldbuilding/japan/sources.jsonl` | `worldbuilding_sources_metadata.jsonl` | 28,187 |
| `worldbuilding/us/report.md` | `worldbuilding_us_catalog.md` | 29,483 |
| `worldbuilding/us/sources.jsonl` | `worldbuilding_sources.jsonl` | 16,789 |

## 検証

```bash
python3 scripts/build_research_catalog.py --check   # 統一カタログの差分
python3 -m pytest tests/test_research_catalog.py -q # 件数・参照・ハッシュ
```

`MANIFEST.json` の SHA-256 と実ファイルが一致しない場合は、コピーが改変されたことを意味します。
