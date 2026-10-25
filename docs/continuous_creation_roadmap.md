# 継続創作基盤：タスク分解・設計・実装順序

- 日付: 2026-10-25
- 状態: **PR 1〜14を実装済み（PR 14はドキュメントのみ）。次は中規模dogfoodで必要性を実測してから候補を決める**
- 対象: AIによる創作を中断・再開し、続編・入れ子作品・世界スケールの作品群へ拡張する基盤
- 前提: PR #18 マージ後の既存 pipeline / skills / replay / Arena operator を利用する

## 1. 決定事項

今後の主目的は、作品の品質を詳細に作り込んだり保証したりすることではなく、
**創作プロジェクトを持続可能にする実行基盤**を完成させることとする。

実装は次の順序で進める。

1. **単一作品の作成・状態保存**
2. **中断からの再開**
3. **完成後の続きの作成と、創作資料の外部保存**
4. **子作品を埋め込む入れ子作品**
5. **複数の時間軸・地域・文化を持つ世界スケール親作品**
6. 必要になった段階で、skill registry と追加ワークフロー

最初から全世界モデルや汎用skill基盤を実装しない。単一作品の縦割りを先に動かし、
その後も各段階で実際に使えるものだけを拡張する。

## 2. 範囲と非目標

### 2.1 今回の実装範囲

- 任意の premise から始める創作プロジェクト
- 作品・章・設計・生成runの永続的な参照
- 応答待ち・プロセス中断からの再開
- 完成済み作品を変更せずに、続きの章や続編を追加
- 子作品を独立に実行し、親作品へ版付きで埋め込む
- 世界共通の設定と、時代・地域・文化ごとの局部設定を分離
- 年代記・地誌・文化圏・作品集などの編纂出力
- Arena operator、既存provider、replayとの接続
- 上記を支える最小限の技術的な回帰test

### 2.2 非目標

- 文体・構成・文化的描写の詳細な品質改善
- 品質スコア、品質ゲート、人間による評定
- L2/L3の実証・較正・追加開発
- protocol-v1、凍結対照群、既存の正式実験結果の変更
- ベンチマークのタスク・seedを増やすこと自体を目的にした作業
- モデルの独立再現性（G5）の主張
- 初期段階でのWeb UI、DB、分散実行、複数writerの同時更新
- 完全自動運用（常駐ワーカー、スケジューラ、依存queueの自動消化、失敗時の自動リトライ）

既存の構造checkerは残すが、新しい作品品質の評価基準は追加しない。
生成の開始は毎回人間が明示的に行う（[project.md](project.md)の「運用モード」）。
testは「良い作品」を判定するためではなく、保存・再開・参照・出力が壊れないことを
確認するために使う。

## 3. 既存資産と不足しているもの

### 3.1 再利用する資産

- `build_plan` / `build_design` / `build_story` / `build_revision` / `build_voice_pass`
- `GenerationRequest` / `CommandProvider` / `ScriptedProvider`
- `RunLedger` と `responses.jsonl`
- `chat_operator.py` / `relay_prompts.py`
- 厳密な記録再生を行う `ReplayProvider`
- canon・13種のskill・各種構造checker
- SHA-256、prompt hash、response provenance

### 3.2 主な不足

- 任意の創作プロジェクトを表す永続モデルがない
- runをまたぐ作品状態と、stageごとの完了状態がない
- 未完runの応答prefixを使って再開するproviderがない
- 完成後に、旧版を守ったまま章を追加する概念がない
- 作品の親子関係、埋め込み位置、子作品の版への参照がない
- canonの適用範囲、文化の時代状態、複数時間軸がない
- 子作品に必要な文脈だけを組み立てる層がない
- replayに必要な原本を外部へ保存・復元するbundleがない

## 4. 全体アーキテクチャ

### 4.1 二つの関係を分ける

世界スケールまで見据え、次の二つを別の構造として扱う。

1. ** containment tree（包含木）**  
   親作品 → 子作品 → 章・場面。出力順と創作の実行単位を表す。
2. **reference graph（参照グラフ）**  
   時間軸・地域・文化・人物・出来事・canon・版の依存関係を表す。

文化や出来事を包含木に無理やり入れない。子作品は一つの親を持ちながら、
複数の時間軸・地域・文化状態を参照できるようにする。

### 4.2 主要モデル

