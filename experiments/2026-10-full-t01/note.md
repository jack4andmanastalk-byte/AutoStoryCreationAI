# 全工程試走（Stage A → Stage B の実応答） — t01 / 2 run

- 日付: 2026-10-26
- 種類: **全工程の実応答試走**。固定台本ではなく、Stage A（構造化ログ）と Stage B（本文）を
  どちらも実応答で通した。1 run 目はそのまま記録し、人手照合で見つけた誤りを 1 か所直した 2 run 目を続けて置いた。
- 前提: [`research/curation/two_stage_next_steps_2026-10-26.md`](../../research/curation/two_stage_next_steps_2026-10-26.md) §2 の 3 番目。
  P0（同 §9）と P1（同 §11）の修正後に実施。
- 決定論的要約: [`results.json`](results.json)（1 run 目）/ [`results-r2.json`](results-r2.json)（2 run 目）

## 目的

1. Stage A の実応答が、canon・設計・マーカー導出の決定論的検査を通るか。通らなければ修復が回るか。
2. その検証済みログから Stage B が本文を書き、マーカー・人物境界・事実境界・必須語を通るか。
3. **検査が通した本文を人手で照合し、検出漏れと誤検出を記録する**（§4 の受入条件）。

**「良い小説が書けた」記録ではない。**品質・面白さ・読者選好は測定していない（L2/L3 は `frozen_not_measured`）。

## 入力と条件

```text
inputs/canon/          t01 の canon（6 チャネル、死者 johan）
inputs/design/         plot.json / scene.json / voice.json と実検査器の report
relay/                 1 run 目の 4 要求と回答（Stage A 1 + Stage B 3）
relay-r2/              2 run 目の 4 要求と回答（Stage A と ch01・ch02 は再利用、ch03 は修正して fresh）
results.json           1 run 目の決定論的要約
results-r2.json        2 run 目の決定論的要約
```

- provider は `command` → `scripts/chat_operator.py`。回答はすべて本バンドルに残る。
- 生成者は Arena の対話エージェント（当方）。**記録された model は `arena-agent-mode` / `unversioned-2026-10-26`**。
- **独立性はない**。同じエージェントが、検査器の実装を読んだうえで Stage A と Stage B を書いている。
  決定論的検査は生成側と独立に走るが、生成側が合格条件を知っている状態での試走である。
  この条件は「実モデルが同じ契約を守れるか」の証拠にならない。**配線と検査の観測に限る。**

## 手順（実際に起きたこと）

```bash
# 1 run 目: 回答なしで起動 → Stage A のプロンプトが出て exit 3
.venv/bin/python scripts/run_twostage.py --task t01 \
  --canon experiments/2026-10-full-t01/inputs/canon \
  --design-dir experiments/2026-10-full-t01/inputs/design \
  --provider command \
  --command "$PWD/.venv/bin/python scripts/chat_operator.py --dir experiments/2026-10-full-t01/relay" \
  --out experiments/2026-10-full-t01 --run-id full-t01-s0 --seed 0
# 2. relay/responses/ に回答を置き、--resume（Stage A → ch01 → ch02 → ch03 の 4 往復）
# 3. 人手照合 → ch03 の日数の誤り 1 件 → 2 run 目（--run-id full-t01-s0-r2, relay-r2）
```

- 1 run 目: Stage A 1 要求・Stage B 3 要求。`exit 3` → 回答 → `--resume` を 4 回（`resume_count: 5`）。
- 2 run 目: 同じ canon / design で新しい run-id。Stage A と ch01・ch02 は**再利用**（`origin: reused`）、
  ch03 だけ `四日ぶり`→`六日ぶり` に直して fresh。`resume_count: 4`。
- どちらの run も `replay` は `replayed 3 / missing 1`（毎回 1 要求ずつ新規）。

## 結果（1 run 目）

| 段 | 状態 | 試行 | 修復 | 内容 |
| --- | --- | --- | ---: | --- |
| Stage A | `clean` | 1 | 0 | 8 検査すべて実行・所見 0。3 章 3 場面。確定マーカー 19 件（time 3 / location 3 / learn 4 / use 3 / foreshadow 6）。許容された死者言及 4 件 |
| Stage B | `clean` | 1 / 1 / 1 | 0 | ch01 1,032 字 / ch02 1,007 字 / ch03 1,008 字（計 3,047 字）。マーカーは 6 / 7 / 6 で導出列と一致 |
| 必須語 | 1.0 | — | — | 灯台・鍵・嵐 すべて出現。`missing_must_include` は空 |
| 既存 continuity 監査 | 6 検査すべて実行 | — | — | 違反 2 件（`dead_character_reappears` / `medium`）、`high` 0 件、CED 5.799/10k |

