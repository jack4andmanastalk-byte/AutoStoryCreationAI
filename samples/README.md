# samples

このディレクトリはリポジトリに同梱する小さなサンプルと検証済みカタログです。
全件データ・全話プレーンテキスト本文は `make data` で `data/` 配下に生成されます（PDF は容量最適化・AI 利用特化のため全てプレーンテキスト化の上で削除済みです）。本文は同梱・配布していません（2026-10-29 削除）。書誌メタデータのみ `make pull-datasets` で取得できます。

* `aozora_works.sample.jsonl` / `aozora_authors.sample.jsonl` … 青空文庫メタデータの部分集合
* `narou_novels.sample.jsonl` … 小説家になろうメタデータの部分集合
* `narou_commercialized_all.jsonl` … 外部実在確認済・商業化統合コーパス（全 373 作品: 総合 Top 300 ＋ 5ジャンル追加 73 作品）
* `narou_commercialized_ranked.jsonl` (`top100` / `rank101_200` / `rank201_300` も同梱) … 総合ランキング上位 300 作品メタデータ
* `narou_commercialized_genre_supplement.jsonl` … 5ジャンル限定（歴史 15・推理 15・現代 15・SF 15・ホラー 13＝計 73 作品）追加カタログ
* （旧 `texts/` 本文サンプルは 2026-10-29 に削除）
