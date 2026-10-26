# 二段階方式の最初の縦割りスライス（Phase 1〜2）

- 日付: 2026-10-26
- 対象: [`research/curation/two_stage_trpg_rewrite_direction_2026-10-26.md`](../research/curation/two_stage_trpg_rewrite_direction_2026-10-26.md) の §3 Phase 1〜2
- 実装: [`src/asc/gamelog/`](../src/asc/gamelog/)、[`scripts/check_gamelog.py`](../scripts/check_gamelog.py)、[`scripts/run_twostage.py`](../scripts/run_twostage.py)、[`prompts/stage-*.md`](../prompts/)
- 固定台本バンドル: [`experiments/2026-10-trpg-slice-t01/`](../experiments/2026-10-trpg-slice-t01/)

## 1. 目的と射程

現行の S1（`Plan → Design → Draft`）は、1 回の章生成に「状態管理（何が起きたか）」と「散文表現（どう語るか）」を同時に要求する。本スライスは、設計書を**事実の骨格**として確定する Stage A（`game_log.json`）と、確定した骨格を**視点・文体だけに集中して散文化する** Stage B に分離する。

`research/curation/../japan_trpg/report.md` の B2（フェイズ／シーン制）、B5（状況→行動→結果ループ）、C4（秘密の開示設計）を、既存の `canon` / `plot.json` / `scene.json` / `voice.json` の上にそのまま載せる。**新しいゲームエンジンは作らない。**

### 実装したもの

1. 章・場面単位の厳密な `game_log.json` スキーマ（`src/asc/gamelog/schema.py`）
2. `canon`・`plot.json`・`scene.json` に対する 8 種の決定論的検査（`src/asc/gamelog/check.py`）
3. `state_delta` から確定マーカー列を導出する純関数（`src/asc/gamelog/markers.py`）
4. Stage B 本文のマーカー・知識境界・人物境界・文体・明示日数の検査（`src/asc/gamelog/rewrite.py`）
5. Stage A → 検査 → 修復 → **検証済みログのみ** Stage B → 検査 → 修復、の配線（`scripts/run_twostage.py`）
6. 固定台本（`scripted`）による決定論的な回帰テストと自己完結バンドル
7. 移動日数・章の日・滞在日数の**決定論的な導出**（`src/asc/gamelog/world.py`）と、その表を渡す Stage B 配線（§14）

### 実装していないもの（Phase 3 以降）

- 分岐・判定（ダイス）・状態変数による一般ゲームエンジン
- 物語途中の死亡イベント、章内の複数場所移動、1 章に複数場面をまたぐ語り直し
- 実モデル（Arena リレー）による応答の収集と L1 ペア比較。**今回は実施していない。**
- L2/L3 の評定・較正。引き続き `frozen_not_measured`。
- モデル自身にツールを呼ばせて日付・移動を決めること（§14.5、往復の契約を作り直す必要があるため見送り）。

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
          ▼  timeline.json = derive_timeline(log, canon)   ← 日数・場所・順序の確定値
[Stage B] 章ごとに stage-b-rewrite.md（ログの該当章 + voice.json + 確定マーカー列
          + この章の時系列表）
          │  本文 → check_rewrite（5 検査）→ 不合格なら stage-b-repair.md
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
| `schema_shape` | 状況・目的・対立・変化・選択・結果・緊張が空でなく行為が 1 件以上。章 ID の重複と canon と違う章順は `high`。未知キーは `low` で報告 | `japan_trpg` B5 / `scene-information` |
| `canon_refs` | 章・人物・事実・場所・伏線が canon（または設計の planted）に存在し全章を覆う | `canon.py` |
| `design_alignment` | `scene_ref` / `act_ref` / `turn_ref` が該当章を指す。学習事実が `disclosed` / `gained` にあり `withheld` でない。設計の `paid` がその場面で回収される | `plot.json` / `scene.json` |
| `timeline_travel` | 章の `day` / `location` が年表と一致。章間と `location_moves` の経過が `travel_days` 以上。移動の起点が当人の直前の現在地と繋がり、登場人物が章の場所にいる | `canon.py: travel_days()` / `characters.location` |
| `presence_death` | 死者が `present_characters` / `action` / `dialogue` の actor **と `subject`** に現れない。死者の言及は `record_reference` / `memory_mention` で `subject` + `medium` を宣言 | `characters.status / status_since` |
| `knowledge_boundary` | `use` は `knows` か `learn` の後（同一場面の `learn` → `use` は `low` で許容）。`learn` は一度きり、canon の `setup` 章より前ではない。死者の `use` は `high` | `canon.py: knows / facts.setup` |
| `foreshadow_order` | 回収は設置より後。canon の `setup` / `payoff` 章どおり。宣言された payoff はすべて回収 | `canon.py: foreshadowing` |
| `emitted_markers` | 宣言列 == 導出列（順序まで）。対応する marker 種別のみ | `markers.derive_markers` |

`high` / `medium` の所見は修復対象、`low` は情報提供。**未知キーは黙って捨てず `low` で報告する**（綴り誤りで検査が弱まるのを防ぐため。値は読み飛ばすので修復ループは止まらない）。`plot.json` / `scene.json` が無い場合は `design_alignment` だけを `skipped` として報告する（既存の各検査器と同じ規約）。移動日数が未定義の組は判定せず `state.travel_pairs_skipped` に件数を残す。

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
| `character_boundary` | 本文に出る人物が `present_characters` か、**媒体を伴う**死者言及だけ。死者は、名前を含む**文**に宣言済みの媒体語（記録・遺物・回想）か参照の語彙（筆跡・手形・思い出 など）がある場合だけ許容 | 未宣言の死者・媒体のない言及 `high` / 未登場の生存者 `medium` |
| `fact_boundary` | 未開示事実の `terms`、この章で `withheld` の事実の語彙、死者の現在時状態マーカーがない | 語彙 `medium` / 死者マーカー `high` |
| `voice_contract` | `voice.json` の `banned`（正規表現）と題材の禁止語が出ず、本文が最低長以上 | `medium`（不正な正規表現は `low`） |
| `timeline_consistency` | 本文に書かれた**明示的な日数**（「N日ぶり」「N日目」「N日後」「N日かけて」）が、ログから導出した時系列の許容値に含まれる | `medium`。既定は**警告のみ**（修復しない）。`--strict-timeline` のときだけ修復対象 |
| `missing_must_include`（作品単位） | 題材の必須語が**作品全体**に現れる。章ごとの検査が通っても、欠ければ Stage B 全体を `unresolved` にする | `medium`（run の状態） |