| モデル | 役割 |
| --- | --- |
| `WorkProject` | 一つの創作プロジェクト全体。schema versionとroot nodeを持つ |
| `WorkNode` | work / chapter / scene / embedded_work の実行・編纂単位 |
| `WorkSpec` | title、premise、genre、章構成、文字数目標、生成条件 |
| `WorkNodeRevision` | あるnodeの入力と生成条件の版。編集時は新版を作る |
| `ArtifactRef` | canon・設計・本文などへのpath、SHA-256、生成run、版 |
| `StageCheckpoint` | stageごとの状態、run ID、完了成果物、待機中request |
| `ResumeLink` | 再開先runと、prefixを取得した未完runの関係 |
| `WorkLink` | 埋め込み位置、依存、前提とする子作品の版 |
| `CanonScope` | global / timeframe / region / culture / work / node の適用範囲 |
| `TimeFrame` / `TimeSpan` | 暦・時間軸・精度・期間・時間軸間の対応 |
| `Region` / `SpatialRelation` | 空間領域と、既知の移動・接続関係 |
| `Culture` / `CultureState` | 文化の永続IDと、時代・地域で変化する状態 |
| `ContextPacket` | 子作品の生成に渡す、時代・地域・知識で絞った文脈 |
| `CompilationProfile` | 年代順・地域別・文化別・単一書籍などの出力定義 |

全てに `schema_version` を持たせ、生成物とその版を区別する。
最初から全modelを実装せず、各段階で必要なものだけを追加する。

### 4.3 runとprojectの責務を分ける

- `RunLedger` は、一回の生成実行の不変な記録とする。
- `ProjectStore` は、作品の現在位置と、runへの参照を管理する。
- 完了したrunを直接書き換えない。
- 再開は、未完runの応答prefixを利用した**新しいrun attempt**として記録する。
- premiseや章構成を変更した場合はresumeではなく、新しい `WorkNodeRevision` にする。

これにより、通常の実験run、厳密なreplay、創作プロジェクトの現在状態を混同しない。

### 4.4 状態遷移

`StageCheckpoint` は少なくとも次の状態を持つ。

```text
pending → ready → running → done
                    ├→ waiting_response → running
                    └→ failed
pending / ready / running / waiting_response / done → stale（依存版の変更時）
```

- `done` は、成功manifestと、hash付きの必須成果物がそろった場合にだけする。
- `waiting_response` は、operatorの未回答を待つ状態で、失敗とは区別する。
- validation上の `failed` を、無条件にresumeして同じ失敗を繰り返さない。
- `stale` は現在の出力を消す状態ではなく、新しい依存版を明示的に採用するまで保持する。
- nodeの状態は、子nodeとstageの状態から算出し、別々に手動で矛盾した更新をしない。

### 4.5 保存形式と場所

初期実装は、外部DBを使わず、JSONファイルと既存のrun directoryを使う。

```text
runs/projects/<project_id>/
├── project.json
├── nodes/<node_id>/current.json
├── nodes/<node_id>/revisions/<revision_id>.json
├── nodes/<node_id>/checkpoints/<stage>.json
├── artifacts/
└── runs/<run-attempt-id>/
```

- `runs/` は従来どおりGit管理外とし、生成本文・応答をcommitしない。
- 小さな現在状態だけをatomic writeで更新する。
- 同時writerは初期段階では許可せず、lockを検出したら停止する。
- コード・schema・fixture・testはGitへ入れ、創作データは外部保存に任せる。

## 5. 再開と続編の設計

### 5.1 中断再開と創作上の続編を区別する

- **resume**: 未完のplan/design/draftを、同じ入力と版で完了させる。
- **continuation**: 完成した作品の旧版を保ったまま、新しい章・続編を追加する。

continuationを、単に未完runへ応答を足す操作として扱わない。

### 5.2 ResumeProvider

厳密な `ReplayProvider` は変更せず、再開専用のproviderを追加する。

1. 未完runの `responses.jsonl` を、設定hashとrequest keyで照合する。
2. 記録済みの応答は、順序どおりprefixとして返す。
3. prefixの次のrequestから、Arena operatorなどの通常providerへ委譲する。
4. 返した応答には、replay/freshとsource runを区別したprovenanceを付ける。
5. promptが変わっていたら停止し、別revisionにする。

replayの記録読み取り層は共通化できるが、厳密replayが要求する `status=ok` を
未完resumeへ緩和しない。検査上の失敗を、単なる中断として無条件に再実行もしない。

外部providerの呼出し自体に分散トランザクションはないため、絶対的な exactly-once は
約束しない。operator responseとrun ledgerの両方を使い、**記録済みpromptを再度新規生成しない**
ことを実装上の目標にする。

