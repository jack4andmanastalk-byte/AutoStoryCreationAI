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
