# バッチ B: 同じ canon で S1 の設計 8 本と本文 3 章を 1 標本走らせる — t01

- 日付: 2026-10-27
- 種類: **実走り（事前登録 → 1 標本 → 判定）**
- 状態: **走行中**（往復のたびに `relay/sample-1/` が増える。`results.json` は判定可能になるまで全 `not_run`）
- 事前登録: [`preregistration.md`](preregistration.md) / [`preregistration.json`](preregistration.json)
- 手順: [`operations.md`](operations.md)（**ハーネス側の記録**。読者は実行しない）
- 計測: [`results.json`](results.json)（`schema: realrun-b-v1`、事前登録の `sha256` を記録）
- 位置づけ: [`docs/two_stage_slice.md`](../../docs/two_stage_slice.md) §23

## このバンドルの建て付け

このリポジトリはモデルを呼ばない。**往復は arena.ai のチャット、状態は GitHub**で完結させる。
作業者が端末を開くことは前提にしない。

| 役 | すること |
| --- | --- |
| ハーネス（エージェント） | `scripts/` の実行、要求の書き出し、回答の取り込み、run・計測・コミット |
| 回答者（対話モデル） | チャットに貼られた 1 リクエストに答える |
| 人 | プロンプトを貼り、回答をそのまま返す |

1 往復ごとに `relay/sample-1/requests/` と `responses/` がコミットされる。作業環境が消えても、
GitHub から同じ位置で再開できる。

## なぜこのバンドルがあるか

バッチ A（§21.1）は **Stage B だけ**を 3 標本走らせ、同じ canon で本文だけを書いた。設計 8 文書のうち
走ったのは `plot` / `scene` / `voice` の 3 つだけである。`2026-10-l1-pair-t01` は同じ canon・同じ設計で
draft 段だけを比べ、「次に試すこと」の 1 番目に **S1 全体（plan → 設計 → draft）を同じタスクで 1 件
走らせ、設計段の出来が本文と L1 にどう出るか**を挙げた。本バッチはその 1 件を、**canon をバッチ A と
同一に固定したまま**で行う。

### 「S1 全体」と「同一 canon」の折り合い

両立しない。canon は plan の成果物なので、plan を走らせれば canon が変わる。本バッチは
**canon を固定する**側を取り、plan は走らせない（要求も出さない）。したがって

- 測るのは **S1 の design → draft**。
- **plan 段の出来は測らない。**「S1 全体を測った」とは書かない。
- 代わりに、バッチ A・`s1-draft`（固定設計）と同じ canon 上で並べられる状態を保つ。

この判断は走らせる前に固定した（登録に `condition.plan = {requested: false}` として残る）。

## 何を固定したか（走らせる前）

1. **条件**: `--system s1 --stage all --canon inputs/canon`、プロンプトは現行
   （`draft-chapter` **1.2**、`design-brief` 1.1、`design-*` 1.0）、temperature 0.8、
   設計・本文とも修復上限 2 試行。
2. **canon**: `inputs/canon` は `2026-10-realrun-a-t01/inputs/canon` のコピーで、
   **バイト一致**（6 ファイル、`tree_sha256` = `eaaf14e6…`）。この値は登録と `results.json` の
   `condition` に残る。
3. **標本数**: 1。結果を見てから足すなら、走らせる前に B2 として別登録する。
4. **判定規則**（`results.json` の `verdicts` がそのまま答える）:
   - B1: 設計 8 文書の 1 試行目 → `design_clean_first_attempt` / `design_repaired` /
     `design_unresolved`
   - B2: 章の長さ（1,000〜1,400 字、3 章中 2 章以上）→ `length_ok` / `length_lost_in_repair` /
     `length_out_at_write` / `length_mixed_causes`。**原因の切り分けを判定に含めた**
   - B3: 繰り返す失敗。**修復で消えた所見を数えるか**を両方の数え方で出し、**片方を主にしない**
     （バッチ A の登録の不備をここで潰す）。N=1 では `not_evaluable_at_n1`
   - B4: 必須語の完全一致（`2026-10-arena-fresh-s1-n3` の「嵐 → 暴風」の再発監視）
   - B5: マーカーの宣言（本文が書いたか、canon から補ったか、canon と食い違うか）
5. **主張しないこと**: L2/L3 は `frozen_not_measured`、G5 は operator 方式では到達しない、
   N=1 で率・区間・有意差は出さない、plan 段は測っていない、地名の観測（バッチ A の R1）は
   Stage B 専用なので S1 では測らない。

登録の `sha256` は計測時に `results.json` へ記録される（結果を見て規則を書き換えたかどうかが残る）。

## 現在の中身

| パス | 内容 |
| --- | --- |
| `inputs/canon/` | バッチ A と同一の 6 チャネル（`sha256` は登録に記載） |
| `preregistration.json` / `preregistration.md` | 走らせる前の判定規則、数え方、役割分担 |
| `operations.md` | ハーネス側の手順（読者は実行しない） |
| `results.json` | 計測スクリプトの出力（判定可能になるまで全 `not_run`、canon 一致は確認済み） |
| `relay/sample-1/` | 要求・回答・配布ログ。**1 往復ごとにコミットする** |
| `sample-1/run/` | 全回答が揃ったあとの最終 run（design 8 ＋ draft 3 ＋ audit） |

## 走行の記録（往復ごとに追記する）

| # | リクエスト | 結果 | 日時 |
| --- | --- | --- | --- |
| 1 | `design:brief`（`s1-t01-s0-design-brief-a1`、tag `CF27`） | 要求を記録・チャットで回答待ち | 2026-10-27 |

## 走行後にここへ書くこと

- 往復の回数、修復が入った箇所（設計の doc 名・本文の章）。
- 標本の `status`、設計 8 文書の `status` と `attempts`、章ごとの字数（最終と attempt 1）。
- `results.json` の verdict をそのまま引用（B3 は 2 つの数え方の両方）。
- バッチ A・固定設計の `s1-draft` との並置は**参考値**として書き、効果の推定とは書かない。
- 回答者が誰で、`provenance.origin` が何だったか（独立性の限界）。

## 限界（走る前から言えること）

- **N=1。** 分布ではない。率・区間・有意差は出さない。
- **plan は固定。** 設計段の出来は測るが、企画段の出来は入っていない。
- **同じ canon・同じタスク・同じ回答者。** バッチ A との差を方式の効果と呼ばない。
  プロンプトも別物（Stage B の `stage-b-rewrite` と S1 の `draft-chapter`）。
- 設計検査は修復上限後に `unresolved` でも本文へ進む（S1 の仕様）。`clean` は意味的整合の
  保証ではない。
- 本文のマーカーは**自己申告**である。S1 には `{{location}}` の中身を canon と照合する検査が
  無い（B5 はその有無を記録するだけで、直しはしない）。
