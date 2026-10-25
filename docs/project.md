# Creative project foundation

`story_project.py` は、固定されたprotocol-v1 taskとは別に、任意のpremiseを持つ
創作projectを永続化するための入口です。現在のschema versionは **1** です。

現在は、projectの **作成・単一/多段入れ子作品のS1生成・依存順実行・中断再開・
continuation・replay bundle・再帰編纂出力・operator pending確認・状態確認** ができます。
S1生成はplan → design → draftのvertical sliceで、S2/S3改稿や品質監査は通りません。
世界modelと時代・地域・文化を指定する完全なContextPacketは後のincrementです。
既存の `run_pipeline.py` と厳密replayの後方互換性は維持しています。

## 作成

```bash
python3 scripts/story_project.py init \
  --project-id prj-seaside \
  --title "潮の記録者" \
  --premise "港町で失われた潮位記録を追う。" \
  --chapters 3 \
  --target-chars 1600
```

`--project-id` を省略すると、題名とは独立したIDを発行します。長いpremiseは
`--premise` の代わりに `--premise-file path/to/premise.txt` から読めます。

機械可読な結果が必要な場合は、subcommandの後に `--json` を付けます。

```bash
python3 scripts/story_project.py init \
  --title "潮の記録者" --premise "港町で失われた潮位記録を追う。" --json
```

## 単一作品の生成

```bash
python3 scripts/story_project.py run prj-seaside \
  --provider scripted --script path/to/project-responses.json --json
```

`scripted` はofflineの配線確認用です。response keyは、projectのnode IDを使う
project固有key、または `plan`、`design:brief`、`draft:ch01` のような汎用purpose keyを
使えます。固定task `t01` 向けのfixtureを、そのまま別projectの生成記録として扱うことは
ありません。

外部providerを使う場合は、既存のJSON stdin/stdout契約を持つcommandを指定します。

```bash
python3 scripts/story_project.py run prj-seaside \
  --provider command --command "<provider command>" --model "<model label>"
```

Arena operatorもこのcommand経路を使えます。`chat_operator.py` が応答未作成でexit 3と
`NEED RESPONSE key=... file=...` を返した場合は、通常のprovider失敗ではなく
`waiting_response` として保存します。それ以外のprovider失敗や検証失敗は `failed` です。
`run` は新規生成を重ねる操作ではないため、`not_started` のrevisionにだけ実行できます。

一回のattemptでは、次の3つの独立したrunを作ります。

```text
<attempt-id>-plan
<attempt-id>-design
<attempt-id>-draft
```

- planはcanonを作り、要求章数と一致することを確認する。
- designはplan runのcanonを読み、8種類の設計書を作る。
- draftはplanのcanonとdesignの設計書を読み、章本文を作る。
- 各runのmanifestとは別に `project-input.json` へ、project・node・revision・attempt・
  WorkSpec hash・入力artifactを記録する。
- manifestの `protocol_version` は `asc-project-v1` で、凍結対照実験の
  `protocol-v1` とは区別する。

## 中断からの再開

未回答のrequestは、project・node・stage・response fileを含むpendingとして確認できます。

```bash
python3 scripts/story_project.py pending prj-seaside
python3 scripts/story_project.py pending prj-seaside --json
```

表示されたresponse fileへ、operator契約どおり `{"text": "..."}` を保存します。
requestの全文とprompt hashは、同じく表示されるrequest fileにも残っています。
応答を書いたら、最初と同じprovider commandで `resume` を実行します。

```bash
python3 scripts/story_project.py resume prj-seaside \
  --provider command --command "<provider command>" --model "<model label>"
```

offline fixtureでは `--provider scripted --script path/to/project-responses.json` を使えます。
`resume` はseed・temperatureを新たに指定せず、checkpointと未完runに記録された値を使います。
response fileがまだない場合は新しいrunを作らず、exit 3で待機状態を返します。

再開時の動作は次のとおりです。

- `done` のstageは、内容hashを検査したartifactからloadし、providerを呼ばない。
- 未完stageは新しいattempt/runを作り、checkpointの `resume_of` から旧runを辿れるようにする。
- 旧runの `responses.jsonl` を順序どおり照合し、記録済みresponseをそのまま返す。
  次の未記録requestから通常providerへ委譲するため、prefixを再生成・再消費しない。