### 5.3 続きの章・続編

- 旧章の本文と旧canonは変更しない。
- 新しい章構成を持つrevisionを作る。
- 新しいcanon versionとrunを作り、前版への参照を残す。
- 生成時には、過去の本文全文ではなく、設定に応じた前章・要約・canonを渡す。
- 旧版から新規生成したものと、厳密replayしたものを区別する。

## 6. 入れ子作品の設計

### 6.1 深さ1から多段へ拡張する

- 親作品に複数の子作品を配置でき、子の下にも孫作品を配置できる。
- root=0・最大深さ8のcontainment treeとして、全nodeのancestryを検証する。
- 子作品は独立した `WorkNode` とpipeline状態を持つ。
- 親は子作品の `ArtifactRef` と `content_version` を保持する。
- 子作品の本文を親のmetadataへコピーしない。
- 循環・orphan・深さ超過の親子関係は拒否する。
- 依存順実行はparent-before-descendantのtopological orderとし、未完の依存を飛び越えない。

### 6.2 版とstale

子作品に新版ができても、親の参照版は自動更新しない。

1. 子作品の新しい版を発行
2. その版を参照する親リンクをstaleとして表示
3. 明示的に新版を採用
4. 親の結合出力を再生成

### 6.3 編纂出力

- 子作品を単独で出力する方式と、親へ再帰的に埋め込む方式を分ける。
- 同じnode revisionとartifact versionからは、同じ順序・見出しで出力する。
- 多段化するときも、本文の配置とcanonの継承を別々に処理する。

## 7. 世界スケール親作品の設計

### 7.1 時間

- 単一の浮動小数点 `day` だけに依存しない。
- 複数の `TimeFrame`、暦、epoch、近似・期間・不明な年代を扱う。
- 時間軸間の変換がないものは、無理に単一年表へ並べない。
- 出来事の前後関係と、変換可能な絶対時刻を区別する。

### 7.2 空間

- `Region` は入れ子にできるが、文化や作品の唯一の親にはしない。
- 移動日数が不明な領域へ、既存の `travel_days` を勝手に適用しない。
- 時間軸によって存在・接続が変わる地域には有効期間を持たせる。

### 7.3 文化

- `Culture` は永続ID、`CultureState` は時代・地域に有効な版とする。
- 文化の分裂・接触・継承はstate間の関係として表す。
- 子作品は、当時の `CultureState` を参照し、未来の状態を暗黙に共有しない。
- このmodelは運用上の参照範囲を示すもので、文化的描写の質を保証するものではない。

### 7.4 世界台帳と文脈

- 子作品のlocal canonを、自動的に世界共通の正史へ昇格させない。
- 世界台帳への採用は明示的な操作とし、採用元の作品・版を残す。
- `ContextPacket` は、時代・地域・文化・人物の知識で絞って作成する。
- 数千年分の全歴史を毎回promptへ入れない。
- 子作品の改訂による依存先のstaleは、自動改訂ではなく通知に留める。

## 8. タスク一覧と依存関係

| ID | タスク | 主な成果物 | 依存 |
| --- | --- | --- | --- |
| F-01 | project model / store | `WorkProject`, `WorkNode`, `ArtifactRef`, JSON store | なし |
| F-02 | 創作用入力のadapter | `WorkSpec` から既存pipelineへの変換 | F-01 |
| F-03 | 単一作品runner | plan→design→draft、stage checkpoint | F-01, F-02 |
| F-04 | 基本CLI | `story_project init/run/status` | F-01（init/status）、F-03（run） |
| R-01 | resume用の応答prefix読み取り | recorded response index、provenance | F-03 |
| R-02 | ResumeProvider / coordinator | 未完runの再開、`resume_of` | R-01 |
| R-03 | operator待機の集約 | project/node別pending、再開可能なstatus | F-04, R-02 |
| C-01 | continuation | 章追加・続編revision、旧版の保持 | F-03 |
| D-01 | replay bundle | export / verify / restore、hash一覧 | F-03, R-02 |
| N-01 | 入れ子nodeと配置 | embedded_work、order、循環拒否 | F-01, C-01 |
| N-02 | 子作品runner | 深さ1の子作品実行と個別再開 | N-01, R-02 |
| N-03 | 版付きlinkとscope | content version、stale、canon scope | N-01 |
| N-04 | 再帰compiler | 単独出力・親への埋め込み | N-01, N-03 |
| N-05 | 多段・依存の拡張 | 孫作品、依存topological order | N-02〜04 |
| W-01 | 時間model | TimeFrame、TimeSpan、複数暦、精度 | N-03 |
| W-02 | 空間model | Region、SpatialRelation、有効期間 | W-01 |
| W-03 | 文化model | Culture、CultureState、分裂・接触 | W-01, W-02 |
| W-04 | 世界canon / 世界台帳 | scope overlay、明示的な正史への採用 | W-01〜03 |
| W-05 | ContextPacket | 時代・地域・文化・知識による文脈選択 | W-04 |
| W-06 | 世界の編纂view | 年代記・地誌・文化圏・作品集 | N-04, W-04 |
| X-01 | skill registry / optional workflow | 必要なskillだけを呼ぶ登録層 | F-03以降、必要時 |

