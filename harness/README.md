# harness — 評価用のケース・ルーブリック・判定器

`skills/evaluation-harness` が使う素材を置く。**評価の対象（作品）と、評価の基準（ルーブリック）を
分けて管理する**ため、ケースは `cases/` に、基準は `rubrics/` に置いている。

```
harness/
├── patterns.yaml              # 決定論的に検出する禁止パターン（L1）
├── rubrics/
│   └── story-quality-v0.yaml  # 6 次元のルーブリック（L2）
├── fixtures/
│   ├── judgements-demo.json   # 記録済み判定（オフライン再現・テスト用）
│   ├── labels-demo/           # 2 名×3 ペアの人間ラベル（κ=0.5 の検証用）
│   └── verdicts-demo.json     # 盲検ペアへの判定器の verdict（較正用）
└── cases/
    ├── demo/                  # 矛盾を 7 件仕込んだ 5 章の作品
    │   ├── canon/             # 設定台帳
    │   ├── text/              # 本文（ch01〜ch05）
    │   └── EXPECTED.md        # 期待される検出結果
    ├── demo-baseline/         # 比較用の初稿（要約調・マーカーなし）
    │   └── text/
    ├── brief-demo/            # 企画核の良好／不良デモ（premise-brief）
    ├── world-demo/            # 世界規則の良好／不良デモ（world-rules）
    ├── history-demo/          # 年表の良好／不良デモ（history-timeline）
    ├── character-demo/        # 人物核の良好／不良デモ（character-core）
    ├── relation-demo/         # 関係網の良好／不良デモ（relationship-web）
    ├── plot-demo/             # 筋立ての良好／不良デモ（plot-architecture）
    ├── scene-demo/            # 場面設計の良好／不良デモ（scene-information）
    ├── voice-demo/            # 文体仕様＋2 章（4 件の仕込み、voice-style）
    ├── branch-demo/           # 分岐構造の良好／不良デモ（interactive-branch）
    ├── adaptation-demo/       # 翻案設計の良好／不良デモ（adaptation）
    └── revision-demo/         # 2 章＋パッチ（改稿で 2 件解消、revision-loop）
```

## 実行

```bash
# 整合性だけを見る（ネットワーク不要・決定論的）
python3 scripts/audit_continuity.py \
  --canon harness/cases/demo/canon \
  --text harness/cases/demo/text \
  --out build/audit/demo.json --markdown build/audit/demo.md

# 3 層の評価（L2 は記録済み判定を再生）
python3 scripts/run_evaluation.py \
  --candidate harness/cases/demo/text \
  --baseline harness/cases/demo-baseline/text \
  --canon harness/cases/demo/canon \
  --rubric harness/rubrics/story-quality-v0.yaml \
  --patterns harness/patterns.yaml \
  --judge-fixture harness/fixtures/judgements-demo.json \
  --out build/eval/demo
```

`make audit` / `make evaluate` でも同じ処理を実行できる。

## ケースの追加

1. `cases/<name>/canon/` に台帳を書く（[`../skills/continuity-ledger/references/canon-schema.md`](../skills/continuity-ledger/references/canon-schema.md)）。
2. `cases/<name>/text/` に `ch01.md` から本文を置き、状態変化にマーカーを書く。
3. `cases/<name>/EXPECTED.md` に「仕込んだ矛盾」と「期待される検出」を表で書く。
4. `tests/` に、期待どおりに検出されることを検証するテストを足す。

**ケースには必ず期待値を書く。** 期待値のないケースは、検出器の回帰テストにならない。

## 注意

* `fixtures/judgements-demo.json` は**実際のモデルの出力ではない**。ハーネスの配線を
  オフラインで検証するための固定値である。研究上の主張には使わない。
* `demo-baseline` はマーカーの無い初稿である。監査カバレッジが違うため、
  CED の比較は `comparable: false` になる（それが正しい挙動）。
* ルーブリックを変えたら `version` を上げる。同じ版の中で次元を増やすと、
  過去の結果と比較できなくなる。