- request key、prompt全文とhash、seed、temperature、記録がある場合はmax_tokens、
  project・node・revision・WorkSpecを照合する。不一致なら再開を拒否する。
- 再開runの `resume-audit.json` に、再利用数・委譲数・source hash・source不変性を記録する。
- 旧runのmanifest・project-input・responsesは書き換えない。

ledgerが `ok` になった直後、checkpointを `done` にする前にprocessが停止した場合も、
未完checkpointから記録済みresponseを再構成できます。一方、通常の検証失敗で `failed` に
なったstageは自動resumeしません。厳密replayは従来どおり完了run専用で、外部providerを
呼ばず全応答をoffline再生する別機能です。resumeの一致は、モデルの独立再現性や作品品質を
示すものではありません。

## 完成後のcontinuation

完成したrevisionにだけ、章を追加する新版を作れます。`--add-chapters` は追加数、
`--chapters` は新版の総章数です（どちらも省略すると1章追加）。

```bash
python3 scripts/story_project.py continue prj-seaside \
  --add-chapters 1 --provider command --command "<provider command>"
```

continuationはresumeとは別の操作です。旧revision・旧run・旧本文を書き換えず、
`parent_revision_id` と各stageの `parent_runs` を持つ新しいWorkNodeRevisionへcurrentを進めます。
新版のplan/designは新しいrunとして作り、draftは旧章をbyte-identicalに新runへ引き継ぎ、
追加章だけを生成します。plan promptには前版のcompact canonを渡し、旧本文全文は渡しません。
旧canonの既存entryや章の時系列・場所を変更する応答は拒否します。

continuationのrequest keyにはrevision IDが含まれるため、同じoperator directoryでも旧版の
responseを新版へ誤適用しません。既存のrevision IDを持たないrequest keyは従来どおりです。
新版が中断した場合は、通常の `resume` で同じ新版を再開できます。

```bash
python3 scripts/story_project.py resume prj-seaside \
  --provider command --command "<provider command>"
```

## 多段入れ子作品と依存順実行

任意のnodeの直下に、独立した子nodeを配置できます。rootの深さは0で、最大8段（rootを
含めて9 node）までです。親関係の後付け変更・循環・rootへ繋がらない親参照・深さ超過は
拒否します。各子は自分のrevision・canon・checkpoint・runを持ち、親の本文を暗黙に継承しません。
`--order`は同じ親の中で一意な正の整数です。

```bash
python3 scripts/story_project.py add-child prj-seaside \
  --node-id node-tide-side --title "潮の側話" \
  --premise "本編の港で起きた別の出来事。" --order 1 --json
python3 scripts/story_project.py add-child prj-seaside \
  --parent-node node-tide-side --node-id node-tide-grandchild \
  --title "灯台の記録" --premise "側話のさらに内側の出来事。" --json
python3 scripts/story_project.py run prj-seaside --node node-tide-side \
  --provider command --command "<provider command>"
```

`run`・`resume`・`continue`・`status`・`pending`は `--node` で任意の子・孫を選択します。
省略時はrootです。各nodeの`status`には直下の`children`と`links`が出て、さらに下位nodeの
状態を再帰的に確認できます。rootの`pending`には全 descendantの未回答がnode ID付きで集約されます。
単独runはPR 5どおり子を独立に開始できますが、親を先に完了させてから子・孫を進める場合は
`run-tree`を使います。

```bash
python3 scripts/story_project.py run-tree prj-seaside \
  --provider command --command "<provider command>" --json
```

`run-tree`はlink順を保ったparent-before-descendantのtopological orderで、未開始nodeだけを
実行し、完了nodeは再実行しません。未完・失敗・応答待ちのnodeを飛び越えず、 descendantを
生成せずに停止します。中断したnodeは個別に`resume`してから再度`run-tree`を実行します。
`--node`を指定すると、そのsubtreeだけを対象にできます（上位の依存は完了している必要があります）。

各linkは子の`child_revision_id`・`order`・draft `ArtifactRef`・`content_version`を保持し、
子本文そのものは保存しません。子・孫をcontinuationするとcurrent revisionだけが進み、対応する
linkは`stale: true`になります。旧いpinned出力を自動で書き換えず、完了した新版をlink IDで明示的に
採用します。nested linkも同じcontractで、親のpinned参照を勝手に更新しません。

