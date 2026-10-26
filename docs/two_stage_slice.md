# 二段階方式の最初の縦割りスライス（Phase 1〜2）

- 日付: 2026-10-26
- 対象: [`research/curation/two_stage_trpg_rewrite_direction_2026-10-26.md`](../research/curation/two_stage_trpg_rewrite_direction_2026-10-26.md) の §3 Phase 1〜2
- 実装: [`src/asc/gamelog/`](../src/asc/gamelog/)、[`scripts/check_gamelog.py`](../scripts/check_gamelog.py)、[`scripts/run_twostage.py`](../scripts/run_twostage.py)、[`prompts/stage-*.md`](../prompts/)
- 固定台本バンドル: [`experiments/2026-10-trpg-slice-t01/`](../experiments/2026-10-trpg-slice-t01/)

## 1. 目的と射程

現行の S1（`Plan → Design → Draft`）は、1 回の章生成に「状態管理（何が起きたか）」と「散文表現（どう語るか）」を同時に要求する。本スライスは、設計書を**事実の骨格**として確定する Stage A（`game_log.json`）と、确定した骨格を**視点・文体だけに集中して散文化する** Stage B に分離する。

`research/curation/../japan_trpg/report.md` の B2（フェイズ／シーン制）、B5（状況→行動→結果ループ）、C4（秘密の開示設計）を、既存の `canon` / `plot.json` / `scene.json` / `voice.json` の上にそのまま載せる。**新しいゲームエンジンは作らない。**

### 実装したもの

1. 章・場面単位の厳密な `game_log.json` スキーマ（`src/asc/gamelog/schema.py`）
2. `canon`・`plot.json`・`scene.json` に対する 8 種の決定論的検査（`src/asc/gamelog/check.py`）
3. `state_delta` から確定マーカー列を導出する純関数（`src/asc/gamelog/markers.py`）
4. Stage B 本文のマーカー・知識境界・人物境界・文体の検査（`src/asc/gamelog/rewrite.py`）
5. Stage A → 検査 → 修復 → **検証済みログのみ** Stage B → 検査 → 修復、の配線（`scripts/run_twostage.py`）
6. 固定台本（`scripted`）による決定論的な回帰テストと自己完結バンドル

### 実装していないもの（Phase 3 以降）

- 分岐・判定（ダイス）・状態変数による一般ゲームエンジン
- 物語途中の死亡イベント、章内の複数場所移動、1 章に複数場面をまたぐ語り直し
- 実モデル（Arena リレー）による応答の収集と L1 ペア比較。**今回は実施していない。**
- L2/L3 の評定・較正。引き続き `frozen_not_measured`。

## 2. 全体像

```text
[入力] canon/ (characters, facts, locations, timeline, foreshadowing, suppressions)
       design/plot.json (幕・転換点)  scene.json (目的/対立/変化/開示/伏線)  voice.json
          │
          ├─ 既存検査器 check_plot / check_scenes で現行 canon に対して再検証
          ▼
[Stage A] stage-a-gamelog.md → game_log.json
          │  決定論的検査 check_game_log（8 検査）→ 不合格なら stage-a-repair.md
          │  状態: clean のみ通過（fail-closed）
          ▼  emitted_markers = derive_markers(state_delta)
[Stage B] 章ごとに stage-b-rewrite.md（ログの該当章 + voice.json + 確定マーカー列）
          │  本文 → check_rewrite（4 検査）→ 不合格なら stage-b-repair.md
          ▼
[監査]    既存 continuity-ledger（audit_texts）＋ L1 衛生指標を記録
          （L2/L3 は実行しない）
```

Stage A と Stage B は **別の provider リクエスト**（`stage_a`、`stage_b:<章>`）として `responses.jsonl` に残る。修復ラウンドは `<purpose>:repair` として別記録されるため、初回出力と修復後出力を区別できる。

## 3. `game_log.json` スキーマ（`schema_version: "1.0"`）

