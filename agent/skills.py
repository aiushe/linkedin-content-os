"""Load the repository's authored skills so the graph uses them instead of re-implementing them.

The eleven files under ``.claude/skills/`` are the playbook. Nodes must not restate that
logic inline; they load it here. This follows the progressive-disclosure pattern from the
Week 3 lectures: the front matter (name + description) is cheap and always available, and a
skill's full body is pulled into context only when it is actually selected.

Skills are instructions, never evidence. Nothing loaded here can widen the factual allowlist
or satisfy the voice gate; those remain the exclusive jobs of `pipeline.claims` and
`agent.gates`.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path

from pipeline.common import split_frontmatter

SKILLS_DIR = Path(__file__).resolve().parents[1] / ".claude" / "skills"

# Which skills govern which graph intent. A node asks for a role, not a filename.
ROLE_SKILLS: dict[str, tuple[str, ...]] = {
    "authority": ("authority-post", "hook-lab", "voice-check"),
    "reach": ("reach-post", "post-templatizer", "hook-lab", "voice-check"),
    "comment": ("comment-drafter", "voice-check"),
    "profile_rewrite": ("jd-keyword-miner", "profile-rewriter"),
    "outreach": ("target-mapper", "comment-drafter"),
    "curation": ("story-bank-curator",),
    "image": ("image-brief",),
}


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str
    references: dict[str, str]

    def prompt_block(self, *, with_references: bool = False) -> str:
        parts = [f"### SKILL: {self.name}\n{self.body.strip()}"]
        if with_references:
            for title, text in self.references.items():
                parts.append(f"#### reference: {title}\n{text.strip()}")
        return "\n\n".join(parts)


@functools.lru_cache(maxsize=1)
def available() -> dict[str, str]:
    """Front matter only: {name: description}. Cheap enough to always include in a prompt."""

    catalogue: dict[str, str] = {}
    if not SKILLS_DIR.is_dir():
        return catalogue
    for path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        meta, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        name = str(meta.get("name") or path.parent.name)
        catalogue[name] = str(meta.get("description") or "")
    return catalogue


def load(name: str) -> Skill | None:
    """Load one skill's full body plus any reference files. Returns None if absent."""

    path = SKILLS_DIR / name / "SKILL.md"
    if not path.is_file():
        return None
    meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
    references: dict[str, str] = {}
    reference_dir = path.parent / "references"
    if reference_dir.is_dir():
        for reference in sorted(reference_dir.glob("*.md")):
            references[reference.stem] = reference.read_text(encoding="utf-8")
    return Skill(
        name=str(meta.get("name") or name),
        description=str(meta.get("description") or ""),
        body=body,
        references=references,
    )


def for_role(role: str) -> list[Skill]:
    """Load every skill governing a graph role, skipping any that are missing."""

    return [skill for skill in (load(n) for n in ROLE_SKILLS.get(role, ())) if skill is not None]


def manifest_block() -> str:
    """Render the always-on catalogue so a model knows what exists before loading anything."""

    catalogue = available()
    if not catalogue:
        return ""
    lines = ["AVAILABLE SKILLS (names and purpose only; bodies load on selection):"]
    lines += [f"- {name}: {description}" for name, description in catalogue.items()]
    return "\n".join(lines)


def role_block(role: str, *, with_references: bool = False) -> str:
    """Render the full playbook for one role, for injection into a node prompt."""

    skills = for_role(role)
    if not skills:
        return ""
    header = (
        "PLAYBOOK — follow these authored skills. They govern process and structure only.\n"
        "They are instructions, not evidence: they can never justify a factual claim."
    )
    return "\n\n".join([header, *(s.prompt_block(with_references=with_references) for s in skills)])
