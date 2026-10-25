# 既存資料・創作技法の棚卸し（2026-10-25）

**対象:** このリポジトリの `052c8f2` 時点の採録資料、研究カタログ、13 スキル、検査器、実験用・創作プロジェクト用の工程。**今回は新規の外部調査やスキル実装をしていない。** 件数はリポジトリ内の JSONL と各スキルの技法参照表から数え直した。以下の「ある」は「資料としてある」「seed に紐づく」「検査器がある」「生成工程で使う」を区別する。

## 結論

- **技法の総当たり再調査は不要。** [採録判定](selection_report.md)は 34 成果物を採用 9・参照保持 21・除外 4 に分けている。採録した 88 ファイルから、[統一カタログ](../catalog/README.md)に技法等 488 件、分類体系 10 件、ツール索引 96 件、書誌 529 件がある。ただし、索引のツール 96 件を導入したという意味ではない。
- [13 件のスキル種](../program/skill_seeds.jsonl)は全件 `implemented`。各 seed に対応する `SKILL.md`、CLI、テスト、デモのパスが存在する。一方、標準の線形短編で設計書として作るのは **8 種**。分岐・翻案は**単独の検査器はあるが、標準の生成工程には未接続**である。コードが引用しながら技法表で説明していない ID は **4 件**あり、対応付けの確認が必要。
- 次に縦割りで確かめる候補は、すでに参照している**三幕・ビートシートによる外形設計**（`narrative/us_2026:T004`）。現在はプロット設計書の章割りを検査できるが、**そのプロットを本文生成用の章別メモには渡していない**。新しい定番技法を探す前に、この設計から本文への受け渡しを一件追うのが具体的である。これは**次の実装候補**であり、今回実装・効果実証したという意味ではない。

## 1. 資料がどこまで整理されているか

| 層 | 現状 | 根拠・読み方 |
| --- | --- | --- |
| 元資料の選別 | 採用 9・参照 21・除外 4、採録ファイル 88 | [採録判定](selection_report.md)、[成果物インベントリ](../inventory/artifacts.jsonl)、[採録物の来歴](../curated/README.md)。参照 21 件は保存済みだが、統一カタログへは**未正規化**。 |
| 機械可読カタログ | 技法等 488・分類 10・ツール 96・書誌 529 | [カタログの構成・限界](../catalog/README.md)。技法には手順だけでなく、型の索引や制作実務も含む。外部のツール一覧は利用可能なリポジトリ機能の数ではない。 |
| 追加調査の記録 | 既存の追加資料 24 件 | [ギャップ分析](gap_analysis_and_added_sources.md)、[記録](added_sources.jsonl)。AI 評価・長編生成・スキル規格などを対象とした**過去の調査**であり、今回の再検索ではない。 |
| 実行可能度の仕分け | `executable` 115・`partial` 290・`reference_only` 83 | [仕分けと方法](executability_report.md)、[データ](../catalog/executability.jsonl)。文字数・判定語等に基づく**レコードの記述の分類**。原典の品質、手法の効果、実装での合否や作品の質を表さない。 |
| スキル種が指す範囲 | 13 seed に紐づく技法 ID は計 191 記載、重複除去で **164 / 488**（48・100・16） | [seed](../program/skill_seeds.jsonl) と[仕分け](executability_report.md)。残りの **324 件は seed の参照外**だが、それだけで不足・不要とは決めない。seed のツール参照は重複除去で 8 件（96 件中）。 |
| スキル側の技法表 | 13 枚の `references/techniques.md` に計 130 行、重複除去で **110 ID** | 次節の表。seed の記載 191 件より狭い。**表への掲載＝すべてがプログラムで検査済み、ではない**（例: [`continuity-ledger` の未実装項目](../../skills/continuity-ledger/references/techniques.md)、[`voice-style` の標語](../../skills/voice-style/references/techniques.md)）。 |

未正規化の参照資料には、たとえば[日本の世界観構築](../curated/worldbuilding/japan/report.md)、[日本の人物造形](../curated/character/japan/report.md)、[日本の TRPG シナリオ](../curated/narrative/japan_trpg/report.md)、[欧州ゲーム制作](../curated/production/game_narrative_europe/report.md)がある。**対象となる作品形式を決めてから**関連する報告書を読む。参照資料を全件カタログ化したり、出典の強さを異なるカタログ間で同じ等級として比較したりはしない。

## 2. 13 スキルの参照と実行経路

件数は「seed の `technique_ids` の要素数／技法参照表の ID 行数」。同じ技法が複数スキルに現れるため、行の合計と重複除去件数は異なる。表の「接続」は**標準の線形短編の実験用工程**を主に示し、各スキル単独で CLI 実行できることとは別である。seed の実装パス・状態は[機械可読の記録](../program/skill_seeds.jsonl)、設計書の対象は[`DOCS`](../../src/asc/pipeline/design.py)、工程ごとの決定は[接続記録](spec_changes_2026-10-p4.md)を参照。

