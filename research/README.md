# research — 創作技法・制作実務・AIスキルの研究基盤

このディレクトリは、外部で収集した創作研究資料（`StoryAutomation.zip`、25 成果物・約 11 MB）を
**監査可能な形で選別し、AI による自動創作のスキル／ハーネス／パイプラインへ接続する**ための基盤です。

> 位置づけ: Phase 0（データセットアップ）の次に来る **Phase 1 — 創作知識の運用可能化**。
> 作品本文の生成そのものではなく、
> 「どの技法を・どの工程で・どう検証するか」を機械可読にすることを目的にしています。

## 1. まず読むもの

| ドキュメント | 内容 |
| --- | --- |
| [`curation/materials_inventory_2026-10-25.md`](curation/materials_inventory_2026-10-25.md) | **棚卸し**。採録資料→カタログ→13 スキル→実行工程の接続（2026-10-25 時点）。 |
| [`curation/plot_to_draft_2026-10-25.md`](curation/plot_to_draft_2026-10-25.md) | **後続実装**。T004 の幕・転換点を章別 Draft メモへ渡す条件と、固定台本での L1 配線比較。 |
| [`curation/selection_report.md`](curation/selection_report.md) | **採用判定の本体**。実用性の評価基準、34 成果物の採否、重複・権利・除外理由、次工程。 |
| [`curation/gap_analysis_and_added_sources.md`](curation/gap_analysis_and_added_sources.md) | コーパスの空白を埋める追加調査（2026 年のベンチマーク、長編生成、Agent Skills、評価ハーネス、日本語研究）。 |
| [`catalog/README.md`](catalog/README.md) | 統一カタログのスキーマと読み方、件数、限界。 |
| [`curation/executability_report.md`](curation/executability_report.md) | **実務化できるか**の仕分け（手順・合格条件・失敗条件・例の 4 項目、488 件）。 |
| [`program/skill_pipeline_mapping.md`](program/skill_pipeline_mapping.md) | 技法カタログを `SKILL.md` / 評価ハーネスへ変換する設計。 |
| [`curation/spec_changes_2026-10.md`](curation/spec_changes_2026-10.md)・[p2](curation/spec_changes_2026-10-p2.md)・[p3](curation/spec_changes_2026-10-p3.md)・[p4](curation/spec_changes_2026-10-p4.md) | 13 スキル実装と、11 スキルの S1/S2 等への接続時に補った条件・設計変更の記録。 |
| [`inventory/artifacts.jsonl`](inventory/artifacts.jsonl) | 成果物 34 件の機械可読インベントリ（判定・点数・保存先・根拠）。 |
| [`curated/README.md`](curated/README.md) | 採録した 88 ファイルの扱い、除外したもの、ファイル名の正規化。 |
| [`curated/MANIFEST.json`](curated/MANIFEST.json) | 各ファイルの元パスと SHA-256（改変検出用）。 |

## 2. ディレクトリ構成

```
research/
├── README.md
├── curated/                     # 選別して保存した 88 ファイル（バイト単位のコピー）
│   ├── README.md                # 採録方針・除外理由・名前の対応
│   ├── MANIFEST.json            # 元パスと SHA-256
│   ├── narrative/               # 日本・米国・中国・欧州の技法カタログ
│   ├── worldbuilding/           # 日本・欧州・米国・中国
│   ├── character/               # 日本・欧州・中国
│   ├── production/              # 米国・日本・欧州・中国のゲーム制作実務
│   ├── ai_creation/             # AI スキル／ハーネス／パイプラインのカタログ
│   └── history_myth/            # 比較神話、物語分類体系
├── catalog/                     # 統一カタログ（生成物・機械可読）
│   ├── techniques.jsonl         # 488 項目（技法・パラダイム・実務・概念）
│   ├── taxonomies.jsonl         # 10 の分類体系
│   ├── tools.jsonl              # 96 のスキル／ツール／パイプライン
│   ├── sources.jsonl            # 529 の重複排除済み書誌
│   ├── executability.jsonl      # 488 件の実行可能度（手順・合格条件・失敗条件・例）
│   ├── executability_summary.md # その集計（自動生成）
│   ├── schema.json              # JSON Schema（record family ごと）
│   ├── manifest.json            # 件数・分類・入力ハッシュ
│   └── validation_report.json   # 構造検査の結果
├── program/
│   ├── skill_seeds.jsonl        # 13 のスキル／ハーネス種（全件 status: implemented）
│   └── skill_pipeline_mapping.md # スキル／ハーネスへの変換設計
├── inventory/
│   └── artifacts.jsonl          # 34 成果物の採否インベントリ
└── curation/
    ├── selection_report.md
    ├── executability_report.md
    ├── gap_analysis_and_added_sources.md
    ├── materials_inventory_2026-10-25.md  # 現状と接続状況の棚卸し
    ├── spec_changes_2026-10.md  # seed-08/13 の実装時に補った条件
    ├── spec_changes_2026-10-p2.md # seed-01/02/03/09/10
    ├── spec_changes_2026-10-p3.md # 残り 6 スキル
    ├── spec_changes_2026-10-p4.md # 設計ステージへの接続
    └── added_sources.jsonl      # 追加調査 24 件
```