## 9. 決定した実装順序（PR単位）

### PR 1: 単一作品のproject foundation（F-01, F-02, F-04のinit/status）

- JSON schema、stable ID、project store、WorkSpecを実装する。
- `story_project init` と `status` を作る。
- まだ生成は行わない。
- 将来のnested用に、parent ID・artifact version・schema versionだけを確保する。

**完了条件**: 任意premiseのprojectを作成し、別processで同じ状態を読める。

### PR 2: 単一作品のvertical slice（F-03, F-04のrun）

- 既存S1を呼び、plan→design→draftを実行する。
- protocol-v1のTaskとは別に、任意の章数・文字数目標をadapterで渡す。
- stageごとにcheckpointを保存する。
- S2/S3や品質改稿は必須経路にしない。

**完了条件**: 新規projectから3章を作成し、各stageのrunと成果物をstatusで辿れる。

### PR 3: 中断再開とoperator待機（R-01〜03）

- 未完runの応答prefixを使うResumeProviderを実装する。
- `story_project resume` とpending一覧を追加する。
- prompt/revisionの変更を検出したら再開を拒否する。
- 厳密なreplayの仕様は変更しない。

**完了条件**: plan/design/draftの各段階で中断しても、完了済み応答を新規生成せず、
同じrevisionを最後まで完了できる。

### PR 4: 続きの作成と外部保存（C-01, D-01）

実装: parent revision / stage runを参照する新版、旧章のbyte-identicalな引継ぎ、追加章だけの
生成、全payloadのSHA-256 manifest付きexport / verify / restoreを追加。continuation専用の
revision-scoped request keyを使い、revisionを持たない旧request keyは変更しない。

- 完成後の章追加・続編revisionを実装する。
- replayに必要な原本をbundleとしてexport/verify/restoreする。
- bundleはGitへ入れず、指定した外部pathへ保存する。

**完了条件**: 旧章のhashが変わらず、新版だけが増える。保存したbundleから同じ資料を復元できる。

### PR 5: 深さ1の入れ子作品（N-01〜04のうち深さ1）

実装: root直下の独立した子node、順序・pinned revision・ArtifactRef・content_versionを持つ
`WorkLink`、node別のrun/resume/continuation、stale表示、明示的なadopt、単一/結合出力を追加。
結合versionには時刻を含めず、子の新版で旧結合が変わらないことをoffline testで確認する。

- 親作品へ子作品を追加するCLIと、子作品の独立したrunnerを実装する。
- 版付きlinkとstale、単一作品/結合出力を実装する。
- canon共有は最小限にし、子作品の独立を既定にする。

**完了条件**: 親に2つの子作品を配置し、片方だけを再開・更新できる。
親が固定した版の結合出力は、子の新版で勝手に変わらない。

### PR 6: 多段入れ子と依存順序（N-05）

実装: root=0・最大深さ8の任意親への子作成、全nodeのancestry/cycle検証、全階層の
link/status/pending集約、nested linkのsync/adopt、深さ付き再帰composeを追加。`run-tree`と
`dependency_order`はlink順のparent-before-descendant topological orderを使い、完了nodeを
再実行せず、未完・失敗・待機中のnodeとそのdescendantで安全に停止する。単独nodeの
run/resume/continuationとPR 5のpinned/stale契約は維持する。

`context.py`の`asc-context-packet-pre1`は、祖先のcompact canonと章の構造要約だけを選択し、
章本文を除外してpromptと`project-input.json`へ記録するContextPacket前身である。世界modelの
時代・地域・文化選択はまだ行わない。

**完了条件**: 親→子→孫を個別に再開でき、循環や未完了の依存を検出して停止できる。
多段のpinned結合が決定的で、bundle復元後も同じ本文を再現できることをoffline testで確認した。

