# ファイル案内

基準日：2026-10-22。主成果物は **report_ja.md** です。

- `report_ja.md`：日本語のサマリー、方法、144項目、解説、出典一覧。
- `sources.jsonl`：86件の出典・版メタデータ（UTF-8、1行1JSON）。
- `techniques.jsonl`：144項目の構造化データ。
- `categories.json`：18分類の説明。
- `retrieval_audit.jsonl`：146件の通常HTTP取得試行のメタデータ。検索全件のログではありません。
- `sources.schema.json` / `techniques.schema.json`：JSON Schema。
- `validation_report.json`：件数・参照・構文等の検証結果。

A＝公開本文の対象箇所、B＝公認抜粋、C＝要旨・目次等、D＝検索情報のみ。**確認水準は有効性や査読の等級ではありません。** 未確認原著の直接引用に使わず、参照箇所・版を照合してください。操作と例は特記しない限り本カタログの編集的提案です。

ZIPには第三者の本文・PDFを再配布していません。台帳のローカル証跡パスは作業時の記録であり、ZIP内に対応する本文があるという意味ではありません。URLは外部リンクなので、閲覧環境により開けない場合はダウンロード後に参照してください。

Markdownは標準UTF-8です。JSONLは多くの表計算ソフトに直接取り込むより、Python等で行ごとに読む用途に適しています。

```python
import json
with open('sources.jsonl', encoding='utf-8') as f:
    sources = [json.loads(line) for line in f if line.strip()]
```
