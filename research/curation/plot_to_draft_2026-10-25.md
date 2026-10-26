# `narrative/us_2026:T004` の縦割り接続 — Plot → Draft

- 日付: 2026-10-25
- 対象: [棚卸しで特定した切れ目](materials_inventory_2026-10-25.md#3-次の縦割り候補今回は未実装)。「技法を集め直す」より先に、すでにある設計の受け渡しを一つ検証する。
- 範囲: **線形短編の S1–S3 と創作プロジェクトの章別本文リクエスト**。新規の外部調査、創作技法の効果検証、L2/L3 の再開はしない。

## 対応付けと今回の変更

[`narrative/us_2026:T004`](../catalog/techniques.jsonl)（「三幕・ビートシートによる外形設計」）は、[seed-06](../program/skill_seeds.jsonl) → [`plot-architecture` の技法表](../../skills/plot-architecture/references/techniques.md) → [`acts_cover` の構造検査](../../src/asc/plot/check.py) → [Design の `plot.json`](../../src/asc/pipeline/design.py) に対応する。ここまでの**幕と章の被覆**は以前から検査していた。新たに、[章別メモの組み立て](../../src/asc/pipeline/design.py)から[Draft](../../src/asc/pipeline/draft.py)の [`draft-chapter` v1.2](../../prompts/draft-chapter.md)へ次だけを渡す。

- **その章に属する幕の ID と問い**。幕数は固定せず、2 幕以上の既存スキーマのまま。
- **その章に置かれた転換点の ID と選択**。転換点は既存スキルが定義した欄で、T004 に由来する「特定数のビート」を実証・強制するものではない。`plot.json` 全文、他章の幕／転換点、結末、副筋、未回収項目は本文リクエストに足さない。

`plot.report.json` が `clean` であり、かつ**現在の canon**で既存の `check_plot` を通るときに使う。設計書が `missing`／`unresolved`／記録が読めない／現行 canon では検査を通らない場合は、**幕メモを省略した理由をリクエスト内に明示**し、生成工程を止めない。旧版から `plot.json` だけを引き継ぐ創作プロジェクトの部分改稿では、検査記録がなくても現在の canon で再検査してから使う。canon も検査記録も無ければ使わない。S0 と `--no-design` は従来どおり設計メモなし。場面と文体の既存メモは変えない。プロンプトには設定台帳と矛盾しない範囲でのみ使うよう明記した。どの情報を渡したかは run の `responses.jsonl` の本文リクエストと `prompt_hash` で確認できる。

この ID の[カタログ記録](../catalog/techniques.jsonl)の証拠等級は `C` で、原著全文の確認や効果の追試ではない。`acts_cover` に併記される日本資料 `T010` の対応付けも、[棚卸しで挙げた未確認事項](materials_inventory_2026-10-25.md#コードが引用する技法-id-と参照表の差)として残す。今回の追加条件は原典の主張ではなく、本リポジトリの編集上の判断である。

これは**プロンプトへの編集上の受け渡し**で、物語に三幕を押し付ける検査・品質ゲートではない。[protocol-v1 の §9](../../docs/protocol.md#9-版の上げ方)にいうタスク・系の段階構成・指標・閾値は変更せず、スキルの利用／プロンプトの改善として扱う。ただしリクエスト本文は変わるので、**旧コードで保存した応答を新コードで厳密 replay するとプロンプト差分で止まる**（[replay の検査契約](../../docs/replay.md)）。旧 run を改変したり、新旧を同一条件の実測結果として混ぜたりしない。

## 同じ台本による L1・配線比較

変更の前後に、同じ `t01`・S1・seed 0・`plan-demo.json` の**固定台本**で `scripts/run_pipeline.py --report-only` を実行した。原本の出力は Git 管理外の `build/plot-vslice/`。表の「旧」は基点 `538a730` のコード、「新」はこの接続を加えた作業ツリー。実行形は以下のとおり（旧コード側では `--run-id baseline-t01-s1-s0` を使う）。

```sh
.venv/bin/python scripts/run_pipeline.py --task t01 --system s1 --provider scripted \
  --script benchmarks/protocol-v1/fixtures/plan-demo.json --out build/plot-vslice \
  --run-id plot-t01-s1-s0-final --report-only --quiet
```

`--report-only` は退出コードを 0 にするが、内部の `status` はゲート判定による。`run-summary.json` と `responses.jsonl` の Draft 行で比較する。

| 観測項目 | 旧 | 新 |
| --- | ---: | ---: |
| 章別の幕・転換点メモ（3章中） | 0 章 | **3 章**（各章 1 幕・1 転換点） |
| Draft リクエストの `prompt_hash` | 3 章とも旧値 | **3 章とも変更**。例: ch01 `0bc2adcdae51aa57` → `fb911ffee3a4d758` |
| 実際に返された本文 | 同じ固定台本 | **同一**（各章の `response_sha256` が一致） |
| 本文字数（`run-summary.json`） | 746 | 746 |
| 必須語の出現率 | 1.0（3/3） | 1.0（3/3） |
| 監査の違反 / skipped / CED | 0 / 0 / 0.0 | 0 / 0 / 0.0 |
| 長さゲート / 内部 `status` | 不合格 / `fail` | 不合格 / `fail` |

固定台本はプロンプトが変わっても**同じ文章を返す**。したがって L1 値が同じなのは予想どおりで、作品の構成・面白さ・T004 の効果については**何も実証していない**。長さも規定の 3,000～4,200 字より短い。この比較で確認したのは、3 章すべてで該当する幕・選択だけがリクエストに入り、既存の監査やゲートを変えていないことまで。

## 次に実測するときの条件

モデルが実際に答える場合は、**同じ題材・seed・温度・モデル版**で、Plot → Draft の受け渡しだけを変えた条件を別々の run として記録し、マーカー被覆、必須語、禁止表現、継続性違反、長さ等の **L1 指標を個別に**比較する。モデル版を固定できない Arena 経路なら探索的な参考値に留め、G5 や作品品質の改善を主張しない（[現行の評価範囲](../../docs/evaluation_scope.md)）。今回の固定台本比較は、その実測の代わりにはならない。根拠の不足が実際に判明した項目に限って、次に追加調査する。

## 次の一手: Plot メモだけの draft 条件差

目的は、**同一の canon・Plot/scene/voice 設計書を使い、章別 Plot メモを Draft に含めるかだけを変える**小さな L1 条件比較である。ここでいう「Plot だけ」は入力介入の定義であり、後続章の「前章末尾」文脈は先行する章の応答によって変わりうる。この伝播は下流の媒介として記録し、独立した章ごとの直接効果とは解釈しない。

実装は `build_story(..., include_plot_memos=False)` と `run_pipeline.py --stage draft --canon ... --design-dir ... --no-plot-memos`。既定（フラグなし）が Plot メモありの条件である。比較用CLIは `plot.report.json=status=clean` と `plot.json`・`scene.json`・`voice.json` を要求し、現在の canon でも Plot を再検査する。両 run は同じ外部 canon/design を読み、canon は各 run にコピーされる。`run-summary.json` の `draft_condition` に `canon_files_sha256` / `design_files_sha256` として canon/design 全ファイルの SHA-256 を記録する。L1 の指標・閾値、L2/L3、S1 の定義は変更していない。

現行スコープは `configs/evaluation_scope.yaml` のとおり **Arena.ai のみ**であり、外部APIモデルを比較に使わない。まずArena relayで canon と設計書を一度だけ作り、その同じ成果物を両条件で共有する。`run_plot_ablation.py --prepare-shared` を使えば、共有 `plan`・`design`（8文書のみ、準備用の余分な初稿は作らない）から paired `draft`（`no_plot` / `with_plot`）までを単一の実験バンドル `<out>/` 内で一貫して進められる（既存の `--canon` / `--design-dir` 指定も引き続き利用可能）。回答待ち（exit 3）で停止したら `<out>/PROMPTS.md` のリクエストへ回答し、`<<<ANSWER TAG>>>` ブロックを保存したファイルを `--ingest <file> --resume` で渡す。

```sh
EXP=experiments/2026-10-plot-ablation-t01/paired
.venv/bin/python scripts/run_plot_ablation.py --id t01-s1-seed0 --task t01 \
  --prepare-shared --provider arena --seed 0 --temperature 0.8 --out "$EXP"

# 回答待ち（exit 3）のとき: $EXP/PROMPTS.md を Arena チャットへ送り、
# 返ってきた <<<ANSWER TAG>>> ブロック（複数段階・両 arm まとめ貼り可）を
# answers.txt に保存して 1 コマンドで取り込み＋再開する。
.venv/bin/python scripts/run_plot_ablation.py --id t01-s1-seed0 --task t01 \
  --provider arena --seed 0 --temperature 0.8 --out "$EXP" \
  --ingest answers.txt --resume
```

A/B runner は初回起動時に canon/design を `out/inputs/` へ固定コピー（または `--prepare-shared` で `out/inputs/` 内に生成）し、既定では試行runを `out/attempts/`、Arena request/response とrelayを `out/relay/` に保存する。`build/` 配下の scratch パスは出力先に指定できない。回答が未着なら exit 3 で止まり、統合 `out/PROMPTS.md`（および arm 別の `PROMPTS.md`）と再開コマンドを出す。`--ingest` は `shared_prep`・`no_plot`・`with_plot` の各 operator ディレクトリを横断して該当タグに振り分けるため、両 arm の回答を 1 ファイルで渡しても `unknown tag` にならず、回答が揃っている段階は自動で連続進行する。`state.json` の再開検査は `canon_files_sha256` / `design_files_sha256` とバンドル内相対位置を使うため、元の `runs/` が消えていても、またリポジトリのチェックアウトパスが変わっても実験パッケージ内のコピーだけで再開できる。実験をGitHubで共有・復元する場合は、レビュー後に `experiments/<id>/` の必要な入力・relay・結果をブランチへcommit/pushする（自動commitはしない）。別々のrequest namespaceでarm間の応答取り違えを防ぐ。完了時は `results.json` / `note.md` / `l1/` に加え、共有入力hash、条件、モデル来歴を記録し、**ch01のプロンプト差が幕／転換点行だけ**であることを検査する。Arenaのモデル版は固定されないため `version_pinned=false`、G5未達、L1は探索的参考値となる。後続章は前章本文の違いが伝播する媒介効果を含む。

runner のL1出力では、必須語、タスク固有の禁止語、共通の禁止パターン、継続性監査（違反・高 severity・未実行検査・CED）、文字数・記述統計を個別に記録する。L1レポートを総合点や品質判定にまとめず、L2/L3は実行しない。

### 2026-10-26 実施結果（Arena × L1 探索的ペア比較 `t01-s1-seed0`）

前回のマルチターン実験（PR #43）では、共有準備や試行 run・relay の初期状態が Git 管理外の `runs/` に置かれていたこと、共有準備が別コマンドに分かれていたこと、2 arm 一括 ingest 時に他方 arm のタグが `unknown tag` になること、`state.json` が絶対パス文字列を比較していたことにより、ch02 後の workspace reset で中断した。

今回の再試行では `scripts/run_plot_ablation.py` に `--prepare-shared`、マルチ arm / マルチステップ `--ingest`、統合 `<out>/PROMPTS.md`、パス非依存の再開検査、`build/` 拒否を実装した上で、`experiments/2026-10-plot-ablation-t01/paired/` 内で共有準備（`1AD3`〜`F050`）と両 arm の全 3 章（`no_plot`: `8181` / `C3A0` / `EFA7`、`with_plot`: `CCBC` / `4DEF` / `D342`）を完走させた。成果物一式は [`experiments/2026-10-plot-ablation-t01/paired/results.json`](../../experiments/2026-10-plot-ablation-t01/paired/results.json) と [`note.md`](../../experiments/2026-10-plot-ablation-t01/paired/note.md) に保存している。

- **条件統制の確認**:
  - 共有 `canon`（6 ファイル）と `design`（8 設計書すべて `status: clean`）の SHA-256 は両 arm で完全一致。
  - `prompt_control.ch01_diff_only_plot_memo_lines = true`（ch01 の `no_plot` `09143bfcbad0a32d` と `with_plot` `f7b63c15aa0622d7` のプロンプト差は章別 Plot メモの 2 行のみ）。
  - ch02・ch03 のプロンプトは各 arm の前章本文（「前章の末尾」）を含むため、下流の媒介効果を含む。

| L1 観測項目（`t01` / S1 / seed 0 / temp 0.8 / Arena） | `no_plot`（Plot メモなし） | `with_plot`（Plot メモあり） | 差（`with - without`） |
| --- | ---: | ---: | ---: |
| ゲート判定（`run-summary.json` `status`） | `pass` | `pass` | — |
| 本文字数（マーカー除外、規定 3,000〜4,200 字） | 3,343（1028 / 1206 / 1109） | 3,374（964 / 1202 / 1208） | +31 |
| 章単体の長さ警告（目安 1,000〜1,400 字） | 0 件 | 1 件（ch01: 964 字） | +1 |
| 必須語の出現率（`灯台`・`鍵`・`嵐`） | 1.0（3/3） | 1.0（3/3） | 0.0 |
| タスク禁止語（`選ばれし者`・`古代の予言`） | 0 件 | 0 件 | 0 |
| 共通禁止表現（`forbidden_hits` / 1万字あたり） | 0 件 / 0.0 | 0 件 / 0.0 | 0 / 0.0 |
| 継続性監査: 未実行検査（`checks_skipped` / 全6検査） | 0 件 | 0 件 | 0 |
| 継続性監査: 高 severity 違反（`high`） | 0 件 | 0 件 | 0 |
| 継続性監査: 違反合計（すべて `medium`） | 8 件 | 5 件 | -3 |
| — 内訳 `unresolved_foreshadow` | 1 件（`fs-004` payoff マーカー欠落） | 0 件（全 6 伏線回収） | -1 |
| — 内訳 `dead_character_reappears`（`name_mention`） | 7 件 | 5 件 | -2 |
| 継続性誤り密度 CED（1万字あたり） | 20.207 | 12.447 | -7.76 |
| 記述統計: 段落数 / 平均段落字数 / 会話比率 | 24 / 165.0 / 0.223 | 26 / 154.5 / 0.228 | +2 / -10.5 / +0.005 |
| 記述統計: 文数 / 平均文長 / 文長 CV | 168 / 19.9 / 0.529 | 175 / 19.3 / 0.515 | +7 / -0.6 / -0.014 |

#### 結果の読み方と限界

- **単一ペア・Arena 経路の制約**: Arena 経路はモデル版が固定されないため（`model_version: unversioned`, `version_pinned: false`）、G5（再現性）は成立せず、本結果は **Arena × L1 の探索的参考値（1 ペアのみ）** に留まる。
- **継続性違反（`medium`）の内訳**:
  - `unresolved_foreshadow` は `no_plot` の ch02 で `{{foreshadow: fs-004 payoff}}` マーカーが出力されなかったことによる 1 件（`with_plot` は 0 件）。ただし ch02 は前章本文を介した下流段階であり、また 1 ペアの観測であるため、Plot メモの一般効果とは結論づけない。
  - `dead_character_reappears`（`no_plot` 7 件、`with_plot` 5 件）はいずれも物語開始前に死亡している `johan`（ヨハン・アール／「兄」）の名前・別名が記録引用や会話中に出現したことに対する `name_mention` ベースの `medium` 報告であり（監査器の仕様上、回想・記録・言及と区別できないため `medium` として計上）、死者本人が現在時に行為・発話した `high` 違反は両 arm とも 0 件である。
- **未検証事項**: 複数タスク・複数シード・固定モデル版での効果の再現性（G5）、および章別 Plot メモが物語の質・面白さ・読者選好に与える影響。**L1 指標は構造・衛生チェックであり、物語の質や面白さの証拠ではない。** L2/L3 は引き続き `frozen_not_measured`。