### PR 7: 世界model（W-01〜04）

実装: `world.py` / `world_store.py` に、複数TimeFrame、exact/approximate/range/unknownの
TimeSpan、明示的な時間変換、入れ子Region、有効期間付きSpatialRelation、Cultureと版付き
CultureState、state間の継承・分裂・接触を追加。作品revisionへ固定する `WorkWorldBinding`、
scope overlayを持つ `WorldCanonEntry`、pinned sourceからの明示的採用と
stale通知を実装し、world recordもreplay bundleのhash・復元検証へ含める。

- 複数時間軸、地域、文化状態、有効期間付きcanonを実装する。
- まずは少数の時代・地域・文化でschemaと保存を確立する。
- 世界の正史への採用を、子作品の生成から分離する。

**完了条件**: 二つの時間軸と複数時代の文化状態を持つ子作品を、同じ世界project内に保存できる。

### PR 8: 世界規模の生成文脈と編纂（W-05, W-06）

実装: `world_context.py`で、現在revisionのbindingが明示したTimeSpan・Region・CultureStateと、
current・scope・有効期間に合うcanonだけを選択。`WorkSpec.options.context_knowledge`と祖先
`Character.knows`で人物別のfacts選択も行う。`asc-context-packet-world1`に参照ID・content version・
overlay順を記録し、指定なしprojectのpre1 packetを維持する。resumeは記録packetを再利用し、
continuationは`--world-binding`を指定した場合だけ旧選択を新版へ複製する。
`world_compile.py`と`world add-profile|profiles|compile`で、時間軸別の年代記、地域別の地誌、
文化圏、pinned作品集を生成し、profileと選択sourceの版から決定的な出力versionを作る。

- ContextPacketを生成し、子作品へ必要な世界情報だけを渡す。
- 年代記・地域別・文化圏別・作品集の出力を追加する。

**完了条件**: 同じ世界資料から、子作品別の文脈と複数の編纂出力を生成できる。
全歴史をpromptへ渡さず、参照した資料のIDと版を記録できる。

### PR 9: 運用dogfoodと可観測性（実装済み）

Arena operator（`scripts/chat_operator.py`）で小規模な実創作projectを最後まで操作し、観測した
運用課題だけを`doctor`と`context show`として実装した。`doctor.py`はproject/node/revision/
checkpoint/link/世界record/runの7検査をまとめ、pending responseの`response_ready`、staleな
link・canon・bindingの対象ID、`failed`/`running` stageをfindingとして返す。`context_view.py`は
現在のpacketとrunに記録済みのpacketを同じ形で表示し、参照recordのID・content version・overlay順・
byte数・hashを出す。同じrevisionの記録packetに限り、現在値との差分（追加/削除/版変更）を表示する。
どちらも読み取り専用で、生成・再開・採用・編纂・復元を起動しない。

dogfoodは2時間軸・3地域・2文化・3文化状態、root→child→grandchild、43 operator応答、
19 run directory（11 attempt）で、中断再開、continuation、人物別知識、明示canon採用と
supersession、5編纂view、bundle export/restore、別rootへの復元を含む。復元先の`doctor`と
`context show`は元projectと同じ結果になった。観測した未解決課題は、`failed` stageの再試行手段が
CLIにないこと、`content_version`を持たない世界recordの改変を検出できないこと、
編纂view/packetの差分をrecord単位で一覧できないこと（`diff`候補）である。

- Arena operatorで、二つの時間軸・少数の時代/地域/文化・親子孫作品を使う小規模な実創作を行う。
- 中断再開、continuation、世界binding、canon採用、stale/adopt、編纂、bundle復元を一通り操作する。
- 作品品質ではなく、operator操作回数、pending/staleの解消手順、ContextPacketサイズ、選択資料と版、
  中断・復元が必要になった箇所を記録する。生成した創作データはGitへ入れない。
- まずは`story_project doctor`と`context show`を最小実装の候補とし、dogfoodで確認した必要性に応じて
  `diff`・`next`を後続PRへ分割する。検査は生成や自動採用を行わず、現在/記録済みの版を読む操作に限定する。

**完了条件**: project・世界record・参照artifactの異常とpending/staleを検査でき、選択nodeの
ContextPacketと参照ID/content versionを確認できる。同じ小規模projectで運用手順を再現し、
発見した問題を品質評価と混同せず次の実装対象へ分類できる。

### PR 10: 章単位の改訂・分岐workflow（実装済み）