知識境界の語彙検査は**手掛かり**であって断定ではない（既存の `knowledge_violation` と同じく `medium`）。死者の現在時状態マーカー（`{{state: johan ...}}` 等）は文字列として厳密に検出できるため `high` にする。

死者の言及は**章スコープではなく文スコープ**で判定する。章に `record_reference` が 1 件あるだけでは、同じ章の「ヨハンが戸口から入ってきた」を通さない。逆に「ヨハンの筆跡が…」「ヨハンの手形だった」のように、名前を含む文に媒体語か参照の語彙があれば通す（媒体は `石膏手形` と `石膏の右手…手形` のように分かれて書かれうるため、2 文字の部分語も媒体語として扱う）。この規則は**語彙による近似**であり、「ヨハンが潮札を革袋に入れた」（媒体語と同じ文で死者が行為する）ような形は依然として通る。死者の現在時行動の完全な検出を主張しない。

題材の必須語（`must_include`）は protocol-v1 の L1 指標であり、章ではなく**作品**に対する条件なので、`run_twostage.py` が全章を書き終えた後に `missing_must_include` で 1 回だけ判定する（章単位にすると、その語を別章で使う設計を誤って落とす）。長さの下限は既定 200 字で、これは空文の検出用であり、プロンプトの目標 1,000〜1,400 字は合否に使っていない（`results.json` の `l1_hygiene.length_gate` に明記）。

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
- `--provider command` で Arena/chat operator を繋ぐ場合、回答待ちでは exit 3 で止まり、同じバンドルへ `PROMPTS.md` と `state.json` を書く。回答を `responses/<key>.json` に置いた後 `--resume --run-id <id>` で、記録済み応答を再生しつつ残りのリクエストだけを delegate する。プロンプトが変わった記録は再生せず stale として扱い（`replay.report.json` に件数を残す）、`response_sha256` が一致しない記録は再生せず停止する。
- **再開の契約**（P0 修正済み）:
  - `state.json` の `resume_command` は、実行に必要な全引数（`--script` / `--command` / `--stage` / `--game-log` / `--seed` / `--temperature` / `--max-attempts` / `--results`）を含む。そのまま実行できることをテストで確認している。
  - provider の失敗・入力の不合格でも `state.json` を書く（`status: failed` / `unresolved` と `error`）。部分的な `responses.jsonl` が再開不能な形で残らない。
  - `--resume` は `responses.jsonl` を切り詰めない（同じ内容を原子的に書き直してから追記する）。再開が途中で失敗しても既存の記録は残る。
  - `--resume` は `task` / `system` / `stage` / `seed` / `temperature` / `max_attempts` / `provider` / `protocol_version` と、入力ハッシュ（canon・design・script・game-log・プロンプト）を比較し、不一致は `exit 2` で拒否する。意図的な変更は `--allow-config-change` で続行でき、差分は `state.json` の `config_changes` に残る。
  - 再生された応答は `responses.jsonl` に二重追記しない（`replay.report.json` に `replayed` / `stale` / `missing` の件数を残す）。
- **Stage の選択**（P0 修正済み）: `--stage both|a|b` と `--game-log <path>`。
  - `--stage b --game-log <path>` は Stage A を**実行しない**。与えたログをこの場で `check_game_log` にかけ、`clean` のときだけ Stage B に渡す（不合格なら `exit 2` で fail-closed。`--allow-unverified-log` を明示した場合だけ続行し、`game_log.report.json` と `run-summary.json` に `unverified: true` を残す）。入力ログは `inputs/game_log.input.json` に固定コピーし、SHA-256 を `state.json` に記録する。
  - `--stage a` は Stage A だけを実行し、`stage_b.status: skipped` を残す。
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

## 11. 第1段階の点検（2026-10-26）で判明した契約と実装の差

本仕様の §5・§6 の表は「検査が何を問うか」を書いているが、**点検した時点**のコードが保証する範囲はそれより狭い箇所があった。詳細と再現は [`research/curation/two_stage_stage1_audit_2026-10-26.md`](../research/curation/two_stage_stage1_audit_2026-10-26.md) §4 に置いた。以下は**点検時の記録**であり、P0 は §11.1、P1 は §11.2 で修正済み。修正後も残る穴（意味的整合性・自由記述・語彙の近似）はそのまま有効である。

- **現在地の連続性**: `canon` の `Character.location` はどの検査からも参照されない。`location_moves` は `travel_days` との日数と章 day の前後だけを見る。移動の起点・連結・その人物が実際にその章にいるかは未検査。
- **死者の現在時行動**: 現在時型（`action` / `dialogue`）の `subject`、`summary` / `text` の自由記述、`target` の部分一致は走査しない。Stage B 側の許容判定は**章スコープ**で、その章に 1 件でも記録言及があれば同じ死者の現在時行動も通る。短い別名（2 文字未満）は人物境界の走査対象外。
- **学習と使用の順序**: `known` は場面をまたいで蓄積されるが、**同一場面内では `used_facts` を `learned_facts` より先に判定**するため、同一場面の `learn` → `use` が `high` の偽陽性になる。
- **設計との照合**: `design_alignment` が比較するのは ID・章・`tension`・開示/保留の事実集合・`paid` の有無。場面の `purpose` / `conflict` / `change` の**文面は比較しない**（`schema_shape` は空でないことだけを見る）。
- **マーカーと本文の事実**: `marker_sequence` は文字列と順序だけを見る。本文が事実を否定・省略・言い換えていても、マーカーが残っていれば `clean`。`fact_boundary` は `canon.facts[].terms` の部分文字列一致で、言い換え・含意による漏洩は捕まらない（変異プローブでは、事実を否定・省略した本文も `clean` になる）。
- **厳密ローダー**: 型の誤りは拒否するが、**未知キーは黙って捨てる**。綴り誤りは検査を弱める方向に働く。
- **再開と記録保全**: `state.json` の `resume_command` に `--script` / `--seed` などが入らず、そのままでは失敗する。provider 失敗時は `state.json` を書かないため `--resume` できない。`--resume` は冒頭で `responses.jsonl` を空にする。`config` の比較は入力ハッシュ 3 種のみで、`seed` を変えた再開は記録済み応答を捨てて再要求する。


