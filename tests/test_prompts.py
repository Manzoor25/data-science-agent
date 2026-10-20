from app.prompts import PROMPTS


def test_version_one_has_five_analysis_chips() -> None:
    assert [item.label for item in PROMPTS] == [
        "Profile the fleet",
        "Compare two groups",
        "Show the trend",
        "Explain a change",
        "Risky overlap",
    ]
    assert all(item.as_dict()["sends"] is False for item in PROMPTS)
    assert "[GROUP A]" in PROMPTS[1].prompt
    assert "dim.vwDevices" not in " ".join(item.prompt for item in PROMPTS)
    assert "SiteCode" not in " ".join(item.prompt for item in PROMPTS).replace("Do not use SiteCode.", "")
