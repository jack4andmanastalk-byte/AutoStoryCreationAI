# データセットスキーマ

すべてのデータセットは JSONL（1 行 1 レコード、UTF-8）です。
`asc.schema.Work` / `asc.schema.AuthorRecord` が正であり、`src/asc/schema.py` に実装があります。

## 1. 作品レコード（`aozora_works.jsonl` / `narou_novels.jsonl`）

| キー | 型 | 説明 |
| --- | --- | --- |
| `id` | str | グローバルに一意な ID。`<source>:<native id>` 形式（`aozora:000148` / `narou:N3558ML`） |
| `source` | str | `aozora_bunko` / `syosetsuka_narou` |
| `title` | str | 作品名 |
| `url` | str | 作品の公式 URL（図書カード / 作品ページ） |
| `text_url` | str\|null | 本文をダウンロードできる URL |
| `authors` | list[obj] | 著者・翻訳者。`{name, role, id, name_kana, url, born_on, died_on, extra}` |
| `genre` | obj\|null | 主ジャンル。`{taxonomy, code, label, parent{taxonomy, code, label}}` |
| `genres` | list[obj] | 副ジャンル・キーワード（小説家になろうのみ） |
| `published_at` | str\|null | 初出日・掲載日（`YYYY-MM-DD`、年のみの場合は `YYYY`） |
| `published_year` | int\|null | 出版年（和暦は西暦へ変換） |
| `language` | str | 常に `ja` |
| `license` | str\|null | ライセンスの短い説明 |
| `rights` | obj | 権利情報（下記） |
| `stats` | obj | 統計値（下記） |
| `text_path` | str\|null | リポジトリ相対の本文テキストパス |
| `pdf_path` | str\|null | リポジトリ相対の PDF パス |
| `extra` | obj | ソース固有のフィールド（下記） |

### `rights`

```json
{
  "source": "Aozora Bunko",
  "copyright_flag": false,
  "note": "作品著作権フラグが有効な作品は再配布不可"
}
```

小説家になろうの `rights.commercialized` は、商用化されているかどうかの判定結果を入れる
intended 領域です（`null` = 未判定 / `true` = 商業化あり / `false` = なし）。
商用版そのものは再配布せず、公式ストアの URL は `extra` に記録します。

### `stats`

| フィールド | 意味 |
| --- | --- |
| `char_count` | 本文の文字数 |
| `paragraph_count` | 段落数（青空文庫） |
| `ruby_count` | ルビの個数（青空文庫） |
| `episodes` | 話数 |
| `read_minutes` | 読了目安時間（分） |
| `fav_novel_cnt` / `impression_cnt` / `review_cnt` | ブックマーク・感想・レビュー数 |
| `all_point` / `all_hyoka_cnt` / `global_point` | 評価ポイント・評価者数・総合評価 |
| `comic_ratio` | 会話率（%） |
| `illustrations` | 挿絵数 |
| `is_completed` / `is_stopped` | 完結済・長期連載停止中 |
| `elements` | R15・残酷な描写などの要素フラグ |

### `extra`（ソース固有）

青空文庫:

```json
{
  "title_kana": "わがはいはねこである",
  "first_appearance": "「ホトトギス」1905（明治38）年1月",
  "base_book": "吾輩は猫である（上）",
  "base_publisher": "岩波文庫",
  "base_edition": "1994（平成6）年4月16日",
  "kana_type": "新字旧仮名",
  "person_id": 148,
  "work_id": 148,
  "text_filename": "148_ruby_1778.zip",
  "text_created_on": "1999-09-21",
  "text_updated_on": "2005-11-14",
  "worker": {"input": "...", "proofread": "..."},
  "metadata_origin": "https://www.aozora.gr.jp/..."
}
```

小説家になろう:

```json
{
  "synopsis": "あらすじ",
  "keywords": "異世界 転生 主人公",
  "first_up": "2013-01-27 07:49:05",
  "last_up": "2026-10-08 01:50:34",
  "updated_at": "2026-10-22 23:18:05",
  "userid": 125212,
  "official_info_url": "https://ncode.syosetu.com/novelview/infotop/ncode/n8406bm/",
  "text_origin": "official data download"
}
```

## 2. 著者レコード（`aozora_authors.jsonl`）

| キー | 型 | 説明 |
| --- | --- | --- |
| `id` | str | `aozora:<人物ID>` |
| `source` | str | `aozora_bunko` |
| `name` | str | 氏名 |
| `name_kana` | str\|null | ヨミガナ |
| `url` | str\|null | 作家ページ URL |
| `born_on` / `died_on` | str\|null | 生年月日・没年月日 |
| `rights` | obj | `copyright_flag` など |
| `extra` | obj | 備考・役割 |

## 3. `manifest.json`

各実行ステップについて取得元・件数・生成時刻・出力先を記録します。

```json
{
  "generated_at": "2026-10-22T06:40:00Z",
  "steps": {
    "aozora_metadata": {"origin": "...", "works": 16330, "authors": 1064},
    "aozora_texts": {"works": 120, "pdf_dir": "data/pdf/aozora"},
    "narou_metadata": {"works": 1534},
    "narou_texts": {"works": 12}
  }
}
```

## 4. 使い方の例

```python
import json

with open("data/datasets/narou_novels.jsonl", encoding="utf-8") as fh:
    for line in fh:
        work = json.loads(line)
        if work["genre"]["code"] == 303 and work["published_year"] >= 2015:
            print(work["title"], work["url"])
```