```bash
python3 scripts/story_project.py continue prj-seaside --node node-tide-grandchild \
  --add-chapters 1 --provider command --command "<provider command>"
python3 scripts/story_project.py status prj-seaside --node node-tide-side --json
python3 scripts/story_project.py adopt-child prj-seaside LINK_ID --json
```

単一nodeの出力と再帰結合出力は別の操作です。`render`は選択nodeの現在の完了draftだけを出し、
`compose`は選択nodeの完了draftと全 descendantのpinned draftを順序どおりに編纂します。
選択nodeを`#`、子を`##`、孫を`###`のように、深さから決定的に見出しを付けます。

```bash
python3 scripts/story_project.py render prj-seaside --node node-tide-side --out /external/child.md
python3 scripts/story_project.py compose prj-seaside --out /external/combined.md
python3 scripts/story_project.py compose prj-seaside --node node-tide-side --out /external/subtree.md
```

結合結果は`artifacts/<selected-node>/combined-<version>.md`と同名のJSON manifestにも保存します。
versionは選択nodeのrevisionと全階層のpinned link/artifactから決まり、時刻や子のcurrent revisionでは
変わりません。したがって、descendantがstaleになった後もadopt前の`compose`は同じbytesを再現します。
adopt後の`compose`だけが新しいversionを追加し、旧い結合artifactも残ります。

### 祖先文脈の選択（ContextPacket前身）

多段nodeの生成では、祖先の全本文をpromptへ投入しません。`context.py`がrootから直近の親までを
対象に、compactなcanon（人物・事実・場所・章構造など）と、章ID・文字数・時日・場所などの
構造要約だけを`asc-context-packet-pre1`として組み立てます。章本文とdraftのtext fieldは除外します。
packetは各stageの`project-input.json`に記録され、plan/design/draftのpromptにも同じ内容が付与されます。
祖先が未完の単独runでは、その祖先の構造と状態だけを記録し、完了したcanonがないことを隠しません。
これは世界modelの時代・地域・文化選択を行う完全なContextPacketではなく、後のincrementへ渡す
小さな前身です。resumeは旧runに記録されたpacketを明示的に再利用するため、待機中に祖先が完了しても
子のpromptを変えません。記録packet・prompt・requestの照合に失敗した場合は再開を拒否します。

## replay bundleの外部保存

project metadata、全node/revision/link、checkpoint、全runのmanifest・prompt/response・
生成artifact・結合artifactを一つの外部directoryへexportできます。lockと一時fileだけを除外し、
創作資料はGitへ入れません。

```bash
python3 scripts/story_project.py bundle export prj-seaside \
  --out /external/replay/prj-seaside.bundle --json
python3 scripts/story_project.py bundle verify \
  /external/replay/prj-seaside.bundle --json
python3 scripts/story_project.py --root /external/restored-projects \
  bundle restore /external/replay/prj-seaside.bundle --json
```

`bundle.json` は全payload fileのrelative path・size・SHA-256を保持します。verifyはhashと
file一覧を再計算し、さらに復元先と同じ `ProjectStore` の参照・artifact検査を行います。
restoreは既存projectを上書きせず、一時directoryで検査してから最終pathへ配置します。
bundle自体を変更した場合はverify/restoreを拒否します。

## 状態確認

```bash
python3 scripts/story_project.py status prj-seaside --json
```

別processで読み直しても、同じproject ID、root node ID、current revision ID、
WorkSpec、設定SHA-256を返します。初期状態は `not_started` で、
`plan`・`design`・`draft` はいずれも `pending` です。生成後は `checkpoints` に
各stageのrun ID・状態・seed・temperature・artifact参照が入り、3 stageが完了すると
`complete` になります。`attempt_id` は最新のcheckpointが属するattempt、
`attempt_ids` は同一revisionに関わった全attemptです。`revision_ids` / `revisions` には
旧版を含む版履歴、currentの `parent_revision_id` / `parent_runs` にはcontinuationの参照が入ります。
`artifact_refs` から、現在の章本文と設計資料を内容hash付きで辿れます。`--node`を指定すると
その子の`revision_ids`・`runs`・`checkpoints`だけを返します。rootの`links`には
`pending/ready/stale`の状態とcurrent child revisionが入ります。`pending` には、待機中のrequest key、
project/node/stage、request/response path、response fileの有無が集約されます。

