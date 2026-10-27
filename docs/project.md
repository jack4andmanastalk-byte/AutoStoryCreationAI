# Creative project foundation

`story_project.py` は、固定されたprotocol-v1 taskとは別に、任意のpremiseを持つ
創作projectを永続化するための入口です。現在のschema versionは **1** です。

現在は、projectの **作成・単一/多段入れ子作品のS1生成・依存順実行・中断再開・
continuation・replay bundle・再帰編纂出力・世界model・operator pending確認・状態確認** ができます。
S1生成はplan → design → draftのvertical sliceで、S2/S3改稿や品質監査は通りません。
世界modelは複数時間軸・地域・文化状態・版付きbinding・明示的canon採用を保存します。
bindingで選んだ世界資料を生成ContextPacketへ記録し、年代記・地誌・文化圏・作品集の
決定的な編纂viewも作れます。既存の `run_pipeline.py` と厳密replayの後方互換性は維持しています。

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

### 失敗したstageの再試行

`failed` は「providerや生成textが原因で、記録済みresponseを再生しても同じ結果になる」状態です。
そのため `resume` は既定で拒否し、exit 2で `--retry-failed` を案内します。

```bash
python3 scripts/story_project.py status prj-seaside        # Failed stages: ... と案内が出る
python3 scripts/story_project.py resume prj-seaside \
  --provider command --command "<provider command>" --model "<model label>" \
  --retry-failed
```

再試行の意味は「新規attemptとして同じstageをやり直す」ことであり、再開ではありません。

- 失敗したrunのmanifest・project-input・responses・artifactはそのまま残し、書き換えない。
- 新しいrunはseed・temperatureをcheckpointから引き継ぎ、失敗runのresponseは再利用しない
  （`resume-audit.json` は作られない）。
- 新checkpointの `retry_of` に失敗runのIDを記録する。`status` は
  `Retried stages: plan<-att-...` と表示し、`--json` では `checkpoints.<stage>.retry_of` に出る。
- `done` のstageは再生成せず、artifact hashを検査してloadする。chapter改訂の再試行でも、
  引き継いだ章のbytesは同一のまま `revise.json` の `copied` に残る。
- 対象stageが `failed` でない場合（未開始・完了・`waiting_response` など）は拒否する。
  未回答requestが残っているstageは従来どおり `pending` を埋めて `resume` する。
- 再試行後のrunは通常のrunと同じ検査対象で、`doctor` は再試行後もfindingを出さない。

## 完成後のcontinuation

完成したrevisionにだけ、章を追加する新版を作れます。`--add-chapters` は追加数、
`--chapters` は新版の総章数です（どちらも省略すると1章追加）。

```bash
python3 scripts/story_project.py continue prj-seaside \
  --add-chapters 1 --provider command --command "<provider command>"
```

世界bindingを新版の生成文脈にも使う場合は、旧revisionのbinding IDを明示します。

```bash
python3 scripts/story_project.py continue prj-seaside --node node-tide-side \
  --add-chapters 1 --world-binding binding-tide-early \
  --provider command --command "<provider command>"
```

指定したbindingが選択nodeの現在の親revisionに属することを確認し、同じ時間・地域・文化状態を
新しいbinding IDで新版へ複製します。この指定がなければbindingを暗黙に引き継ぎません。

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

### 未完成の子を含む部分編纂（`--partial`）

既定の`compose`は、全linkがpinnedであることを要求します。作業中の子が1つあるだけで
作品集全体が出せないため、`--partial`を付けると**その子だけを明示的に未収録として残し**、
残りを編纂します。

```bash
# 1作品が未完成のまま、完成済みの作品集を読む
python3 scripts/story_project.py compose prj-seaside --partial --out /external/partial.md
```

- 未収録のlinkは元の順序位置に残り、見出し（子の現在のtitle）と
  `<!-- asc-omitted: link=… node=… order=… reason=no-pinned-draft -->`、可視の1行
  「この作品は未収録（未完成）。」に置き換わります。**黙って飛ばしません**。
- `--json`の`omitted`に`link_id` / `node_id` / `order` / `title` / `reason`が入り、
  manifest JSONにも同じ`omitted`が入ります（`--partial`無しの出力は`omitted`キー自体を持たず、
  従来と同じ形）。
- `content_version`は`omitted`を含めて決まるため、部分編纂と完成後の完全編纂は別のartifactに
  なります。部分編纂のartifactを後から上書きしません（write-once）。
- 未収録のtitleはlinkがpinしていない現在のrevisionから読む参考情報です。本文・canon・
  pinned本文の同一性には関与しません。pinned側の本文は1 byteも変わりません。
- `world compile`の`collection` profileは従来どおり全link pinnedを要求します（部分編纂は
  `compose --partial`のみ）。

### 祖先と世界の選択文脈（ContextPacket）

多段nodeの生成では、祖先の全本文をpromptへ投入しません。`context.py`がrootから直近の親までを
対象に、compactなcanon（人物・事実・場所・章構造など）と、章ID・文字数・時日・場所などの
構造要約だけを選択します。章本文とdraftのtext fieldは除外します。bindingのないnodeは従来どおり
`asc-context-packet-pre1`で、rootに祖先もbindingもない場合はpacket自体を作りません。

現在のwork revisionにbindingがあるnodeでは、`asc-context-packet-world1`の`world`を追加します。
選択規則は次のとおりです。

- TimeSpan・Region・CultureStateは、bindingが列挙したIDだけを展開します。地域の親・未来のstate・
  関係先だけを理由に、指定外recordを自動追加しません。両端が選ばれたSpatialRelation / state関係と、
  選択した二つの時間軸を結ぶTimeConversionだけを含めます。
