# 技法カタログからスキル／ハーネスへ

**目的**: `research/catalog/` の知識を、実行可能な `SKILL.md` と評価ハーネスへ変換する設計。
**基準日**: 2026-10-23

---

## 1. 全体像

```
research/catalog/techniques.jsonl   ─┐
research/catalog/taxonomies.jsonl   ─┤  参照（必要なときだけ読む）
research/catalog/tools.jsonl        ─┘
             │
             ├─ skill_seeds.jsonl（13 種）──► skills/<name>/SKILL.md
             │                                   ├── references/  （技法の詳細・出典）
             │                                   ├── scripts/     （台帳検査・統計）
             │                                   └── assets/      （テンプレート）
             │
             └─ evaluation plan ─────────────► harness/
                                                 ├── rubrics/     （判定基準）
                                                 ├── cases/       （回帰用の入力）
                                                 └── run.py       （CI 実行）
```

**原則**:
1. カタログは**スキルの本文に埋め込まない**。`SKILL.md` から `references/` へリンクする。
2. スキルは**出力の検証条件**を持つ。検証できないスキルは未完成とみなす。
3. 決定論的に検査できるもの（台帳、禁止表現、構造）と、LLM 判定（質、面白さ）を**混ぜない**。
4. カタログの `evidence.level` は**スキル内で強さの主張に使わない**。

---

## 2. `SKILL.md` への変換規則

Agent Skills 仕様（<https://agentskills.io/specification>）に従う。

```yaml
---
name: continuity-ledger
description: 長編・連載の本文から人物の生死・所在・知識・時系列を抽出し、設定台帳と照合して矛盾を報告する。章を追加した後、矛盾が心配なときに使う。
license: MIT
compatibility: Python 3.11+; no network required
metadata:
  seed: seed-08-continuity-ledger
  catalog: research/catalog/techniques.jsonl
  version: "0.1"
---
```

* `name`: 1–64 字、小文字・数字・ハイフン。ディレクトリ名と一致。
* `description`: 1–1024 字。「何をするか」と「いつ使うか」を両方書く。
* 本文: **500 行未満 / 5,000 トークン未満**。手順・入出力・失敗時の扱い・検証条件。
* 詳細（技法の背景、出典、バリエーション）は `references/*.md` に分割。
* スクリプトは `scripts/`。出力だけがコンテキストに入る。

### 2.1 変換テンプレート

```markdown
# <スキル名>

## いつ使うか
- <トリガー>

## 入力
- <必須入力>
- <任意入力>

## 手順
1. <観察>
2. <判断>
3. <出力>

## 出力
- <成果物と形式>

## 検証（必須）
- [ ] <決定論的に検査できる条件>
- [ ] <人間/LLM が確認する条件>

## しないこと
- <アンチパターン>

## 参照
- `references/techniques.md`（対応する技法 ID と出典）
```

### 2.2 seed → スキルの優先順位

| 優先 | seed | 理由 |
| --- | --- | --- |
| 1 | seed-08 continuity-ledger | 決定論的に検査でき、効果測定が容易。既存ツール（story-skills, inkos）に参考実装がある。 |
| 2 | seed-13 evaluation-harness | 他のスキルの効果を測る基盤。先に作らないと改善ループが回らない。 |
| 3 | seed-01 premise-brief | 入力が小さく、出力の妥当性を人間が判断しやすい。 |
| 4 | seed-09 voice-style | 日本語の文体指標（三浦 2026）と接続できる。 |
| 5 | seed-02/03 world/history | 世界観・歴史の空白領域。ただし成果物が大きく、評価設計が重い。 |
| 6 | seed-04/05/06/07/10/11/12 | 既存ツール・カタログが厚い領域。後続でよい。 |

---

## 3. 工程への割り当て

| 工程 | スキル | 主な成果物 | 検査 |
| --- | --- | --- | --- |
| **Plan** | premise-brief, world-rules, history-timeline, character-core, relationship-web, plot-architecture, adaptation | ログライン、世界規則、年表、人物表、関係図、プロット、機能マップ | 因果の説明可能性、規則のコスト、年表の前後関係、人物の選択の一貫性 |
| **Do** | scene-information, voice-style, interactive-branch | 場面表、本文、分岐グラフ | 場面の変化、視点の逸脱、知識状態、到達可能性 |
| **Check** | continuity-ledger, evaluation-harness | 矛盾レポート、評価結果、失敗類型 | 台帳との照合、CED/選好/コミットメント |
| **Act** | revision-loop | 修正パッチ、再検査結果、未解決課題 | 修正の依存範囲、再発の有無 |

**注意**: これは理想的な直列工程ではない。実際の制作は Plan と Do の往復を含む。
スキルは工程の**ゲート**ではなく、必要なときに呼ぶ**検査可能な手続き**として設計する。

---

## 4. 評価ハーネスの設計

