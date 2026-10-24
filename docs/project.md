# Creative project foundation

`story_project.py` は、固定されたprotocol-v1 taskとは別に、任意のpremiseを持つ
創作projectを永続化するための入口です。現在のschema versionは **1** です。

この最初のincrementが提供するのは **projectの作成と状態確認だけ** です。
まだ文章生成、中断再開、続編、入れ子作品は実行しません。既存の
`run_pipeline.py` と厳密replayの動作も変更しません。

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

## 状態確認

```bash
python3 scripts/story_project.py status prj-seaside --json
```

別processで読み直しても、同じproject ID、root node ID、current revision ID、
WorkSpec、設定SHA-256を返します。初期状態は `not_started` で、
`plan`・`design`・`draft` はいずれも `pending` です。

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
│   └── checkpoints/
├── artifacts/
└── runs/
```

- `project.json`: project ID、root node、作成・更新時刻。
- `current.json`: nodeの現在のrevisionへの小さな参照。
- `<revision_id>.json`: 完全なWorkSpec、そのSHA-256、版付きartifact参照。
- `checkpoints/`: 後のpipeline incrementがstage状態を保存する場所。
- `artifacts/`・`runs/`: 生成物と実行記録の保存場所。初期化時は空です。

project・node・revisionには、それぞれ `record_type` と `schema_version` があります。
WorkSpecの一部だけを変更して古いhashを残したrecordは読み込み時に拒否します。

## 更新上の不変条件

- project・node・revisionのIDは、題名やpremiseから導出せず永続化する。
- 初期化は一時directoryで完結させてから最終pathへ配置し、既存projectを上書きしない。
- 現在状態のJSONは、同じdirectory内の一時fileへ完全に書いた後にatomic replaceする。
- writerは非blocking lockを使い、同時writerを待たずに拒否する。readerはlockを取らない。
- nodeのcurrent pointerは、同じproject・nodeに属する既存revisionだけを指せる。
- artifact pathはrelative POSIX pathに限定し、内容のSHA-256を保持する。
- 創作データはGitへ入れない。`runs/` は従来どおりGit管理外である。

これは破損や意図しない不整合を検出する仕組みであり、悪意ある改ざんに対する
署名付きstorageではありません。

## 次のincrement

PR 2で、既存のplan/design/draftをadapter経由で呼び、runとstage checkpointを
このprojectへ接続します。現時点の `pending` は生成失敗ではなく、まだ生成を
開始していないことを示します。