### 11.1 第1段階 P0 の修正（同日、実装済み）

点検で挙げた P0 のうち、次を実装した。**意味的整合性の保証は変わっていない**（B-03〜B-05・A-08 などの仕様上の制限は残る）。

| 項目 | 変更 | 確認 |
| --- | --- | --- |
| P0-1 | `resume_command` に全引数を入れ、`state.json` に `argv` を残す | `test_resume_command_is_complete_and_executable`、プローブ R1（rc=0） |
| P0-2 | 失敗・不合格でも `state.json` を書く（`status: failed` / `unresolved`） | `test_a_provider_failure_still_writes_resumable_state`、プローブ R4 |
| P0-3 | `--resume` で `responses.jsonl` を切り詰めない（原子的に書き直して追記） | 同テスト（中断後も 2 行が残る） |
| P0-4 | `config` 全項目と入力ハッシュを比較し、不一致は `exit 2`。`--allow-config-change` で続行＋記録 | `test_resume_with_a_different_seed_is_refused_and_can_be_allowed`、プローブ R3 |
| P0-5 | `BundleProvider` が `response_sha256` を照合。不一致は停止。再生は二重追記しない | `test_a_modified_recorded_response_is_refused`、プローブ R2 |
| P0-6 | 死者言及を**文スコープ**で判定（媒体語か参照の語彙を要求） | `test_dead_mention_needs_its_medium_in_the_same_sentence`、プローブ B1 |
| P0-7 | `--stage b --game-log` を追加。Stage A を実行せず、与えたログを再検査してから Stage B へ | `test_stage_b_only_rewrites_a_verified_log_without_calling_stage_a` ほか |

台本経路の結果は変わらない: Stage A `clean`（8 検査・0 所見）、Stage B 3 章 `clean`、確定マーカー 19 件。
`results.json` は `inputs` に `game_log_sha256: null` が加わったため再生成した（他は不変）。

P1（全工程試走の前）: P0 の直後に §11.2 で実施した。

### 11.2 全工程試走前 P1 の修正（同日、P0 の後）

| 項目 | 変更 | 確認 |
| --- | --- | --- |
| P1-1 | 同一場面の `learn` → `use` を許容（場面内では `learned_facts` を先に反映。許容した場合は `low`） | `test_same_scene_learn_then_use_is_allowed`、プローブ A5 |
| P1-2 | 未知キーを拒否せず `low` で報告（読み飛ばしは維持） | `test_unknown_keys_are_reported_not_dropped`、`test_unknown_keys_are_kept_for_reporting`、プローブ A8 |
| P1-3 | 現在時型（`action` / `dialogue`）の `subject` を検査（死者 `high` / 生存者 `low` の型混同） | `test_present_tense_subject_is_checked`、プローブ A3 |
| P1-4 | 死者の `used_facts` を `high` | `test_a_dead_characters_knowledge_use_is_high`、プローブ A4 |
| P1-5 | 章 ID の重複を `high`（名指し）、canon と違う章順を `high`（重複があるときは順序の所見を出さない） | `test_chapter_ids_and_order_are_named`、プローブ A9・A10 |
| P1-6 | 現在地の連続性: 移動の起点が直前の現在地と繋がるか（`high`）、登場人物が章の場所にいるか（`medium`）、登場しない人物の移動（`medium`） | `test_current_location_and_movement_chain_are_checked`、プローブ A7 |
| P1-7 | 題材の必須語を**作品単位**でゲート（`missing_must_include`）。章ごとの検査が通っても欠ければ Stage B は `unresolved` | `test_a_missing_required_word_fails_the_work_not_the_chapter`、プローブ B7 |
| P1-8 | `--min-chars` を追加（既定 200 は空文検出用）。目標長 1,000〜1,400 字は合否に使わないことを `l1_hygiene.length_gate` に明記 | `test_committed_bundle_summary_is_reproducible`（値を固定） |
| P1-9 | `PROMPTS.md` は未回答の 1 件だけを載せ、回答済みは件数だけを書く | `test_prompts_md_lists_only_the_unanswered_request` |

`--min-chars` の値を上げれば長さをゲートできるが、固定台本は約 300 字で書かれており、
既定を上げると台本経路の記録が変わる。試走条件として別途決める。

§8 の「Stage B 3 章すべて `clean`」「既存監査の違反 3 件は既知の誤検出類型」という記述は**そのまま有効**だが、それは**検査が期待どおり動いたこと**の確認であり、意味的整合性の証明ではない。上記の穴は `make probe-gamelog`（`scripts/probe_gamelog_contracts.py`）で再現できる。

## 12. Stage B 単独の実応答試走（2026-10-26、1 件）

[`experiments/2026-10-stageb-solo-t01/`](../experiments/2026-10-stageb-solo-t01/note.md) で、
`--stage b --game-log` に t01 の検証済みログを与え、Stage A を呼ばずに 3 章を実応答で書いた。
回答は `relay/` に置き、章ごとに `--resume` で続行している（4 要求・resume 5 回）。

| 項目 | 値 |
| --- | --- |
| Stage A | 実行せず。与えたログを再検査して `clean`（`source: provided`、`attempts: 0`） |
| Stage B | ch01 / ch02 は 1 回で `clean`、ch03 は 1 回不合格 → 修復 1 回で `clean` |
| 文字数 | 1,152 / 1,023 / 1,006（計 3,181） |
| マーカー | 6 / 7 / 6。すべて導出列と一致 |
| 既存 continuity 監査 | 違反 3 件（`dead_character_reappears` / `medium`）、CED 8.373/10k |