Stage A は**1 回で通った**（修復 0）。Stage B も 3 章とも 1 回で通った（修復 0）。
直前の Stage B 単独試走では ch03 が 1 回修復に入ったが、今回は媒体語を同じ文に置いたため
`character_boundary` の `high` は出ていない。

## 人手照合の結果（§4 の受入条件）

### 検出漏れ（検査は `clean`、人手では誤り）

| # | 箇所 | 内容 | 検査が通した理由 |
| --- | --- | --- | --- |
| M-1 | ch03 冒頭 | 「**四日ぶり**の灯台」— day 1 出発・day 7 帰着なので**六日**。 | 日数と現在地を見る検査はログ（`location_moves` の前後関係）だけで、本文の散文を読まない。 |
| M-2 | ch02 | 「手の甲に古い**火傷の跡**がある」— canon にもログにもない人物細部。 | `character_boundary` は人物名しか見ない。新しい属性は検出対象外（B-03）。 |
| M-3 | ch01 | 「刻みの**深さはそれぞれ違う**」— ログは刻みが三つとだけ書く。 | 同上。ログにない細部の追加は機械的に検出できない。 |
| M-4 | ch02 | 「札の日付と写しの欄の日付は、**半日だけ**ずれていた」— ログは「突き合わせる」とだけ書き、差の量は宣言していない。 | 数値の捏造は語彙一致では捕まらない。 |

M-2〜M-4 は契約 2「ゲームログにない新しい事実・人物の行動・会話・場所・時点・伏線を追加しない」に
反するが、いずれも**検査は通した**。M-1 は事実の誤りで、しかも日数という物語の骨格に関わる。

### 誤検出（人手では正しい、既存監査が違反にした）

| # | 箇所 | 内容 |
| --- | --- | --- |
| F-1 | ch02 | 「ヨハンの石膏手形だった」— 宣言済み `record_reference`（medium: 石膏手形） |
| F-2 | ch03 | 「ヨハンが握ったままだったのは、この加減だったのだ」— 潮札についての回想 |

どちらも既存 `dead_character_reappears`（`name_mention` 由来）の既知の誤検出類型で、
Stage B の `character_boundary` は同じ箇所を許容している。

### 問題なしと確認した点

- 死者の現在時行動は 0 件（`present_characters` / `action` / `dialogue` に死者が出ない）。
- 知識の順序: F-05 は ch01、F-02・F-03 は ch02、F-04 は ch03 で学び、開示章より前の言及はない
  （ch01 に「雷」「三年前」「書き換え」「削られた頁」は無い。ch02 に「雷」「三年前」は無い）。
- 場所: 灯台 → 王都 → 灯台。章の `location` と本文の場所が一致。
- 伏線: fs-001（ch01 設置 → ch03 回収）、fs-002（ch01 → ch02）、fs-003（ch02 → ch03）。
- マーカー列: 3 章とも導出列と完全一致。

## 2 run 目の意味（重要）

ch03 の「四日ぶり」を「六日ぶり」に直した 2 run 目の結果は、**1 run 目と機械的に区別できない**。

| | 1 run 目 | 2 run 目 |
| --- | --- | --- |
| 状態 | `clean` | `clean` |
| 章ごとの所見 | 0 / 0 / 0 | 0 / 0 / 0 |
| 文字数 | 1,032 / 1,007 / 1,008（3,047） | 1,032 / 1,007 / 1,008（3,047） |
| 必須語 | 1.0 | 1.0 |
| 既存監査の違反 | 2（medium） | 2（medium） |

同じ字数・同じ所見である。**「2 run 目も `clean`」は「直った」ことの証拠にならない。**
この試走で機械的に観測できたのは「配線が通り、修復なしで 4 要求が完走した」ことまでで、
本文の事実の正しさは人手照合でしか判定できていない。

## 非主張・未実施

- 実モデルの品質・面白さ・読者選好は未測定。L2/L3 は `frozen_not_measured`、G3/G4 は未達とも合格とも記録しない。
- G5（同一 seed・同一出力）は主張しない。`model_version: unversioned-2026-10-26` は版の同定ではない。
- 生成者と検査実行者が同一で、生成側は合格条件を読んでいる。**実モデル一般の契約遵守率の推定には使えない。**
- 1 章 1 場面・章内移動なしの最小スライス。分岐・ダイス・物語途中の死亡・複数場面の章は未対応。
- Stage B は前章本文を受け取らない（入力差は Phase 3 の比較条件として明示する）。
- 直接生成（S1）との L1 比較は未実施。本記録は二段階方式の内部観測であり、S1 と比べていない。
- P1 で足した検査（現在地・章順・未知キーなど）はログ側のみ。**本文側の現在地・日数の検査は無い。**