- 世界canonはsupersedeされていないcurrent entryのうち、global / timeframe / region / culture / work /
  nodeのscopeが選択へ適用され、かつ`valid_span_id`が未指定またはbindingのTimeSpanにあるものを選びます。
  `selection.overlay_order`のglobal → timeframe → region → culture → work → nodeの順で記録し、
  後のscopeを上位overlayとします。最大64件を超える場合はlocalで具体的なentryを優先し、
  `omitted_canon_count`に省略数を残します。
- `references`に、実際に含めた世界recordとbindingのID・`content_version`を記録します。
  source revisionのstale表示のために採用contentを書き換えることはありません。

人物の知識で祖先factsを絞る場合は、作品作成時に`--knowledge-character CHARACTER_ID`を指定します。

```bash
python3 scripts/story_project.py add-child prj-seaside \
  --node-id node-aria-view --title "アリアの側話" --premise "アリアの知る出来事。" \
  --knowledge-character aria
```

これはWorkSpecの`options.context_knowledge.character_id`として版に保存され、各祖先canonの
`Character.knows`を使ってfactsを選択します。その人物が存在しない祖先のfactsは空になり、
間接的な伏線の開示を避けるためforeshadowingも除外します。世界canonのscope・時代選択とは別の
フィルタです。指定しない既存作品は、従来のcompact factsをそのまま使います。

packetは各stageの`project-input.json`に記録され、plan/design/draftのpromptにも同じ内容が付与されます。
したがって、二つの子作品が同じ世界台帳を使っても、bindingが違えば別々の文脈を受け取り、指定外の
時間軸・未来のCultureState / canonを受け取りません。祖先が未完の単独runでは、その祖先の構造と状態だけを
記録し、完了したcanonがないことを隠しません。resumeは旧runに記録されたpacketを明示的に再利用するため、
待機中に祖先や世界台帳が変わっても子のpromptを変えません。記録packet・prompt・requestの照合に失敗した
場合は再開を拒否します。

## 世界model：時間・空間・文化・世界canon

世界資料は作品の親子木とは別の参照graphとして、同じproject内の `world/` に保存します。
地域を作品や文化の唯一の親にはせず、子作品は必要な時間・地域・文化状態のIDを明示的に選びます。
この層は資料の参照と版を管理するもので、文化的描写や歴史的記述の品質を保証するものではありません。

### 世界recordの追加

`world add` は1 JSON fileから1件の不変recordを追加します。kindは `timeframe`、`time-span`、
`time-conversion`、`region`、`spatial-relation`、`culture`、`culture-state`、`culture-relation`、
`canon`、`binding` です。`record_type`、`schema_version`、`project_id`、`created_at` と、
版付きrecordの `content_version` はCLIが補います。長期間参照するIDはfile内で明示する運用を推奨します。

```json
{
  "id": "tf-empire",
  "name": "帝国暦",
  "calendar": "solar",
  "epoch": "建国"
}
```

```bash
python3 scripts/story_project.py world add prj-seaside timeframe \
  --file /external/world/timeframe.json --json
python3 scripts/story_project.py world add prj-seaside time-span \
  --file /external/world/span.json --json
python3 scripts/story_project.py world status prj-seaside --json
```

主なrecordと制約は次のとおりです。

- `TimeFrame` は暦・epochを持つ永続時間軸です。複数の時間軸を一つの日付系へ統合しません。
- `TimeSpan` は `exact` / `approximate` / `range` / `unknown` を持ちます。`unknown` は
  絶対座標なしで保存でき、`before_span_ids` による前後関係は絶対時刻とは別に記録します。
  既知の前後関係もcycleなく保存します。
- `TimeConversion` は二つの時間軸間の明示的な `scale` / `offset` による順序保存変換です。
  変換が登録されていない時間軸同士を自動換算せず、relative orderから絶対時刻を推定しません。
- `Region` は `parent_region_id` による入れ子と任意の `valid_span_id` を持てます。
  `SpatialRelation` は接続種別・任意の有効期間・既知の場合だけ `travel_days` を持ちます。
  未指定の移動日数を、既存planの同名地域や他の関係から推定して埋めることはありません。
- `Culture` は文化の永続ID、`CultureState` は時代・複数地域・属性を持つ版です。
  `previous_state_id` と `culture-relation` の `inheritance` / `split` / `contact` で、
  継承・分裂・接触をstate間の関係として保存します。新しいstateを追加しても旧stateは書き変わりません。

### 子作品revisionへのbinding

`world bind` は、選択nodeの**現在のwork revision**に世界参照を固定します。時間軸が異なる
TimeSpanや、異なる時代・文化のCultureStateを同じproject内に保持できます。

```bash
python3 scripts/story_project.py world bind prj-seaside --node node-tide-side \
  --time-span span-empire-early --time-span span-tide-12 \
  --region region-harbor --culture-state state-tide-early \
  --binding-id binding-tide-early --json
python3 scripts/story_project.py world status prj-seaside --node node-tide-side --json
```

binding自体にもIDと `content_version` があり、同じnode revisionへの重複bindingは拒否します。
子作品をcontinuationしてcurrent revisionが進んでも、旧bindingを新版へ暗黙に引き継ぎません。
新版の生成時に同じ選択を使う場合だけ、`continue --world-binding`で旧bindingを明示的に指定します。
`world status` の `selected_binding` は、選択nodeのcurrent revisionに対するbindingだけです。
未来のCultureStateを新規追加した場合も、旧bindingの `culture_state_ids` は変わりません。

