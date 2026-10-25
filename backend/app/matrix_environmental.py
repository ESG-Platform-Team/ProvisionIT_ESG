"""
Environmental pillar, draft matrix.

Anchored to AASB S2 Climate-related Disclosures for the climate themes, because
it is the Australian standard listed entities now report against and it is free
and public, which is the same reasoning that anchored governance to the ASX CGC
Principles. The resource and nature theme draws on the GRI 300 series topics.

Status: DRAFT for Chen Yu's review. Criteria wording, keywords and grouping are a
first pass written to exercise the pipeline, not a finished matrix. The version
string says so, and every result carries it.

Same shape as matrix.py on purpose. The scoring engine does not know which
pillar it is scoring, which is the payoff of modelling the framework as data.
"""

PILLAR = "ENVIRONMENTAL"
LABEL = "Environmental"
MATRIX_VERSION = "E-draft v0.1"
FRAMEWORK_EDITION = "AASB S2 climate, GRI 300 series"
FRAMEWORK_NAME = "AASB S2 Climate-related Disclosures and GRI environmental topics"
UNIT_NAME = "Theme"

PRINCIPLES = [
    {
        "number": 1,
        "title": "Climate governance",
        "evidenceHint": "climate statement, sustainability report, governance statement, board charter",
        "criteria": [
            {
                "criterionCode": "E1.1",
                "recommendationCode": "AASB S2 Governance",
                "question": "The body responsible for oversight of climate-related risks and opportunities is identified, with how and how often it is informed.",
                "weight": 1.0,
                "keywords": ["climate-related risk", "oversight of climate", "sustainability committee", "board oversight"],
            },
            {
                "criterionCode": "E1.2",
                "recommendationCode": "AASB S2 Governance",
                "question": "Management's role in assessing and managing climate-related risks and opportunities is described, including the controls and procedures used.",
                "weight": 1.0,
                "keywords": ["management's role", "climate-related", "executive responsible", "climate working group"],
            },
        ],
    },
    {
        "number": 2,
        "title": "Climate strategy and resilience",
        "evidenceHint": "climate statement, sustainability report, annual report",
        "criteria": [
            {
                "criterionCode": "E2.1",
                "recommendationCode": "AASB S2 Strategy",
                "question": "Climate-related risks and opportunities are identified, distinguishing physical from transition risks, with the time horizons over which each could arise.",
                "weight": 1.0,
                "keywords": ["physical risk", "transition risk", "time horizon", "climate-related opportunit"],
            },
            {
                "criterionCode": "E2.2",
                "recommendationCode": "AASB S2 Strategy",
                "question": "Climate scenario analysis is disclosed, including a scenario consistent with limiting warming to 1.5°C, with its implications for the business.",
                "weight": 1.0,
                "keywords": ["scenario analysis", "1.5", "climate resilience", "scenario"],
            },
            {
                "criterionCode": "E2.3",
                "recommendationCode": "AASB S2 Strategy",
                "question": "A climate transition plan is disclosed, with the actions, dependencies and resourcing it relies on.",
                "weight": 1.0,
                "keywords": ["transition plan", "net zero", "decarbonisation", "decarbonization"],
            },
        ],
    },
    {
        "number": 3,
        "title": "Climate risk management",
        "evidenceHint": "climate statement, risk management policy, governance statement",
        "criteria": [
            {
                "criterionCode": "E3.1",
                "recommendationCode": "AASB S2 Risk management",
                "question": "The process for identifying, assessing, prioritising and monitoring climate-related risks is described, with how it is integrated into overall risk management.",
                "weight": 1.0,
                "keywords": ["climate risk", "risk management framework", "risk register", "integrated into"],
            },
        ],
    },
    {
        "number": 4,
        "title": "Emissions metrics and targets",
        "evidenceHint": "climate statement, sustainability report, NGER data, annual report",
        "criteria": [
            {
                "criterionCode": "E4.1",
                "recommendationCode": "AASB S2 Metrics",
                "question": "Scope 1 and Scope 2 greenhouse gas emissions are reported for the period, with the methodology used.",
                "weight": 1.0,
                "keywords": ["scope 1", "scope 2", "greenhouse gas", "tco2"],
            },
            {
                "criterionCode": "E4.2",
                "recommendationCode": "AASB S2 Metrics",
                "question": "Scope 3 emissions are reported, or their omission is explained.",
                "weight": 1.0,
                "keywords": ["scope 3", "value chain emissions"],
            },
            {
                "criterionCode": "E4.3",
                "recommendationCode": "AASB S2 Targets",
                "question": "An emissions reduction target is stated with a base year, a target year and the scopes it covers.",
                "weight": 1.0,
                "keywords": ["emissions reduction target", "base year", "net zero by", "reduction target"],
            },
            {
                "criterionCode": "E4.4",
                "recommendationCode": "AASB S2 Targets",
                "question": "Progress against emissions targets is reported for the period.",
                "weight": 1.0,
                "keywords": ["progress against", "reduction achieved", "compared to the base year", "on track"],
            },
            {
                "criterionCode": "E4.5",
                "recommendationCode": "AASB S2 Assurance",
                "question": "Reported emissions are subject to independent assurance, with the level of assurance stated.",
                "weight": 1.0,
                "keywords": ["limited assurance", "reasonable assurance", "independent assurance", "assurance statement"],
            },
        ],
    },
    {
        "number": 5,
        "title": "Resources, nature and compliance",
        "evidenceHint": "sustainability report, environmental policy, annual report",
        "criteria": [
            {
                "criterionCode": "E5.1",
                "recommendationCode": "GRI 302",
                "question": "Energy consumption is reported, with the share drawn from renewable sources.",
                "weight": 1.0,
                "keywords": ["energy consumption", "renewable electricity", "renewable energy", "mwh"],
            },
            {
                "criterionCode": "E5.2",
                "recommendationCode": "GRI 303",
                "question": "Water withdrawal or consumption is reported, with how water-related impacts are managed.",
                "weight": 1.0,
                "keywords": ["water withdrawal", "water consumption", "water use", "water stewardship"],
            },
            {
                "criterionCode": "E5.3",
                "recommendationCode": "GRI 306",
                "question": "Waste generated is reported, with diversion from landfill or circularity initiatives.",
                "weight": 1.0,
                "keywords": ["waste", "landfill", "recycl", "circular"],
            },
            {
                "criterionCode": "E5.4",
                "recommendationCode": "GRI 304",
                "question": "Impacts on biodiversity and land are identified, with how they are managed.",
                "weight": 1.0,
                "keywords": ["biodiversity", "rehabilitation", "nature-related", "tnfd"],
            },
            {
                "criterionCode": "E5.5",
                "recommendationCode": "GRI 2-27",
                "question": "Significant environmental incidents, breaches or penalties in the period are disclosed, or their absence is stated.",
                "weight": 1.0,
                "keywords": ["environmental incident", "environmental breach", "penalty", "infringement"],
            },
        ],
    },
]
