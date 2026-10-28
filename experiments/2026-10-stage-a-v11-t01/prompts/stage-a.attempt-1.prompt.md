# Stage A: 構造化ゲームログの生成

あなたは擬似 TRPG のゲームマスターです。**散文は書きません。** 与えられた設定台帳（canon）と設計書（plot.json / scene.json）だけを根拠に、章・場面ごとの【構造化ゲームログ】を 1 つの JSON として返してください。返答は JSON のみ（コードフェンス可、説明文不可）。

## 入力

### 題材
題材: 灯台の鍵（t01）
前提: 嵐の夜、灯台守の娘は、灯りを消すために貸した鍵が、三年前に死んだ人物の手に渡っていたことを知る。彼女は灯りを守るか、鍵の行方を追うかを選ばなければならない。
必ず含める語: 灯台、鍵、嵐
使ってはいけない語: 選ばれし者、古代の予言

### 設定台帳（canon の要約・これ以外の人物・事実・場所・伏線を作らない）
{
  "characters": [
    {
      "id": "aria",
      "name": "アリア",
      "aliases": [
        "灯守の娘"
      ],
      "status": "alive",
      "location": "灯台",
      "age_at_start": 24,
      "knows": [
        "F-01"
      ]
    },
    {
      "id": "boris",
      "name": "ボリス",
      "aliases": [
        "鍵屋"
      ],
      "status": "alive",
      "location": "王都",
      "age_at_start": 51,
      "knows": [
        "F-02",
        "F-03"
      ]
    },
    {
      "id": "celia",
      "name": "セリア",
      "aliases": [
        "渡し守"
      ],
      "status": "alive",
      "location": "港",
      "age_at_start": 33,
      "knows": []
    },
    {
      "id": "johan",
      "name": "ヨハン",
      "aliases": [
        "兄",
        "帰らぬ兄"
      ],
      "status": "dead",
      "location": "王都",
      "age_at_start": null,
      "knows": [
        "F-04"
      ]
    }
  ],
  "facts": [
    {
      "id": "F-01",
      "summary": "灯りを消してはいけない。霧が港町を呑む。",
      "terms": [
        "灯り"
      ],
      "setup": "ch01"
    },
    {
      "id": "F-02",
      "summary": "鍵は二本あり、予備は王都の鍵屋に預けられている。",
      "terms": [
        "予備の鍵"
      ],
      "setup": "ch02"
    },
    {
      "id": "F-03",
      "summary": "三年前の嵐の夜の記録は、後から別の筆で書き換えられている。",
      "terms": [
        "書き換え",
        "削られた頁"
      ],
      "setup": "ch02"
    },
    {
      "id": "F-04",
      "summary": "ヨハンは雷から港町を守るために灯りを落とし、その夜に死んだ。",
      "terms": [
        "雷",
        "三年前"
      ],
      "setup": "ch03"
    },
    {
      "id": "F-05",
      "summary": "灯台から王都までは三日、戻りも三日である。",
      "terms": [
        "三日"
      ],
      "setup": "ch01"
    }
  ],
  "locations": [
    {
      "id": "灯台",
      "travel_days": {
        "港": 1,
        "王都": 3
      }
    },
    {
      "id": "港",
      "travel_days": {
        "灯台": 1,
        "王都": 2
      }
    },
    {
      "id": "王都",
      "travel_days": {
        "灯台": 3,
        "港": 2
      }
    }
  ],
  "chapters": [
    {
      "id": "ch01",
      "day": 1,
      "location": "灯台"
    },
    {
      "id": "ch02",
      "day": 4,
      "location": "王都"
    },
    {
      "id": "ch03",
      "day": 7,
      "location": "灯台"
    }
  ],
  "foreshadowing": [
    {
      "id": "fs-001",
      "description": "父が『鍵は二本ある』と言ったまま口を閉ざしたこと。",
      "setup": "ch01",
      "payoff": "ch03"
    },
    {
      "id": "fs-002",
      "description": "三年前の嵐の夜の記録が帳面から欠けていること。",
      "setup": "ch01",
      "payoff": "ch02"
    },
    {
      "id": "fs-003",
      "description": "潮札に書かれた『半灯』の刻み。",
      "setup": "ch02",
      "payoff": "ch03"
    }
  ]
}

### plot.json（幕と転換点。幕 ID・転換点 ID・所属章をそのまま使う）
幕（ID / 章 / 問い）:
- setup / ch01 / アリアは灯台に残って油を見守るのか、王都の帳面を確かめに行くのか。
- investigation / ch02 / アリアは鍵屋の写しをそのまま信じるのか、削られた記録を疑うのか。
- resolution / ch03 / アリアは予備の鍵に頼るのか、自分の判断で灯りを支えるのか。
転換点（ID / 章 / 選択）:
- t1 / ch01 / アリアは父の言いつけだけを守るのをやめ、潮札を携えて王都へ向かうと決める。
- t2 / ch02 / アリアは鍵を受け取って帰るのをやめ、書き換えられた頁の写しを求める。
- t3 / ch03 / アリアは予備の鍵を探すのをやめ、潮札の刻みどおりに自分の手で灯りを合わせる。