### 世界canonへの明示的採用とscope overlay

plan/draftを生成しただけでは、root・子作品のlocal canonは世界正史へ登録されません。
世界canonへの採用は、完了nodeのpinned plan JSONから値を選ぶ別操作です。採用元のpathは
`status --node ... --json` のplan checkpointで確認できます。

```bash
python3 scripts/story_project.py world adopt-canon prj-seaside \
  --node node-tide-side \
  --artifact "runs/<plan-run-id>-plan/canon/facts.json" \
  --pointer "/facts/0" --scope global --subject "F-01" \
  --valid-span span-empire-early --entry-id canon-world-f01 --json
```

`--pointer` はRFC 6901 JSON pointerで、省略するとdocument全体を採用します。採用recordには
選択したcontentだけでなく、source node・source work revision・ArtifactRef（path/SHA-256/run）・
JSON pointer・採用contentの `content_version` を保存します。scopeは `global`、`timeframe`、
`region`、`culture`、`work`、`node` で、global以外は `--scope-id` が必要です。異なるscopeの
entryをoverlayとして併存でき、任意の `valid_span_id` も保持します。人手で確定した正史は
`source: null` のcanon JSONを `world add canon` で追加できます。

source nodeをcontinuationしても、採用済みcontentとsource revisionは自動更新しません。
`world status` は各採用entryの `current` / `stale` と現在のsource revisionを表示するだけです。
新版を採用する場合は、もう一度 `adopt-canon` を実行し、必要なら `--supersedes` に
旧entry IDを指定します。supersedeしても旧entryは残り、同じentryから複数の後継を分岐させることは
拒否します。採用操作自体は生成promptを変更せず、run時のContextPacketがbinding・scope・有効期間に
従って採用済みentryを選択します。

## 世界の編纂view

同じ世界recordから、複数の決定的なMarkdown viewを生成できます。profileはselectorと表示名を持つ
不変JSONで、`compilations/profiles/<profile-id>.json`に保存します。

| kind | 必須selector | 選択する資料 |
| --- | --- | --- |
| `chronicle` | `timeframe_id` | 一つの時間軸のTimeSpan、relative order、適用されるglobal/timeframe canon |
| `gazetteer` | `region_id` | 地域subtree、接続、該当地域のCultureState、global/region canon |
| `culture` | `culture_id` | 一つのCultureの全state、state間関係、参照時期、global/culture canon |
| `collection` | `node_id`（省略時root） | 既存の再帰composeによる現在nodeとpinned descendantの作品集 |

```json
{
  "id": "profile-empire-chronicle",
  "kind": "chronicle",
  "title": "帝国年代記",
  "timeframe_id": "tf-empire"
}
```

```bash
python3 scripts/story_project.py world add-profile prj-seaside \
  --file /external/world/chronicle-profile.json --json
python3 scripts/story_project.py world profiles prj-seaside --json
python3 scripts/story_project.py world compile prj-seaside profile-empire-chronicle \
  --out /external/views/empire-chronicle.md --json
```

年代記は常に一つのTimeFrameで編纂し、他の時間軸を自動換算して単一年表へ混ぜません。座標を持つ
TimeSpanと年代不明のTimeSpanを分け、前後関係は別sectionに保持します。地誌・文化圏viewは全時代の
資料を対象にできますが、profileのselector外の地域・文化の属性を展開しません。

編纂結果は`artifacts/world/<kind>-<profile-id>-<version>.md`と同名のJSON manifestに保存します。
versionはprofileの`content_version`と、実際に使用したsource recordのID・content version（作品集では
pinned composition version）から決まります。同じ入力では同じpath・bytesを返し、関連recordを追加すると
新しいversionを残して旧viewを上書きしません。年代記では無関係な時間軸への追加、作品集では親が
pinしていない子の新版だけでは旧viewを変更しません。manifestの`source_references`から各viewの
入力版を辿れます。

## replay bundleの外部保存

project metadata、全node/revision/link、世界record、compilation profile、checkpoint、全runの
manifest・prompt/response・生成artifact・結合/世界編纂artifactを一つの外部directoryへexportできます。
lockと一時fileだけを除外し、創作資料はGitへ入れません。

```bash
python3 scripts/story_project.py bundle export prj-seaside \
  --out /external/replay/prj-seaside.bundle --json
python3 scripts/story_project.py bundle verify \
  /external/replay/prj-seaside.bundle --json
python3 scripts/story_project.py --root /external/restored-projects \
  bundle restore /external/replay/prj-seaside.bundle --json
```

`bundle.json` は全payload fileのrelative path・size・SHA-256を保持します。verifyはhashと
file一覧を再計算し、さらに復元先と同じ `ProjectStore` / `WorldStore` の参照・artifact検査を
行います。世界record間のID、work revision binding、canonのpinned source contentも対象です。
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

`work` は `doctor` と共通の作業要約です（schema `asc-project-work-summary-v1`）。

- `state`、`stages`、`completed_stages` / `failed_stages` / `waiting_stages`、`next_stage`。
- `pending`（`count` / `ready` / `waiting_for_reply`）、`stale`（`links` / `canon` / `bindings`）、
  `runs`（`count` / `interrupted`）。
- `inspected` は**そのコマンドが実際に調べた範囲**です。`status` は checkpoints・links・pending
  だけを読み、世界record・binding・run manifestは調べません。そのため未検査の件数は `0` ではなく
  `null`（人間向け表示は `not inspected`）になります。「無い」と「見ていない」を混同しません。
