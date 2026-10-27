# works/ — 版管理する作品の置き場所

`scripts/story_project.py --root works ...` で作る作品の保存先です。`runs/` は
git 管理外でセッションを越えて残る保証がないため、**残す作品はここに置いて
commit / push します**（`docs/standard_flow.md` §3）。

```bash
.venv/bin/python scripts/story_project.py --root works init \
  --project-id prj-seaside --title "潮の記録者" --premise "港町で失われた潮位記録を追う。"
```

- 作品ごとに `<project_id>/` ができます。中身は `docs/project.md` の「保存形式」。
- `relay/responses/` には実際に生成した応答だけを置きます。生成していない応答や
  手で書き換えた本文を置かないでください。
- 実験として登録する走りは `experiments/<id>/` に置き、ここには混ぜません。
- 原稿は `render --out works/<project_id>/manuscript.md` で書き出します。
