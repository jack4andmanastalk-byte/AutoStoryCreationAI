# demo — 期待される検出結果

`harness/cases/demo` は、監査が「検出できるはずのもの」を検出できるかを
確かめるための 5 章の小さな作品です。本文には意図的に矛盾を仕込んであります。
章ファイルには説明を書かず、ここにまとめています（説明文が本文として
解析されるのを避けるため）。

| 章 | 仕込んだもの | 期待される検出 |
| --- | --- | --- |
| ch01 | セリアが、知らない事実 F-07 の語「王の病」を台詞で使う | `knowledge_violation` / medium |
| ch01 | fs-002 の回収が、設置（ch03）より前 | `foreshadow_order` / high |
| ch02 | アリアが、ch03 で学ぶ事実 F-07 を先に使う | `knowledge_violation` / high |
| ch02→ch03 | 灯台→王都は 3 日必要だが、経過は 1 日 | `travel_time` / medium |
| ch04 | ボリスが ch02 で死亡、ch04 で発話 | `dead_character_reappears` / high（＋言及 medium） |
| ch04 | アリアの年齢が 24 から 23 に減る | `stated_age` / medium |
| ch04 | fs-003 が設置されたまま回収されない | `unresolved_foreshadow` / medium |
| ch05 | ボリスが夢の中で発話 | 除外（`suppressions.yaml`） |

```bash
python3 scripts/audit_continuity.py \
  --canon harness/cases/demo/canon --text harness/cases/demo/text --out build/audit/demo.json
```

既定の `--fail-on high` では high が 3 件あるため**終了コード 1**になります。
デモをそのまま表示したいときは `make audit`（`--fail-on none`）を使ってください。
`ch04` のボリスは「発話（high）」と「言及（medium）」の 2 通りで報告されます。

`tests/test_continuity.py` が、この表と同じ検出結果になることを検証しています。
