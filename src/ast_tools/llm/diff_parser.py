"""Parse and validate unified diffs from LLM suggestions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParseResult:
    """Result of parsing and validating a unified diff."""
    success: bool
    edits: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    error: str | None = None
    parsed_hunks: int = 0
    matched_hunks: int = 0
    applied_text: str | None = None


_HUNK_HEADER_RE = re.compile(r"^@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@")
_DIFF_LINE_RE = re.compile(r"^([ +\-\\])")


def parse_and_validate_diff(
    diff_text: str,
    original_content: str,
    file_extension: str = ".py",
) -> ParseResult:
    """Parse a unified diff and validate it applies cleanly.

    Parses hunks, validates context/removed lines match original_content,
    applies changes in-place, and returns confidence score based on
    context match quality.

    Args:
        diff_text: Unified diff string from LLM response
        original_content: Original file content to validate against
        file_extension: File extension for syntax validation (unused in v1)

    Returns:
        ParseResult with parsed edits, confidence, and validation status
    """
    if not diff_text or not diff_text.strip():
        return ParseResult(success=False, error="Empty diff text")

    lines = original_content.splitlines(keepends=True)

    # Split into hunks
    hunks = _parse_hunks(diff_text)
    if not hunks:
        return ParseResult(success=False, error="No hunks found in diff")

    total_confidence = 0.0
    all_edits = []
    matched = 0

    for hunk in hunks:
        result = _apply_hunk(hunk, lines)
        if result.success:
            matched += 1
            total_confidence += result.confidence
            if result.edits:
                all_edits.extend(result.edits)

    if matched == 0:
        return ParseResult(
            success=False,
            error="No hunks matched the original content",
            parsed_hunks=len(hunks),
            matched_hunks=0,
            confidence=0.0,
        )

    # Reconstruct the full content
    applied_text = "".join(lines)

    # Confidence = average context match across all hunks
    avg_confidence = total_confidence / len(hunks) if hunks else 0.0

    return ParseResult(
        success=True,
        edits=all_edits,
        confidence=avg_confidence,
        parsed_hunks=len(hunks),
        matched_hunks=matched,
        applied_text=applied_text,
    )


def _parse_hunks(diff_text: str) -> list[dict]:
    """Split diff into individual hunks."""
    hunks = []
    current_hunk = None

    for line in diff_text.splitlines():
        match = _HUNK_HEADER_RE.match(line)
        if match:
            if current_hunk:
                hunks.append(current_hunk)
            current_hunk = {
                "old_start": int(match.group(1)),
                "old_count": int(match.group(2)) if match.group(2) else 1,
                "new_start": int(match.group(3)),
                "new_count": int(match.group(4)) if match.group(4) else 1,
                "context_before": [],
                "removed": [],
                "added": [],
                "context_after": [],
                "phase": "context_before",
            }
        elif current_hunk:
            if line.startswith(" "):
                content = line[1:]  # Remove leading space
                current_hunk[current_hunk["phase"]].append(content)
            elif line.startswith("-"):
                current_hunk["removed"].append(line[1:])
                current_hunk["phase"] = "removed"
            elif line.startswith("+"):
                current_hunk["added"].append(line[1:])
                current_hunk["phase"] = "added"
            elif line.startswith("\\"):
                # No newline at end of file marker — skip
                pass

    if current_hunk:
        hunks.append(current_hunk)

    return hunks


def _apply_hunk(hunk: dict, lines: list[str]) -> ParseResult:
    """Apply a single hunk to the lines array. Modifies lines in place.

    Validates that context lines and removed lines match the original
    content before applying changes.
    """
    total_lines = len(lines)
    old_start = hunk["old_start"] - 1  # Convert to 0-indexed

    context_before = hunk["context_before"]
    removed = hunk["removed"]
    added = hunk["added"]
    context_after = hunk["context_after"]

    # Verify context before
    for i, ctx_line in enumerate(context_before):
        idx = old_start + i
        if idx >= total_lines or lines[idx].rstrip("\n") != ctx_line.rstrip("\n"):
            return ParseResult(success=False, error="Context mismatch before changes")

    # Verify removed lines
    removed_start = old_start + len(context_before)
    for i, rem_line in enumerate(removed):
        idx = removed_start + i
        if idx >= total_lines or lines[idx].rstrip("\n") != rem_line.rstrip("\n"):
            return ParseResult(success=False, error="Removed lines don't match content")

    # Verify context after
    after_start = removed_start + len(removed)
    for i, ctx_line in enumerate(context_after):
        idx = after_start + i
        if idx >= total_lines or lines[idx].rstrip("\n") != ctx_line.rstrip("\n"):
            return ParseResult(success=False, error="Context mismatch after changes")

    # Track the edit
    edit = {
        "start_line": removed_start,
        "end_line": removed_start + len(removed),
        "old_text": "".join(removed),
        "new_text": "".join(added),
    }

    # Apply the change in-place: replace removed lines with added lines
    added_with_newlines = [a + ("\n" if not a.endswith("\n") else "") for a in added]
    lines[removed_start:removed_start + len(removed)] = added_with_newlines

    # Calculate confidence based on context match ratio
    total_context = len(context_before) + len(context_after)
    confidence = min(1.0, total_context / max(1, total_context + len(removed)))

    return ParseResult(
        success=True,
        edits=[edit],
        confidence=confidence,
        parsed_hunks=1,
        matched_hunks=1,
        applied_text="".join(lines),
    )