### 4.1 3 層に分ける

| 層 | 何を測るか | 実装 | 例 |
| --- | --- | --- | --- |
| **L1 決定論的** | 台帳との矛盾、禁止表現、構造、文字数、視点逸脱 | Python / 正規表現 / グラフ検査 | 死亡人物の再登場、伏線の回収順序、移動時間 |
| **L2 モデル判定** | 一貫性、関連性、読みやすさ、指示追従 | LLM-as-judge（根拠位置つき） | ConStory-Checker 型の誤り検出 |
| **L3 人間/選好** | 面白さ、独自性、感情的効果 | ペア比較、専門家評価 | LitBench 型のA/B、評定者属性の記録 |

**L1 で落とせるものを L2 に渡さない。** L2 は L1 の代替ではなく、意味の評価に限定する。

### 4.2 ルーブリックの例（v0）

```yaml
id: story-quality-v0
scale: 1-5
dimensions:
  coherence:
    question: 出来事の因果と時系列が、本文の情報だけで説明できるか。
    anchors:
      5: 主要な転換がすべて前の出来事に根拠を持つ。
      3: 一部の転換に説明が足りないが、読み進められる。
      1: 唐突な転換が複数あり、因果が追えない。
  character_consistency:
    question: 人物の選択が、設定された欲望・恐れ・知識と整合するか。
  world_rule_consistency:
    question: 世界の規則とコストが、都合よく変更されていないか。
  originality:
    question: 既存作品の定型の組合せを超えた固有の要素があるか。
  reader_orientation:
    question: 初見の読者が、人物・場所・目的を追えるか。
```

* 各次元に**根拠位置**（章・段落）を要求する。
* 総合点は出さない。次元ごとの分布と失敗類型を出す。
* 評定者（モデル名・版・温度・プロンプト）を記録する。

### 4.3 CI への載せ方

```yaml
# 例: promptfoo の場合
prompts:
  - file://prompts/scene_v3.txt
providers:
  - openai:gpt-5-mini
defaultTest:
  options:
    provider: openai:responses:gpt-5.4   # judge
tests:
  - vars:
      brief: cases/scene_001.md
    assert:
      - type: contains
        value: "灯台"
      - type: llm-rubric
        value: file://rubrics/story-quality-v0.md
```

* 決定論的検査は pytest（または `scripts/`）で先に実行。
* LLM 判定は**同じ入力・同じ順序**で再実行し、差分を比較。
* 失敗時は「どの次元が・どの根拠位置で・なぜ落ちたか」を出力する。

### 4.4 外部較正

| ベンチマーク | 何を較正するか | 使い方 |
| --- | --- | --- |
| ConStory-Bench | 整合性検査器の再現性 | 公開プロンプトの一部で、自前の検査器と CED を比較。 |
| LitBench | 選好判定器の人間一致率 | 公開ペアの一部で、判定器の一致率を測る。 |
| NCP-Bench | 長期対話のコミットメント保持 | 分岐スキルの検査項目が妥当か確認。 |
| WSE-bench | プロセス評価の設計 | 生成被覆・一貫性・豊穣さの指標を参考にする。 |

**注意**: ベンチマークのスコアを最適化することが目的ではない。
自前のパイプラインが**どの失敗類型で落ちるか**を知るために使う。

---

## 5. 実装例: continuity-ledger

### 5.1 入力

* 本文（章ごとのテキスト）
* `canon/characters/*.md`（YAML frontmatter に生死・所在・知識）
* `canon/timeline.md`
* `canon/foreshadowing.yaml`

### 5.2 出力

```json
{
  "run_id": "2026-10-23T12:00:00Z",
  "chapter": "ch07",
  "violations": [
    {
      "type": "dead_character_reappears",
      "severity": "high",
      "evidence": {"path": "ch07.md", "line": 184},
      "canon_ref": "canon/characters/aria.md#status",
      "message": "アリアは ch04 で死亡しているが、ch07 で発話している。"
    }
  ],
  "unresolved_foreshadowing": ["fs-012"],
  "knowledge_conflicts": []
}
```

### 5.3 検査

* 決定論的: 生死・所在・移動時間・伏線の順序・知識状態。
* モデル判定: 含意された矛盾（「知らないはずのことを示唆している」など）。
* 人間: 意図的な矛盾（信頼できない語り手、時間遡行）かどうかの最終判断。

### 5.4 失敗時の扱い

* `severity=high` は修正必須。`medium` は人間の確認。`low` は記録のみ。
* 意図的な矛盾は `canon/intentional_contradictions.yaml` に理由つきで登録し、再検出を抑制する。

### 5.5 実装した結果（2026-10-23）

上の設計から、実装時に次の 3 点を変えた。理由と検証は
[`../curation/spec_changes_2026-10.md`](../curation/spec_changes_2026-10.md) にある。