- **誤検出 1 件**: ch03 の「書いたのはヨハンだった。」は、直前の文で潮札の筆跡に触れている記録への
  言及だが、文スコープの判定は同じ文に媒体語を要求するため `high` になった。修復は 1 か所のみ。
- **検出漏れ（人手で発見、いずれも `clean` のまま）**: 「四日ぶりの灯台」（実際は六日）、
  「片方だけでは灯りは消せない」（題材の前提と矛盾）、「二本ぶんの空き」（直後の記述と不一致）、
  ch01 の「鍵は二本ある」（F-02 は ch02 開示。ただし fs-001 の setup と同文面）、
  ch02 のアリアの現在地（`characters.json` は `灯台` のまま）。
- したがって **`clean` は「ログの事実と整合している」ことを意味しない**。§11 の穴は実応答でも
  そのまま現れた。
- 品質・面白さは未測定（L2/L3 `frozen_not_measured`）。版を固定できないため G5 は主張しない。
  `results.json` の `claim` は provider ごとに切り替わり、relay run では「実応答だが再現可能な
  モデルではない」と明記される。

## 13. 全工程試走（Stage A → Stage B、実応答、2026-10-26）

[`experiments/2026-10-full-t01/`](../experiments/2026-10-full-t01/note.md) で、Stage A（構造化ログ）と
Stage B（本文）をどちらも実応答で通した。1 run 目をそのまま残し、人手照合で見つけた誤り 1 件を
直した 2 run 目を続けて置いている。

| 段 | 状態 | 試行 | 修復 | 内容 |
| --- | --- | --- | ---: | --- |
| Stage A | `clean` | 1 | 0 | 8 検査・所見 0・3 章 3 場面・マーカー 19 件・死者言及の許容 4 件 |
| Stage B | `clean` | 1 / 1 / 1 | 0 | 1,032 / 1,007 / 1,008 字（計 3,047）。マーカー 6 / 7 / 6 で一致 |
| 必須語 | 1.0 | — | — | 灯台・鍵・嵐。`missing_must_include` は空 |
| 既存監査 | 6 検査 | — | — | 違反 2 件（`dead_character_reappears` / `medium`）、CED 5.799/10k |

`relay/` の回答だけで新しい run-id から同じ 3 章（同じ字数・同じ状態）を作り直せることを確認した。
run 出力はコミットしていない。

### 13.1 人手照合で見つかった検出漏れ

| 箇所 | 内容 | 通した理由 |
| --- | --- | --- |
| ch03 | 「四日ぶりの灯台」— day 1 出発・day 7 帰着なので六日 | 日数・現在地の検査はログ側だけで、散文を読まない |
| ch02 | 「手の甲に古い火傷の跡」— canon にもログにもない | 人物境界は名前だけを見る |
| ch01 | 「刻みの深さはそれぞれ違う」— ログは三つの刻みとだけ書く | ログにない細部の追加は検出対象外 |
| ch02 | 「半日だけずれていた」— ログは突き合わせるだけで差の量を宣言しない | 数値の捏造は語彙一致では捕まらない |

いずれも契約 2（ログにない事実を足さない）に反するが `clean` のまま通った。
**`clean` は本文がログの事実と整合していることを意味しない**という §9・§12 の結論が、Stage A を含む
全工程でもそのまま再現した。

### 13.2 2 run 目の意味

`四日ぶり`→`六日ぶり` の修正後も、状態・章ごとの所見・文字数（3,047）・必須語・既存監査の違反数は
**1 run 目と完全に同じ**である。「2 run 目も `clean`」は「直った」ことの証拠にならない。
機械的に観測できたのは「配線が通り、修復なしで 4 要求が完走した」ことまでで、
本文の事実の正しさは人手照合でしか判定していない。

### 13.3 この試走で言えること・言えないこと

- 言える: Stage A → B が実応答で 1 周し、決定論的検査（マーカー・人物境界・事実境界・必須語）が
  生成物に対して働き、`relay/` から再現できる。
- 言えない: 実モデル一般が契約を守れること。生成者と検査実行者が同一で、生成側は合格条件を読んでいる。
  品質・面白さ（L2/L3）と G5 は主張しない。S1 との比較は未実施。
- 次に必要: 本文側の現在地・日数（今回の M-1）を機械的に近づけるか、人手照合を手順として固定するか。
  後者を選ぶ場合、照合の観点と記録様式を試走ごとに同じにする。

## 14. 日数・場所・順序の権威を決定論側へ移す（2026-10-26）

§13.1 の検出漏れ M-1（ch03 の「四日ぶり」）は、**言語モデルに計算させていた**ことの症状だった。
日数・現在地・時系列は、物語の創作物ではなく canon とログから決まる値である。そこで「決める」役割を
決定論側へ移し、モデルには**決まった値を渡す**だけにした。3 層に分けて持ち場を明示する。

| 層 | 何を決めるか | 実装 | 失敗したときの扱い |
| --- | --- | --- | --- |
| 権限 | 移動日数（`travel_days`）・章の日・経過日数・滞在日数 | `src/asc/gamelog/world.py` の `World` / `derive_timeline` | 決定論。推定しない（未知の場所対は `None`） |
| 受渡し | 確定値を Stage B に渡す | `timeline.json`（派生成果物）＋プロンプトの `$timeline` | 表が無ければ検査は `skipped` |
| 検証 | 本文に**書かれた**数字が表と合うか | `check_rewrite` の `timeline_consistency` | `medium`。既定は警告、`--strict-timeline` で修復対象 |

### 14.1 `timeline.json` は派生成果物

`scripts/run_twostage.py` は Stage A が検証を通った直後に

```python
timeline = derive_timeline(log, canon, build_world(canon))
```

