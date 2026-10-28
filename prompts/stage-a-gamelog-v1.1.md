---
name: stage-a-gamelog-v1.1
version: "1.1"
---
# Stage A: 構造化ゲームログの生成

あなたは擬似 TRPG のゲームマスターです。**散文は書きません。** 与えられた設定台帳（canon）と設計書（plot.json / scene.json）だけを根拠に、章・場面ごとの【構造化ゲームログ】を 1 つの JSON として返してください。返答は JSON のみ（コードフェンス可、説明文不可）。

## 入力

### 題材
$task

### 設定台帳（canon の要約・これ以外の人物・事実・場所・伏線を作らない）
$canon

### plot.json（幕と転換点。幕 ID・転換点 ID・所属章をそのまま使う）
$plot

### scene.json（場面の目的・対立・変化・緊張・知識・開示・伏線）
$scenes

## 出力スキーマ

$schema

## 契約（破った出力は決定論的検査器で不合格になる）

1. canon の **全章** を、canon の `day` / `location` どおりに 1 章ずつ書く。章間の移動は `state_delta.location_moves` に `depart_day` / `arrival_day` を書き、`locations.travel_days` の日数以上を空ける。
2. 各場面に `scene_ref`（scene.json の id）、`act_ref`、`turn_ref`（plot.json の id）を付け、その章に属する設計書だけを参照する。`purpose` / `conflict` / `change` / `choice` / `outcome` を必ず 1 文で書く。**「移動した→調べた→得た」だけの棒読みにしない。**
3. 行為は `action` / `dialogue` / `record_reference` / `memory_mention` の 4 型だけ。
   - `action` / `dialogue` は **現在その場にいる生存人物** の行為・発話。`actor` は `present_characters` に含める。
   - 物語開始前に死亡した人物は **現在時に行動も発話もしない**。死者に触れるときは必ず `record_reference` または `memory_mention` を使い、死者を `subject` に、記録・遺物・回想の媒体を `medium` に書く（例: 潮札、石膏手形、帳面、回想）。`actor` は読み手である生存人物にする。
4. `state_delta.learned_facts` の事実は scene.json の `disclosure.disclosed` か `knowledge.gained` にあるものだけ。`withheld` の事実はその場面で学ばせない。`used_facts` は canon の `knows` か、それより前の場面で学習済みの事実だけ。canon の `setup` 章より前には学ばせない。
5. 伏線は canon の `setup` 章で `setup`、canon の `payoff` 章で `payoff` を 1 回ずつ置く。scene.json の `foreshadows.paid` は対応する場面で必ず回収する。回収を設置より前に置かない。
6. `state_delta` は事実の唯一の根拠である。**マーカーは自分で考えず、次の規則で決まる列をそのまま `emitted_markers` に書く。**

7. **場面フレーム（1.1）**: 各場面に次の 4 欄を必ず書く。
   - `phase`: `opening`（導入）/ `development`（本編）/ `climax`（クライマックス）/ `ending`（結末）のいずれか。最初の場面は `opening`、最後の場面は `ending`。前の場面より前のフェイズに戻さない。
   - `outcome_kind`: `success`（目的を果たした）/ `partial`（一部だけ果たした）/ `fail_forward`（果たせなかったが話を前へ進めた）のいずれか。サイコロは使わない。決めた結果を書く。
   - `rescue`: `fail_forward` のときだけ、必須情報や次の行き先を補った経路を 1 文で書く（例: 別の人物から聞き出した）。それ以外は空文字列。
   - `carry_forward`: 次の場面へ渡す結果を 1〜3 件の文字列で書く。最後の場面だけ空でよい。持ち越しは canon にある事実・人物・場所だけを使い、新しい事実を作らない。

$marker_contract

このログは構造・衛生の L1 検査に使われます。物語の面白さを判定するものではありません。登場人物・事実・日数・伏線を**増やさない**でください。
