# 生成リクエスト（貼り付け用）

上から順に、1 リクエストずつチャットへ送ってください。
**この節より上は送らないでください。**各リクエストの見出しも送る必要はありません。

- 残り 1 件 / 回答済み 38 件

## 最初に一度だけ送る文章（プリアンブル）

```text
あなたは生成ハーネスの「モデル役」です。次の規則だけを守ってください。

1. 各リクエストは独立しています。前のリクエストの内容を持ち越さないでください。
2. 指示された成果物だけを返してください。前置き・後書き・解説・見出し・コードフェンスを
   書かないでください。
3. 回答は必ず次の形で囲んでください（タグはリクエストごとに違います）。

<<<ANSWER タグ>>>
（成果物）
<<<END タグ>>>

4. 日本語で書いてください。文字数の指定がある場合はそれに従ってください。
5. 指示に従えない場合は、成果物の代わりに次を返してください。

<<<ERROR タグ>>>
（従えない理由を 1 行）
<<<END タグ>>>

6. 質問を返さないでください。判断が必要な点は、作品として自然なほうを選んでください。
```

---

## リクエスト 1/1（タグ `2D9C4D23`）

```text
あなたは短編小説の歴史設定担当です。次の固定タスクと設定台帳から、歴史年表（history）を作ってください。

## タスク
- 題名: 切り取られた頁
- ジャンル: novel
- ログライン: 閉山の年、沢渡町役場支所の記録係だった前任者が、事故死者欄に零と書くよう命じられた夜。のちに野々宮あおいが引き継ぐ閲覧簿の裏に、切り取った頁の控えを挟む。
- 章数: 1 章

## 設定台帳
{
  "characters": [
    {
      "id": "yoriko",
      "name": "梶原頼子",
      "aliases": [],
      "status": "alive",
      "location": "沢渡",
      "age_at_start": 42,
      "knows": [
        "F-11"
      ]
    },
    {
      "id": "kuroda",
      "name": "黒田支所長",
      "aliases": [
        "支所長"
      ],
      "status": "alive",
      "location": "沢渡",
      "age_at_start": 55,
      "knows": [
        "F-11"
      ]
    }
  ],
  "facts": [
    {
      "id": "F-11",
      "summary": "閉山時の事故死者欄は本庁への提出前に零と清書し直された",
      "terms": [
        "清書"
      ],
      "setup": "ch01"
    },
    {
      "id": "F-12",
      "summary": "切り取られた下書きの頁の控えが閲覧簿の裏表紙の袋に挟まれている",
      "terms": [
        "裏表紙"
      ],
      "setup": "ch01"
    }
  ],
  "locations": [
    {
      "id": "沢渡",
      "travel_days": {
        "尾根野": 2
      }
    },
    {
      "id": "尾根野",
      "travel_days": {
        "沢渡": 2
      }
    }
  ],
  "chapters": [
    {
      "id": "ch01",
      "day": 1,
      "location": "沢渡"
    }
  ],
  "foreshadowing": [
    {
      "id": "fs-101",
      "description": "定規を当てて切り取った下書きの頁",
      "setup": "ch01",
      "payoff": "ch01"
    }
  ]
}

## 先行する設計書
（先行する設計書なし）

## 守ること
1. 出来事は年代順に並べ、紀年を逆行させない。
2. 原因の参照は実在の出来事 ID を指し、年代が前後しないようにする。
3. すべての出来事に、現在に残る痕跡を 5 字以上で書く。
4. 正史と異説を分ける。異説（apocrypha）に挙げた言い伝えは、出来事の題・結果・痕跡の
   いずれかにも同じ内容が現れるものにする（年表のどこにも現れない言い伝えだけを置かない）。
5. 史料（sources）の由来（origin）は invented / adapted / cited のいずれかで始める
   （「cited: 補足」のように後ろに補足を付けてもよい）。cited の場合は citation を必ず書き、
   holder（保持者）は空欄にしない。実在史料と創作を混ぜない。
6. 知識地図の人物は設定台帳に、出来事は年表に存在させる。同じ出来事を
   knows と unknown の両方に入れない。

## 出力
JSON のみを返してください。前後に説明文やコードフェンスを付けないでください。

{
  "eras": [{"id": "era-1", "name": "時代名", "begins": -100, "ends": 0}],
  "events": [
    {"id": "ev-1", "year": -50, "title": "出来事", "cause": "原因となった出来事のID",
     "effect": "結果", "trace": "現在に残る痕跡（5字以上）", "era": "era-1"}
  ],
  "sources": [
    {"id": "src-1", "kind": "正史か異説か", "holder": "保持者（必須）",
     "origin": "invented / adapted / cited のいずれか", "citation": "引用（cited の場合は必須）"}
  ],
  "apocrypha": ["異説として扱う言い伝え（出来事の題・結果・痕跡のいずれかにも現れるもの）"],
  "knowledge": {"人物ID": {"knows": ["ev-1"], "unknown": ["ev-2"]}},
  "notes": ""
}
出来事は年代順。原因の参照は実在の出来事を指し、年代が前後しない。
すべての出来事に痕跡を書く。正史と異説を分ける。
史料の由来は invented / adapted / cited のいずれかにする。
異説は年表の出来事にも現れるものにする。
知識地図の人物は canon に、出来事は年表に存在させる。
## 前版からの改訂
これは完成作品の一部だけを作り直す作業です。
改訂する章: なし
変更しない章（本文を保持し、書き換えない）: ch01
作り直す設計資料: history

## 祖先作品の選択文脈（本文ではありません）
以下は選択したcanonと構造要約だけです。祖先の章本文は含めず、この作品の前提と矛盾する場合はこの作品の指定を優先してください。
{"ancestors":[{"canon":{"chapters":[{"day":1,"id":"ch01","location":"尾根野"},{"day":3,"id":"ch02","location":"沢渡"},{"day":5,"id":"ch03","location":"尾根野"},{"day":7,"id":"ch04","location":"沢渡"}],"characters":[{"aliases":[],"id":"aoi","location":"沢渡","name":"野々宮あおい","status":"alive"},{"aliases":["源じい"],"id":"gen","location":"尾根野","name":"大庭源太郎","status":"alive"},{"aliases":[],"id":"sumi","location":"尾根野","name":"佐伯スミ","status":"alive"},{"aliases":["トオル"],"id":"toru","location":"尾根野","name":"三村トオル","status":"dead"}],"facts":[{"id":"F-01","setup":"ch01","summary":"三通の手紙はどれも差出人が同じで、宛名がない","terms":["差出人"]},{"id":"F-02","setup":"ch02","summary":"公式記録は閉山時の事故死者を零と書いている","terms":["零"]},{"id":"F-03","setup":"ch03","summary":"トオルは事故の日に坑道へ入っていない","terms":["入坑記録"]},{"id":"F-04","setup":"ch04","summary":"あおいは写しの手続きの欄外に、聞き取りとして差出人の名を残した","terms":["欄外"]}],"foreshadowing":[{"description":"切手の貼られていない手紙","id":"fs-001","payoff":"ch03","setup":"ch01"},{"description":"源じいが言いよどむ理由","id":"fs-002","payoff":"ch02","setup":"ch01"},{"description":"零と書かれた死者の欄","id":"fs-003","payoff":"ch03","setup":"ch02"},{"description":"写しの手続きに添える聞き取り欄","id":"fs-004","payoff":"ch04","setup":"ch02"}],"locations":[{"id":"尾根野","travel_days":{"沢渡":2}},{"id":"沢渡","travel_days":{"尾根野":2}}]},"chapters":[{"chars":807,"day":1,"id":"ch01","location":"尾根野","markers":5},{"chars":668,"day":3,"id":"ch02","location":"沢渡","markers":5},{"chars":795,"day":5,"id":"ch03","location":"尾根野","markers":5},{"chars":646,"day":7,"id":"ch04","location":"沢渡","markers":6}],"draft_run_id":"att-08815b0b73c447a89b074b8df3c557fe-draft","node_id":"node-4e577937dd8046188907958c9e82c19e","parent_node_id":null,"plan_run_id":"att-5eb3ffd445f2404ca3ffa65742c06539-plan","premise":"閉山した銅山の町。最後の坑道に残された、宛名のない手紙を届ける郵便配達員の話。手紙は三通あり、差出人はいずれも同じ人物。町の公式記録と、年寄りたちの記憶は食い違っている。","revision_id":"rev-5f5c678e61054d6193be2f09716d3466","spec_sha256":"1c756e9620e93f437079c8233bb7dfad59df21f1fbed841623c9b8cc2a31cb79","state":"complete","title":"宛名のない手紙"}],"node_id":"node-sawatari","project_id":"prj-mine","record_type":"asc-context-packet-pre1","revision_id":"rev-60a71ed1795342f091ed718fc773e986","schema_version":1,"selection":{"canon":"compact_structured_v1","max_items_per_collection":32,"prose":"excluded","scope":"ancestors"}}
```

タグは必ずこの 8 文字 **`2D9C4D23`** を使ってください（`ch01` やファイル名を使わないでください）。

回答はこの形で返ってきます（そのまま貼り返してください）。

```text
<<<ANSWER 2D9C4D23>>>
…本文…
<<<END 2D9C4D23>>>
```