| 設計時 | 実装 | 理由 |
| --- | --- | --- |
| `canon/characters/*.md` の YAML frontmatter | `canon/characters.yaml` ほか 6 ファイル | 1 ファイルにまとめた方が、正解の全体を 1 回で読める |
| `canon/intentional_contradictions.yaml` | `canon/suppressions.yaml`（`reason` 必須） | 「除外」であることが名前から分かるようにした |
| 本文から状態を抽出 | 本文に `{{death: ...}}` などのマーカーを書く | 日本語の人称・省略により自動抽出は誤検出が多い |

| 成果物 | パス |
| --- | --- |
| スキル | `skills/continuity-ledger/SKILL.md`（詳細は `references/` 3 本） |
| ライブラリ | `src/asc/story/{canon,text,ledger,continuity}.py` |
| CLI | `scripts/audit_continuity.py`（終了コード 0/1/2） |
| デモ | `harness/cases/demo/`（矛盾 7 件＋意図的な矛盾 1 件、`EXPECTED.md`） |
| テスト | `tests/test_continuity.py`（14 件） |

### 5.6 evaluation-harness の実装

| 層 | 実装 | 停止条件 |
| --- | --- | --- |
| L1 | `src/asc/evaluation/metrics.py` ＋ 継続性監査 | high の違反が 1 件でもあれば fail |
| L2 | `src/asc/evaluation/judge.py`（外部コマンド／記録済み判定） | 根拠の無い判定は `unevidenced` として fail |
| L3 | `_calibrate`（人間ラベルの一致率） | 評定者 1 名なら警告 |

**総合点は出さない。** 回帰として扱うのは欠陥（CED・禁止パターン・次元得点）だけで、
文字数・会話率・段落長・文長 CV は記述統計として並べる。
CLI は `scripts/run_evaluation.py`、デモは `harness/cases/demo{-baseline}`。

---

## 6. アンチパターン

| アンチパターン | なぜ悪いか | 代わりに |
| --- | --- | --- |
| カタログ全文を `SKILL.md` に貼る | コンテキストを圧迫し、指示が薄まる。 | 要約＋`references/` へのリンク。 |
| 全技法を 1 つの「小説生成スキル」に統合 | 検証不能で、失敗の原因が特定できない。 | 工程・成果物ごとに分割。 |
| LLM に「矛盾を探して」とだけ頼む | 見落とし・幻覚・ばらつき。 | 台帳＋決定論的検査を先に。 |
| ベンチマークのスコアだけを最適化 | 画一化・過適合。 | 失敗類型の分布と人間評価を併用。 |
| 評価者を記録しない | 比較不能。 | モデル名・版・温度・プロンプト・評価者属性を保存。 |
| 参照資料の出典を落とす | 引用・検証ができない。 | `references/` に `source_ids` と URL を残す。 |

---

## 7. ロードマップ

| フェーズ | 成果物 | 完了条件 |
| --- | --- | --- |
| P1-a ✅ | `continuity-ledger` の `SKILL.md` と `scripts/audit_continuity.py` | 3 作品以上で、既知の矛盾を再現率高く検出。**デモ 1 作品で 7/7 を検出。作品数の拡充は未了。** |
| P1-b ✅ | `evaluation-harness` の L1 検査 + ルーブリック v0 | ベースラインとの比較で、改善/悪化を判定できる。**L2 は記録済み判定のみ（実モデル未接続）。** |
| P1-c ✅ | `premise-brief` / `voice-style` / `revision-loop` | 出力の検証条件を満たし、人間評価でベースライン以上。**構造検査のみ実装。意味の判定（L2 較正）は未実施。** |
| P1-d ✅ | 世界観・歴史スキル（`world-rules` / `history-timeline`） | 年表・規則の矛盾検出が動く。**canon との照合まで。** |
| P1-e ✅ | S2 改稿・S3 文体のパイプライン配線 | `run_pipeline --system s2/s3` が台本で完走。**実モデル未接続。** |
| P1-f ✅ | L2/L3 較正の道具（`judge_pairs` / `calibrate_judge`） | κ と判定器一致率の計算。**評定は未実施。** |
| P2 | 参照資料の昇格（世界観日本 22、キャラ日本 118） | カタログへ正規化し、スキルの `references/` に接続。 |
| P2 | 外部較正（ConStory/LitBench） | 自前検査器の一致率・再現性を記録。 |

---

## 8. 参考

* Agent Skills 仕様: <https://agentskills.io/specification>
* Anthropic Engineering: <https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills>
* promptfoo: <https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/llm-rubric/>
* Inspect AI: <https://inspect.aisi.org.uk/>
* ConStory-Bench: <https://arxiv.org/abs/2603.05890>
* LitBench: <https://arxiv.org/abs/2507.00769>
* NCP-Bench: <https://arxiv.org/abs/2608.08160>
* NstAgent: <https://arxiv.org/abs/2609.35759>
