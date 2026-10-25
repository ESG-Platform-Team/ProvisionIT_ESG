"""
Social pillar, draft matrix.

Anchored to Australian disclosure regimes that are free and public, then to the
GRI 400 series topics. Two of the anchors are legislated and therefore strong
signals: modern slavery statements under the Modern Slavery Act 2018 (Cth), and
gender reporting to the Workplace Gender Equality Agency. The privacy and cyber
theme covers the security question raised in the client meeting.

Status: DRAFT for Chen Yu's review, exactly as matrix_environmental.py.
"""

PILLAR = "SOCIAL"
LABEL = "Social"
MATRIX_VERSION = "S-draft v0.1"
FRAMEWORK_EDITION = "Modern Slavery Act, WGEA, GRI 400 series"
FRAMEWORK_NAME = "Australian social disclosure regimes and GRI social topics"
UNIT_NAME = "Theme"

PRINCIPLES = [
    {
        "number": 1,
        "title": "Workforce, health and safety",
        "evidenceHint": "sustainability report, annual report, health and safety policy",
        "criteria": [
            {
                "criterionCode": "S1.1",
                "recommendationCode": "GRI 403",
                "question": "Workplace health and safety performance is reported with lagging measures such as TRIFR or LTIFR, including any fatalities.",
                "weight": 1.0,
                "keywords": ["trifr", "ltifr", "injury frequency", "fatalit"],
            },
            {
                "criterionCode": "S1.2",
                "recommendationCode": "GRI 403",
                "question": "A health and safety management system is described, including how psychosocial hazards are managed.",
                "weight": 1.0,
                "keywords": ["safety management system", "psychosocial", "health and safety policy", "wellbeing"],
            },
            {
                "criterionCode": "S1.3",
                "recommendationCode": "GRI 404",
                "question": "Training and development for the workforce is described, with investment or hours reported.",
                "weight": 1.0,
                "keywords": ["training hours", "learning and development", "professional development", "training"],
            },
        ],
    },
    {
        "number": 2,
        "title": "Diversity, equity and inclusion",
        "evidenceHint": "WGEA report, diversity policy, sustainability report, reconciliation action plan",
        "criteria": [
            {
                "criterionCode": "S2.1",
                "recommendationCode": "GRI 405",
                "question": "Gender composition is reported across the workforce and senior leadership, with measurable targets.",
                "weight": 1.0,
                "keywords": ["women in leadership", "senior leadership", "gender balance", "female representation"],
            },
            {
                "criterionCode": "S2.2",
                "recommendationCode": "WGEA",
                "question": "The gender pay gap is reported, consistent with Workplace Gender Equality Agency reporting.",
                "weight": 1.0,
                "keywords": ["gender pay gap", "pay equity", "wgea", "workplace gender equality"],
            },
            {
                "criterionCode": "S2.3",
                "recommendationCode": "RAP",
                "question": "Engagement with Aboriginal and Torres Strait Islander peoples is described, such as through a Reconciliation Action Plan.",
                "weight": 1.0,
                "keywords": ["reconciliation action plan", "first nations", "aboriginal and torres strait islander", "traditional owners"],
            },
        ],
    },
    {
        "number": 3,
        "title": "Human rights and supply chain",
        "evidenceHint": "modern slavery statement, supplier code of conduct, human rights policy",
        "criteria": [
            {
                "criterionCode": "S3.1",
                "recommendationCode": "Modern Slavery Act 2018",
                "question": "A modern slavery statement is published addressing the mandatory reporting criteria of the Modern Slavery Act 2018 (Cth).",
                "weight": 1.0,
                "keywords": ["modern slavery statement", "modern slavery act", "modern slavery risk"],
            },
            {
                "criterionCode": "S3.2",
                "recommendationCode": "GRI 414",
                "question": "Supply chain due diligence is described, including a supplier code of conduct and how suppliers are assessed.",
                "weight": 1.0,
                "keywords": ["supplier code of conduct", "due diligence", "supplier assessment", "responsible sourcing"],
            },
            {
                "criterionCode": "S3.3",
                "recommendationCode": "UNGP",
                "question": "A human rights policy is disclosed, with a grievance or remediation mechanism.",
                "weight": 1.0,
                "keywords": ["human rights policy", "grievance mechanism", "remediation", "human rights"],
            },
        ],
    },
    {
        "number": 4,
        "title": "Communities and customers",
        "evidenceHint": "sustainability report, annual report, community investment report",
        "criteria": [
            {
                "criterionCode": "S4.1",
                "recommendationCode": "GRI 413",
                "question": "Community investment or engagement is reported, with amounts or programmes identified.",
                "weight": 1.0,
                "keywords": ["community investment", "community partnership", "social investment", "donations"],
            },
            {
                "criterionCode": "S4.2",
                "recommendationCode": "GRI 416",
                "question": "Customer outcomes are addressed, including complaints handling and product safety or responsibility.",
                "weight": 1.0,
                "keywords": ["complaints", "customer outcomes", "product safety", "financial hardship"],
            },
        ],
    },
    {
        "number": 5,
        "title": "Data privacy and cyber security",
        "evidenceHint": "privacy policy, annual report risk section, governance statement",
        "criteria": [
            {
                "criterionCode": "S5.1",
                "recommendationCode": "Privacy Act APP 1",
                "question": "A privacy policy is published, describing how personal information is collected, used and protected.",
                "weight": 1.0,
                "keywords": ["privacy policy", "personal information", "privacy act"],
            },
            {
                "criterionCode": "S5.2",
                "recommendationCode": "GRI 418",
                "question": "Cyber security governance is described, including board oversight, controls and incident response.",
                "weight": 1.0,
                "keywords": ["cyber security", "cybersecurity", "information security", "cyber risk"],
            },
            {
                "criterionCode": "S5.3",
                "recommendationCode": "GRI 418",
                "question": "Material data breaches or cyber incidents in the period are disclosed, or their absence is stated.",
                "weight": 1.0,
                "keywords": ["data breach", "cyber incident", "notifiable data breach", "security incident"],
            },
        ],
    },
]
