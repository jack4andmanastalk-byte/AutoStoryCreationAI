# Stage B プロンプト v1.1（`$timeline`）での再生成 — t01

- 日付: 2026-10-26
- 種類: **実応答の再生成と、v1.0 との L1 比較**。Stage A は実行せず、検証済みログを与えた
  `--stage b` の単独実行。
- 位置づけ: [`../2026-10-l1-pair-t01/note.md`](../2026-10-l1-pair-t01/note.md) の「次に試すこと」3 番目、
  および [`docs/two_stage_slice.md`](../../docs/two_stage_slice.md) §14 の確認。
- 決定論的要約: [`results.json`](results.json)（`schema: l1-arm-comparison-v1`）

## 目的

1. Stage B プロンプト v1.1（`$timeline` と契約 6「日数を自分で計算しない」）で本文を作り直し、
   決定論的検査と既存監査を通るか確認する。
2. 「導出した確定値を渡す」ことが、**日数の誤り（v1.0 の M-1「四日ぶり」）を実際に防ぐか**を見る。
3. v1.0 の記録（`2026-10-full-t01/relay-r2/`）はプロンプト変更により replay できないため、
   現在のプロンプトに対する**有効な記録**を残す。

**質・面白さの比較ではない。** L2/L3 は `frozen_not_measured`、G3/G4 は未測定、G5 は未達。

## 入力と条件

```text
inputs/canon/      t01 の canon（2026-10-full-t01/inputs のコピー、sha256 一致）
inputs/design/     plot.json / scene.json / voice.json（同コピー）
inputs/game_log.json  Stage A の実応答（2026-10-full-t01/relay/ の回答）をそのまま入力にした。
                      与えた時点で check_game_log により再検査し、clean（所見 0）を確認。
relay/             4 要求（ch01・ch02・ch02 修復・ch03）と回答
```

- 生成は `--provider command` → `scripts/chat_operator.py`。生成者は当方（Arena の対話エージェント）、
  model は `arena-agent-mode` / `unversioned-2026-10-26`。**独立性はない。**
- プロンプト: `stage-b-rewrite` v1.1（`prompt_hash` は ch01 `ab8be3c448d7e96d`）。
- ログは v1.0 の試走と**同一**（`game_log.json` の内容は変えていない）。したがって差はプロンプトに由来する。

## 手順（実際に起きたこと）

```bash
# 1. Stage A の実応答を入力ログとして保存し、検査
.venv/bin/python scripts/check_gamelog.py \
  --game-log experiments/2026-10-stageb-v11-t01/inputs/game_log.json \
  --canon experiments/2026-10-stageb-v11-t01/inputs/canon \
  --design-dir experiments/2026-10-stageb-v11-t01/inputs/design --require-design
# → clean（8 検査・所見 0）

# 2. Stage B のみ実行（回答なしで起動 → exit 3 → 回答を置いて --resume）
.venv/bin/python scripts/run_twostage.py --task t01 --stage b \
  --game-log experiments/2026-10-stageb-v11-t01/inputs/game_log.json \
  --canon experiments/2026-10-stageb-v11-t01/inputs/canon \
  --design-dir experiments/2026-10-stageb-v11-t01/inputs/design \
  --provider command \
  --command "$PWD/.venv/bin/python scripts/chat_operator.py --dir experiments/2026-10-stageb-v11-t01/relay" \
  --out experiments/2026-10-stageb-v11-t01 --run-id stageb-v11-s0 --seed 0 --resume

# 3. 比較（v1.0 の記録は replay せず、応答の text を読む）
.venv/bin/python scripts/compare_l1_arms.py --task t01 \
  --canon experiments/2026-10-stageb-v11-t01/inputs/canon \
  --arm "v1.0=experiments/2026-10-full-t01/relay-r2/responses" \
  --arm "v1.1=experiments/2026-10-stageb-v11-t01/relay/responses" \
  --model-version unversioned-2026-10-26 \
  --out experiments/2026-10-stageb-v11-t01/results.json
```

- 4 要求で完走。run の状態は `clean`（`stage_a_clean: true` は入力ログの再検査、`stage_b_clean: true`）。
- run ディレクトリは削除した。**`relay/` から同じ 3 章が再生成できる**ことを確認済み
  （削除 → 同条件で再実行 → `text/ch01..ch03.md` の sha256 が一致、`status: clean`）。