| スキル | seed 参照 | 技法表に掲載 | 現在の主な接続 |
| --- | ---: | ---: | --- |
| [premise-brief](../../skills/premise-brief/SKILL.md) | 7 | [7](../../skills/premise-brief/references/techniques.md) | Design: `brief` |
| [world-rules](../../skills/world-rules/SKILL.md) | 10 | [10](../../skills/world-rules/references/techniques.md) | Design: `world` |
| [history-timeline](../../skills/history-timeline/SKILL.md) | 12 | [10](../../skills/history-timeline/references/techniques.md) | Design: `history` |
| [character-core](../../skills/character-core/SKILL.md) | 15 | [12](../../skills/character-core/references/techniques.md) | Design: `character` |
| [relationship-web](../../skills/relationship-web/SKILL.md) | 9 | [9](../../skills/relationship-web/references/techniques.md) | Design: `relation` |
| [plot-architecture](../../skills/plot-architecture/SKILL.md) | 16 | [10](../../skills/plot-architecture/references/techniques.md) | Design: `plot` |
| [scene-information](../../skills/scene-information/SKILL.md) | 21 | [13](../../skills/scene-information/references/techniques.md) | Design: `scene`、一部を Draft に渡す |
| [voice-style](../../skills/voice-style/SKILL.md) | 33 | [11](../../skills/voice-style/references/techniques.md) | Design: `voice`、一部を Draft と S3 に渡す |
| [continuity-ledger](../../skills/continuity-ledger/SKILL.md) | 14 | [14](../../skills/continuity-ledger/references/techniques.md) | 本文と canon の監査（Audit） |
| [revision-loop](../../skills/revision-loop/SKILL.md) | 16 | [12](../../skills/revision-loop/references/techniques.md) | 実験用の S2 改稿・再監査 |
| [interactive-branch](../../skills/interactive-branch/SKILL.md) | 25 | [10](../../skills/interactive-branch/references/techniques.md) | [単独の分岐検査器](../../scripts/check_branch.py)。標準 Design の対象外 |
| [adaptation](../../skills/adaptation/SKILL.md) | 7 | [6](../../skills/adaptation/references/techniques.md) | [単独の翻案検査器](../../scripts/check_adaptation.py)。標準 Design の対象外 |
| [evaluation-harness](../../skills/evaluation-harness/SKILL.md) | 6 | [6](../../skills/evaluation-harness/references/techniques.md) | [別の評価コマンド](../../scripts/run_evaluation.py) |
| **合計（延べ）** | **191** | **130** | **実装済み 13 ≠ 標準 Design の 8** |

分岐検査は到達可能性、状態変数、結末への経路、合流等の**構造**を扱う。翻案検査は機能の対応、削除理由、権利の**記録状態**を扱う。いずれも選択の面白さや許諾の法的有効性は判定しない（[分岐の非目標](../../skills/interactive-branch/references/measurement.md)、[翻案の非目標](../../skills/adaptation/references/measurement.md)）。

**読み違えやすい過去資料:** [2026-10-23 の変換計画](../program/skill_pipeline_mapping.md)や[実行可能度の当時計画](executability_report.md)は実装前の優先順位を含む。現在の実装状態は seed、各スキル、[p2](spec_changes_2026-10-p2.md)・[p3](spec_changes_2026-10-p3.md)・[p4](spec_changes_2026-10-p4.md)と突き合わせる。この棚卸しでは、技法表の旧集計（character-core、interactive-branch、scene-information）と continuity-ledger の T033 の区分表記をカタログに合わせて訂正した。scene-information では、米国資料の T035（シーン化）は場面設計に転用し、T003/T036/T037/T038 の本文中の時間操作とは区別した。

### コードが引用する技法 ID と参照表の差

既存検査器の `Check.technique_ids` 等には、seed とカタログには存在するものの、該当スキルの技法参照表には載っていない **4 ID** がある。参照表の 130 行を「コードが引用する技法の全件」とも解釈できない。

| 検査器・項目 | 表にない ID | 確認が必要な点 |
| --- | --- | --- |
| [history `knowledge_consistent`](../../src/asc/history/check.py) | `narrative/us_2026:T053` | 元資料は反実仮想。知識地図の実在参照の根拠とした理由が参照表にない。 |
| [character `views_separated`](../../src/asc/character/check.py) | `narrative/japan_2026:T029` | 元資料は人物への面接。自己像／他者像の区分への対応が参照表にない。 |
| [plot `acts_cover`](../../src/asc/plot/check.py) | `narrative/japan_2026:T010` | 起承転結を章割り検査にどう位置付けるかの説明がない。 |
| [plot `debts_listed`](../../src/asc/plot/check.py) | `narrative/japan_2026:T015` | 全体・クエスト・場面の階層化を未回収の検査に使う説明がない。 |

