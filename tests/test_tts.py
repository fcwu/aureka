"""Unit tests for TTS Markdown preprocessing."""
import pytest

pytestmark = pytest.mark.unit


def test_strip_frontmatter():
    from aureka.tts import strip_markdown
    text = "---\ntitle: Test\ndate: 2026-05-01\n---\n\nHello world."
    assert strip_markdown(text) == "Hello world."


def test_strip_headings():
    from aureka.tts import strip_markdown
    assert strip_markdown("# Title\n## Sub\nContent") == "Title\nSub\nContent"


def test_strip_bold_italic():
    from aureka.tts import strip_markdown
    assert strip_markdown("**bold** and *italic*") == "bold and italic"


def test_strip_inline_code():
    from aureka.tts import strip_markdown
    result = strip_markdown("Use `foo()` to do it")
    assert "`" not in result
    assert "foo" not in result


def test_strip_links():
    from aureka.tts import strip_markdown
    result = strip_markdown("[Click here](https://example.com)")
    assert "Click here" in result
    assert "https://" not in result


def test_strip_images():
    from aureka.tts import strip_markdown
    result = strip_markdown("![alt text](image.jpg)")
    assert "alt text" not in result
    assert "image.jpg" not in result


def test_empty_input():
    from aureka.tts import strip_markdown
    assert strip_markdown("") == ""


def test_no_markdown():
    from aureka.tts import strip_markdown
    text = "This is plain text with no markup."
    assert strip_markdown(text) == text


def test_complex_document():
    from aureka.tts import strip_markdown
    doc = """---
source: video
processed_at: 2026-05-01
---

# Meeting Notes

## Summary

This is the **main summary** with some `code` and a [link](http://example.com).

- Point one
- Point two
"""
    result = strip_markdown(doc)
    assert "Meeting Notes" in result
    assert "This is the main summary" in result
    assert "**" not in result
    assert "---" not in result
    assert "source: video" not in result
