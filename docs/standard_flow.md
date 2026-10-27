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

各段の間で、応答待ちは必ず1つの状態として残る。

```text
run / resume が exit 3
  → relay export  （未回答のプロンプトを PROMPTS.md と index.json に書き出す）
  → 生成（Arena のAIが1件ずつ応答する。応答の捏造・代筆はしない）
  → relay ingest  （<<<ANSWER タグ>>> を responses/ へ。タグ→key は台帳が決める）
  → resume        （記録済みの応答は再生成せず、次の未回答から続ける）
```

`run` は最初の1回だけ、以後は `resume` を使う。`resume` は記録済み応答を照合して
再利用し、次の未回答から provider へ委譲する。応答ファイルが無いまま `resume` しても
新しい run は作らず、exit 3 で待機状態を返す。

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
- 最終成果物は `render --out <root>/<project_id>/manuscript.md` の markdown である。
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