### scene.json（場面の目的・対立・変化・緊張・知識・開示・伏線）
{
  "scenes": [
    {
      "id": "s01",
      "chapter": "ch01",
      "purpose": "帳面の欠落と潮札を置き、王都へ行く動機を作る。",
      "conflict": "父の言いつけを守りたい気持ちと、記録の欠落を確かめたい気持ちがぶつかる。",
      "change": "アリアは潮札を革袋に入れ、王都へ発つと決める。",
      "tension": "curiosity",
      "knowledge": [
        {
          "character": "aria",
          "entry": [
            "F-01"
          ],
          "gained": [
            "F-05"
          ]
        }
      ],
      "disclosure": {
        "disclosed": [
          "F-01",
          "F-05"
        ],
        "withheld": [
          {
            "fact": "F-03",
            "reason": "王都の帳面の写しを見るまで記録の改竄を匂わせない。"
          }
        ]
      },
      "foreshadows": {
        "planted": [],
        "paid": []
      }
    },
    {
      "id": "s02",
      "chapter": "ch02",
      "purpose": "鍵屋の写しと石膏手形から、記録が書き換えられた証拠を得る。",
      "conflict": "ボリスは預かり物として鍵だけを渡したい。アリアは欠けた頁の写しを求める。",
      "change": "アリアは写しを受け取り、潮札の刻みが記録と食い違うと気づく。",
      "tension": "irony",
      "knowledge": [
        {
          "character": "aria",
          "entry": [
            "F-01",
            "F-05"
          ],
          "gained": [
            "F-02",
            "F-03"
          ]
        },
        {
          "character": "boris",
          "entry": [
            "F-02",
            "F-03"
          ],
          "gained": []
        }
      ],
      "disclosure": {
        "disclosed": [
          "F-02",
          "F-03"
        ],
        "withheld": [
          {
            "fact": "F-04",
            "reason": "兄が灯りを落とした理由は、灯台で潮札を読む終章まで伏せる。"
          }
        ]
      },
      "foreshadows": {
        "planted": [],
        "paid": [
          "fs-002"
        ]
      }
    },
    {
      "id": "s03",
      "chapter": "ch03",
      "purpose": "潮札の刻みどおりに灯りを合わせ、兄の選択を自分の務めとして引き受ける。",
      "conflict": "予備の鍵に頼りたい気持ちと、目の前の灯りを自分の手で支える責任が対立する。",
      "change": "アリアは半灯の刻みを選び、灯りを消さずに嵐の夜を越える。",
      "tension": "deadline",
      "knowledge": [
        {
          "character": "aria",
          "entry": [
            "F-01",
            "F-02",
            "F-03",
            "F-05"
          ],
          "gained": [
            "F-04"
          ]
        }
      ],
      "disclosure": {
        "disclosed": [
          "F-04"
        ],
        "withheld": []
      },
      "foreshadows": {
        "planted": [],
        "paid": [
          "fs-001",
          "fs-003"
        ]
      }
    }
  ]
}

## 出力スキーマ

{
  "schema_version": "1.1",
  "task": "題材 ID",
  "notes": "任意",
  "chapters": [
    {
      "id": "ch01", "day": 1, "location": "canon の場所 ID",
      "emitted_markers": ["{{time: day=1}}", "{{location: 灯台}}"],
      "scenes": [
        {
          "id": "g01", "scene_ref": "s01", "act_ref": "setup", "turn_ref": "t1",
          "situation": "状況提示", "purpose": "目的", "conflict": "対立",
          "change": "変化", "tension": "curiosity", "choice": "転換点の選択",
          "outcome": "結果", "phase": "opening", "outcome_kind": "success", "rescue": "", "carry_forward": ["次の場面へ渡す結果"], "present_characters": ["aria"],
          "actions": [
            {"id": "a1", "type": "action", "actor": "aria",
             "target": "対象", "summary": "何をしたか"},
            {"id": "a2", "type": "record_reference", "actor": "aria",
             "subject": "johan", "medium": "潮札", "summary": "記録への言及"}
          ],
          "state_delta": {
            "learned_facts": [{"character": "aria", "fact": "F-05"}],
            "used_facts": [{"character": "aria", "fact": "F-01"}],
            "foreshadow_events": [{"id": "fs-001", "event": "setup"}],
            "location_moves": [{"character": "aria", "origin": "灯台",
                                "destination": "王都", "depart_day": 1,
                                "arrival_day": 4}]
          },
          "emitted_markers": ["{{learn: aria fact=F-05}}",
                              "{{foreshadow: fs-001 setup}}"]
        }
      ]
    }
  ]
}
型: action / dialogue / record_reference / memory_mention。tension: suspense /
curiosity / surprise / irony / deadline / quiet。event: setup / payoff。
場面フレーム（1.1）: phase は opening/development/climax/ending、outcome_kind は success/partial/fail_forward、rescue は fail_forward のときだけ、carry_forward は最後の場面以外で 1〜3 件。

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

- 章ごとに、先頭へ `{{time: day=<章の day>}}`、`{{location: <章の location>}}`
  をこの順で 1 件ずつ。この 2 件を章の `emitted_markers` に書く。
- 場面ごとに、`state_delta.learned_facts` の順で
  `{{learn: <人物ID> fact=<事実ID>}}`、続いて `used_facts` の順で
  `{{use: <人物ID> fact=<事実ID>}}`、続いて `foreshadow_events` の順で
  `{{foreshadow: <布石ID> setup|payoff}}`。これらを場面の
  `emitted_markers` に、同じ順序で書く。
- `location_moves` は移動日数の検査に使うだけで、マーカーは出さない。
- マーカーを自分で追加・削除・並べ替えしてはいけない。導出列がそのまま確定列になる。

このログは構造・衛生の L1 検査に使われます。物語の面白さを判定するものではありません。登場人物・事実・日数・伏線を**増やさない**でください。