| 階層 | 主な欄 | 意味 |
| --- | --- | --- |
| root | `task`, `notes`, `chapters` | 題材 ID と章列 |
| chapter | `id`, `day`, `location`, `emitted_markers`, `scenes` | canon の年表と一致する時点・場所 |
| scene | `scene_ref`, `act_ref`, `turn_ref` | `scene.json` / `plot.json` の ID への参照 |
| scene | `situation`, `purpose`, `conflict`, `change`, `tension`, `choice`, `outcome` | B5 のループと、棒読み化を防ぐ対立・選択の記録 |
| scene | `present_characters`, `actions`, `state_delta`, `emitted_markers` | 現在の登場人物・行為・状態更新・確定マーカー |

`actions` の型は 4 種だけ。

| 型 | 行為者 `actor` | `subject` | `medium` | 死者の扱い |
| --- | --- | --- | --- | --- |
| `action` / `dialogue` | 現在時に動く生存人物 | — | — | **禁止**。`present_characters` に死者がいれば `high` |
| `record_reference` | 記録を読む生存人物 | 言及される死者 | 潮札・石膏手形・帳面など | **許容**。`allowed_dead_references` に列挙 |
| `memory_mention` | 回想する生存人物 | 思い出される死者 | 回想 | **許容**。同上 |

`record_reference` / `memory_mention` は `subject` と `medium` を必須とする。媒体の宣言が無い場合、既有の文字列監査と同じく「回想か現在時行動か」を区別できなくなるため `high` で不合格にする。`state_delta` は `learned_facts` / `used_facts` / `foreshadow_events` / `location_moves` の 4 channel。

## 4. 確定マーカー列の導出

マーカーはモデルが散文を書きながら思い出すものではなく、**Stage A の状態遷移から機械的に決まる**。

```text
章:   {{time: day=<day>}}  {{location: <location>}}
場面: {{learn: <character> fact=<fact>}} ...        （learned_facts の順）
      {{use:   <character> fact=<fact>}} ...        （used_facts の順）
      {{foreshadow: <id> setup|payoff}} ...          （foreshadow_events の順）
```

- `derive_markers(log)` が全ログの順序付き列を返す。章の `emitted_markers` は章マーカー 2 件、場面の `emitted_markers` はその場面の `learn`/`use`/`foreshadow` だけを宣言する。
- 文字列は既有の `asc.story.text.MARKER_RE` と `continuity-ledger` の文法に一致するため、リライト本文はそのまま既存監査に通せる。
- `location_moves` は移動日数の検査に使うだけでマーカーを出さない（章の場所が章粒度で確定するというスライス上の制約）。
- Stage B 本文に含まれるマーカー列は、導出列と**文字列・順序まで完全一致**しなければならない。欠落・余分・順序差・未知種別はすべて `high`。

## 5. Stage A の決定論的検査（`check_game_log`）

| 検査 | 合格条件 | 主な根拠 |
| --- | --- | --- |
| `schema_shape` | 状況・目的・対立・変化・選択・結果・緊張が空でなく行為が 1 件以上 | `japan_trpg` B5 / `scene-information` |
| `canon_refs` | 章・人物・事実・場所・伏線が canon（または設計の planted）に存在し全章を覆う | `canon.py` |
| `design_alignment` | `scene_ref` / `act_ref` / `turn_ref` が該当章を指す。学習事実が `disclosed` / `gained` にあり `withheld` でない。設計の `paid` がその場面で回収される | `plot.json` / `scene.json` |
| `timeline_travel` | 章の `day` / `location` が年表と一致。章間と `location_moves` の経過が `travel_days` 以上 | `canon.py: travel_days()` |
| `presence_death` | 死者が `present_characters` / `action` / `dialogue` の actor に現れない。死者の言及は `record_reference` / `memory_mention` で `subject` + `medium` を宣言 | `characters.status / status_since` |
| `knowledge_boundary` | `use` は `knows` か過去の `learn` の後。`learn` は一度きり、canon の `setup` 章より前ではない | `canon.py: knows / facts.setup` |
| `foreshadow_order` | 回収は設置より後。canon の `setup` / `payoff` 章どおり。宣言された payoff はすべて回収 | `canon.py: foreshadowing` |
| `emitted_markers` | 宣言列 == 導出列（順序まで）。対応する marker 種別のみ | `markers.derive_markers` |