を実行し、run ディレクトリへ `timeline.json`（`schema: trpg-timeline-v1`）を書き出す。中身は
章ごとの `day` / `location` / `elapsed_since_previous` / `days_until_next`、登場人物ごとの
`days_since_leaving_here` / `days_since_arriving_here`、`state_delta.location_moves` から畳んだ
移動（`depart_day` / `arrival_day` / `days` / `required_days`）、そして `travel_days` の全対最短経路。

* 入力は canon と `game_log.json` だけ。**同じ 2 つからは同じ表が出る**（テストで文字列一致を確認）。
* 手で編集しない。直すべきはログか canon で、表は毎回作り直す。
* `run-summary.json` と `results.json` には表そのものではなく要約（章ごとの日・場所・滞在日数と
  SHA-256）を入れる。`results.json` の他の欄は変えていない。

`World` は `locations[].travel_days` を**無向**の重み付きグラフとして読み、`travel_days(a, b)` を
Dijkstra の最短経路で返す。対称表なので両方向を登録し、同じ対に違う値があれば**小さい方**を採る
（別経路があるのに移動不能になるのを避ける）。**繋がっていない対は `None`** を返し、勝手に距離を
作らない。`None` はそのまま「検査できない」として `skipped` に落ちる。

### 14.2 二段構え — ログ側は厳密、本文側は抽象化を許す

利用者の判断（2026-10-26）どおり、**ログの時系列は厳密に、読み物としての本文は抽象化を許す**。

* ログ側（`check_game_log`）は従来どおり厳密。移動日数は `travel_days` と照合し、章の日は単調に進む。
* 本文側（`timeline_consistency`）が見るのは**明示された数字だけ**。「N日ぶり」「N日目」「N日後」
  「N日かけて」を拾い、種類ごとに別の許容集合と比べる（「ぶり」は滞在日数、「目」は章の日、
  「後」は経過、「かけて」は移動日数）。
* 「しばらく」「明け方」「数日」「翌日」「一週間」のような抽象表現は**対象外**で、`skipped` として
  数えるだけ。数字を書かない文は**失敗ではない**。章が時系列を口にすることも要求しない。
* 「N日ぶり」の N は**その場所を離れてからの日数**なので、`days_since_leaving_here` と比べる。
  到着日からの日数と混同しないよう、種類ごとに許容値を作り直している。

つまり契約は「**明示した数字は表と一致させる**」であって「**表を本文に書かせる**」ではない。
抽象化は文体の選択であり、検査の対象ではない。

### 14.3 警告を既定にした理由（`--strict-timeline`）

数字の拾い方は語彙による近似なので、偽陽性が出る（「半日だけずれていた」のような数量は拾わないが、
「三日分の食料」のような言い回しは将来拾いうる）。既定で修復を強制すると、正しい本文を語彙の都合で
書き換えさせることになる。そこで

* 既定: `medium` の**警告**。`findings` には残るが `blocks_repair` が `False` なので修復しない。
  `rewrite.report.json` の `warning_findings` と `timeline: {checked, skipped, strict}` で見える。
* `--strict-timeline`: 同じ所見が修復対象になり、直らなければ章は `unresolved`。

`results.json` の `timeline.strict` にどちらで回したかが残る。既定と厳密を混ぜた比較をしないため、
run の条件（`config`）にも `strict_timeline` を含め、`--resume` の条件一致判定にも入れてある。

### 14.4 実データでの確認

全工程試走の実ログ（`experiments/2026-10-full-t01/relay/`）から導出した表:

| 章 | 日 | 場所 | 前章から | アリア：この場所を離れてから |
| --- | ---: | --- | ---: | ---: |
| ch01 | 1 | 灯台 | — | 0（到着も 0） |
| ch02 | 4 | 王都 | 3 | 0 |
| ch03 | 7 | 灯台 | 3 | **6** |

`make probe-gamelog` の B8 で、ch03 に 1 文だけ足して 3 通りを比べた（2026-10-26 実行）:

| 足した文 | 既定（警告） | `--strict-timeline` |
| --- | --- | --- |
| 「六日ぶりの灯台だった。」 | `clean` / 警告 0 / checked 1 | `clean` |
| 「四日ぶりの灯台だった。」 | `clean` / 警告 1（許容: 6 日）/ checked 1 | `unresolved`・blocking 1 |
| 「しばらくぶりの灯台だった。」 | `clean` / 警告 0 / checked 0・skipped 1 | `clean` |

§13.1 の M-1 は、既定でも**報告される**ようになった（修復はしない）。ただし M-2〜M-4
（ログにない細部・数値）は依然として検出対象外で、`clean` が意味的整合を意味しないことは変わらない。

### 14.5 やらなかったこと — ツール呼び出し（第 3 段、未実施）

モデル自身に `travel_days` や `derive_timeline` を**呼ばせて**値を決める設計は、今回は採らない。

* `GenerationRequest` / `GenerationResult` は単発往復で、`BundleProvider` の再生契約
  （`prompt_hash` + `response_sha256`、`--resume`）は「1 プロンプト = 1 応答」を前提にしている。
  ツール往復を入れると 1 リクエストが手順列になり、記録・再生・`--resume` の意味を作り直す必要がある。
* 今の時点でモデルが**選ぶ**値は無い。章の日・場所・移動は canon とログで既に決まっており、
  渡せば足りる。ツール呼び出しが効くのは、新しい場所・未定義の対・分岐する日付をモデルが決める
  段階（Phase 3 以降）で、そのときは手順列として設計し直す。

したがって今回の変更は**受渡しの追加と検証の追加**であって、生成の自由度は増やしていない。
L1 の値（`must_include`・legacy 監査・CED）も、protocol-v1 の系・指標・閾値も変えていない。
新しい所見は `medium` の警告として `rewrite.report.json` にだけ増える。

## 15. S1 直接生成との L1 参考比較（2026-10-26）

[`experiments/2026-10-l1-pair-t01/`](../experiments/2026-10-l1-pair-t01/note.md) で、**同じ canon・
同じ設計書**から本文を書く 2 条件を同じ L1 指標で並べた。二段階方式（検証済みログ → 本文）と、
`run_pipeline.py --system s1 --stage draft --canon … --design-dir …` による直接生成である。
後者は S1 全体ではなく、plan と設計を固定して draft 段だけを比べたもの。

