# リクエスト 1/1（タグ `CF27`）

```text
あなたは短編小説の企画担当です。次の固定タスクと設定台帳から、企画核（brief）を作ってください。
企画核は「検証可能な形の企画」であり、本文ではありません。

## タスク
- 題名: 灯台の鍵
- ジャンル: fantasy
- ログライン: 嵐の夜、灯台守の娘は、灯りを消すために貸した鍵が、三年前に死んだ人物の手に渡っていたことを知る。彼女は灯りを守るか、鍵の行方を追うかを選ばなければならない。
- 本文に必ず含める語: 灯台、鍵、嵐
- 使ってはいけない定型: 選ばれし者、古代の予言
- 章数: 3 章

## 設定台帳
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

## 先行する設計書
（先行する設計書なし）

## 守ること
1. ログラインは一文にし、`elements` の who / where / wants / obstacle に書いた各文字列を、
   言い換えず一字一句そのままログラインに含める。
2. 主題は対立する命題の形（A対B）にする。
3. 類似作は 3 件以上挙げ、各 `axis` は `structure / character / world` のいずれかに限定し、
   差分の説明は 10 字以上にする。
4. 禁止条件には、後工程が判定できる確認方法を添える。
5. 失敗の問いは「〜か？」の検証可能な形にする。

## 出力
JSON のみを返してください。前後に説明文やコードフェンスを付けないでください。

{
  "logline": "一文のログライン（20〜300字。elements の各文字列を一字一句そのまま含める）",
  "premise": "前提の要約",
  "theme": "主題を対立命題の形で（例: 務め対情）",
  "elements": {"who": "誰", "where": "どこ", "wants": "望み", "obstacle": "妨げ"},
  "similar": [
    {"title": "類似作の題名", "axis": "structure / character / world のいずれか", "difference": "10字以上の差分"}
  ],
  "prohibitions": [
    {"rule": "禁止条件", "check_ja": "後工程での確認方法"}
  ],
  "failure_questions": ["検証可能な問いの形（〜か？）"],
  "genre": "ジャンル", "audience": "想定読者"
}
similar は 3 件以上。禁止条件には確認方法を添える。
```
