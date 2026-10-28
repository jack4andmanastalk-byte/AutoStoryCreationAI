# 標準の自動創作フロー（U-01 の決定）

- 決定日: 2026-10-27
- 状態: 採用。以後、「標準で1本作る」経路は本書の1つだけとする。
- 関連: [`practical_roadmap.md`](practical_roadmap.md)（U-01）、
  [`quickstart.md`](quickstart.md)（実行手順）、
  [`project.md`](project.md)（創作projectの機能一覧）、
  [`arena_operation.md`](arena_operation.md)（Arena × GitHub の運用モデル）

## 1. 決定

**標準入口は `scripts/story_project.py`（創作project）とする。**
題材と条件（題名・premise・章数・目標字数）を渡し、`plan → 8設計 → draft` を通して
3章の原稿まで進め、そのまま `continue` / `revise` / `branch` / `compose` / `bundle` で
続き・改訂・分岐・編纂へ進める。生成の担い手は既定で **Arena relay**
（`<project>/relay` に置いたプロンプトと応答）であり、人間（またはArenaのAI）は
プロンプトを1件処理して応答を書き戻すだけである。

他の2つの入口は、標準経路ではなく**実験・履歴のための固定経路**として残す。

| 入口 | 役割 | 位置づけ |
| --- | --- | --- |
| `scripts/story_project.py` | 任意の題材から作品を作り、状態を保って続き・改訂・分岐・編纂へ進む | **標準** |
| `scripts/run_pipeline.py` | 固定タスク `t01`（`benchmarks/protocol-v1/tasks.yaml`）を protocol-v1 で回す研究用ハーネス | 凍結した実験条件の再実行・参照。事前登録したバッチの経路 |
| `scripts/run_twostage.py` | Stage A（`game_log.json`）→ Stage B（散文化）の二段階方式スライス | 実験経路。固定台本バンドルと回帰テストが対象 |
| `scripts/story_project.py --provider command` | 外部コマンド（`model_adapter.py` 等）を繋ぐ互換経路 | 標準の relay を使わない場合の代替 |

`run_pipeline.py` を標準にしない理由は、題材が固定タスクに限られること、作品を
続き・改訂へ進める状態モデルを持たないこと、protocol-v1 の凍結条件（L1 の比較）と
実用の改善が同じコマンドに混ざるためである。`run_twostage.py` を標準にしない理由は、
章ごとの構造化ログを作る追加工程が要り、固定 canon・固定 design を前提にした
スライスだからである（[`two_stage_slice.md`](two_stage_slice.md)）。

過去のバッチ（A / B / B2 など）の結果と手順は書き換えない。標準フローは新しい作品を
作るための経路であり、凍結した実験の再解釈ではない。

## 2. 流れ

```text
題材・条件（--title / --premise / --chapters / --target-chars）
        │  init                      … 作品と revision を固定
        ▼
[plan]  canon 6 チャネル             … 検査を通った canon だけが次へ
        │  run                      … 応答が無ければ exit 3 で待つ
        ▼
[design] 8 設計書（brief/world/history/character/relation/plot/scene/voice）
        │                          … 各設計書を既存検査器で検証
        ▼
[draft]  章本文（3章）              … マーカー・知識境界・必須語などを検証
        │
        ├─ status / doctor         … 状態・未回答・整合性
        ├─ render --out            … 読める原稿（manuscript.md）
        └─ continue / revise / branch / compose / bundle
```

各段の間で、応答待ちは必ず1つの状態として残る。1巡（1ラウンド）は次の3つで完結する。

```text
① run（最初の1回だけ）または relay submit
   → exit 3。このとき PROMPTS.md が自動更新され、次の1件が示される
② 待っている1件に応答する
   → プロンプトは relay/requests/ にある。生成した本文だけを answers.txt に
     <<<ANSWER タグ>>> … <<<END タグ>>> で書く（捏造・代筆はしない）
③ relay submit --file answers.txt
   → 取り込み（タグ→key は台帳が決める。prompt_hash を固定して保存）
   → そのまま再開（記録済みの応答は照合して再利用し、次の未回答から委譲）
   → exit 3（次の1件）/ 0（完成）/ 2（失敗）。どれも同じ書式で報告する
```

`relay status` は生成せずに同じ報告だけを出す（`exit 0` 完成・待機なし /
`3` 応答待ち / `2` 失敗）。`relay export` と `relay ingest` は③を分割した
下位コマンドで、取り込みだけ・書き出しだけを行いたいときに使う。

`run` は最初の1回だけ、以後は `relay submit`（または `resume`）を使う。`resume` は
記録済み応答を照合して再利用し、次の未回答から provider へ委譲する。応答ファイルが
無いまま `resume` しても新しい run は作らず、exit 3 で待機状態を返す。完成した作品に
`relay submit` しても取り込まず、「完成済み。新しい版は `continue` / `revise`」と返す。

### 1ラウンドの報告

`relay status` / `relay submit` は、どの状態でも同じ形で答える。