- `next_actions` は状態から決まる次の操作で、既存CLIのcommand文字列と理由を持ちます
  （例: `failed` → `resume --retry-failed`、待機中 → `pending`、stale link → `adopt-child`、
  編纂や採用の版ずれ → `world bind` / `world adopt-canon`、記録との差 → `diff`）。
  commandは表示専用で、自動実行はしません。

既定の保存先は `runs/projects/` です。`runs/` は git 管理外なので、セッションを
越えて残す作品は `--root works`（リポジトリ内・版管理）に置きます。testや外部保存では、
**subcommandの前**に `--root` を指定できます。

```bash
python3 scripts/story_project.py --root /path/to/projects status prj-seaside
```

## 運用モード：人間が開始する

この基盤は、**モデルをArena.aiのチャットに置き、生成の開始だけ人間が行う**運用を前提にします。
APIキーはrepositoryに置かず、`scripts/chat_operator.py` が「モデル＝人間（またはチャット）」の
providerになります。これが**標準フロー**で、providerを省略すると
`<project>/relay` を使う `arena` が既定になります
（決定と手順は [`standard_flow.md`](standard_flow.md) / [`quickstart.md`](quickstart.md)）。

```bash
# 1回の生成を人間が開始する（応答が無ければexit 3でその場に止まる）
python3 scripts/story_project.py --root works run prj-seaside

# 何が待っているか（生成しない。1巡の報告と終了コード 0/3/2）
python3 scripts/story_project.py --root works relay status prj-seaside

# 応答を1件書いたら、取り込みと再開をまとめて行う
python3 scripts/story_project.py --root works relay submit prj-seaside --file answers.txt

# 書き出しだけ・取り込みだけを行いたい場合
python3 scripts/story_project.py --root works relay export prj-seaside
python3 scripts/story_project.py --root works relay ingest prj-seaside --file answers.txt

# 何が足りないか / 次に何をするか / 原稿の場所
python3 scripts/story_project.py --root works status prj-seaside   # Next: と Manuscript:
```

- `--provider command --command "python3 scripts/chat_operator.py --dir <任意のdir>"` は
  従来どおり使えます。relay の置き場所を project の外にしたい場合や、
  `run_pipeline.py` と共有したい場合の経路です。
- `--provider arena` の run manifest には `provider: arena-relay` が記録されます。
  台本（`scripted`）や外部コマンド（`command`）と後から区別するためです。

- **常駐ワーカー・スケジューラ・依存queueの自動消化・失敗時の自動リトライは持ちません。**
  これらは非目標です。`run-tree` も人間が起動し、未完のnodeがあれば飛ばさずに停止します。
  失敗したstageは `resume --retry-failed` で明示的に再試行します。
- 停止点は必ずファイルに残ります（run manifest、未完runの応答prefix、`pending`）。
  processをまたいでも、日をまたいでも状態は同じです。
- 中断中にpromptが変わった場合（revisionや文脈の変更）は、`chat_operator.py` がexit 4で
  古い応答の再利用を拒否します。別の応答で穴埋めはしません。
- Arena.aiはunversionedなので、同じseed・同じ出力（G5）は満たせません。記録した数値は
  再現可能な性能値ではなく参照値として扱います。

## 運用の可観測性（doctor / context show）

`doctor` と `context show` は、dogfoodで実際に詰まった点（待機responseの解消先、staleの対象、
ContextPacketの大きさと参照資料）を、生成せずに確認するための読み取り専用コマンドです。
どちらもproviderを呼ばず、resume・continuation・adopt・compose・compile・replayを実行せず、
project配下のfileを一つも書き換えません。現在のrecordと、runに記録済みの版だけを読みます。

### 全体の整合性: `doctor`

```bash
python3 scripts/story_project.py doctor prj-seaside
python3 scripts/story_project.py doctor prj-seaside --json
```

project record、node木、revision、checkpoint、link、世界record、run manifestの順に検査し、
`project`・`node_tree`・`revisions`・`checkpoints`・`links`・`world`・`runs` の7 checkごとに
`pass` / `warn` / `failed` / `skipped` を返します。checkの状態はfindingの深刻度から決まり、
`error` が1件でもあれば `failed`、`warning` だけなら `warn` です。

- `error`: 読み込み・参照・hash検証が破綻している（project unreadable、orphan node、
  artifact missing / hash_differs、run missing、`world.invalid` など）。
- `warning`: 運用上の判断待ち。`checkpoint.failed` / `checkpoint.running` / `link.stale` /
  `world.canon_stale` / `world.record_changed` / `design.unresolved` /
  `run.running`（終了記録のない中断process）/ `run.status_unknown`。
- 同じ`artifact`でも、revision・checkpoint・link・runのどこから参照されているかで
  複数checkに現れます。1つのfile欠落が `revisions` と `links` の両方に出るのは正常です。

`pending` には待機中のstage、response key、request/response path、response fileの有無
（`response_ready`）が入ります。`stale` には pinned link とchildのcurrent revisionの差、
source改訂で古くなった世界canon、現在revision以外を指すworld bindingが入り、
それぞれ「どのlink・binding・entryを、どの`adopt-child` / `world adopt-canon` / 再bindingで
解消するか」までを対象IDとして示します。解消操作自体は行いません。