`runner.revise` / `runner.branch` と `revise.py` で、完成した任意revisionから新しいrevision
（または新しいnode）を作る。指定した章と設計資料だけを生成し直し、それ以外は元runから
byte単位でコピーする。planと未指定のdesign資料はproviderを呼ばないcarried stageとして
新しいrunに記録し、`revise.json` にコピー元hashと再生成対象を残す。改訂章のpromptには
「改訂する章／本文を保持する章」を明示し、旧本文は渡さない。中断した改訂は`resume`でき、
親のpinned出力は`adopt-child`まで変わらない。世界bindingは`--world-binding`指定時だけ複製する。

- 完成した任意revisionから`revise`で新版を作り、指定した章・設計だけを再生成する。
- 変更しない章とartifactはbyte-identicalに引き継ぎ、旧run・旧版を上書きしない。
- 旧revisionからのwhat-if `branch`を作り、世界bindingは明示指定した場合だけ複製する。
- 変更による親・子・canonへの影響はstale通知とし、新版の採用は明示的なadoptに限定する。
- 改訂・分岐版もresume、厳密replay、bundle、pinned composeと整合させる。

**完了条件**: 旧版の任意revisionから分岐し、選択した章だけを改訂しても、旧版と未選択章の
bytesが変わらない。中断再開とbundle復元ができ、親のpinned出力はadoptまで変わらない。

確認: `tests/test_project_revise.py` と `tests/test_project_branch.py` が、未選択章と
旧revision・旧runのbytes一致、旧revisionからの改訂、設計資料だけの再生成、中断→resume、
改訂後のcontinuation、bindingの明示複製、bundle復元後の`doctor`一致を検査する。
CLIでは同じprojectで、子作品の第2章だけをoperatorが改訂し、`compose`がadoptまで
byte-identicalであること、分岐がprovider呼び出し0回で作れることを確認した。

### PR 11: 失敗したstageの明示的な再試行（実装済み）

`resume --retry-failed` で、`failed` になったstageだけを新しいrunとしてやり直す。既定の
`resume` は従来どおり失敗stageを拒否し、`pending`（未回答request）が残るstageは従来の再開手順
（response fileを埋めて`resume`）を使う。再試行は失敗runを書き換えず、新checkpointの
`retry_of` に失敗run IDを残す。失敗runのresponseは再利用しない（`resume-audit.json` は
作られない）ため、再開（prefix再生）と再試行（新規生成）が記録上区別できる。

`status` は `Failed stages:` と `Retried stages: <stage><-<旧run>` を表示し、`doctor` の
`checkpoint.failed` findingも再試行commandを案内する。改訂（`revise`）の途中で失敗した場合の
再試行でも、引き継いだ章のbytesと`revise.json`の`copied`は変わらない。

**完了条件**: 失敗stageの再試行が明示操作でだけ起き、旧runと完了済みstageがbyte単位で
不変、再試行後のprojectが通常の`doctor`検査を通る。

確認: `tests/test_project_retry.py` が、既定`resume`の拒否、`retry_of`の記録、旧runの
bytes不変、完了stageの再利用、draft/revise失敗からの再試行、未回答requestを持つstageの
拒否、CLIの終了コードと表示を検査する。

### PR 12: 編纂view・ContextPacketのrecord単位差分（実装済み）

`diff` で、2つのContextPacketまたは同じprofileの2つの編纂viewをrecord単位で比較する。
`--left` / `--right` は `current`、`stage:<stage>`、`run:<run_id>`、
`compile:<profile_id>[@<content_version>]` を受け付ける。packet側は世界の選択資料
（`record_type`・ID・`content_version`）と祖先compact canonの項目hash、編纂側は
manifestの`source_references`を比較し、`added` / `removed` / `changed` / `unchanged`と、
bindingや省略件数、祖先revisionの差を返す。read-onlyで、記録側のrunや編纂物は書き換えない。
packetと編纂viewの混在比較は無意味なので拒否する。

**完了条件**: 編纂versionが変わった理由を、どのrecordの追加・削除・版変更かで説明でき、
比較が保存物を一切変更しない。

確認: `tests/test_project_diff.py` が、同一revisionのstage比較が`identical`になること、
明示canon採用・supersessionと祖先continuationが追加/削除recordとして現れること、
編纂2版の差分、版未指定の拒否、種類混在の拒否、read-only性、CLIの終了コードを検査する。

### PR 13: `status` / `doctor` の情報統合と世界record改変の警告（実装済み）

