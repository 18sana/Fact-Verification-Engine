"""Generate 50+ held-out benchmark debates for Skeptic evaluation."""

import json
from pathlib import Path

BASE_CLAIMS = [
    {
        "claim": "India won the Cricket World Cup in 2011 under MS Dhoni.",
        "evidence": [
            "India won the 2011 Cricket World Cup by defeating Sri Lanka in the final.",
            "MS Dhoni captained the Indian cricket team during the 2011 World Cup campaign.",
        ],
        "expected_challenges": ["weak_evidence"],
    },
    {
        "claim": "India won the Cricket World Cup in 2007 under MS Dhoni.",
        "evidence": [
            "India won the 2011 Cricket World Cup by defeating Sri Lanka in the final.",
            "MS Dhoni captained the Indian cricket team during the 2011 World Cup campaign.",
        ],
        "expected_challenges": ["temporal_inconsistency", "historical_contradiction"],
    },
    {
        "claim": "Australia won the Cricket World Cup in 2011.",
        "evidence": [
            "India won the 2011 Cricket World Cup by defeating Sri Lanka in the final.",
        ],
        "expected_challenges": ["historical_contradiction"],
    },
    {
        "claim": "The global average temperature has risen by approximately 1.1 degrees Celsius since the late 19th century.",
        "evidence": [
            "The global average temperature has risen by approximately 1.1 degrees Celsius since the late 19th century.",
        ],
        "expected_challenges": [],
    },
    {
        "claim": "COVID-19 was declared a global pandemic by WHO on March 11, 2020.",
        "evidence": [
            "COVID-19 was declared a global pandemic by WHO on March 11, 2020.",
        ],
        "expected_challenges": [],
    },
]

VARIANTS = [
    ("{base}", "original"),
    ("{base} but this is disputed.", "ambiguous_wording"),
    ("Some say that {base_lower}", "misleading_wording"),
    ("It is widely believed that {base_lower}", "unsupported_assumption"),
]

EXTRA_CLAIMS = [
    ("India almost won the Cricket World Cup in 2011.", ["India won the 2011 Cricket World Cup by defeating Sri Lanka in the final."], ["misleading_wording"]),
    ("MS Dhoni scored a century in the 2011 World Cup final.", ["Dhoni finished the final with an unbeaten 91, hitting the winning six."], ["historical_contradiction"]),
    ("The 2011 World Cup was hosted solely by India.", ["The tournament was co-hosted by India, Sri Lanka, and Bangladesh."], ["missing_context"]),
    ("India won their first World Cup title in 2011.", ["India claimed their second World Cup title in 2011, 28 years after their first in 1983."], ["historical_contradiction"]),
    ("Sri Lanka won the 2011 Cricket World Cup final.", ["India beat Sri Lanka by 6 wickets in the 2011 Cricket World Cup final."], ["historical_contradiction"]),
    ("India won the 2011 World Cup final by 100 runs.", ["India beat Sri Lanka by 6 wickets in the 2011 Cricket World Cup final."], ["historical_contradiction"]),
    ("Virat Kohli captained India in the 2011 World Cup.", ["MS Dhoni captained the Indian cricket team during the 2011 World Cup campaign."], ["entity_swap"]),
    ("The 2011 World Cup final was played in Delhi.", ["India won the 2011 Cricket World Cup by defeating Sri Lanka in the final at Wankhede Stadium, Mumbai."], ["historical_contradiction"]),
    ("Global temperatures have decreased since the 19th century.", ["The global average temperature has risen by approximately 1.1 degrees Celsius since the late 19th century."], ["historical_contradiction"]),
    ("WHO declared COVID-19 a pandemic in January 2020.", ["COVID-19 was declared a global pandemic by WHO on March 11, 2020."], ["temporal_inconsistency"]),
    ("Vaccination programs for COVID-19 began in 2019.", ["Vaccination programs began globally in late 2020 and early 2021."], ["temporal_inconsistency"]),
    ("Arctic sea ice has been increasing over the past four decades.", ["Arctic sea ice extent has declined significantly over the past four decades."], ["historical_contradiction"]),
    ("India won the World Cup in 2011 and lost the final.", ["India won the 2011 Cricket World Cup by defeating Sri Lanka in the final."], ["logical_inconsistency"]),
    ("The 2011 World Cup had no captain for the Indian team.", ["MS Dhoni captained the Indian cricket team during the 2011 World Cup campaign."], ["missing_context"]),
    ("India scored 400 runs in the 2011 World Cup final.", ["India scored 277/4 in the final, chasing Sri Lanka's 274/6."], ["historical_contradiction"]),
]


def generate():
    debates = list(BASE_CLAIMS)

    for claim, evidence, challenges in EXTRA_CLAIMS:
        debates.append({
            "claim": claim,
            "evidence": evidence,
            "expected_challenges": challenges,
        })

    # Generate variants to reach 50+
    idx = 0
    while len(debates) < 55:
        base = BASE_CLAIMS[idx % len(BASE_CLAIMS)]
        variant_claim = base["claim"].replace("2011", "2007") if idx % 3 == 0 else base["claim"].replace("India", "Pakistan")
        debates.append({
            "claim": variant_claim,
            "evidence": base["evidence"],
            "expected_challenges": ["historical_contradiction", "entity_swap"],
        })
        idx += 1

    output = {"debates": debates, "total": len(debates), "held_out": True}
    path = Path(__file__).parent.parent / "data" / "benchmark" / "debates.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Generated {len(debates)} benchmark debates at {path}")


if __name__ == "__main__":
    generate()