`high` / `medium` の所見は修復対象、`low` は情報提供。`plot.json` / `scene.json` が無い場合は `design_alignment` だけを `skipped` として報告する（既存の各検査器と同じ規約）。移動日数が未定義の組は判定せず `state.travel_pairs_skipped` に件数を残す。

CLI 単体でも実行できる。

```bash
.venv/bin/python scripts/check_gamelog.py \
  --game-log experiments/2026-10-trpg-slice-t01/inputs/game_log.json \
  --canon experiments/2026-10-trpg-slice-t01/inputs/canon \
  --design-dir experiments/2026-10-trpg-slice-t01/inputs/design \
  --require-design --markdown build/twostage/game_log.md
```

## 6. Stage B の決定論的検査（`check_rewrite`）

| 検査 | 合格条件 | 重要度 |
| --- | --- | --- |
| `marker_sequence` | 本文のマーカー列が導出列と完全一致。未知・余分な `{{...}}` なし | `high` |
| `character_boundary` | 本文に出る人物が `present_characters` か、宣言済みの死者言及だけ | 未宣言の死者 `high` / 未登場の生存者 `medium` |
| `fact_boundary` | 未開示事実の `terms`、この章で `withheld` の事実の語彙、死者の現在時状態マーカーがない | 語彙 `medium` / 死者マーカー `high` |
| `voice_contract` | `voice.json` の `banned`（正規表現）と題材の禁止語が出ず、本文が最低長以上 | `medium`（不正な正規表現は `low`） |

知識境界の語彙検査は**手掛かり**であって断定ではない（既存の `knowledge_violation` と同じく `medium`）。死者の現在時状態マーカー（`{{state: johan ...}}` 等）は文字列として厳密に検出できるため `high` にする。

Stage B プロンプトは `game_log.json` の**該当章だけ**と `voice.json` を渡し、前章本文は渡さない。設計書の結末・他章の幕・未開示の事実をプロンプトに含めないことで開示順序の先取りを抑える（[`plot_to_draft_2026-10-25.md`](../research/curation/plot_to_draft_2026-10-25.md) の知見）。

## 7. 配線と自己完結バンドル

```bash
.venv/bin/python scripts/run_twostage.py --task t01 \
  --canon experiments/2026-10-trpg-slice-t01/inputs/canon \
  --design-dir experiments/2026-10-trpg-slice-t01/inputs/design \
  --provider scripted \
  --script experiments/2026-10-trpg-slice-t01/scripted.json \
  --out experiments/2026-10-trpg-slice-t01/bundle \
  --results experiments/2026-10-trpg-slice-t01/results.json \
  --report-only --quiet
```

- `--out` は **`experiments/<id>/` 配下のみ**。`build/` と `runs/` は拒否する（セッション境界で消えるため）。
- 実行ごとに `<out>/<run-id>/` へ `inputs/`（canon・design・台本の固定コピー）、`responses.jsonl`、全プロンプト（`*.prompt.txt`）、`game_log.json`、`game_log.report.json`、`text/*.md`、`rewrite.report.json`、`audit.json`、`state.json`、`run-summary.json` を書く。入力は SHA-256 で固定し、`state.json` に記録する。
- Stage A が `clean` にならない場合、Stage B は**実行しない**（`stage_b.status: skipped`）。未検証のログを小説化しないための fail-closed ゲート。
- `--provider command` で Arena/chat operator を繋ぐ場合、回答待ちでは exit 3 で止まり、同じバンドルへ `PROMPTS.md` と `state.json` を書く。回答を `responses/<key>.json` に置いた後 `--resume --run-id <id>` で、記録済み応答を再生しつつ残りのリクエストだけを delegate する。プロンプトが変わった記録は再生せず stale として拒否する。
- `--results` はタイムスタンプと実行パスを含まない**決定論的な要約**で、コミット用。`run-summary.json` と `state.json` は run 固有の情報を含む。