| 指標 | 二段階 | 直接生成（draft 段） |
| --- | ---: | ---: |
| 文字数（マーカー除く） | 3,047 | 3,313 |
| 必須語率 / 題材の禁止語 | 1.0 / 0 | 1.0 / 0 |
| 禁止パターン密度 / 1 万字 | 0.0 | 0.0 |
| 連続性監査の違反（未実行検査） | 2 `medium`（0） | 3 `medium`（0） |
| CED / 1 万字 | 5.799 | 8.217 |
| マーカー（time/location/learn/use/foreshadow） | 19（3/3/4/3/6） | 16（3/3/4/0/6） |
| 会話率 / 平均段落字数 / 文長 CV | 0.007 / 181.5 / 0.425 | 0.047 / 93.6 / 0.469 |

数値は `scripts/compare_l1_arms.py` が既存の L1 関数（`measure`・`find_forbidden`・
`audit_texts`）で計算し、[`results.json`](../experiments/2026-10-l1-pair-t01/results.json) に残す。
二段階の腕は relay に記録された応答から抽出した本文で、抽出値は `2026-10-full-t01` の記録
（3,047 字・CED 5.799・違反 2）と一致する。

### 15.1 読み取れること

* **L1 は 2 条件を識別しない。** 必須語・禁止語・禁止パターン・未実行検査は両腕で同じ。
  `2026-10-arena-l1-t01`（S0–S3）で「パターン集合だけでは生成系を区別できない」と記録したのと
  同じ結果が、二段階方式と直接生成のあいだでも出た。
* **差は指標ではなく検査可能性にある。** ログがある腕では、マーカー列・人物境界・事実境界・
  移動日数を機械的に照合できる。ログがない腕には照合先がなく、人手照合で見つかった 4 件
  （写しの保管場所、父の行為、刻みのずれの数値化、石膏手形の細部）は「検出漏れ」にすらならない。
* **`clean` の意味は変わらない。** 二段階の腕にも、ログが宣言していない細部（§13.1 の M-2〜M-4）が
  入っていた。直接生成の腕にも同種の追加がある。どちらの腕でも、構造検査の通過は意味的整合の
  保証ではない。
* 直接生成の腕は `use` マーカーを 1 つも書かなかった。ただしこれは自己申告の記録であり、
  本文に「事実を使った」場面が無いことの証明ではない。

差（文字数 +266、平均段落字数 −88、会話率 +0.04）は記述統計である。段落の切り方と台詞の量は
当方の書き方の癖で、方式の効果として解釈しない。

### 15.2 この比較で言えないこと

* 二段階方式のほうが本文が正確・面白い。**N=1・単一タスク・同一著者**で、条件差と著者の癖を
  分離できない。L2/L3 は測っていない。
* S1 全体（plan → 8 設計 → draft）との比較。設計を固定したため、設計段の出来は入っていない。
* 二段階の腕を**現在のプロンプト**（v1.1）で再生成した場合の同一性。記録済み応答は v1.0 の
  プロンプトで生成されており、`prompt_hash` が変わるため replay は exit 4 で拒否される
  （これは再生契約の意図どおりの動作で、欠陥ではない）。

次は「ログがある腕にしかできない検査」の検出力を測る段になる。既知の変異（誤った日数・
未宣言の死者言及・ログ外の移動）を直接生成の本文に注入し、二段階の検査器が何件拾えるかを
数える形で、検出漏れと誤検出を同じ様式で残す。

## 16. プロンプト v1.1 での再生成（2026-10-26）

[`experiments/2026-10-stageb-v11-t01/`](../experiments/2026-10-stageb-v11-t01/note.md) で、§14 の
`$timeline` を入れた Stage B（v1.1）を使い、**同じ検証済みログ**から 3 章を作り直した。
`--stage b` の単独実行で、入力ログは `2026-10-full-t01` の Stage A 実応答（与えた時点で再検査し
`clean`）。したがって v1.0 との差はプロンプトに由来する。

| 章 | 試行 / 修復 | 文字数 | マーカー | 時系列検査 | 状態 |
| --- | --- | ---: | --- | --- | --- |
| ch01 | 1 / 0 | 1,043 | 6 / 6 | checked 0・skipped 1 | `clean` |
| ch02 | 2 / 1 | 989 | 7 / 7 | checked 1・skipped 2 | `clean` |
| ch03 | 1 / 0 | 835 | 6 / 6 | checked 1・skipped 1 | `clean` |

- 必須語 1.0、禁止語 0、禁止パターン 0、未実行検査 0。既存監査の違反 1（`medium`、既知の誤検出）、
  CED 3.059。v1.0 は 3,047 字・違反 2・CED 5.799 だった（どちらも N=1 の記述統計）。
- **日数の扱いは変わった。** v1.0 の 1 run 目は ch03 で「四日ぶり」と誤った（§13.1 の M-1）が、
  v1.1 は「六日ぶり」と書き、`timeline_consistency` が照合して不一致 0 で通した。導出表
  （`アリア: この場所を離れてから 6日`）がプロンプトに載っている。
- **修復が 1 回入った。** ch02 の初回が「三年前」— F-04 の語彙 — を使い、`fact_boundary`（`medium`）
  で止められた。修復でその一語を外している。v1.0 の ch02 はこの語を使っていないため発火していない。
  ログの `outcome` 自体が「三年前」と書いているのに本文では禁じられる、という仕様のねじれが見えた。
- **長さは目標に届かなかった。** ch02 989 字・ch03 835 字は 1 章 1,000〜1,400 字の目安を下回る。
  `--min-chars` 200 の下限は満たすので `clean` だが、タスクの目標帯には 2,867 字で届いていない。
  これは書き手の長さの管理の問題で、プロンプトの効果として解釈しない。