`catalog/README.md` は統一カタログのスキーマ・限界・変更ポリシーを説明しています。

## 3. 何を採用し、何を捨てたか（要約）

保存量は **88 ファイル・6,146,821 bytes**（アーカイブ全体の約 55%）。
本文・PDF・clone 済みコードは含まない。

* **採用（9 成果物）**: AI スキル／パイプラインのカタログ、米国ゲーム制作実務、日本・米国・中国の
  技法カタログ、比較神話、物語分類体系。統一カタログへ正規化したものと、ツール索引として
  正規化したものを含みます。
* **参照保持（21 成果物）**: 地域別・媒体別の報告書、世界観・キャラクター研究、TRPG、映画脚本など。
  内容は保存するが、統一カタログには入れず、比較・深掘り用の資料として扱います。
* **除外（4 成果物）**: 第三者本文の抽出テキスト集、clone 済みリポジトリ／検索生ログ、
  CNKI・万方の HTML／PDF、入れ子 ZIP の重複。**容量・著作権・監査コスト**が理由です。

詳細な点数と理由は [`curation/selection_report.md`](curation/selection_report.md) を参照してください。

### 3.1 実務に落とせるか

「知識が抽象的で使えない」を件数で扱うため、各技法に実行可能度を付けている。

| 区分 | 件数 | 使い方 |
| --- | ---: | --- |
| `executable` | 115 | 手順と判定語がある（そのまま有効な検査になるという意味ではない） |
| `partial` | 290 | 合格条件の記述を補い、用途に応じて検証する |
| `reference_only` | 83 | 分類・評価・発想の語彙として使う |

これはレコードの長さ・判定語等から付けた**記述上の分類**で、技法の効果や実装済みの検査数ではありません。
欠けているのは主に**合格条件**（488 件中 124 件しか持たない）。
詳細は [`curation/executability_report.md`](curation/executability_report.md)。

実装側で補った合格条件や、原典とは別に決めた設計は
[`curation/spec_changes_2026-10.md`](curation/spec_changes_2026-10.md) と
[p2](curation/spec_changes_2026-10-p2.md)・[p3](curation/spec_changes_2026-10-p3.md)・
[p4](curation/spec_changes_2026-10-p4.md)、各スキルの `references/techniques.md` に記録しています。
これらは編集上の追加であり、原典の主張や生成品質の実証ではありません。

## 4. 再生成と検証

```bash
python3 scripts/build_research_catalog.py          # 統一カタログを再生成
python3 scripts/build_research_catalog.py --check  # コミット済みカタログとの差分検査
python3 -m pytest tests/test_research_catalog.py -q
```

依存パッケージは不要です（標準ライブラリのみ）。`research/curated/` を変えたら再生成し、
`manifest.json` と `validation_report.json` も一緒にコミットしてください。

## 5. データの使い方

```python
import json
from pathlib import Path

def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]

techniques = read_jsonl("research/catalog/techniques.jsonl")
sources = {s["id"]: s for s in read_jsonl("research/catalog/sources.jsonl")}

# 例: 「世界の規則」に関わる技法を、根拠つきで引く
for t in techniques:
    if "world" in t["domains"] and "rule" in (t["title_ja"] + (t["summary_ja"] or "")).lower():
        print(t["id"], t["title_ja"])
        for sid in t["source_ids"]:
            print("   ", sources[sid]["title"], sources[sid]["url"])
```

## 6. この基盤が支えるもの

1. **スキル**: `program/skill_seeds.jsonl` の 13 種（企画、世界規則、歴史、人物、関係、構造、
   場面、継続性、文体、改稿、分岐、翻案、評価）はすべて `status: implemented` で、
   `skills/` に手順・検査・デモがあります。ただし通常の短編の設計工程に自動接続されるのは
   8 種で、分岐と翻案は個別利用です（[接続状況](curation/materials_inventory_2026-10-25.md)）。
2. **ハーネス**: 決定論的検査とモデル／人間による評価を分離します。現行研究運用は
   [L1 のみ](../docs/evaluation_scope.md)で、L2/L3 の実証・較正は凍結中です。
3. **パイプライン**: Plan → Design → Draft → 監査、必要に応じて S2 改稿・S3 文体調整へ
   接続します。設計書の構造検査は作品の品質や技法の効果の証明ではありません。

## 7. 注意

* 収録したのは**書誌・分析・手順の要約**であり、第三者の本文・PDF・コードは再配布していません。
* 証拠水準（`evidence.level`）は**各カタログ内の相対評価**で、カタログ間で比較できません。
* `domains` と `mapping_authorship` は本リポジトリによる編集上の分類です。原典の主張ではありません。
* 収集時点は 2026-10-22/23 です。リンク切れ・版の更新・ベンチマークの陳腐化は定期的に再確認してください。
