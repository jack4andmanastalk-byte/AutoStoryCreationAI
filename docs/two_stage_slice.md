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
| `character_boundary` | 本文に出る人物が `present_characters` か、**媒体を伴う**死者言及だけ。死者は、名前を含む**文**に宣言済みの媒体語（記録・遺物・回想）か参照の語彙（筆跡・手形・思い出 など）がある場合だけ許容 | 未宣言の死者・媒体のない言及 `high` / 未登場の生存者 `medium` |
| `fact_boundary` | 未開示事実の `terms`、この章で `withheld` の事実の語彙、死者の現在時状態マーカーがない | 語彙 `medium` / 死者マーカー `high` |
| `voice_contract` | `voice.json` の `banned`（正規表現）と題材の禁止語が出ず、本文が最低長以上 | `medium`（不正な正規表現は `low`） |

知識境界の語彙検査は**手掛かり**であって断定ではない（既存の `knowledge_violation` と同じく `medium`）。死者の現在時状態マーカー（`{{state: johan ...}}` 等）は文字列として厳密に検出できるため `high` にする。

死者の言及は**章スコープではなく文スコープ**で判定する。章に `record_reference` が 1 件あるだけでは、同じ章の「ヨハンが戸口から入ってきた」を通さない。逆に「ヨハンの筆跡が…」「ヨハンの手形だった」のように、名前を含む文に媒体語か参照の語彙があれば通す（媒体は `石膏手形` と `石膏の右手…手形` のように分かれて書かれうるため、2 文字の部分語も媒体語として扱う）。この規則は**語彙による近似**であり、「ヨハンが潮札を革袋に入れた」（媒体語と同じ文で死者が行為する）ような形は依然として通る。死者の現在時行動の完全な検出を主張しない。

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

本仕様の §5・§6 の表は「検査が何を問うか」を書いているが、コードが保証する範囲はそれより狭い箇所がある。詳細と再現は [`research/curation/two_stage_stage1_audit_2026-10-26.md`](../research/curation/two_stage_stage1_audit_2026-10-26.md) §4 に置いた。要点だけをここに残す。**実装は変更していない**（試走前の修正候補は同文書 §5）。

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

未着手（P1）: 同一場面 `learn`→`use` の偽陽性、未知キーの報告、現在時 `subject` の検査、死者の `used_facts`、
章順・章 ID 重複、現在地の連続性、`must_include` のゲート、`MIN_REWRITE_CHARS`、`PROMPTS.md` の未回答 1 件化。

§8 の「Stage B 3 章すべて `clean`」「既存監査の違反 3 件は既知の誤検出類型」という記述は**そのまま有効**だが、それは**検査が期待どおり動いたこと**の確認であり、意味的整合性の証明ではない。上記の穴は `make probe-gamelog`（`scripts/probe_gamelog_contracts.py`）で再現できる。