`world.record_changed` は、`region` や `time_frame` のように `content_version` を保存しない
世界recordが、**記録済みpacketのhashと一致しない**場合に出ます。これらのrecordは追記専用の
CLIしかないため、差がある場合は保存JSONがrun後に直接編集されたことを意味します
（`content_version` を持つ `culture_state`・`world_canon_entry`・`work_world_binding` は
読み込み時にhash検証され、不一致は `world.invalid` のerrorになります）。findingの`details`に
`record_type` / `record_id` / `recorded_content_version` / `current_content_version` を出し、
解消手順として `diff --left run:<run_id> --right current` を案内します。判定はread-onlyで、
recordもhashも書き換えません。

findingは**record単位**です。1つのrecordを書き換えた事実は1つなので、そのrecordを記録した
nodeがいくつあっても警告は1件で、影響したnodeは`details.node_ids`と`details.nodes`
（`node_id` / `run_id` / `recorded_content_version`）に並べます。

- `details.node_id` は影響nodeが1つだけのときだけ入り、複数nodeに及ぶ場合は`null`になります
  （特定の1 nodeの問題ではないため）。
- 後方互換のため`details.run_id` / `details.recorded_content_version`は
  **先頭の影響node**（`node_ids`の辞書順先頭）の値を返します。
- `next_actions`の`diff`もrecord単位で1件です。commandは先頭の影響nodeを使い、
  `node_ids`に全nodeを持つので、他のnodeを見たいときは`--node`を差し替えて実行します。
- 2つのrecordを書き換えた場合は2件（recordごと）になります。

同じrecordを7 nodeが記録している状態で1件を改称した実測では、7 warnings + 7 `diff` commands
（doctor JSON 9,843 bytes、text 30行）が、1 warning + 1 `diff` command（4,956 bytes、12行）に
なりました（PR 17のdogfood）。

`design.unresolved` は、`design` stage が**checkerを通らないまま記録した設計文書**がある場合に出ます。
design stageはfail-openで、修復しても通らない文書を `unresolved`（parse不能なら `missing`）として
`design.json` に残し、runは続行します。そのため生成が完了していても、検証できなかった設計文書が
残ることがあります。`doctor` は現行revisionの `design` checkpointが参照する `design.json`
（hash検証済みのartifact）を読み、`unresolved` / `missing` が空でなければ**1 nodeにつき1件**の
warningにします。

- `details`: `stage` / `run_id` / `unresolved` / `missing` / `unresolved_count` / `missing_count` /
  `report_path` / `attempts` / `findings`。人間向け表示は文書名を先頭4件まで出します。
- 品質の判定ではありません。「設計が未検証のまま生成が進んだ」という**構造情報**です。
  `ok` は `true` のまま、exit 0です（`checkpoints` checkは`warn`）。
