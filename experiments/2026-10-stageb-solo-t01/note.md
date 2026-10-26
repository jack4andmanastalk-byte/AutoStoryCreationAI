# Stage B 単独試走（実応答 1 件） — t01 / 検証済みログ / seed 0

- 日付: 2026-10-26
- 種類: **Stage B 単独の実応答試走**。Stage A は実行していない。入力ログは
  [`2026-10-trpg-slice-t01`](../2026-10-trpg-slice-t01/) で検証済みの固定ログ（`inputs/game_log.json`）を
  そのまま与えた。
- 前提条件: [`research/curation/two_stage_next_steps_2026-10-26.md`](../../research/curation/two_stage_next_steps_2026-10-26.md)
  §4 の順序（P0 修正 → scripted 配線確認 → **Stage B 単独の実応答** → 全工程試走）。
- 決定論的要約: [`results.json`](results.json)

## 目的

1. `--stage b --game-log` が **Stage A を呼ばずに** 検証済みログから本文だけを作れること。
2. 実応答（固定台本ではない本文）が Stage B の決定論的検査を通るか、通るとき何を見落とすか。
3. 回答待ちで停止し、回答を置いて `--resume` で続行する往復が、章ごとに成立すること。

**「良い小説が書けた」ことの記録ではない。**品質・面白さ・読者選好は測定していない（L2/L3 は `frozen_not_measured`）。

## バンドルの中身

```text
inputs/canon/            6 チャネル（死者 johan を含む。t01 と同一ハッシュ）
inputs/design/           plot.json / scene.json / voice.json と実検査器の report（t01 と同一）
inputs/game_log.json     Stage A 検証済みログ（t01 のログ、sha256 5894e3dd…667e）
relay/requests/          4 件（ch01 / ch02 / ch03 / ch03 修復）のプロンプト全文
relay/responses/         4 件の回答（本文全文＋prompt_hash＋provenance）
results.json             実行に依存しない決定論的要約（コミット用）
note.md                  本文書
```

生の run 出力（`<out>/<run-id>/`）はコミットしない。`results.json` と `relay/responses/` から
同じ本文・同じ検査結果を作り直せる。

## 手順（実際に起きたこと）

```bash
# 1. 回答なしで起動 → ch01 のプロンプトが relay/requests に書かれ、exit 3 で停止
.venv/bin/python scripts/run_twostage.py --task t01 \
  --canon experiments/2026-10-stageb-solo-t01/inputs/canon \
  --design-dir experiments/2026-10-stageb-solo-t01/inputs/design \
  --stage b --game-log experiments/2026-10-stageb-solo-t01/inputs/game_log.json \
  --provider command \
  --command "$PWD/.venv/bin/python scripts/chat_operator.py --dir experiments/2026-10-stageb-solo-t01/relay" \
  --out experiments/2026-10-stageb-solo-t01 --run-id stageb-t01-s0 --seed 0

# 2. relay/responses/<key>.json に本文を置き、--resume（章ごとに 1 往復）
#    … 3 章 + ch03 の修復 1 回 = resume 5 回
.venv/bin/python scripts/run_twostage.py ... --resume --results experiments/2026-10-stageb-solo-t01/results.json
```

- 回答は 4 件。`prompt_hash` を固定して置いたため、プロンプトを変えた場合は stale として再要求される。
- Stage A は 1 度も呼ばれていない（`stage_a.source: "provided"`、`attempts: 0`、`limits` にその旨を記録）。
- 各章の応答は 1 回で書き、**ch01・ch02 は 1 回で合格**、ch03 は 1 回不合格 → 修復 1 回で合格。

## 回答の来歴

| 項目 | 値 |
| --- | --- |
| provider | `command` → `scripts/chat_operator.py`（relay ディレクトリ経由） |
| 記録された model / model_version | `arena-agent-mode` / `unversioned-2026-10-26` |
| 生成の仕方 | Arena の対話エージェントが各章 1 回で生成（プロンプトは本バンドルの `relay/requests/` と同一） |
| 独立性 | **なし**。同じエージェントが生成と検査実行の両方を行った。検査器は決定論的だが、生成側の事前知識（検査項目を読んでいる）は排除できていない |
| 再現性 | なし。G5 は主張しない（`results.json` の `claim` と `gate_status.G5`） |

`results.json` の `claim` は provider ごとに切り替わる（scripted = 配線確認、command = relay run）。
以前は scripted 用の文言が固定で、relay run にも「not a model response」と書かれていたため、
本試走に合わせて分岐を入れた。

## 結果（L1 のみ）