```text
Project: prj-seaside (waiting_response)
Stages: plan=done, design=waiting_response, draft=pending
Relay: 1 answered / 1 pending / 2 request(s) recorded
Relay directory: works/prj-seaside/relay
Next request: tag 1F3A9C2D (design:brief)
  request:  works/prj-seaside/relay/requests/<key>.json
  response: works/prj-seaside/relay/responses/<key>.json
Next: python3 scripts/story_project.py --root works relay submit prj-seaside --file <answers.txt>
```

- 待っている要求は**パイプライン順**（plan → design → draft）で1件だけ示す。
- 括弧内は要求の `purpose`（`design:brief`、`draft:ch02` のように stage を含む）。
  `relay/index.json` は export 時点の控えなので、待ちの正は `relay status`。
- 完成なら `Next:` が原稿の書き出しコマンドになる。失敗なら `--retry-failed` になる。
- 同じ内容が `status` / `doctor` の `next_actions` にも出る（`relay export`）。
- 終了コードは「作業単位の状態」そのもの: `0` 完了・待機なし、`3` 応答待ち、`2` 失敗。

### 完了済み応答を再生成しない

- `relay export` は**未回答だけ**を書き出す。回答済みは件数としてしか出ない。
- `relay submit` は取り込んだ応答を `prompt_hash` 付きで保存し、`resume` は記録済みの
  応答を prompt・seed・temperature・request key で照合して再利用する。照合が合わなければ
  再開を拒否する。
- 完成済み・失敗済みの作品への `relay submit` は取り込まない（完成時は `0`、失敗時は
  `--retry-failed` の案内）。保存済みの応答ファイルは書き換えない。

## 3. 状態と成果物の場所

```text
<root>/<project_id>/
├── project.json / nodes/           作品・revision・checkpoint（状態の正）
├── relay/                          Arena relay（標準の生成経路）
│   ├── requests/<key>.json         prompt 全文と prompt_hash
│   ├── responses/<key>.json        応答（prompt_hash・model 付き）
│   ├── PROMPTS.md / index.json     relay export の出力（未回答のみ）
│   └── outbox/request-NN-<tag>.md  1件ずつ貼るための断片
├── runs/<attempt>-<stage>/         manifest・responses.jsonl・canon・design・text
├── artifacts/                      結合 markdown 等
└── manuscript.md                   `render --out` の出力（読むための原稿）
```

- 既定の `<root>` は `runs/projects/` だが、**`runs/` は git 管理外**でセッションを
  越えて残る保証がない。残す作品は `--root works`（リポジトリ内・版管理）に置く。
  実験として登録する走りは `experiments/<id>/` に置く。
- 最終成果物は `render --out <root>/<project_id>/manuscript.md` の markdown である（検査マーカー込みの正本）。
  人間が読むときは `render --reader` で章見出し付き・マーカーなしの読書用コピーも出せる。
  JSON（`runs/`）を開かないと本文が読めない状態を標準にしない。
- `status` は完成した作品で `Manuscript:` と書き出しコマンドを表示する。
- 再現に必要な材料は `bundle export` にまとまる（relay と run のハッシュ付き）。

## 4. 検査の位置づけ

標準経路が止まるのは、生成物の形が壊れた場合と、明確に作品を壊す所見だけである。

- plan の canon が既存スキーマ・検査を満たさない → 修復プロンプトで再試行し、
  それでも駄目なら `failed`。
- 8設計は各検査器（brief/world/history/character/relation/plot/scene/voice）を通る。
- draft は章ごとの検証（マーカー・知識境界・必須語・死者の扱い）を通る。
- `doctor` は project・node・revision・artifact・world・pending を横断して確認する。

`clean` / `pass` は「検査した範囲で進める」という意味であり、面白さや品質の保証では
ない。L2/L3 は `frozen_not_measured` のまま扱い、標準フローは品質を主張しない。

## 5. 今回の決定に伴う実装変更