`observability.py` に作業要約（`work`、schema `asc-project-work-summary-v1`）と次操作
（`next_actions`）の共通定義を置き、`status` と `doctor` の両方が同じ形で返す。
`status` は checkpoints・links・pending だけを読むため、世界record・binding・run manifestの
件数は `0` ではなく `null`（表示は `not inspected`）とし、「無い」と「調べていない」を区別する。
`next_actions` は既存CLIのcommand文字列（`resume --retry-failed`、`pending`、`adopt-child`、
`world bind`、`world adopt-canon`、`diff`、`run`）と理由を返し、`doctor` のfinding文言も
同じ定義から作るため、案内が実装からずれない。自動実行はしない。

あわせて `doctor` に `world.record_changed` を追加した。`region` や `time_frame` など
`content_version` を保存しないrecordは、読み込み時のhash検証ができない。そこで各nodeの
現行revisionが記録したpacketのreference（読み取り時に計算されたhash）と現在値を比べ、
一致しない場合にwarningを出し、`diff --left run:<run_id> --right current` を案内する。
追記・明示採用・supersessionは追加/削除として扱い、この警告にはしない。

**完了条件**: 同じ状態に対して `status` と `doctor` の `work` が同じ定義で一致し（`status` は
未検査を明示）、両者の `next_actions` が同じcommandを出し、`doctor` はread-onlyのまま、
`content_version` を持たないrecordの直接編集がwarningとして現れる。

確認: `tests/test_project_observability.py` が、要約形状と未検査の`null`、status/doctor の
一致、failed/pending/stale時のaction、actionによる`adopt-child`・`world bind`の一致、
record編集の警告と`diff`案内、追記・採用・supersessionで警告しないこと、read-only性、
CLIのJSONと人間向け表示を検査する。`tests/test_project_doctor.py` の
「未検出」テストは「記録packetと比べて検出」に置き換えた。

### PR 14: 運用モードの明文化と拡張点の予約（ドキュメントのみ・実装なし）

想定するモデルはArena.aiのチャットであり、APIキーをrepositoryに置かない。生成は人間が
1コマンドで開始し、停止点では `pending` / `status` の `Next:` / `resume` で受け渡す。
常駐ワーカー・スケジューラ・依存queueの自動消化・自動リトライは非目標とする。
`WorldEvent` / `KnowledgeState` / `CharacterState` とindex・incremental検査は実装せず、
**拡張点の約束だけを先に決める**（IDの予約prefix、scopeの持ち方、additive-onlyの互換方針、
後付けしても既存runのpacketが有効なままであること）。実装の引き金は作品数ではなく、
dogfoodで観測した手戻りとする。

**完了条件**: 上記が `project.md` と本roadmapに明記され、実装・JSON・CLIの変更が無い。

### その後の候補

- より大きなdogfood（複数作品・複数時間軸・長期の中断再開）で、次に必要な運用機能を測る。
- 出来事中心の年代記と時代別の知識選択が必要になったら`WorldEvent` / `KnowledgeState` / `CharacterState`を追加する。
- 多数作品・大規模世界で実測上の問題が出たら、ContextProfile、依存順queue、index、incremental検査を追加する。
- 上記の実装・運用で繰り返し現れる共通形が見えた場合だけX-01へ進む。

### 予約する拡張点（未実装）

以下は「作らない」ではなく「必要が実測で確認できるまで作らない」項目である。後から足すとき、
既存の作品・run・packetを移行せずに済むよう、次の約束だけを先に決めておく。

| 拡張 | 状態 | 予約する約束 |
| --- | --- | --- |
| `WorldEvent` | 未実装 | record type `world_event`、IDは `event-<sha256[:32]>`。`time_frame_id` と時点（近似・不明を許す）を必須にし、既存recordのID空間とは接頭辞で分ける |
| `KnowledgeState` | 未実装 | IDは `knowledge-<sha256[:32]>`。`node_id`・`time_frame_id`・保持者・対象recordの組でscopeし、既存のcanon scope（`project`/`time_frame`/`region`/`culture`）に新しい段を足す形にする |
| `CharacterState` | 未実装 | IDは `character-state-<sha256[:32]>`。人物record本体（`character`）とは別recordにし、時点ごとの差分だけを持つ |
| index / incremental検査 | 未実装 | 追加時も保存形式は現行のまま（indexは派生で、無くても全走査で同じ結果）。`doctor` の判定結果をindex有無で変えない |
| 依存queueの自動消化 | 非目標 | `run-tree` は人間が起動し、未完nodeで止まる現行挙動を変えない |

