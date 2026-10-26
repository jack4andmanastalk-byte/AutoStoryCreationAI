# L1 参考比較: 二段階方式と直接生成（S1・draft 段のみ） — t01

- 日付: 2026-10-26
- 種類: **L1 の参考比較**。固定台本ではなく、両腕とも実応答（Arena の対話エージェント＝当方）。
- 位置づけ: [`research/curation/two_stage_next_steps_2026-10-26.md`](../../research/curation/two_stage_next_steps_2026-10-26.md)
  §2 の 4 番目（「必要な部品だけ流用」の後、Phase 3 の S1 比較）。仕様は
  [`docs/two_stage_slice.md`](../../docs/two_stage_slice.md) §15。
- 決定論的要約: [`results.json`](results.json)（`schema: l1-arm-comparison-v1`）

## 目的

二段階方式（検証済みゲームログ → 本文）と、**同じ canon・同じ設計書から直接本文を書く**条件を、
同じ L1 指標で並べる。目的は優劣の判定ではなく、次の 2 点の切り分けである。

1. L1（構造・衛生）は、この 2 条件を**識別するか**。
2. 二段階方式が持つ「ログへの束縛」は、**何を検査可能にしているか**。

**品質・面白さ・読者選好の比較ではない。** L2/L3 は `frozen_not_measured`、G3/G4 は未測定、
G5 は未達（版を固定したモデルではない）。

## 条件

| 腕 | 入力 | 生成 | 出典 |
| --- | --- | --- | --- |
| two-stage | canon + 設計 + **検証済み `game_log.json`** | Stage A のログから Stage B が章ごとに執筆 | [`../2026-10-full-t01/relay-r2/`](../2026-10-full-t01/note.md)（2 run 目） |
| s1-draft | **同じ** canon + 同じ設計書（plot/scene/voice）。ログなし | `run_pipeline.py --system s1 --stage draft` が章ごとに直接執筆 | [`relay/`](relay/)（本バンドル） |

- 入力は同一。`inputs/canon` と `inputs/design` は `2026-10-full-t01/inputs` の**コピー**で、
  sha256 が一致する（`results.json` の `canon_sha256` と `run-summary.json` の
  `draft_condition.*_sha256`）。
- s1-draft は **S1 全体ではない**。plan と 8 種の設計は実行せず、固定設計を再利用した
  draft 段のみの比較である（`--canon` + `--design-dir` + `--stage draft`）。
- 生成者は両腕とも当方（Arena の対話エージェント）。**独立性はない**。記録された
  model は `arena-agent-mode` / `unversioned-2026-10-26`。
- 条件の違いは「ログを渡すか、設計だけを渡すか」の 1 点に揃えたが、**プロンプトは別物**である
  （Stage B はマーカー列と日数の確定表を受け取り、S1 draft は設計メモから章を書く）。

## 手順（実際に起きたこと）

```bash
# 1. 入力のコピーと sha256 の確認
cp -r experiments/2026-10-full-t01/inputs/canon  experiments/2026-10-l1-pair-t01/inputs/canon
cp -r experiments/2026-10-full-t01/inputs/design experiments/2026-10-l1-pair-t01/inputs/design

# 2. 直接生成の腕: 回答なしで起動 → 1 章ずつプロンプトが出て exit 3（`chat_operator.py`）
.venv/bin/python scripts/run_pipeline.py --task t01 --system s1 --stage draft \
  --canon experiments/2026-10-l1-pair-t01/inputs/canon \
  --design-dir experiments/2026-10-l1-pair-t01/inputs/design \
  --provider command \
  --command "$PWD/.venv/bin/python scripts/chat_operator.py --dir experiments/2026-10-l1-pair-t01/relay" \
  --out experiments/2026-10-l1-pair-t01 --run-id s1-draft-s0 --seed 0
# 3. relay/responses/ に 3 章を置き、同じコマンド（run_pipeline は resume しないので毎回新しい run-id か削除）
# 4. 比較（結果は results.json）。両腕とも、コミットされている relay の応答から読む
.venv/bin/python scripts/compare_l1_arms.py --task t01 \
  --canon experiments/2026-10-l1-pair-t01/inputs/canon \
  --arm "two-stage=experiments/2026-10-full-t01/relay-r2/responses" \
  --arm "s1-draft=experiments/2026-10-l1-pair-t01/relay/responses" \
  --model-version unversioned-2026-10-26 \
  --out experiments/2026-10-l1-pair-t01/results.json
```

- s1-draft の run は `status: pass`（`must_include`・`length`・`no_high_severity`・
  `all_checks_ran` がすべて true）。3 章とも 1 回で採用、修復なし。
- run ディレクトリは削除した。**`relay/` から同じ 3 章が再生成できる**ことを確認済み
  （削除 → 同条件で再実行 → `text/ch01..ch03.md` が `relay/responses/*.json` の `text` と
  末尾改行を除いて一致）。比較は run ディレクトリではなく relay の応答から計算しているので、
  この実験の数値はコミット済みファイルだけで再計算できる。
- **two-stage 腕の本文は relay から抽出した**。Stage B プロンプトが同日 v1.1（`$timeline`）に
  変わったため、記録済み応答は現在のプロンプトに対して stale になり、replay は exit 4 で拒否する
  （`prompt_hash` の食い違い）。抽出は §14 以前に生成された当時のバイト列であり、
  抽出値が `2026-10-full-t01/results.json` の `chars` 3,047・CED 5.799・違反 2 と一致することを
  確認している。

## 結果