| 変更 | 内容 | 理由 |
| --- | --- | --- |
| 既定 provider | `run` / `resume` / `continue` / `run-tree` / `revise` / `branch` の省略時は `arena`（relay） | 「標準で1本作る」に provider の配線を書かせない |
| `--provider arena` | `<project>/relay` の `chat_operator.py` を provider にする。run manifest の provider は `arena-relay` | relay 経由の応答を、台本（`scripted`）や外部コマンド（`command`）と後から区別できる |
| `relay export / status / ingest` | 創作projectのサブコマンド。既定の出力先は `<project>/relay` 自身 | 台帳・タグ・貼り付け形式を1か所に集約し、`--dir` の手作業をなくす |
| 応答待ちの表示 | `run`/`resume` が exit 3 のとき、PROMPTS.md のパスと ingest / resume の次コマンドを表示 | 待機状態で次に開くファイルを迷わない |
| relay タグ | 4 hex → **8 hex** | 同一 node では key が `purpose` しか違わず、4文字で実際に衝突した。衝突時は応答が別 request に付いたまま成功と表示された（U-01 の作例で発見） |
| 完成時の表示 | `status` が `Manuscript:` と `render --out` を表示 | 最終成果物と状態を1コマンドで示す |
| 未開始の next action | `run <project>`（provider 引数なし） | 既定 provider が relay になったため |
| `relay submit`（U-02） | 取り込みと再開を1コマンドにし、状態・次の1件・次のコマンド・完成/失敗を同じ書式で報告 | 1ラウンドが「3コマンド+状態確認」に分かれ、往復のたびに台帳を読み直していた |
| `relay status` の終了コード | `0` / `3` / `2` を状態に対応させた | スクリプトも人も、報告を読まずに次を決められる |
| 待機中の next action | `pending` → `relay export`（`status` / `doctor` 共通） | relay 手順と別の入口に見えていた |
| 完成・失敗時の `relay submit` | 取り込まずに `continue`/`revise` または `--retry-failed` を案内 | 完了済み応答の上書きと、再試行で再利用されない回答の収集を防ぐ |
| `status` の relay 行 | `Relay: N answered / M pending` | 完成・待機が1画面で分かる |
| 字数の目安（F-39 / U-11） | 単一の `--target-chars` も draft では **±5%** の許容幅として扱い、幅の外にだけ `Warnings:` を出す | 1200 字指定で 1201 字が「目安の外」になり、±数十字の調整に時間を使っていた |
| carried した設計書の履歴（F-40 / U-12） | `revise` / `continue` で持ち越す設計書は元 run の試行・修復・所見を引き継ぎ、`summary` の Info に累計と「このリビジョンでの作り直し」を出す | 1章だけ作り直すと、8設計がすべて「試行0・修復0」に見えていた |
| `revise --note`（F-41） | 改訂の意図を依頼文の `## 改訂の意図` に渡し、`derived.note` と `summary` に残す | 「何を直したいか」を渡す口がなく、狙いと別の点が変わりうる |

`build_actions` の pending 関連の文言（`pending` → `relay export` への統一など）は
**U-02 で扱う**。今回は既存の契約を壊さない範囲に留めた。

## 6. 非目標（維持）

- 常駐ワーカー、スケジューラ、自動リトライ、依存 queue の自動消化。
- L2/L3 の評定・較正、品質・面白さの主張、率・再発率・因果効果の主張。
- ローカル実行を前提にした手順。手順書の宛先は Arena エージェントとする
  （[`arena_operation.md`](arena_operation.md)）。

## 7. U-01 の記録（最小記録）

- **きっかけ**: 入口が `run_pipeline.py`・二段階方式・創作projectに分かれ、
  「標準で1本作る」導線が1つに定まっていなかった（roadmap §3）。
- **困りごとの分類**: 運用（入口の選択と relay の往復）。
- **行った変更**: 上表のとおり。加えて `docs/quickstart.md` を新設し、
  `tests/test_standard_flow.py` で導線を回帰対象にした。
- **確認したこと**: 固定台本（`benchmarks/protocol-v1/fixtures/project-demo.json`）
  で、premise → init → run → relay export → ingest → resume ×12 → render が通り、
  3章の原稿と `status` / `doctor` の表示を確認した。**実モデルの応答ではない。**
  記録は [`experiments/2026-10-u01-standard-flow-t01/`](../experiments/2026-10-u01-standard-flow-t01/note.md)。
- **残した制限**: 実応答での導線確認は U-03（dogfood）で行う。relay の往復回数
  （1作品で12回）と、stage ごとの一括書き出しは U-02 の課題として残した。

## 8. U-02 の記録（2026-10-27）

- **きっかけ**: U-01 の作例で、1作品が12往復になり、各往復が「export → 生成 → ingest →
  resume → status」の5操作に分かれていた。状態の確認と次の操作が別の場所にあった。
- **困りごとの分類**: 運用（往復と状態確認）。
- **行った変更**:
  - `relay submit`（ingest + resume）を追加し、1ラウンドを1コマンドにした。
  - `relay status` を1ラウンドの報告に統一し、終了コードを状態に対応させた
    （`0` 完了・待機なし / `3` 応答待ち / `2` 失敗）。
  - 待機中の `next_actions` を `relay export` に変更（`status` と `doctor` で共通）。
  - 完成済み・失敗済みの作品では `relay submit` が取り込まないようにした。
  - `status` に `Relay: N answered / M pending` を表示。
- **確認したこと**: 固定台本で、1作品を12ラウンド（各1コマンド）で完成まで通した。
  要求数12・応答数12のまま増えず、完成後の再 submit は応答ファイルを1バイトも変えない。
  失敗stageでは `--retry-failed` を案内し、回答は取り込まない。記録は
  [`experiments/2026-10-u02-relay-round-t01/`](../experiments/2026-10-u02-relay-round-t01/note.md)。
- **残した制限**: 往復回数そのもの（12）は減っていない。設計8件と本文3件は前段の結果に
  依存するため、プロンプトを先に作れない（推測生成をしない方針）。往復を減らすには
  「1つの応答の中で複数成果物を返す」契約変更が要るが、検査の粒度が変わるため
  U-03 の実運用で必要性が出てから扱う。実応答での確認は U-03。

