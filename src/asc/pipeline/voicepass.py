"""The Voice pass (S3): restyle the chapters without changing the facts.

S3 is S2 plus a style layer. The pass rewrites each chapter against a voice
guide while keeping the events, the canon facts and the markers. The default
guide is deliberately generic (keep the viewpoint, show feelings through
action, avoid stock similes); a work-specific ``voice.yaml`` can be rendered
into the prompt instead. What the pass changed is measured afterwards with
``check_voice`` — never claimed from the prompt alone.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..story.canon import Canon
from .draft import check_chapter, clean_text, ensure_markers
from .llm import GenerationRequest, Provider, ProviderError
from .prompts import load_prompt
from .run import RunLedger
from .tasks import Task

TITLE = "Voice"

DEFAULT_VOICE_GUIDE = """\
* 視点と人称を維持する。視点人物の知りえない内面を地の文で断定しない。
* 感情の直接命名（悲しかった、嬉しかった）は、所作か知覚で示す。
* 在庫の比喩（まるで時間が止まったかのよう、まるで夢のよう）は使わない。
* 出来事の順序・台詞の内容・固有名詞は変えない。
* マーカー（{{...}}）と必須語は残す。"""


class VoicePassError(RuntimeError):
    """Raised when the provider fails mid-voice-pass (the run is kept)."""


@dataclass
class VoicePass:
    chapters: tuple[str, ...]
    kept: tuple[str, ...]
    warnings: tuple[str, ...]

    def as_dict(self) -> dict:
        return {"chapters": list(self.chapters), "kept": list(self.kept),
                "warnings": list(self.warnings)}


def voice_guide_text(voice_path: str | Path | None) -> tuple[str, bool]:
    """Render a voice spec into prompt prose, or fall back to the default."""
    if not voice_path:
        return DEFAULT_VOICE_GUIDE, False
    from ..style import load_voice  # local import: style is optional for S3 wiring
    voice = load_voice(voice_path)
    person_ja = "一人称" if voice.person == "first" else "三人称"
    lines = [
        f"* {person_ja}。視点人物は{voice.character}。",
        f"* 語り手の知識範囲: {voice.narrator_knows_ja}",
    ]
    if voice.pronouns:
        lines.append(f"* 自称は「{'」「'.join(voice.pronouns)}」に統一する。")
    for banned in voice.banned:
        lines.append(f"* 禁止: {banned.message_ja or banned.id}")
    lines += ["* 出来事の順序・台詞の内容・固有名詞は変えない。",
              "* マーカー（{{...}}）と必須語は残す。"]
    return "\n".join(lines), True


def build_voice_pass(task: Task, provider: Provider, ledger: RunLedger,
                     canon: Canon | None, *,
                     voice_path: str | Path | None = None,
                     prompt_dir: str | Path | None = None,
                     temperature: float = 0.8, max_tokens: int = 2500,
                     seed: int = 0) -> VoicePass:
    """Restyle every chapter in ``ledger.path / 'text'`` in place."""
    template = load_prompt("voice-pass", prompt_dir)
    ledger.prompt_hashes[template.name] = template.digest
    guide, from_spec = voice_guide_text(voice_path)
    text_dir = ledger.path / "text"

    chapters = sorted(p for p in text_dir.iterdir()
                      if p.is_file() and p.suffix.lower() in {".md", ".txt"})
    done, kept, warnings = [], [], []
    for path in chapters:
        chapter_id = path.stem
        current = path.read_text(encoding="utf-8")
        values = {
            "title": task.title_ja,
            "chapter_id": chapter_id,
            "chapter_text": current,
            "voice_guide": guide,
            "must_include": "、".join(task.must_include),
            "avoid": "、".join(task.avoid),
        }
        request = GenerationRequest(
            purpose=f"voice:{chapter_id}", prompt=template.render(values),
            temperature=temperature, max_tokens=max_tokens, seed=seed,
            context={"task_id": task.id, "chapter": chapter_id,
                     "system": ledger.system},
        )
        try:
            result = provider.generate(request)
        except ProviderError as exc:
            ledger.fail(f"voice:{chapter_id}: {exc}")
            raise VoicePassError(f"voice:{chapter_id}: {exc}") from exc
        ledger.record(request, result)
        ledger.write_text(f"draft/{chapter_id}-voice.txt", result.text)
        text = clean_text(result.text)
        problems = check_chapter(text, task, {"id": chapter_id})
        if problems:
            ledger.write_text(f"draft/{chapter_id}-voice.issues.txt",
                              "\n".join(problems) + "\n")
            kept.append(chapter_id)
            warnings.append(f"{chapter_id}: 文体適用を採用せず初稿を残した"
                            f"（{'; '.join(problems)}）")
            continue
        meta: dict = {}
        if canon is not None:
            chapter = canon.chapters.get(chapter_id)
            if chapter is not None:
                meta = {"day": chapter.day, "location": chapter.location}
        body, injected = ensure_markers(text, meta)
        if injected:
            warnings.append(f"{chapter_id}: マーカーを補った（{', '.join(injected)}）")
        path.write_text(body, encoding="utf-8")
        done.append(chapter_id)

    voice_pass = VoicePass(chapters=tuple(done), kept=tuple(kept),
                           warnings=tuple(warnings))
    ledger.write_json("voice.json", {**voice_pass.as_dict(),
                                     "guide_from_spec": from_spec})
    ledger.finish("ok")
    return voice_pass
