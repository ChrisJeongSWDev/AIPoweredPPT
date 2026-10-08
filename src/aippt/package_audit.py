#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Every r:-namespaced attribute in the package resolves to a rel that exists on ITS part.

This IS the corruption test. We have no PowerPoint to test against, and LibreOffice is far
more forgiving than PowerPoint about a dangling relationship -- it will happily render a
deck that PowerPoint offers to repair. So a clean LibreOffice render proves nothing here;
this audit does.

Cheap enough to run as a post-render assertion in production, not just in tests.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


class DanglingRelationship(RuntimeError):
    """A relationship id in the XML has no matching entry in that part's .rels."""


def _rel_ids(part: Any) -> set[str]:
    try:
        return set(part.rels.keys())
    except AttributeError:                        # older Relationships types
        return {r.rId for r in part.rels}


def audit_part(part: Any) -> list[str]:
    element = getattr(part, "_element", None)
    if element is None:                           # binary part (image, media): no XML, no refs
        return []
    known = _rel_ids(part)
    problems = []
    for el in element.iter():
        for attr, rid in el.attrib.items():
            if not attr.startswith("{%s}" % _R_NS) or not rid:
                continue
            if rid not in known:
                problems.append(
                    f"{part.partname}: <{el.tag.split('}')[-1]} {attr.split('}')[-1]}=\"{rid}\"> "
                    f"-> no such relationship on this part"
                )
    return problems


def audit_package(prs: Any) -> list[str]:
    problems = []
    for part in prs.part.package.iter_parts():
        problems.extend(audit_part(part))
    return problems


def audit_file(path: Path) -> list[str]:
    """Reopen a saved .pptx and audit it. Reopening matters: it is the round-trip through
    serialisation that turns an in-memory inconsistency into a real dangling id."""
    from pptx import Presentation
    return audit_package(Presentation(io.BytesIO(Path(path).read_bytes())))


def assert_clean(path: Path) -> None:
    problems = audit_file(path)
    if problems:
        raise DanglingRelationship(
            f"{len(problems)} dangling relationship(s) in {path.name} -- PowerPoint will offer "
            f"to repair this file:\n  " + "\n  ".join(problems[:20])
        )