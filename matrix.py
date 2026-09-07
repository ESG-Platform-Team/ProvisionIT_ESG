"""
ASX Corporate Governance Council, 4th edition.
Framework as versioned data, not constants in code. Loaded into the database on
first run so a result can always say which matrix version produced it.

This is the seam with cy0701's ranking matrix. If the matrix shape changes,
this file changes and nothing else does.
"""

MATRIX_VERSION = "G-4thEd v1.0"
FRAMEWORK_EDITION = "ASX CGC 4th edition"

# Uniform 0..4 maturity across every criterion. If cy0701's matrix introduces
# per-criterion scales, add a "scale" key here and normalise in scoring.py.
MATURITY_LABELS = ["NONE", "STATED", "IMPLEMENTED", "MONITORED", "EMBEDDED"]

PRINCIPLES = [
    {
        "number": 1,
        "title": "Lay solid foundations for management and oversight",
        "evidenceHint": "governance statement, board charter, notice of meeting, annual report",
        "criteria": [
            {
                "criterionCode": "G1.1",
                "recommendationCode": "1.1",
                "question": "The board charter sets out the respective roles and responsibilities of the board, the chair and management, and is publicly available.",
                "weight": 1.0,
                "keywords": ["board charter", "roles and responsibilities", "respective roles"],
            },
            {
                "criterionCode": "G1.2",
                "recommendationCode": "1.2",
                "question": "Appropriate checks are undertaken before appointing a director, and material information relevant to a decision on election is provided to security holders.",
                "weight": 1.0,
                "keywords": ["appropriate checks", "before appointing", "election of directors"],
            },
            {
                "criterionCode": "G1.5",
                "recommendationCode": "1.5",
                "question": "A measurable objective for gender diversity is stated, with progress against it reported for the period.",
                "weight": 1.0,
                "keywords": ["gender diversity", "measurable objective", "diversity policy"],
            },
            {
                "criterionCode": "G1.7",
                "recommendationCode": "1.7",
                "question": "A process for periodically evaluating the performance of senior executives is disclosed.",
                "weight": 1.0,
                "keywords": ["performance evaluation", "senior executives", "evaluating the performance"],
            },
            {
                "criterionCode": "G1.3",
                "recommendationCode": "1.3",
                "question": "A written agreement setting out the terms of appointment is in place with each director and senior executive.",
                "weight": 1.0,
                "keywords": ["written agreement", "terms of appointment", "letter of appointment"],
            },
        ],
    },
    {
        "number": 2,
        "title": "Structure the board to be effective and add value",
        "evidenceHint": "governance statement, committee charters, annual report",
        "criteria": [
            {
                "criterionCode": "G2.1",
                "recommendationCode": "2.1",
                "question": "A nomination committee exists with a majority of independent directors and a disclosed charter.",
                "weight": 1.0,
                "keywords": ["nomination committee"],
            },
            {
                "criterionCode": "G2.3",
                "recommendationCode": "2.3",
                "question": "The names of directors considered independent are disclosed, with the length of service of each.",
                "weight": 1.0,
                "keywords": ["independent", "length of service", "tenure"],
            },
            {
                "criterionCode": "G2.4",
                "recommendationCode": "2.4",
                "question": "A majority of the board is independent, with independence assessed annually against stated criteria.",
                "weight": 1.0,
                "keywords": ["majority", "independent director", "independence assessed"],
            },
            {
                "criterionCode": "G2.5",
                "recommendationCode": "2.5",
                "question": "The chair is an independent director and is not the chief executive officer.",
                "weight": 1.0,
                "keywords": ["chair", "chief executive officer", "separate"],
            },
            {
                "criterionCode": "G2.6",
                "recommendationCode": "2.6",
                "question": "An induction programme and ongoing professional development for directors are described.",
                "weight": 1.0,
                "keywords": ["induction", "professional development"],
            },
        ],
    },
    {
        "number": 3,
        "title": "Instil a culture of acting lawfully, ethically and responsibly",
        "evidenceHint": "code of conduct, whistleblower policy, governance statement",
        "criteria": [
            {
                "criterionCode": "G3.1",
                "recommendationCode": "3.1",
                "question": "A statement of values is articulated and disclosed.",
                "weight": 1.0,
                "keywords": ["values", "statement of values"],
            },
            {
                "criterionCode": "G3.2",
                "recommendationCode": "3.2",
                "question": "A code of conduct for directors, senior executives and employees is disclosed, and the board is informed of material breaches.",
                "weight": 1.0,
                "keywords": ["code of conduct", "material breaches"],
            },
            {
                "criterionCode": "G3.3",
                "recommendationCode": "3.3",
                "question": "A whistleblower policy is disclosed and material incidents are reported to the board.",
                "weight": 1.0,
                "keywords": ["whistleblower", "whistleblowing"],
            },
            {
                "criterionCode": "G3.4",
                "recommendationCode": "3.4",
                "question": "An anti-bribery and corruption policy is disclosed.",
                "weight": 1.0,
                "keywords": ["anti-bribery", "corruption"],
            },
        ],
    },
    {
        "number": 4,
        "title": "Safeguard the integrity of corporate reports",
        "evidenceHint": "audit committee charter, annual report, governance statement",
        "criteria": [
            {
                "criterionCode": "G4.1",
                "recommendationCode": "4.1",
                "question": "An audit committee of at least three members, all non-executive and a majority independent, chaired by an independent director who is not the board chair.",
                "weight": 1.0,
                "keywords": ["audit committee", "non-executive", "independent"],
            },
            {
                "criterionCode": "G4.2",
                "recommendationCode": "4.2",
                "question": "Before approving financial statements, the board receives declarations from the chief executive and chief financial officer that the records are properly maintained.",
                "weight": 1.0,
                "keywords": ["declaration", "chief financial officer", "properly maintained"],
            },
            {
                "criterionCode": "G4.3",
                "recommendationCode": "4.3",
                "question": "The process followed to verify the integrity of periodic reports that are not audited or reviewed is disclosed.",
                "weight": 1.0,
                "keywords": ["integrity", "periodic report", "not audited"],
            },
            {
                "criterionCode": "G4.4",
                "recommendationCode": "4.4",
                "question": "The external auditor attends the annual meeting and is available to answer questions about the audit.",
                "weight": 1.0,
                "keywords": ["external auditor", "annual general meeting", "attend"],
            },
        ],
    },
    {
        "number": 5,
        "title": "Make timely and balanced disclosure",
        "evidenceHint": "continuous disclosure policy, governance statement",
        "criteria": [
            {
                "criterionCode": "G5.1",
                "recommendationCode": "5.1",
                "question": "A written policy for complying with continuous disclosure obligations is disclosed.",
                "weight": 1.0,
                "keywords": ["continuous disclosure", "disclosure policy"],
            },
            {
                "criterionCode": "G5.2",
                "recommendationCode": "5.2",
                "question": "The board receives copies of all material market announcements promptly after release.",
                "weight": 1.0,
                "keywords": ["market announcement", "board receives copies"],
            },
            {
                "criterionCode": "G5.3",
                "recommendationCode": "5.3",
                "question": "New and substantive investor or analyst presentations are released ahead of the presentation.",
                "weight": 1.0,
                "keywords": ["investor presentation", "analyst presentation"],
            },
        ],
    },
    {
        "number": 6,
        "title": "Respect the rights of security holders",
        "evidenceHint": "investor relations pages, notice of meeting, AGM results, annual report",
        "criteria": [
            {
                "criterionCode": "G6.1",
                "recommendationCode": "6.1",
                "question": "Information about the entity and its governance is available on the website.",
                "weight": 1.0,
                "keywords": ["website", "governance information", "investor centre"],
            },
            {
                "criterionCode": "G6.2",
                "recommendationCode": "6.2",
                "question": "An investor relations programme facilitating two-way communication with security holders is disclosed.",
                "weight": 1.0,
                "keywords": ["investor relations", "two-way communication"],
            },
            {
                "criterionCode": "G6.3",
                "recommendationCode": "6.3",
                "question": "Security holders are given the option to receive communications from, and send communications to, the entity electronically.",
                "weight": 1.0,
                "keywords": ["electronically", "electronic communication"],
            },
            {
                "criterionCode": "G6.4",
                "recommendationCode": "6.4",
                "question": "All substantive resolutions at security holder meetings are decided by a poll rather than a show of hands.",
                "weight": 1.0,
                "keywords": ["poll", "show of hands"],
            },
        ],
    },
    {
        "number": 7,
        "title": "Recognise and manage risk",
        "evidenceHint": "risk committee charter, governance statement, sustainability report",
        "criteria": [
            {
                "criterionCode": "G7.1",
                "recommendationCode": "7.1",
                "question": "A risk committee of at least three members, a majority independent and chaired by an independent director, with a disclosed charter.",
                "weight": 1.0,
                "keywords": ["risk committee", "risk management committee"],
            },
            {
                "criterionCode": "G7.2",
                "recommendationCode": "7.2",
                "question": "The risk management framework is reviewed at least annually, and that review is disclosed as having occurred.",
                "weight": 1.0,
                "keywords": ["risk management framework", "reviewed annually"],
            },
            {
                "criterionCode": "G7.3",
                "recommendationCode": "7.3",
                "question": "An internal audit function is disclosed, with how it is structured and what role it performs.",
                "weight": 1.0,
                "keywords": ["internal audit"],
            },
            {
                "criterionCode": "G7.4",
                "recommendationCode": "7.4",
                "question": "Material exposure to environmental and social risks is disclosed, with how those risks are managed.",
                "weight": 1.0,
                "keywords": ["environmental and social risk", "climate", "material exposure"],
            },
        ],
    },
    {
        "number": 8,
        "title": "Remunerate fairly and responsibly",
        "evidenceHint": "remuneration report, remuneration committee charter, annual report",
        "criteria": [
            {
                "criterionCode": "G8.1",
                "recommendationCode": "8.1",
                "question": "A remuneration committee of at least three members, a majority independent and chaired by an independent director.",
                "weight": 1.0,
                "keywords": ["remuneration committee"],
            },
            {
                "criterionCode": "G8.2",
                "recommendationCode": "8.2",
                "question": "Policies for the remuneration of non-executive directors and of executive directors are separately disclosed.",
                "weight": 1.0,
                "keywords": ["remuneration policy", "non-executive director remuneration"],
            },
        ],
    },
]


def all_criteria():
    for pr in PRINCIPLES:
        for c in pr["criteria"]:
            yield pr, c


def criterion(code):
    for _, c in all_criteria():
        if c["criterionCode"] == code:
            return c
    return None


CRITERION_COUNT = sum(len(pr["criteria"]) for pr in PRINCIPLES)
