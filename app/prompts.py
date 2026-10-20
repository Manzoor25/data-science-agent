"""The five version-1 analysis chips. A click fills the box. It does not send."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GuidedPrompt:
    label: str
    prompt: str

    def as_dict(self) -> dict[str, str | bool]:
        return {"label": self.label, "prompt": self.prompt, "sends": False}


PROFILE = (
    "Using only deviceinfo_org_ago24h, profile the current device population. "
    "KPI cards: total devices, distinct MachineGroup or ECH, high-exposure devices, and not-onboarded devices. "
    "Bar charts: count by ExposureLevel, by OnboardingStatus, and by OSPlatform. "
    "Use MachineGroup or ECH, whichever column exists. Do not use SiteCode. Do not list individual devices."
)
COMPARE = (
    "Using only deviceinfo_org_ago24h, compare machine group or ECH [GROUP A] with [GROUP B]. "
    "KPI cards: device count and high-exposure count for each group. "
    "Bar charts: operating-system mix for each group. "
    "Use whichever of MachineGroup or ECH exists. Do not use SiteCode. If either value is missing, say so."
)
TREND = (
    "Using only DeviceInfo_DailySummary, show onboarded device counts by ReportDate and which MachineGroup "
    "changed the most between the latest two report dates. KPI cards: latest count, previous count, change, "
    "and the group that changed most. One bar chart of device count by ReportDate. Do not use SiteCode."
)
CHANGE = (
    "Using only DeviceInfo_DailySummary, compare the latest ReportDate with the previous ReportDate. "
    "Explain which MachineGroup or device category drove the change. KPI cards: latest total, previous total, "
    "difference, and the group with the largest change. Bar chart: change by MachineGroup. "
    "Do not use SiteCode. Do not invent a cause."
)
OVERLAP = (
    "Using only deviceinfo_org_ago24h and v_SoftwareVulnerabilities_Daily, find high-exposure devices that also "
    "have a critical vulnerability with an exploit available. Match on DeviceId. KPI cards: high-exposure devices, "
    "devices with an exploitable critical finding, devices in both, and distinct MachineGroup or ECH values. "
    "Bar chart: overlap count by MachineGroup or ECH. Do not use SiteCode. Do not list every device."
)

PROMPTS = (
    GuidedPrompt("Profile the fleet", PROFILE),
    GuidedPrompt("Compare two groups", COMPARE),
    GuidedPrompt("Show the trend", TREND),
    GuidedPrompt("Explain a change", CHANGE),
    GuidedPrompt("Risky overlap", OVERLAP),
)