既定の保存先は `runs/projects/` です。testや外部保存では、**subcommandの前**に
`--root` を指定できます。

```bash
python3 scripts/story_project.py --root /path/to/projects status prj-seaside
```

## 保存形式

```text
runs/projects/<project_id>/
├── project.json
├── nodes/<node_id>/
│   ├── current.json
│   ├── revisions/<revision_id>.json
│   ├── checkpoints/<stage>.json
│   └── links/<link_id>.json        # 任意の親から子へのpinned参照
├── artifacts/<node_id>/combined-<version>.md
└── runs/<attempt-id>-<stage>/
```

- `project.json`: project ID、root node、作成・更新時刻。
- `current.json`: nodeの現在のrevisionへの小さな参照。
- `<revision_id>.json`: 完全なWorkSpec、そのSHA-256、版付きartifact参照。continuation版は
  `parent_revision_id` と親stageの `parent_runs` も持ち、旧recordは追記・上書きしない。
- `checkpoints/<stage>.json`: current revisionのstage状態、attempt、run、版付きartifact参照。
- `links/<link_id>.json`: 任意の親から子への順序・pinned revision・content version・draft artifact参照。
  子の本文は含めず、新版の採用は`adopt-child`だけが変更する。linkは全階層で探索できる。
- `runs/`: 各stageのmanifest、prompt/response、project-input、生成物。再開runには
  `resume-audit.json` もあり、旧runは別directoryに残る。
- `artifacts/`: node別の結合markdownとmanifest。S1の個別生成物は各runから直接参照します。

project・node・revisionには、それぞれ `record_type` と `schema_version` があります。
WorkSpecの一部だけを変更して古いhashを残したrecordは読み込み時に拒否します。

## 更新上の不変条件

- project・node・revisionのIDは、題名やpremiseから導出せず永続化する。
- 初期化は一時directoryで完結させてから最終pathへ配置し、既存projectを上書きしない。
- 現在状態のJSONは、同じdirectory内の一時fileへ完全に書いた後にatomic replaceする。
- writerは非blocking lockを使い、同時writerを待たずに拒否する。readerはlockを取らない。
- generation attempt全体にも別のexecution lockを掛け、同じprojectの並行runを拒否する。
- nodeのcurrent pointerは、同じproject・nodeに属する既存revisionだけを指せる。
- artifact pathはrelative POSIX pathに限定し、内容のSHA-256を保持する。
- checkpointを `done` として読むには、同じnodeの成功manifest、一致するproject-input、
  参照artifactの存在と内容hashが必要である。
- runは不変記録、checkpointは現在状態への参照である。resumeは旧runを書き換えず、
  検証済みprefixを持つ新規runとして記録する。
- `waiting_response` と `failed` を区別し、response未作成のまま新規attemptを重ねない。
- continuationは完了版から新版を追加し、旧revision・旧run・旧章の内容を変更しない。
  新版のdraftでは旧章をコピーし、追加章だけをproviderへ要求する。
- replay bundleは全payloadをhashで検査し、restore時の上書きを拒否する。
- 子nodeは独立したrevision/checkpoint/runを持ち、親linkはpinned artifactだけを保持する。
  子のcurrent revisionとlinkが違う場合はstaleとして表示し、自動採用しない。
- 結合versionには時刻を含めず、同じ親revisionと全階層のpinned内容から同じ結合bytesを再現する。
- 親子関係はroot=0・最大深さ8の木に限定し、循環・orphan・深さ超過と親関係の変更を拒否する。
- `run-tree`はparent-before-descendantの順序を守り、未完・失敗・待機中の依存を飛び越えない。
- 祖先の章本文を子の文脈へコピーせず、選択したcanon・構造要約・参照IDだけを記録する。
- 創作データはGitへ入れない。`runs/` は従来どおりGit管理外である。

これは破損や意図しない不整合を検出する仕組みであり、悪意ある改ざんに対する
署名付きstorageではありません。

## 次のincrement

PR 6では、孫作品・循環検出・深さ制限・依存順実行・再帰compose・祖先文脈packetを追加しました。
PR 5のpinned link、個別run/resume/continuation、bundle互換を保ち、世界model（PR 7）と
時代・地域・文化を指定する完全なContextPacket（PR 8）は後のincrementです。
