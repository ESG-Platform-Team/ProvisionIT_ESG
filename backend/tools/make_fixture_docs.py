#!/usr/bin/env python3
"""
Generate the environmental and social documents for the offline fixture site.

The content is written to exercise each outcome the scoring engine distinguishes:
disclosed practices at several maturity levels, an explained omission (Scope 3),
topics the company is silent on (biodiversity, transition plan), and a linked
document that does not exist (the reconciliation action plan returns 404).

    python tools/make_fixture_docs.py
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

OUT = Path(__file__).resolve().parent.parent / "fixture-site" / "docs"

CLIMATE = [
    ("Climate Statement 2026", [
        "Fixture Test Group. Climate-related financial disclosure prepared under "
        "AASB S2 Climate-related Disclosures for the year ended 30 June 2026.",
        "Governance. The Board Sustainability Committee is responsible for oversight of "
        "climate-related risks and opportunities. The committee receives a written report "
        "from management each quarter and reviews climate targets annually.",
        "Management's role. The Chief Sustainability Officer is the executive responsible "
        "for assessing and managing climate-related risks and chairs a climate working group "
        "that meets monthly. Climate controls are tested by internal audit each year.",
    ]),
    ("Strategy and scenario analysis", [
        "We identify physical risk, including flooding at two distribution sites, and "
        "transition risk, including carbon pricing and changing customer demand. Each is "
        "assessed over short (to 2028), medium (to 2035) and long (to 2050) time horizons.",
        "Scenario analysis. We tested the resilience of our strategy against a 1.5°C scenario "
        "and a 2.7°C scenario. Under the 1.5°C scenario, carbon costs rise materially after "
        "2030; under the 2.7°C scenario, physical damage to sites becomes the larger exposure.",
    ]),
    ("Risk management, metrics and targets", [
        "Climate risk is recorded in the enterprise risk register and assessed with the same "
        "likelihood and consequence scales as other risks, so it is integrated into the risk "
        "management framework rather than managed separately.",
        "Scope 1 emissions were 12,400 tCO2-e and Scope 2 emissions were 8,900 tCO2-e, "
        "calculated using the National Greenhouse and Energy Reporting methodology.",
        "We have not reported Scope 3 emissions this year because supplier data covers less "
        "than a third of spend. We expect to report Scope 3 from FY2028.",
        "Our emissions reduction target is a 42% reduction in Scope 1 and Scope 2 emissions by "
        "2030 from a FY2022 base year. Progress against target: emissions are down 18% compared "
        "to the base year.",
        "Scope 1 and Scope 2 emissions are subject to limited assurance by an independent "
        "assurance provider. The assurance statement is published with this report.",
    ]),
]

SUSTAINABILITY = [
    ("Sustainability Report 2026", [
        "Environment. Energy consumption was 61,200 MWh, with 38% supplied by renewable "
        "electricity under power purchase agreements.",
        "Water withdrawal was 410 megalitres. Water use is metered at every site and reported "
        "to the Sustainability Committee each quarter.",
        "We generated 2,300 tonnes of waste and diverted 71% from landfill through recycling "
        "and a packaging return programme.",
        "No significant environmental incidents, breaches or penalties were recorded in FY2026.",
    ]),
    ("People and safety", [
        "Our total recordable injury frequency rate (TRIFR) was 3.1 and our lost time injury "
        "frequency rate (LTIFR) was 0.8. There were no fatalities.",
        "Our safety management system is certified to ISO 45001. Psychosocial hazards are "
        "identified through an annual survey and managed under the same controls framework.",
        "Employees completed an average of 22 training hours, and we invested $2.1 million in "
        "learning and development.",
        "Women hold 38% of senior leadership roles. Our target is gender balance of 40:40:20 in "
        "senior leadership by 2028.",
        "Our gender pay gap was 11.2%, as reported to the Workplace Gender Equality Agency.",
    ]),
    ("Communities, customers and cyber security", [
        "Community investment totalled $1.4 million across 36 community partnership programmes.",
        "Customer complaints are logged, acknowledged within two business days and reported to "
        "the board monthly, with product safety recalls managed by a dedicated team.",
        "Cyber security. The Risk Committee oversees cyber security. Controls are aligned to the "
        "Essential Eight, and the incident response plan is tested annually.",
        "No notifiable data breach occurred during the year.",
    ]),
]

MODERN_SLAVERY = [
    ("Modern Slavery Statement 2026", [
        "This modern slavery statement is made under the Modern Slavery Act 2018 (Cth) and "
        "addresses each mandatory reporting criterion for the reporting entity.",
        "Our supplier code of conduct prohibits forced labour. Due diligence includes a risk "
        "screen of every new supplier and an on-site supplier assessment for high-risk categories.",
        "Our human rights policy applies across our operations and supply chain. Workers can raise "
        "concerns through an independent grievance mechanism, and remediation is overseen by the "
        "Chief Risk Officer.",
    ]),
]


def build(filename: str, sections) -> None:
    styles = getSampleStyleSheet()
    story = []
    for i, (heading, paras) in enumerate(sections):
        if i:
            story.append(PageBreak())
        story.append(Paragraph(heading, styles["Heading1"]))
        for para in paras:
            story.append(Paragraph(para, styles["BodyText"]))
            story.append(Spacer(1, 8))
    OUT.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(OUT / filename), pagesize=A4).build(story)
    print(f"wrote {OUT / filename}")


if __name__ == "__main__":
    build("climate-statement-2026.pdf", CLIMATE)
    build("sustainability-report-2026.pdf", SUSTAINABILITY)
    build("modern-slavery-statement-2026.pdf", MODERN_SLAVERY)