- **`next_actions` には出しません。** 既存CLIでこの状態を直接解消する操作はなく、内容を作り直す
  `revise --design <doc>` は新しいrevisionを作る重い操作で、同じcheckerに再度落ちる可能性も
  あります。`next_actions` は「止まっている・ずれている状態を戻す」読み取り/再開/採用の操作に
  限定しているため、内容の作り直しは案内しません（必要な場合の手順は
  [章単位の改訂とwhat-if分岐](#章単位の改訂とwhat-if分岐)を参照）。
- 対象は**現行revisionのcheckpointだけ**です。`revise` で新しいrevisionを作れば、その新しい
  `design.json` が判定対象になり、古いrevisionのreportはそのまま残ります。
- `design.json` を持たない古いrunや、`design` checkpointが無いnodeでは何も出しません。
  report自体が壊れている場合は `design.report_unreadable`（warning）になります。
- `status` はrun artifactを読まないため、この項目は`doctor`だけが出します
  （`work.inspected`は従来どおり `design` を含みません）。

binding の stale 一覧は「現在revision以外を指すbinding」を履歴も含めて示すため、再binding後も
古いbindingが残ります。これに対し `next_actions` の `world bind` は、現在revisionにbindingが
無いnodeがある場合だけ出ます（履歴を数えて永久に同じ操作を勧めないため）。

`doctor` も `status` と同じ `work` 要約（root node基準）と `next_actions` を返します。
`doctor` は世界record・binding・run manifestまで調べるため、`work.stale` と `work.runs` が
数値で埋まり、`inspected` も広くなります。`next_actions` は全nodeの状態から集約するので、
未開始の子nodeがあっても「`run` せよ」とは言いません。

`--json` の `schema` は `asc-project-doctor-v1`、`read_only` は常に `true` です。
findingsが`error`を含めばexit 1、なければ0、projectが存在しなければ2です。
待機responseやstaleだけの状態は「異常ではない」ため0を返し、整形した人間向け出力と
`summary.pending` / `summary.stale` / `checks_warn` で判断します。

### ContextPacketの確認: `context show`

```bash
python3 scripts/story_project.py context show prj-seaside
python3 scripts/story_project.py context show prj-seaside --node node-tide
python3 scripts/story_project.py context show prj-seaside --node node-tide --stage design
python3 scripts/story_project.py context show prj-seaside --node node-tide \
  --run att-0123abcd-design --json --out /external/packets/node-tide-design.json
```

- 引数なし（`mode=current`）は、そのnodeの現在revisionで生成した場合に使うpacketを組み立てます。
  packetの種類、byte数、SHA-256、祖先のnode/revision/state/canonサイズ/章数、世界の
  binding IDとbinding revision、overlay順（global → timeframe → region → culture → work → node）、
  canon件数と省略件数、選択した資料の`record_type`・ID・`content_version`、人物知識の指定を表示します。
- `--stage` は現在revisionのそのstageのrunが記録したpacket、`--run` は指定runの
  `project-input.json` に記録されたpacketを読みます（`mode=recorded`）。生成当時の
  選択資料と版をそのまま確認でき、現在値からの再構築ではありません。
- 同じrevisionの記録packetであれば `drift` に記録時と現在の差（referenceの追加・削除・版変更、
  binding、canon件数、祖先、packet種類）を出します。差分は表示だけで、再生成・再採用は行いません。
- 古いrevisionのrunを指定した場合は `same_revision=false` となり、`drift` は行いません。
  そのrevisionの記録packet一覧は表示しますが、現在revisionと比較した差分としては扱いません。
- 祖先も世界bindingも持たないnodeは `Packet: none` になります。
- `--out` はproject外へpacket JSONを書き出す任意指定です。指定しなければ何も書きません。
  書き出した場合はstdout側にpacket本文を重複させず、`external_out` に出力pathを返します。
  packetを持たないnode（祖先も世界bindingもない）に `--out` を指定するとexit 2になります。
- `--json` の `schema` は `asc-project-context-view-v1`、`read_only` は常に `true` です。
  未知のrun・stage、node不在はexit 2です。

### record単位の差分: `diff`

`context show` のdriftは「違う」ことと件数しか示さないため、どのrecordが追加・削除・
版変更されたかは `diff` で確認します。read-onlyで、生成・再開・採用は行いません。

```bash
# 記録済みpacketと現在値
python3 scripts/story_project.py diff prj-seaside --node node-tide \
  --left stage:design --right current
# 同じrevisionの別stage（同じpacketなら identical: yes）
python3 scripts/story_project.py diff prj-seaside --node node-tide \
  --left run:att-0123abcd-plan --right stage:draft
# 編纂viewの2版
python3 scripts/story_project.py diff prj-seaside \
  --left compile:profile-chronicle@<content_version> \
  --right compile:profile-chronicle@<content_version>
```

- `--left` / `--right` は `current`、`stage:<stage>`（現在revisionのcheckpoint）、
  `run:<run_id>`、`compile:<profile_id>[@<content_version>]` を受け付けます。
  編纂viewは同じprofileの版が複数ある場合だけ `@<content_version>` が必須で、
  省略すると候補versionを添えてexit 2になります。
- 比較単位はrecordです。packetでは世界の選択資料（`record_type`・ID・`content_version`）と、
  各祖先のcompact canon項目（項目ごとのhash）を `scope` 付きで並べます。
  編纂viewではmanifestの `source_references` を同じ形で並べます。
- 出力は `added` / `removed` / `changed`（同一IDでversionが変わったもの）と `unchanged` 件数、
  record以外の属性差（`binding_id`、`omitted_canon_count`、編纂の `content_version` など）、
  祖先の `node_id → revision_id` の差です。`identical` はそれらが全て無い場合だけ `true` です。
- packetと編纂viewを混ぜた比較は、全recordが追加と削除になるだけなのでexit 2で拒否します。
- `--json` の `schema` は `asc-project-diff-v1`、`read_only` は常に `true` です。
  未知のspec・stage・run、packetを持たないnodeはexit 2です。差分があってもexit 0です
  （`diff` は検査の合否ではなく観測結果を返すため）。

### dogfoodで確認したこと

小規模な実創作project（2時間軸・3地域・2文化・3文化状態、root→child→grandchild、
43 operator応答、19 run directory（11 attempt）、continuation、明示canon採用とsupersession、
5編纂view、bundle export/restore）をArena operatorで操作しました。`doctor` により、待機responseの
`response_ready` とresponse path、staleなlink/binding/canonの対象ID、`running`のまま
終了記録のないrunを、run directoryを開かずに特定できました。`context show` により、
選択資料のIDとcontent version、overlay順、packetの大きさが版とbindingで変わること
（同じnode-lampでもworld1の6825 bytesとpre1の3070 bytes、node-tideは8092 bytes）、
resumeが記録packetを固定していることを確認できました。復元bundleの `doctor` /
`context show` は元projectと同じ結果を返しました。

このdogfoodで見つかった未解決の運用課題（品質評価とは別）は次のとおりで、PR 10の本体とは
分けて後続で扱います。

- `failed` になったstageにはCLIからの再試行手段がない。`resume` は
  `running` / `waiting_response` / `ready` / `pending` だけを受け付け、`run` は
  「未開始のrevision」だけを受け付け、`continue` は「completeなrevision」だけを受け付けるため、
  provider commandの誤記などで一度`failed`になると、そのrevisionはCLIでは前進できない。
- providerへ渡すcommand文字列の誤りはstage単位の`failed`として記録される。`doctor` は
  これをwarningとして対象stageとrunを示すが、修復方法は提示しない。
- `doctor` の検出は保存済みrecordの参照・hashに限る。`content_version` を持たない
  世界record（例: regionの名称）の書き換えは、記録済みpacketと比べる `world.record_changed`
  で警告できるが、packetを一度も記録していないnodeでは検出できない。署名付きstorageではない。
  警告はrecord単位にまとめるため、影響nodeが多い場合でも`details.nodes`の大きさだけが増える
  （1 nodeあたり約120 bytes。100 nodeで1 recordあたり約12 KB）。
- 編纂viewとContextPacketの比較は、編纂versionの不一致としてしか見えず、
  どのrecordの差で変わったかをCLIから一覧できない（PR 12の `diff` で解消）。
- `design.unresolved` は「checkerを通らなかった文書がある」ことだけを示す。どのcheckがどう
  落ちたかは `design.json` の `docs[*]`（`checks_failed` / `by_severity`）を開く必要があり、
  `doctor` はそこまで展開しない。文書を作り直しても同じcheckerに落ちる可能性があり、
  `doctor` は修復も再生成もしない（read-only）。

## 章単位の改訂とwhat-if分岐

完成した作品の一部だけを作り直す場合は `revise`、別案を独立した作品として残す場合は
`branch` を使います。どちらも**指定した章・設計資料だけを生成し直し、それ以外は
元のrunからbyte単位でコピー**します。元のrevision・run・章本文は変更しません。

```bash
# 現在revisionの第2章だけを作り直す（plan/design/他の章はコピー）
python3 scripts/story_project.py revise prj-seaside --chapter ch02 \
  --provider command --command "python3 scripts/chat_operator.py --dir runs/operator/rev"

# 旧revisionから、設計資料のsceneだけ作り直す
python3 scripts/story_project.py revise prj-seaside --revision rev-1a2b \
  --design scene --provider command --command "..."

# 旧revisionの内容をそのまま持つ別案を、独立した子作品として作る（生成なし）
python3 scripts/story_project.py branch prj-seaside --from-node node-tide \
  --from-revision rev-1a2b --node-id node-whatif --link-id link-whatif \
  --title "もう一つの潮"
```

- `--chapter` と `--design` は繰り返し指定できます。指定がなければ全内容をコピーするだけの
  版（スナップショット）になり、provider呼び出しは0回です。何かを生成する場合は
  `--provider` が必須です。
- `--title` / `--premise` / `--target-chars` は新しいrevisionのWorkSpecを上書きします。
  章数は変更しません（章の追加は `continue` の役割）。
- `revise` の新revisionは `parent_revision_id` に元revision、`parent_runs` に元の3 runを持ち、
  `derived` に種別・元node/revision/run・生成し直す章と設計資料を記録します。
- `branch` は新しいnodeを作り、`create_child` と同じ規則（深さ・order・linkの一意性）で
  linkを張ります。`derived.kind=branch` として元node/revisionを記録します。
- 世界bindingは**明示指定した場合だけ**複製します（`--world-binding`）。指定しなければ
  新revisionは世界文脈を持たず、`context show` も `world` なしのpacketを返します。
- 新revisionのplanと、再生成しないdesign資料は、新しいrunへコピーされます。コピー元の
  内容hashは各runの `revise.json` に記録し、`unchanged_bytes: true` とともに残します。
  コピーを担当したstageのmanifestは `provider: "carried"`、`model: null`、response 0件です。
- 生成する章のpromptには `## 前版からの改訂` を付け、「改訂する章」と「本文を保持する章」を
  明示します。旧本文はchatへ渡しません（直前に生成した章の末尾400字だけが文脈）。
- 中断した `revise` / `branch` は `resume` で続行できます。このときも元runの章bytesは
  再検証され、一致しなければ失敗します。
- 親のpinned出力（`compose` / link）は、`adopt-child` するまで変わりません。改訂した子は
  `doctor` で `link.stale` として表示され、採用は明示操作だけです。
- 改訂・分岐版も `bundle` / 復元 / `doctor` / `context show` の対象です。`doctor` は
  `derived` の元revision・元runが失われていれば `revision.derived_source_missing` /
  `revision.derived_run_missing` を報告します。

旧章のbodyを保ったまま章を追加する `continue` とは別操作です。`continue` は章数と時系列を
拡張し、`revise` は同じ章数を保ったまま内容を差し替えます。

## 保存形式

```text
runs/projects/<project_id>/
├── project.json
├── nodes/<node_id>/
│   ├── current.json
│   ├── revisions/<revision_id>.json
│   ├── checkpoints/<stage>.json
│   └── links/<link_id>.json        # 任意の親から子へのpinned参照
├── world/<record-kind>/<record-id>.json
├── compilations/profiles/<profile-id>.json
├── artifacts/<node_id>/combined-<version>.md
├── artifacts/world/<kind>-<profile-id>-<version>.md
└── runs/<attempt-id>-<stage>/
```

- `project.json`: project ID、root node、作成・更新時刻。
- `current.json`: nodeの現在のrevisionへの小さな参照。
- `<revision_id>.json`: 完全なWorkSpec、そのSHA-256、版付きartifact参照。continuation版は
  `parent_revision_id` と親stageの `parent_runs` も持ち、旧recordは追記・上書きしない。
  改訂・分岐版は加えて `derived`（kind、元node/revision/run、生成し直す章と設計資料）を持つ。
- `checkpoints/<stage>.json`: current revisionのstage状態、attempt、run、版付きartifact参照。
- `links/<link_id>.json`: 任意の親から子への順序・pinned revision・content version・draft artifact参照。
  子の本文は含めず、新版の採用は`adopt-child`だけが変更する。linkは全階層で探索できる。
- `relay/`: 標準フローの Arena relay。`requests/<key>.json`（prompt 全文と
  `prompt_hash`）、`responses/<key>.json`（応答と `prompt_hash`・`model`）、
  `relay export` の出力（`PROMPTS.md`・`index.json`・`outbox/`）が入る。タグは
  8 hex で、タグ→key の対応は index と request ファイルが台帳になる。
  `index.json` は export 時点の控えなので、待ちの正は `relay status` の報告。
  `relay status` / `relay submit` の報告は `asc-relay-round-v1` で、状態・次の1件・
  次のコマンドを返す。回答済みの要求は書き出さず、完成済み・失敗済みの作品には
  取り込まない。
- `manuscript.md`: `render --out` の出力。JSON を開かずに読むための原稿。
- `runs/`: 各stageのmanifest、prompt/response、project-input、生成物。再開runには
  `resume-audit.json`、改訂・分岐runには `revise.json`（コピー元のhashと生成し直した対象）も
  あり、旧runは別directoryに残る。
- `artifacts/`: node別の結合markdownとmanifest、および`world/`以下の世界・作品編纂view。
  S1の個別生成物は各runから直接参照します。
- `compilations/profiles/`: kind・selector・title・content versionを持つ不変の編纂profile。
- `world/`: `timeframes`、`time_spans`、`time_conversions`、`regions`、
  `spatial_relations`、`cultures`、`culture_states`、`culture_state_relations`、
  `canon_entries`、`bindings` のJSON。世界recordも `record_type` / `schema_version` を持ち、
  CultureState・canon・bindingは内容hashによる `content_version` を持ちます。

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
- 世界参照はIDと有効期間を検査し、変換不能な時間軸の統合・未知の移動日数の推定をしない。
- work revisionへのbindingとCultureStateの選択を明示し、新版や未来状態を暗黙に共有しない。
- 子作品の生成と世界canon採用を分離し、source node/revision/artifactへpinする。source改訂は
  stale通知に留め、採用content・旧entry・参照版を自動更新しない。
- 祖先の章本文を子の文脈へコピーせず、選択したcanon・構造要約・参照IDだけを記録する。
- 世界文脈はbinding・scope・有効期間で選択し、指定外の時間軸・未来のstate / canonを含めない。
  人物知識の指定時は祖先factsを`Character.knows`で絞り、foreshadowingを除外する。
  使用したrecordのIDとcontent versionをpacketへ残し、resumeでは現在値からpacketを再構築しない。
- 編纂versionはprofileと選択sourceの版から決定し、同じ入力で同じbytesを再現する。
  年代記を時間軸ごとに作り、無関係な追加で旧viewを上書きしない。
- `doctor` と `context show` は読み取り専用で、生成・再開・採用・編纂・復元を起動しない。
  検査のためのtemp fileやlockも作らず、同じ状態に対して同じ結果を返す。
- `status` と `doctor` の作業要約（`work`）と次の操作（`next_actions`）は同じ定義を共有し、
  未検査の件数を`0`と表示しない。`next_actions` は既存CLIのcommandだけで構成し、自動実行しない。
- `revise` / `branch` は既存revisionとrunを書き換えず、指定外の章・設計資料を元のbytesのまま
  新revisionへコピーする。生成し直す章の指定は `derived` と `revise.json` に残し、
  章数・章順は変えない。世界bindingの複製と親linkの更新は明示操作だけが行う。
- 創作データはGitへ入れない。`runs/` は従来どおりGit管理外である。

これは破損や意図しない不整合を検出する仕組みであり、悪意ある改ざんに対する
署名付きstorageではありません。

## 次のincrement

PR 9では運用可観測性（`doctor` / `context show`）を、PR 10では章単位の `revise` と
what-if `branch` を、PR 11では失敗したstageの明示的な再試行（`resume --retry-failed`）を、
PR 12ではContextPacketと編纂viewのrecord単位差分（`diff`）を、PR 13では `status` と
`doctor` の情報統合（共通の `work` 要約と `next_actions`、`world.record_changed` 検査）を
追加しました。創作projectの生成・再開・再試行・continuation・改訂・分岐・世界文脈・編纂・
bundle・検査・差分確認が一通りCLIから操作できます。
PR 14では、運用モード（モデルはArena.ai、生成の開始は人間、完全自動運用は非目標）と、
後から足す場合の拡張点（`WorldEvent` / `KnowledgeState` / `CharacterState` とindex・
incremental検査のID・scope・互換方針）を文書化しました（実装変更なし）。
PR 15では、9作品（root 1 + 子8、各12章、1作品のみ+2章のcontinuation = 102章）をCLIだけで生成し、
`status`・`doctor`・`compose`・`world compile`・`diff`・`bundle` の所要時間と出力量を実測しました
（`doctor` 182 ms @3作品 → 330–360 ms @8作品、`compose` 174 ms / 93.7 KB、規模869ファイル・3.67 MB）。
この傾きでは50作品でも `doctor` 1.7 s 程度に収まるため、index・依存queue・incremental検査は
現時点では実装しないと判断しました。詳細と再検討の引き金は
[`continuous_creation_roadmap.md`](continuous_creation_roadmap.md)の「PR 15」を参照してください。
PR 16では、そのdogfoodで確認した「子1作品が未完成だと作品集が出せない」を、
`compose --partial`（未収録を明示して残りを編纂）で塞ぎました（前述「未完成の子を含む部分編纂」）。
PR 17では、世界recordを1件書き換えたときの `doctor` の警告と`diff`案内を**record単位**に
まとめました（複数nodeが同じrecordを記録していても警告1件・`diff`1件、影響nodeは
`details.nodes`）。PR 18では、design stageがfail-openで残す `unresolved` / `missing` の設計文書を `doctor` の
`design.unresolved`（warning、1 node 1件、`next_actions`なし）として可視化しました。
次の候補は、より大きなdogfood（複数作品・長期の中断再開）で必要性を
測ってから決めます。詳細は
[`continuous_creation_roadmap.md`](continuous_creation_roadmap.md)の「その後の候補」を参照してください。
WorldEvent・KnowledgeStateや大規模運用の最適化は必要性を確認してから検討し、X-01のskill registryは
共通形が必要になった時点だけを対象とします。品質評価やL2/L3の再開は行いません。
