# 統一創作カタログ（v1.0）

`research/curated/` の選別済み成果物から、**同じスキーマで引ける知識**を抽出したものです。
作品本文や第三者の PDF は含みません。書誌・手順の要約・分析上の分類だけを持ちます。

生成: `python3 scripts/build_research_catalog.py`（標準ライブラリのみ）
検証: `python3 scripts/build_research_catalog.py --check` と `tests/test_research_catalog.py`

---

## 1. ファイル

| ファイル | 件数 | 内容 |
| --- | ---: | --- |
| `techniques.jsonl` | 488 | 技法・パラダイム・制作実務・概念 |
| `taxonomies.jsonl` | 10 | ATU、プロップ、モチーフ索引などの分類体系 |
| `tools.jsonl` | 96 | AI スキル、執筆ツール、パイプライン、評価基盤 |
| `sources.jsonl` | 529 | 重複排除済みの書誌（URL/DOI 単位） |
| `manifest.json` | — | 件数、分類別内訳、入力ファイルの SHA-256 |
| `validation_report.json` | — | 構造検査の結果（内容の妥当性ではない） |
| `schema.json` | — | JSON Schema（technique / taxonomy / tool / source / skill_seed） |

`techniques.jsonl` の内訳:

| entry_type | 件数 | 意味 |
| --- | ---: | --- |
| `technique` | 313 | 創作・制作の手順・概念 |
| `paradigm` | 83 | 三幕構成・英雄の旅などの型の索引 |
| `practice` | 42 | 制作工程の実務（ゲーム開発） |
| `concept` | 39 | 神話・物語論の分析概念（創作転用つき） |
| `workflow` | 6 | 制作フロー |
| `critical_principle` | 5 | 批判的・倫理的な設計原則 |

`domains`（複数タグあり）: story 250、style 166、production 68、character 67、
meta 67、world 59、interaction 46、history 38。

---

## 2. レコードの読み方（technique）

```json
{
  "id": "narrative/japan_2026:T033",
  "artifact": "narrative/japan_2026",
  "original_id": "T033",
  "entry_type": "technique",
  "title_ja": "一対一の張りと回収（基本型）",
  "title_en": null,
  "summary_ja": "設置した要素を、後で一度だけ回収する基本形。",
  "operation_ja": "…（作業手順の要約）…",
  "limitations_ja": "…（成立条件・注意）…",
  "domains": ["story", "style"],
  "source_ids": ["src-…"],
  "evidence": {"level": null, "verification": "selected_passages", "source_count": 2},
  "related_ids": [],
  "mapping_authorship": {"domains": "editorial"},
  "provenance": {"path": "research/curated/narrative/japan_2026"}
}
```

| フィールド | 使い方 | 注意 |
| --- | --- | --- |
| `id` | `<artifact>:<元ID>` の安定 ID | 元カタログの ID を保持。 |
| `title_ja` / `title_en` | 検索・表示 | 日本語タイトルは元カタログの見出し。 |
| `summary_ja` / `operation_ja` | スキルの手順・参照資料の素材 | **逐語引用ではない**。原典は `source_ids` から。 |
| `limitations_ja` | スキルの「しないこと」・評価の注意 | 空の場合は原典に明示がない。 |
| `domains` | 工程・領域でのフィルタ | 本リポジトリの編集分類。 |
| `source_ids` | `sources.jsonl` への参照 | URL 正規化後に SHA-256 で採番。 |
| `evidence.level` | 元カタログ内の証拠等級 | **カタログ間で比較不可**（下記）。 |
| `related_ids` | 元カタログの相互参照 | 正規化セット内で解決できるもののみ。 |
| `provenance.path` | 元ファイルの場所 | `research/curated/` 配下。 |

---

## 3. 証拠等級の非互換（重要）

`evidence.level` は元カタログが付けた値をそのまま保持している。
**同じ `A` でも意味が違う。**