- schemaは引き続き追加のみ（additive）。新しいrecord種別はContextPacketと編纂viewに
  **追加の欄**として載せ、既存の `references` の意味を変えない。
- 新しいrecord種別を足しても、その種別を記録していない過去のrunのpacketは有効なままとする
  （未記録は「無い」ではなく「その版では対象外」）。この区別は `status`/`doctor` の
  `inspected` と同じ考え方で扱う。
- 実装の引き金は、dogfoodで観測した具体的な手戻り（年代記の順序を手で直した、過去作品との
  矛盾を人手で修正した、同じ世界の設定を毎回designに書き直した）のいずれかが再現したこと。
  作品数・章数の増加だけでは引き金にしない。
- 意味的な整合性（設定矛盾・時系列破綻）の自動検査は、品質側の凍結が解けるまで追加しない。
  参照・hash・pinの構造的整合性（`doctor` の現行範囲）とは別物として扱う。

### X-01: skill registryは後置する

PR 1〜8と今後の実運用で必要になった共通形だけをregistryへ移す。
先に大きな抽象化を作らず、world/history/character/branch/adaptationなどのoptional workflowは、
実際の創作操作が必要になった時点で追加する。

## 10. 各段階で行う最小限の技術確認

品質評価ではなく、次の運用不変条件を確認する。

- JSON schemaとID参照が読める
- atomic write後にproject状態が壊れていない
- resumeで完了済みstageとresponseを重複処理しない
- 変更されたpromptを旧応答でごまかさない
- 旧版の本文・canonがcontinuationで変わらない
- 入れ子に循環がなく、子作品の版参照が有効である
- bundleのhashと復元結果が一致する
- ContextPacketに、指定外の時間軸・未来のcanonを含まない
- 同一の版と編纂profileから、同じ出力構造を得られる

これらは作品の文学的品質、文化的な真正性、面白さを評価するものではない。

## 11. 主なリスクと設計上の回避策

| リスク | 回避策 |
| --- | --- |
| 再開時にpromptが変わり、別応答を再利用する | revision hash・prompt全文・request keyで停止 |
| 中断時に同じ応答を再生成する | operator responsesと未完runのprefixを併用 |
| 親子・時代をまたいでcanonが混ざる | scope、overlay、local canon、明示的な正史昇格 |
| 子作品の改訂で親が勝手に変わる | 版付きlinkとstale通知 |
| 数千年分の資料でpromptが膨張する | ContextPacketによる選択と参照 |
| 異なる時間軸を偽の単一年表にする | 複数TimeFrame、近似・不明、変換不能の保持 |
| 文化を数千年不変の属性として扱う | 時代・地域ごとのCultureState |
| 初期実装が過度に抽象化される | 単一作品→深さ1→多段→世界modelの順を固定 |

## 12. 最初に着手する具体的なファイル単位

PR 1では、既存の実験runnerを変更せず、次の新規層を追加する。

```text
src/asc/project/
├── model.py       # WorkProject / WorkNode / WorkSpec / ArtifactRef
├── store.py       # JSONの読み書き、atomic update、lock
└── schema.py      # schema versionと入力検査
scripts/story_project.py
tests/test_project_store.py
```

PR 2で `runner.py` と既存pipelineへのadapterを追加し、PR 3で `resume.py`、
`story_project resume/pending`、stage別の再開testを追加した。PR 4で `continuation.py` /
`bundle.py`、project `continue` / `bundle export|verify|restore`、版履歴と追加章生成を追加した。
PR 5で `nested.py`、`WorkLink`、node別runner、`add-child` / `adopt-child` / `render` /
`compose`、pinned結合の回帰testを追加した。PR 6で多段ancestry・`run-tree`・再帰compose・
`context.py`と多段の回帰testを追加した。PR 7で `world.py` / `world_store.py`、
`story_project world add|status|bind|adopt-canon`、二時間軸・文化状態・canon stale/再採用・
bundle復元の回帰testを追加した。PR 8で `world_context.py` / `world_compile.py`、
`world add-profile|profiles|compile`、子作品別の選択・人物知識・未来canon除外・resume固定・
編纂決定性の回帰testを追加した。既存の `run_pipeline.py` / `run_experiment.py` / protocol-v1は、
新しい創作基盤の後方互換性を確認しながら残し、無理に統合しない。

**PR 1〜13は実装済み。次は複数作品・長期運用のdogfoodで必要性を測り、その結果から候補を選ぶ。X-01のskill registryは、実運用で必要になった共通形だけを後置実装する。**