| 指標 | two-stage | s1-draft | 差 |
| --- | ---: | ---: | ---: |
| 文字数（マーカー除く） | 3,047 | 3,313 | +266 |
| 章ごとの文字数 | 1,032 / 1,007 / 1,008 | 1,185 / 1,035 / 1,093 | — |
| 必須語率（灯台・鍵・嵐） | 1.0 | 1.0 | 0 |
| 題材の禁止語 | 0 | 0 | 0 |
| 禁止パターン密度 / 1 万字 | 0.0 | 0.0 | 0.0 |
| 連続性監査の違反 | 2（`medium` 2） | 3（`medium` 3） | +1 |
| CED / 1 万字 | 5.799 | 8.217 | +2.418 |
| 未実行検査 | 0 | 0 | 0 |
| マーカー総数 | 19 | 16 | −3 |
| 　内訳（time/location/learn/use/foreshadow） | 3/3/4/**3**/6 | 3/3/4/**0**/6 | use −3 |
| 会話率 | 0.007 | 0.047 | +0.040 |
| 平均段落字数 | 181.5 | 93.6 | −87.9 |
| 文長 CV | 0.425 | 0.469 | +0.044 |

両腕とも違反は `dead_character_reappears`（`medium`）のみで、既存監査器が死者名の言及を
一律に拾う既知の誤検出クラスである。**この表の差を「質の差」と読まない。** 段落長と会話率の差は、
当方が直接生成のときに短い段落と台詞を多く使ったという記述にすぎない。

## 人手照合（s1-draft 腕）

`clean`／`pass` でも、台帳にない設定は入る。s1-draft で見つかったもの:

| 箇所 | 内容 | 検査の状況 |
| --- | --- | --- |
| ch01 | 「帳面の写しは王都の役所にある」— canon にも設計にもない保管場所 | 検出対象外（照合先のログが無い） |
| ch02 | 「あんたの父さんは、これを読んだ」— 父の行為の追加 | 検出対象外 |
| ch02 | 「刻みの並びは…日付と、ひとつずれていた」— 食い違いの数値化 | 検出対象外 |
| ch02 | 「指の腹のところだけ妙に艶があった」— 石膏手形の細部 | 検出対象外 |
| ch03 | 「六日ぶり」— day 1 出発・day 7 帰着で**正しい** | 二段階の 1 run 目はここを四日と誤った |

## この比較で言えること・言えないこと

- 言える: 同じ canon・同じ設計のもとで、**ログを渡す条件と渡さない条件の L1 指標はほぼ同じ**で
  あった（必須語 1.0・禁止 0・未実行 0・違反は既定の誤検出クラスのみ）。既存の
  `2026-10-arena-l1-t01`（S0–S3）と同じく、L1 のパターン集合だけでは生成条件を識別できない。
- 言える: 二段階方式の利点は指標の差ではなく、**検査の対象が存在すること**である。ログがある腕では
  マーカー列・人物境界・事実境界・移動日数を機械的に照合できる。ログがない腕には照合先がなく、
  上の 4 件は「検出漏れ」にすらならない（検査が存在しない）。
- 言える: ただし**どちらの腕も `clean` は意味的整合を意味しない**。二段階の腕にも、ログが
  宣言していない細部（既知の M-2〜M-4）が入っていた。
- 言えない: 二段階方式のほうが本文が正確である／面白い。N=1・単一タスク・同一著者で、
  両腕の差は条件の差と著者の癖に分離できない。L2/L3 は測っていない。
- 言えない: S1 全体（plan → 8 設計 → draft）との比較。今回は draft 段だけを同一設計で比べた。

## 限界

- **N=1／腕、単一タスク（t01）、同一著者**。区間推定も有意差も意味を持たない。
- 生成者は当方 1 名で、**二段階腕の本文を以前に書いた本人**が直接生成の腕も書いている。
  設計書だけを見て書いたが、記憶による汚染は排除できない。
- 二段階腕の本文は**記録済み応答からの抽出**であり、当時のプロンプト（Stage B v1.0）で生成された。
  現在のプロンプト（v1.1、`$timeline`）では replay できない。バイト列は変わらないが、
  「今のプロンプトで同じ本文が出るか」は示していない。
- マーカーは s1-draft では**自己申告**（導出するログが無い）。`use` が 0 なのは、直接生成の腕が
  「事実を使った」と宣言しなかったという記録であって、本文に使用が無いことの証明ではない。
- 既存監査の `dead_character_reappears` は名前一致で死者を拾う既知の誤検出を含む。両腕で
  同種の違反が出ているが、内訳の差（2 対 3）を生成条件の差と解釈しない。
- L2/L3 は凍結。G3/G4 は未測定。G5 は未達（モデル版を固定していない）。protocol-v1 の系・指標・
  閾値は変更していない。

## 次に試すこと

1. S1 全体（plan → 設計 → draft）を同じタスクで 1 件走らせ、設計段の出来が本文と L1 にどう出るかを
   記録する。今回の draft 段だけの比較では、設計を固定した効果と方式の効果が分離できない。
2. 「ログがある腕にしかできない検査」の**検出力**を測る。既知の変異（日数の誤り・未宣言の死者言及・
   ログ外の移動）を s1-draft の本文に注入し、二段階の検査器にかけたときに何件拾えるかを記録する
   （`scripts/probe_gamelog_contracts.py` の B 系を、直接生成の本文にも当てる形）。
3. 二段階腕の本文が **v1.1 プロンプトで再生成**できるかを、新しい relay で確かめる。
   現在の記録は v1.0 のままで、replay の契約上それは正しく拒否される。
