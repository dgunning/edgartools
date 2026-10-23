"""edgar_read ``press_release`` returned the attachments table instead of the release.

The 8-K branch returned ``str(obj.press_releases)``, and ``PressReleases.__rich__``
renders the attachment list (Seq, Document, Description), 480 characters for Apple.
The release is ``press_releases[0].text()``.

The section now returns the release text, capped at 6,000 characters like every
other section.

Ground truth: Apple 8-K 0000320193-25-000007 (filed 2025-01-30), Exhibit 99.1
starts "Exhibit 99.1 / Apple reports first quarter results" and says quarterly
revenue was $124.3 billion and diluted earnings per share $2.40.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1774
"""
import pytest

from edgar.ai.mcp.tools import reader
from edgar.ai.mcp.tools.reader import edgar_read
from tests._offline_filings import offline_filing

APPLE_8K = "0000320193-25-000007"


@pytest.mark.vcr
async def test_issue_1774_apple_press_release_text(monkeypatch):
    monkeypatch.setattr(reader, "find", lambda search_id: offline_filing(search_id))
    response = await edgar_read(accession_number=APPLE_8K, sections=["press_release"])
    text = response.data["sections"]["press_release"]

    assert response.success is True
    assert text.startswith("Exhibit 99.1\n\nApple reports first quarter results")
    assert "quarterly revenue of $124.3 billion, up 4 percent year over year" in text
    assert "diluted earnings per share of $2.40" in text
    assert "Seq" not in text.splitlines()[0]
    # 21,737 characters of layout-padded text, capped like every other section
    assert len(text) <= 6000 + len("\n\n... (truncated)")