固定台本の `scripted.json` は `$file` 参照で `inputs/game_log.json` と `inputs/rewrite/*.md` を指す。応答本文を二重に持たず、1 つの読みやすい入力をそのまま配線に使う。**この台本は実モデル応答ではない**（`_note` に明記）。

## 8. 観測されたこと（固定台本・1 条件のみ）

[`experiments/2026-10-trpg-slice-t01/results.json`](../experiments/2026-10-trpg-slice-t01/results.json) は配線確認の結果である。`scripted` の全応答が固定されているため、以下の数値は**検査器が期待どおり動いたことの確認**にすぎない。

- Stage A: 3 章 / 3 場面、8 検査すべて実行・0 所見、確定マーカー 19 件（`time` 3 / `location` 3 / `learn` 4 / `use` 3 / `foreshadow` 6）。死者 `johan` の記録・回想への言及 4 件を `allowed_dead_references` として許容し、現在時行動は 0 件。
- Stage B: 3 章すべて `clean`。各章の本文マーカー列が導出列と一致。
- 既存 `continuity-ledger`: 6 検査すべて実行。違反 3 件はすべて `dead_character_reappears`（`name_mention` 由来の `medium`）で、**`high` は 0 件**。これは [`plot_to_draft_2026-10-25.md`](../research/curation/plot_to_draft_2026-10-25.md) で指摘された既知の誤検出類型そのものであり、Stage B の `character_boundary` は同じ言及を「宣言済みの `record_reference` / `memory_mention`」として区別している。

**この差を L1 の改善として主張しない。** 台本は最初から整合するよう書かれており、直接生成（S1）との比較も、実モデルの応答も無い。実験の `note.md` に同じ限界を記録している。

## 9. 評価上の制約

- `configs/evaluation_scope.yaml` を読み込み、`results.json` に `active_layers: [L1]`、`frozen_layers: [L2, L3]`、`G3/G4: frozen_not_measured`、`claims.semantic_quality_or_human_preference: not_evaluated` を記録する。
- protocol-v1 のタスク・系（S0〜S3）・指標・閾値は変更しない。`system: "two-stage"` は実行台帳上のラベルであり、新しい「系」ではない。
- L1 は構造・衛生の検査であり、物語の質・面白さ・読者選好の証拠ではない。L2/L3 は `frozen_not_measured` のまま。Arena など版を固定できない経路では G5 を主張しない。
- 実モデルの応答が無い段階で、応答・スコア・効果を捏造しない。Phase 3 の L1 ペア比較は未実施。

## 10. Phase 3 への接続（未実施）

[`experiments/2026-10-plot-ablation-t01/paired/`](../experiments/2026-10-plot-ablation-t01/paired/) で確立した自己完結バンドルと `--ingest` / `--resume` のワークフローを使い、同一の共有 `canon` / `design`（`t01-s1-seed0`）の上で、直接生成（S1）と二段階方式の L1 各指標を**個別に**比較する。その際は次の点を先に解決する必要がある。

1. 共有設計書は 1 章に複数場面（9 場面）を持つため、Stage A が全設計場面を素材化できるようログを拡張するか、設計側をスライス用に絞るかを決める（現在の `design_alignment` は全設計場面の被覆を要求する）。
2. 直接生成は前章本文を入力に含むが、Stage B はゲームログだけを渡す。この入力差を条件として明示し、下流の媒介効果として記録する。
3. Arena のモデル版を固定できないため、結果は探索的参考値（1 ペア）に留め、G5 や作品品質の改善を主張しない。