| 出所 | 等級の意味 |
| --- | --- |
| `narrative/us_2026` | A–D。A は公開本文の該当箇所を確認、D は検索情報のみ。 |
| `narrative/china_2026` | A–D。A は一次資料・本文の該当箇所を確認。 |
| `narrative/us_2025` | 等級なし。`evidence.tier` は情報源リスト内の tier。 |
| `narrative/japan_2026` | 等級なし。`verification` に確認範囲（full_text / selected_passages 等）。 |
| `production/game_narrative_us` | 等級なし。`verification` に review_extent。 |
| `history_myth/*` | 等級なし。二次資料の比較整理。 |

したがって、**「A の技法だけを使う」といった横断的な閾値には使えない**。
信頼性を判断するときは、`artifact` と `verification` を併せて読む。

---

## 4. ツール（tools.jsonl）

`ai_creation/skills_catalog` の 79 件と `ai_creation/pipeline_catalog` の 20 件を
URL で重複排除して 96 件にしたもの（3 件が両方に存在）。以下を含む:

* Agent Skills / Claude Code プラグイン / MCP サーバー
* 執筆ハーネス、長編生成パイプライン、継続性チェック
* 世界観 DB、地図生成、年表ツール
* 評価基盤（LitBench など）

`score_total`・`rank` は**元カタログの 25 点満点の評価**であり、
本リポジトリによる再評価ではない。`license` は取得時点の GitHub API 判定で、
「なし／不明」は利用前に必ず確認する。**コードは再配布していない。**

---

## 5. 出典（sources.jsonl）

```json
{
  "id": "src-1a2b3c4d5e",
  "title": "…",
  "authors": ["…"],
  "year": 2020,
  "url": "https://…",
  "doi": "…",
  "source_type": "academic_monograph",
  "language": "en",
  "peer_review_status": "…",
  "artifacts": [{"artifact": "narrative/us_2026", "original_id": "S012"}]
}
```

* URL はクエリ・フラグメントを除去して正規化。同一 URL は 1 レコード。
* URL がない検索クエリ（`web_search_query` / `api_search_query`）は、
  出典ではなく探索履歴として保持。
* `artifacts` に元カタログの ID を残すので、元ファイルへ遡れる。

---

## 6. 使い方

```python
import json
from collections import Counter
from pathlib import Path

def read_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]

tech = read_jsonl("research/catalog/techniques.jsonl")
src = {s["id"]: s for s in read_jsonl("research/catalog/sources.jsonl")}

# 1. 工程別に引く
for t in tech:
    if "world" in t["domains"] and t["operation_ja"]:
        print(t["id"], t["title_ja"])

# 2. 出典つきで表示
t = next(x for x in tech if x["id"] == "production/game_narrative_us:P13")
print(t["summary_ja"])
for sid in t["source_ids"]:
    print("-", src[sid]["title"], src[sid]["url"])

# 3. 失敗類型の分布（例: 制約・限界が明示された項目）
print(Counter(bool(t["limitations_ja"]) for t in tech))
```

スキルへの変換は [`../program/skill_pipeline_mapping.md`](../program/skill_pipeline_mapping.md) を参照。

---

## 7. 変更ポリシー

* `schema_version` は破壊的変更のときだけ上げる。フィールド追加はマイナー扱い。
* `id` は**変えない**。元カタログの ID が変わった場合は `original_id` を更新し、
  `id` は維持する（参照の安定性を優先）。
* `research/curated/` を変更したら、必ず再生成し、`manifest.json` の
  `inputs_sha256` と `validation_report.json` を更新する。
* カタログの内容を手で編集しない。編集は `scripts/build_research_catalog.py` の
  アダプタか、`research/curated/` の元データに対して行う。
* 元カタログの解釈を変える編集（例: `domains` の変更）は、
  `mapping_authorship` に理由を残す。

---

## 8. 限界

1. **内容の検証ではない**。構造が正しいことと、学術的に正しいことは別。
2. **網羅ではない**。韓国語・アラビア語・アフリカ諸語の創作論、商用ツールの内部実装、
   非公開の制作ノウハウは含まない。
3. **時点依存**。ツールのスター数・ライセンス・ベンチマーク結果は 2026-10 時点。
4. **編集上の分類**。`domains` と要約は本リポジトリの編集であり、原典の主張ではない。
5. **引用の安全性**。要約が原文に近い場合があるため、公表時は原典を確認し、
   引用ルールに従う。