## 結果

| 章 | 試行 | 修復 | 文字数 | マーカー | 時系列検査（checked / skipped） | 最終状態 |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| ch01 | 1 | 0 | 1,043 | 6 / 6 | 0 / 1 | `clean` |
| ch02 | 2 | 1 | 989 | 7 / 7 | 1 / 2 | `clean` |
| ch03 | 1 | 0 | 835 | 6 / 6 | 1 / 1 | `clean` |

- 必須語率 1.0（灯台・鍵・嵐）、題材の禁止語 0、禁止パターン 0、未実行検査 0。
- 既存監査: 違反 1 件（`dead_character_reappears` / `medium`・既知の誤検出クラス）、CED 3.059。
- 時系列検査は 2 件を照合し（ch02「三日歩いた」、ch03「六日ぶり」）、**不一致 0**。
  4 件は抽象表現などで `skipped` に落ちた。

### v1.0 との比較

| 指標 | v1.0（`2026-10-full-t01` r2） | v1.1（本バンドル） | 差 |
| --- | ---: | ---: | ---: |
| 文字数（マーカー除く） | 3,047 | 2,867 | −180 |
| 必須語率 / 禁止パターン密度 | 1.0 / 0.0 | 1.0 / 0.0 | 0 |
| マーカー総数 | 19 | 19 | 0 |
| 連続性監査の違反 | 2 | 1 | −1 |
| CED / 1 万字 | 5.799 | 3.059 | −2.740 |
| 会話率 / 文長 CV | 0.007 / 0.425 | 0.017 / 0.476 | +0.010 / +0.051 |

差は 1 run ずつの記述統計である。**CED が下がったことを「良くなった」と読まない**
（違反はどちらも死者名の言及を拾う既知の誤検出で、件数は本文の人名の出し方で変わる）。

## 観測できたこと

1. **日数の扱いは変わった。** v1.0 の 1 run 目は ch03 で「四日ぶり」（正しくは六日）と書き、
   検査器はそれを検出できなかった（M-1）。v1.1 の ch03 は「六日ぶり」と書き、
   `timeline_consistency` が照合して **checked 1・不一致 0** で通した。
   導出表（`アリア: この場所を離れてから 6日`）がプロンプトに載っており、計算の余地が減っている。
2. **修復が 1 回入った。** ch02 の初回は「三年前」— F-04 の語彙 — を使い、`fact_boundary`（`medium`）で
   止められた。修復では指摘どおりその一語を外した（「あの嵐の夜」）。
   v1.0 の ch02 は「三年前」を使っていないため、同じ検査は発火していない。
   **これは検査器が働いた記録であり、v1.1 のほうが危険という意味ではない**（同じ本文を書けば
   v1.0 でも止まる）。むしろ、ログの `outcome` 自身が「三年前」と書いているのに本文では禁じられる、
   という仕様のねじれが観測できた。
3. **長さは目標に届かなかった。** 章あたりの目安は 1,000〜1,400 字で、ch02 989 字・ch03 835 字は
   下回る。`--min-chars` 200 の下限は満たすため run は `clean` だが、タスクの目標帯
   （3,000〜4,200 字）には 2,867 字で届いていない。**プロンプトの効果ではなく、書き手の長さの管理**で
   ある。v1.0 との文字数差もこの点で解釈しない。

## 言えないこと

- 導出表を渡せば日数の誤りが一般に防げる、とは言えない。N=1・単一タスク・同一著者で、
  著者は v1.1 の契約文と検査器の実装を読んでいる。四日と書いても既定では**警告**であって
  修復されないため、`--strict-timeline` を付けない run では、誤りは「報告される」だけである。
- v1.0 より v1.1 の本文が正確・面白い。長さ・会話率・CED の差は記述統計にすぎない。
- 実モデル（版を固定したモデル）が同じ契約を守れるか。G5 は未達のまま。

## 次に試すこと

1. `--strict-timeline` で同じ条件を回し、日数の誤りを注入したときに修復が回ることを記録する
   （既定との差は `results.json` の `timeline.strict` に残る）。
2. 直接生成（S1 draft）の本文に既知の変異を注入し、ログ依存の検査器が何件拾えるかを数える
   （[`../2026-10-l1-pair-t01/note.md`](../2026-10-l1-pair-t01/note.md) の残件）。
3. S1 全体（plan → 8 設計 → draft）との比較。