| 項目 | 値 |
| --- | --- |
| Stage A（与えたログの再検査） | `clean` / 8 検査 / 0 所見 / マーカー 19 件（`source: provided`） |
| Stage B | 3 章すべて `clean`（ch01 1 回・ch02 1 回・ch03 2 回） |
| 文字数 | ch01 1,152 / ch02 1,023 / ch03 1,006（計 3,181） |
| マーカー | 6 / 7 / 6 — すべて導出列と完全一致 |
| 必須語 | 灯台・鍵・嵐 すべて 1 章以上に出現（rate 1.0） |
| 禁止語 | 0 件 |
| 既存 continuity 監査 | 6 検査すべて実行。違反 3 件（`dead_character_reappears` / `medium`）、CED 8.373/10k、`high` 0 件 |

`dead_character_reappears` の 3 件は、ヨハンの名前が記録・遺物の文に現れたことによる既知の
誤検出類型（`2026-10-plot-ablation-t01` と同じ）。Stage B の `character_boundary` は同じ箇所を
`record_reference` / `memory_mention` として区別している。**この差を L1 の改善として主張しない。**

## 検査器が実際に止めたこと（1 件）

ch03 の 1 回目は次の 1 件で `high` になり、修復ラウンドに入った。

```text
[high] character_boundary: 死者 ヨハン（ヨハン）の言及に、宣言された媒体（潮札）も
参照の語彙も同じ文にない。現在時の行動として読めるため不合格。
```

該当文は「書いたのはヨハンだった。」— 直前の文で潮札の筆跡について述べており、**意味としては
記録への言及**である。文スコープの判定は媒体語を同じ文に要求するため、この文だけを切り出すと
落ちる。修復は「潮札に書いたのはヨハンだった。」と 1 か所だけ直し、他の文は変えていない。

- これは**検査器の偽陽性**（正当な記録言及を現在時行動と誤認）であり、同時に
  **文スコープにした設計の副作用**でもある。章スコープ（P0-6 以前）なら通っていた。
- 実応答 1 件で 3 章中 1 章が修復に入った、という頻度の記録ではあるが、N=1・同一エージェント
  生成なので頻度の推定には使わない。

## 検査器が通した意味的な誤り（人手で読んだ結果）

いずれも **`clean` のまま通っている**。マーカー・必須語・禁止語・知識境界の語彙検査では捕まらない。

1. **日数の不整合（現在地・移動の連続性）**: ch03 に「四日ぶりの灯台」と書いた。ログでは
   ch01 day 1 出発 → ch02 day 4 到着 → ch03 day 7 帰着なので、灯台を離れていたのは六日。
   カノンの `Character.location` はどの検査からも参照されず、`location_moves` は日数の前後関係
   しか見ないため、この誤りは検出されない。
2. **事実の推論による矛盾**: ch02 に「だから片方だけでは、灯りは消せない」と書いた。題材の前提は
   「鍵を貸したら灯りが消された」であり、この推論は前提と食い違う。マーカーは `learn`/`use` とも
   残っており、`marker_sequence` も `fact_boundary` も通る。
3. **数え方の不一致**: 同じ ch02 で「空いた場所の幅が二本ぶん」と書きながら、直後に
   「一本は灯台に、一本はこの店に預けられている」と書いた。事実の整合は人手でしか見ていない。
4. **保留事実の言い換え**: ch01 で「鍵は二本ある」と書いた。F-02（setup ch02）の内容の一部だが、
   `fact_boundary` が見るのは `terms`（`予備の鍵`）だけなので一致しない。かつ fs-001 の setup が
   同じ文言を ch01 に置くため、**保留と伏線設置が同じ文面で重なる**。どちらが正しい扱いかは
   設計側の判断が要る（本試走ではどちらとも決めていない）。
5. **視点人物の現在地**: ch02 のアリアは王都にいるが、`characters.json` の `location` は `灯台` の
   まま。このフィールドを読む検査は無い（第1段階の点検 A-01 と同じ）。

したがって本試走は、**「L1 が `clean` を返すこと」と「本文がログの事実と整合していること」が
別である**ことの実例になっている。緑のテストを整合性の証拠にしない、という第1段階の結論を
実応答でも確認した形である。

## 非主張・未実施

- 実モデルの品質・面白さ・読者選好は未測定（L2/L3 `frozen_not_measured`、G3/G4 は未達とも合格とも記録しない）。
- G5（同一 seed・同一出力）は主張しない。`model_version: unversioned-2026-10-26` は版の同定ではない。
- Stage A の実応答は無い（入力ログはファイルとして与えた）。`--stage a` の実応答試走と
  全工程試走（Stage A から 3 章 3 場面）は未実施。
- P1 の未修正項目はそのまま（同一場面 `learn`→`use` の偽陽性、未知キー、現在時 `subject`、
  死者の `used_facts`、章順・章 ID 重複、現在地の連続性、`must_include` のゲート、
  `MIN_REWRITE_CHARS`、`PROMPTS.md` の未回答 1 件化）。
- 本文は N=1、同一エージェント生成・同一エージェント検査。盲検でも独立評価でもない。
