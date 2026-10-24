# Creative project foundation

`story_project.py` は、固定されたprotocol-v1 taskとは別に、任意のpremiseを持つ
創作projectを永続化するための入口です。現在のschema versionは **1** です。

現在は、projectの **作成・単一作品のS1生成・中断再開・operator pending確認・状態確認**
ができます。S1生成はplan → design → draftのvertical sliceで、S2/S3改稿や品質監査は
通りません。続編、入れ子作品は後のincrementです。既存の `run_pipeline.py` と
厳密replayの動作は変更していません。

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

## 状態確認

```bash
python3 scripts/story_project.py status prj-seaside --json
```

別processで読み直しても、同じproject ID、root node ID、current revision ID、
WorkSpec、設定SHA-256を返します。初期状態は `not_started` で、
`plan`・`design`・`draft` はいずれも `pending` です。生成後は `checkpoints` に
各stageのrun ID・状態・seed・temperature・artifact参照が入り、3 stageが完了すると
`complete` になります。`attempt_id` は最新のcheckpointが属するattempt、
`attempt_ids` は同一revisionに関わった全attemptです。`artifact_refs` から、現在の章本文と
設計資料を内容hash付きで辿れます。`pending` には、待機中のrequest key、project/node/stage、
request/response path、response fileの有無が集約されます。

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
│   └── checkpoints/<stage>.json
├── artifacts/
└── runs/<attempt-id>-<stage>/
```

- `project.json`: project ID、root node、作成・更新時刻。
- `current.json`: nodeの現在のrevisionへの小さな参照。
- `<revision_id>.json`: 完全なWorkSpec、そのSHA-256、版付きartifact参照。
- `checkpoints/<stage>.json`: stage状態、attempt、run、版付きartifact参照。
- `runs/`: 各stageのmanifest、prompt/response、project-input、生成物。再開runには
  `resume-audit.json` もあり、旧runは別directoryに残る。
- `artifacts/`: 後の編纂出力などのための領域。S1の生成物は各runから直接参照します。

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
- 創作データはGitへ入れない。`runs/` は従来どおりGit管理外である。

これは破損や意図しない不整合を検出する仕組みであり、悪意ある改ざんに対する
署名付きstorageではありません。

## 次のincrement

PR 4で、完成作品の旧版を保ったまま章や続編を追加するcontinuationと、replayに必要な原本を
外部pathへexport / verify / restoreするbundleを実装します。厳密replayとresumeは別機能の
まま維持します。