- 言えないこと: 導出表を渡せば日数の誤りが一般に防げる、とは言えない（N=1・同一著者・著者は
  契約文と検査器を読んでいる）。既定では誤った日数は**警告**であって修復されないため、
  「報告される」ことと「直る」ことは別である。`--strict-timeline` での挙動は別に記録する。
- 記録の意味: v1.0 の記録は `prompt_hash` が変わったため replay できない。この run が現在の
  プロンプトに対する**有効な記録**であり、`relay/` から同じ 3 章を再生成できることを確認している。

## 17. 検査の検出力 — 既知の誤りを注入して数える（2026-10-26）

`clean` は「誤りが無い」ではなく「修復を要する所見が無い」である（§9・§13.1 の結論）。では
**どの誤りなら捕まえられるのか**を、既知の誤りを 1 つずつ注入して数えた:
[`experiments/2026-10-detect-power-t01/`](../experiments/2026-10-detect-power-t01/note.md)。
腕は 2 つ、どちらも同じ t01 の本文である。ログを見て書いた腕（v1.1 の Stage B、`clean`）と、
見ずに書いた腕（S1 draft、`pass`）。

| 注入した誤り | ログを見た腕 | 見ない腕 |
| --- | --- | --- |
| ch03「六日ぶり」→「四日ぶり」 | `timeline_consistency`（`medium`） | 同じ |
| 死者が現在時に行動する一文 | `character_boundary`（`high`） | 同じ |
| 保留事実 F-04 の語「三年前」 | `fact_boundary`（`medium`） | 発火せず（ベースラインで既に発火） |
| ログにない場所と船旅 | 発火せず | 発火せず |
| ログが宣言しない数量「半日」 | 発火せず | 発火せず |

* **語彙と日数で決まる誤りは、本文の作り方に依存せず捕まる。** 3 種は両腕で同じ検査が発火した。
* **ログを見ずに書いた本文は、ログ契約を当てると既に 3 件の所見を持つ。** 「三年前」（F-04 の語）が
  ch01・ch02 に早出しされ、ch03 では `present_characters` にいないボリスに言及している。どれも
  `medium` で、検出できない類のものではない。**検査が走っていないので通っていた**（§15 の
  「差は指標ではなく検査可能性」の中身）。
* **ログにない場所・移動と、宣言のない数量は、どちらの腕でも検出できない。** §13.1 の M-2〜M-4 と
  同じ穴で、§14 の時系列照合では塞がっていない。塞ぐには場所名・数量を本文から抽出してログと
  突き合わせる別の検査が要る（未実装。L1 で足せるか L2 相当になるかの切り分けが先）。
* `marker_sequence` は比較から外した。直接生成の腕は導出マーカー列を要求されていないため
  ベースラインで必ず落ち、内容の所見を覆い隠す（3 章とも落ちることは `results.json` に残した）。

実施は `scripts/probe_detection_power.py`（腕は relay の応答ディレクトリ、`--game-log` は
`2026-10-stageb-v11-t01/inputs/game_log.json`）。1 本文 1 注入なので、**発火しなかったことは
盲点の証明ではなく、この言い回しでの記録**である。

`--strict-timeline` の効果は v1.1 の試走で確認した（[§16](../experiments/2026-10-stageb-v11-t01/note.md)）。
ch03 を意図的に「四日ぶり」にすると、既定では `clean`＋警告 1 で通り、`--strict-timeline` では
`unresolved`・修復 1 回。**strict は線を動かすだけで、誤りそのものを直すのは修復の側**である。

## 18. 残った 2 つの穴に対する候補検査（2026-10-26）

§17 で「どちらの腕でも検出できない」と分かった 2 種（ログにない場所・移動、ログが宣言しない数量）
に対して、L1 のまま検査を作れるかを試作して測った:
[`experiments/2026-10-surface-checks-t01/`](../experiments/2026-10-surface-checks-t01/note.md)。
実装は `src/asc/gamelog/surface.py` で、**`check_rewrite` からは呼ばない**（契約の外）。

**地名（候補検査）**

* 「〈場所らしい語〉へ／に ＋ 移動動詞」だけを移動の主張として拾い、地名の接尾辞（港・島・町・塔…）で
  非場所を落とす。目的地が canon にもログにも無ければ `medium`、canon にあるがこの章の移動として
  宣言されていなければ別の文言で `medium`（いずれも `advisory: true`）。
* clean な 6 章（2 腕 × 3 章）で**所見 0**、注入した「対岸の島へ渡った」は**1 件検出**。
  小さな標本だが、移動の主張に絞ったことで精度が保てている。
* 拾えるのは**移動を明言した文**だけ。「対岸の島が見えた」や、地名を出さない移動は対象外。

**数字（報告のみ）**

* 数詞＋助数詞を拾い、ログ・canon に同じ表記が無いものを一覧にする。注入した「半日」は一覧に
  現れるが、clean な本文でも 1 章あたり 2〜4 個の数詞（`一本`・`一枚`・`一度`・`一晩`）が並ぶ。
* 理由は、**数詞に指示対象が無い**こと。「環には一本」の `一本` は事実の主張ではなく、
  「刻みは四つ」の `四つ` はログにない追加の細部である。表記の一致では区別できない。
  区別には「何の数を言っているか」を読む必要があり、それは語彙照合ではなく意味の照合（L2 相当）。
* したがって**数字は検査として実装しない**。報告関数だけ残す。

**採否**

* 地名は候補として採用に値するが、まだ契約に入れない。次は `advisory` のまま
  `rewrite.report.json` に載せて偽陽性を集める段（合否には使わない）。
* 数字は L1 では入れない。必要なら L2 の設計として切り分ける（凍結中なので実施しない）。

**限界**: 偽陽性 0 は 6 章での観測であって偽陽性率ではない。地名抽出は接尾辞と移動動詞に依存し、
「霧の岬」のような接尾辞の無い固有名は拾えない。数字の報告は文字列一致で、値の比較はしていない。

## 19. 地名検査の言い換え耐性と、実本文が見つけた欠陥（2026-10-26）

