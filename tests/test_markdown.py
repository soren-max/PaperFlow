from paperflow.markdown import choose_citekey, render_note


def test_fallback_citekey_is_stable_and_readable():
    item = {
        "zotero_key": "XYZ12345",
        "citekey": None,
        "authors": ["Ada Lovelace"],
        "date": "1843-01-01",
        "title": "Notes on the Analytical Engine",
    }
    assert choose_citekey(item) == "lovelace1843notes"


def test_markdown_is_obsidian_friendly():
    item = {
        "zotero_key": "XYZ12345",
        "title": "论文标题",
        "authors": ["作者甲"],
        "date": "2025",
        "venue": "期刊",
        "doi": "",
        "url": "",
        "abstract": "摘要。",
        "tags": ["中文"],
        "annotations": [],
    }
    text = render_note(item, "paper2025")
    assert text.startswith("---\n")
    assert "# 论文标题" in text
    assert "## My Notes" in text
    assert "authors:\n- 作者甲" in text