いずれも**技法が未収録なのではなく、引用の対応付けを確認すべき箇所**である。この棚卸しでは引用 ID や検査ロジックを推測で書き換えず、個別の縦割り作業時に原資料と実装を照合する宿題として残す。コードの `technique_ids` も技法の効果の証拠ではない。

## 3. 次の縦割り候補（今回は未実装）

**線形短編を改善する場合の第一候補:** `narrative/us_2026:T004`（三幕・ビートシートによる外形設計）。[技法](../catalog/techniques.jsonl) → [seed-06](../program/skill_seeds.jsonl) → [技法表](../../skills/plot-architecture/references/techniques.md) → [`acts_cover` の構造検査](../../src/asc/plot/check.py) → [Design で `plot.json` を生成・検査](../../src/asc/pipeline/design.py)、まではある。`acts_cover` は幕が章を過不足なく覆うかを調べるだけで、三幕を強制したり物語上の効果を測ったりはしない。

**接続の切れ目:** [Draft が参照する章別メモ](../../src/asc/pipeline/design.py)は `scene.json` の場面の目的・対立・変化と、`voice.json` の視点行だけを抽出して[本文用プロンプト](../../prompts/draft-chapter.md)に渡す。`plot.json` の幕・転換点はそこで直接は渡さない（ただし合格した先行設計書は、場面設計時の入力には含まれ得る）。したがって**「プロットを作った」から「本文でその構成が実現した」とは言えない**。設計検査は修復上限後に `unresolved` でも続行する（[Design の実装](../../src/asc/pipeline/design.py)）。

次の作業に進むなら、**一技法に絞り**、(1) 章に必要な幕・転換点の情報だけを本文リクエストへ渡す条件を設計し、(2) デモ・回帰テストで「何を渡したか」と未解決設計書の扱いを確認し、(3) 同条件の L1 指標と失敗例を比較する。その後に初めて、不足している資料を特定して追加調査する。型の効果や本文の面白さを L1 で採点しない。

**もし目標が選択式作品なら**、第一候補は変わる。すでに[`interactive-branch`](../../skills/interactive-branch/SKILL.md)と日本資料の状態変数技法 `narrative/japan_2026:T094` があり、まず標準の線形工程とは別に「分岐設計→分岐本文→構造検査」の受け渡しを定義する必要がある。どちらの形式を進めるかが決まる前に、未正規化資料 21 件を一括で掘り返さない。

## 4. 検証方法と判断の限界

件数は次のように再計算できる（標準ライブラリのみ）。`references/techniques.md` の表行を数えるため、**掲載件数**であって実行された検査件数ではない。

```bash
python3 - <<'PY'
import json, re
from collections import Counter
from pathlib import Path

def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]

seeds = rows('research/program/skill_seeds.jsonl')
techniques = rows('research/catalog/techniques.jsonl')
tiers = {r['id']: r['tier'] for r in rows('research/catalog/executability.jsonl')}
seed_ids = [tid for s in seeds for tid in s['technique_ids']]
table_ids = [tid for s in seeds for tid in re.findall(
    r'^\|\s*`([^`]+)`\s*\|', Path('skills', s['name'], 'references/techniques.md').read_text(encoding='utf-8'), re.M)]
print('seed / table (extended, unique):', len(seed_ids), len(set(seed_ids)), len(table_ids), len(set(table_ids)))
print('catalog / tiers:', len(techniques), Counter(tiers.values()))
print('seed tiers:', Counter(tiers[tid] for tid in set(seed_ids)))
print('skill statuses:', Counter(s['status'] for s in seeds))
print('artifact decisions:', Counter(r['decision'] for r in rows('research/inventory/artifacts.jsonl')))
PY
python3 scripts/build_research_catalog.py --check
make ci
```

期待する主な集計は seed `191 / 164`、技法表 `130 / 110`、スキル `implemented: 13`。検証はファイルの存在・ID・構造と決定論的デモを確かめるもので、技法の有効性や作品の品質は確かめない。[現在の評価運用](../../docs/evaluation_scope.md)は **Arena.ai 経由の生成 × L1 のみ**。L2/L3 の実証・較正は凍結中で、G3/G4 は未測定、G5 の再現性は主張できない。[創作プロジェクトの通常実行](../../docs/project.md)も実験用 S2/S3 を自動適用しない。上の次候補は、その境界を守った**作業仮説**である。