§18 の地名候補は「1 つの言い回し・clean 6 章」でしか測っていなかった。語彙の校正として、
clean 本文を 9 章に増やし、言い換えと紛らわしい文の固定表 18 件で測り直した:
[`experiments/2026-10-surface-checks-t02/`](../experiments/2026-10-surface-checks-t02/note.md)
（`scripts/probe_surface_variants.py`、`schema: surface-variants-v1`）。

* **clean 9 章で所見 0**。ただし主張の抽出は働いており、`direct` ch03 の「灯台」、v1.0 ch01 の
  「王都」は拾われたうえで（滞在地・宣言済みの移動先として）許容された。抽出と判定が別だと分かる。
* **言い換え 6/6 発火**（に／へ、別の動詞、期間句つき、節つき、未宣言の canon 地名）。
  **紛らわしい文 12/12 沈黙**（「話に戻った」「島が見えた」「台所へ行った」など）。
* **実本文が欠陥を見つけた**: v1.0 の「三日かけて王都へ着いた」で、目的地が `三日かけて王都` と
  して抽出され偽陽性になっていた。節の境界に `て` が無かったため期間の句が地名に食い込んでいた。
  `_CLAUSE_SPLIT_RE` に `て` を足して `王都` になり、9 章の所見は 0 に戻った。t01 の `results.json`
  は再生成しても同一である。
* **採否は変えない（まだ契約に入れない）**。「canon にあるが、この章の移動として宣言されていない」
  枝は、章の外の移動（回想・伝聞・到着済みの前提）を偽陽性にする。v1.0 ch01 は宣言済みだったため
  今回は助かっただけで、次に観測で集めるべきはこの枝の事例である。
* **限界**: 18 件はこちらが書いた文で、実本文の分布ではない。6/6・12/12 は「この 18 文で期待どおり」
  以上の意味を持たない。取りこぼし（「歩いた」「霞んで見えた」）は仕様上の限界で、表に残してある。

## 20. 観測モード: 候補検査を契約の外で走らせる（2026-10-26）

§19 で「事例を集めるまで地名検査は採らない」と決めたので、集める仕組みを先に作った:
[`experiments/2026-10-surface-observe-t01/`](../experiments/2026-10-surface-observe-t01/note.md)
（`schema: surface-observe-v1`）。

* `check_rewrite(..., observe_surface=True)` は報告に `observations` / `observation_summary` を足す。
  **既定は無効**で、無効ならキー自体が存在しない（既存の記録は変わらない）。
  `scripts/run_twostage.py --observe-surface` が走りから通す。
* 観測は `findings` に入れないので、`status`・重大度・修復判定に触れない。同じ scripted バンドルを
  2 回走らせて、`status`・`findings`・`checks` が**完全に一致**することを確認した
  （ch01〜ch03 の `clean`、`observations` はオンの走りにだけ存在）。
* ログ外の旅を ch01 に注入すると、フラグ無しは `clean` / 所見 0、`--observe-surface` も
  `clean` / 所見 0 で、**観測だけが 1 件**（`対岸の島`）増える。
* **見つかった穴**: `place_findings` は `advisory: True` しか持っておらず、既存の `needs_repair` は
  「`REPAIR_SEVERITIES` かつ `blocks_repair` が真」で判定する。つまり観測を `findings` に混ぜるだけで
  修復が走っていた。各項目に `blocks_repair: False` を明記して塞いだ。
* **限界**: 測ったのは scripted の本文で、実モデルの文章ではない。観測は事例を集めるだけで率を測らない。
  L2/L3 は `frozen_not_measured`、G5 は未達、protocol-v1 は不変。

## 21. バッチ A: 実モデル 3 標本の事前登録（2026-10-26）

§18〜§20 で検査の側は「実本文が足りない」ところまで来た。地名観測の枝も、二段構成の価値も、
長さの目安割れも、根拠は 3 走り・9 章（同一 canon）しかない。そこで**コードを足す前に**、
小さな実走りを 1 巡することにし、走らせる前に判定規則を固定した:
[`experiments/2026-10-realrun-a-t01/`](../experiments/2026-10-realrun-a-t01/note.md)。

* 条件: Stage B のみ・プロンプト v1.1・`--observe-surface`・canon/design/log は同バンドルの `inputs/`
  （ログは走行前に `check_gamelog.py` で clean を再確認）。3 標本（`sample-1`〜`3`）。
* **事前登録**: [`preregistration.json`](../experiments/2026-10-realrun-a-t01/preregistration.json)。
  判定は 3 つだけ。R1 地名の枝（`no_examples` / `drop_undeclared_branch` / `narrow_branch_only` /
  `inspect_both`。**blocking 化は決めない**）、R2 長さ（1,000〜1,400 字が 3 章中 2 章以上か）、
  R3 繰り返す失敗（2 標本以上で落ちた検査）。
* **計測**: `scripts/measure_realrun_a.py` が登録ファイルの `sha256` を結果に記録し、閾値もそこから読む
  （結果を見て規則を書き換えたかどうかが残る）。`results.json` は現在 `not_run`（標本 0）。
* **手順**: [`runbook.md`](../experiments/2026-10-realrun-a-t01/runbook.md)。生成は
  `scripts/chat_operator.py` のリレー（記録された実テキスト）。初回は `--resume` を付けない
  （付けると exit 2）。リレー送信ディレクトリは標本ごとに分ける。
* **プロンプトの事前書き出し**: `scripts/export_stageb_prompts.py` が 3 章ぶんを
  `prompts/`（`ch0N.prompt.md`・`ALL.md`・`index.json`）に出す。描画はパイプラインと同じ関数
  （`run_twostage.stage_b_rewrite_prompt`）を使い、初回の実要求と**バイト一致**することを確認した
  （ch01 `prompt_hash` = `ab8be3c448d7e96d`、v1.1 の実走りと同値）。seed はプロンプトに入らないので
  3 標本のプロンプトは同一で、**違いは回答だけ**になる。
* **主張しないこと**: L2/L3 は `frozen_not_measured`、G5 は operator 方式では到達しない、
  面白さは測らない、観測は事例であって率ではない、応答の独立性は保証されない。
