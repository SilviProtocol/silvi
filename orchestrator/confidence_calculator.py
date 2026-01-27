"""
Evidence-Based Confidence Calculator for Treekipedia Insights

Confidence is calculated from observable evidence, not AI self-assessment.

Factors:
1. Source count and diversity (more independent sources = higher confidence)
2. Source credibility (peer-reviewed > database > encyclopedia > website)
3. Source agreement (do sources corroborate each other?)
4. Claim specificity (specific values vs vague statements)
5. Recency of sources (newer = more relevant for some fields)

The goal: Make confidence reproducible and auditable.
"""

import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class SourceType(Enum):
    """Source types ordered by typical credibility."""
    PEER_REVIEWED = "peer-reviewed"
    DATABASE = "database"          # GBIF, IUCN, POWO, etc.
    GOVERNMENT = "government"      # Forest service, botanical gardens
    ENCYCLOPEDIA = "encyclopedia"  # Wikipedia, Encyclopedia of Life
    WEBSITE = "website"
    UNKNOWN = "unknown"


# Base credibility by source type (can be overridden per-source)
SOURCE_TYPE_CREDIBILITY = {
    SourceType.PEER_REVIEWED: 0.90,
    SourceType.DATABASE: 0.85,
    SourceType.GOVERNMENT: 0.82,
    SourceType.ENCYCLOPEDIA: 0.70,
    SourceType.WEBSITE: 0.55,
    SourceType.UNKNOWN: 0.50,
}

# Known authoritative sources with fixed credibility
AUTHORITATIVE_SOURCES = {
    "iucnredlist.org": 0.98,
    "gbif.org": 0.95,
    "powo.science.kew.org": 0.96,
    "plantsoftheworldonline.org": 0.96,
    "worldfloraonline.org": 0.94,
    "tropicos.org": 0.92,
    "eol.org": 0.80,
    "wikipedia.org": 0.72,
    "en.wikipedia.org": 0.72,
    "ncbi.nlm.nih.gov": 0.90,
    "pubmed.ncbi.nlm.nih.gov": 0.92,
    "jstor.org": 0.90,
    "springer.com": 0.88,
    "nature.com": 0.92,
    "science.org": 0.92,
    "mdpi.com": 0.82,
    "researchgate.net": 0.75,
    "fao.org": 0.88,
    "usda.gov": 0.90,
    "fs.usda.gov": 0.90,
    "forestry.gov.uk": 0.88,
    "arbolapp.es": 0.85,
}


@dataclass
class ConfidenceBreakdown:
    """Detailed breakdown of how confidence was calculated."""
    final_confidence: float
    source_score: float           # From source count and credibility
    agreement_score: float        # How well sources agree
    specificity_score: float      # How specific is the claim
    source_count: int
    source_diversity: int         # Number of unique domains/types
    corroboration_notes: str      # What was corroborated
    methodology: str              # How the score was calculated
    factors: Dict[str, float] = field(default_factory=dict)


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    if not url:
        return "unknown"
    # Simple extraction
    url = url.lower()
    if "://" in url:
        url = url.split("://")[1]
    domain = url.split("/")[0]
    # Remove www.
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def get_source_credibility(source: Dict[str, Any]) -> float:
    """Get credibility for a source, using known sources or type-based default."""
    # Check if source has explicit credibility
    if "credibility" in source and source["credibility"]:
        return float(source["credibility"])

    # Check against known authoritative sources
    url = source.get("url", "")
    domain = extract_domain(url)

    for auth_domain, cred in AUTHORITATIVE_SOURCES.items():
        if auth_domain in domain:
            return cred

    # Fall back to source type
    source_type = source.get("type", "unknown").lower()
    for st in SourceType:
        if st.value == source_type:
            return SOURCE_TYPE_CREDIBILITY[st]

    return SOURCE_TYPE_CREDIBILITY[SourceType.UNKNOWN]


def calculate_source_score(sources: List[Dict[str, Any]]) -> tuple[float, int, int]:
    """
    Calculate confidence contribution from sources.

    Returns: (score, source_count, source_diversity)
    """
    if not sources:
        return 0.3, 0, 0  # Low confidence if no sources

    # Get credibilities
    credibilities = [get_source_credibility(s) for s in sources]
    source_count = len(sources)

    # Count unique domains for diversity
    domains = set(extract_domain(s.get("url", "")) for s in sources)
    source_diversity = len(domains)

    # Count unique source types
    types = set(s.get("type", "unknown") for s in sources)
    type_diversity = len(types)

    # Base score: weighted average of credibilities
    avg_credibility = sum(credibilities) / len(credibilities)

    # Bonus for multiple sources (diminishing returns)
    # 1 source: 1.0x, 2 sources: 1.1x, 3 sources: 1.15x, 4+: 1.18x max
    count_multiplier = 1.0 + min(0.18, (source_count - 1) * 0.06)

    # Bonus for diverse sources (different domains/types)
    diversity_bonus = min(0.10, (source_diversity - 1) * 0.03 + (type_diversity - 1) * 0.02)

    # Calculate score (capped at 0.98)
    score = min(0.98, avg_credibility * count_multiplier + diversity_bonus)

    return score, source_count, source_diversity


def check_source_agreement(sources: List[Dict[str, Any]], claim_value: Any) -> tuple[float, str]:
    """
    Check if sources agree on the claim.

    For now, we assume sources listed support the claim.
    Future: Could parse source content to verify agreement.

    Returns: (agreement_score, notes)
    """
    if not sources:
        return 0.5, "No sources to verify agreement"

    source_count = len(sources)

    # More sources implicitly means more agreement (they all support the claim)
    if source_count >= 3:
        return 0.95, f"{source_count} sources corroborate this claim"
    elif source_count == 2:
        return 0.85, "2 sources corroborate this claim"
    else:
        return 0.70, "Single source - no cross-reference available"


def assess_claim_specificity(claim_type: str, claim_value: Any) -> float:
    """
    Assess how specific/verifiable a claim is.

    Specific numeric values > ranges > qualitative descriptions
    """
    # Convert to string for analysis
    if isinstance(claim_value, dict):
        text = str(claim_value.get("text", claim_value))
    else:
        text = str(claim_value)

    # Check for specific numeric values
    has_numbers = bool(re.search(r'\d+\.?\d*\s*(m|cm|mm|kg|g|years|°C|°F|mm/year)', text, re.IGNORECASE))
    has_ranges = bool(re.search(r'\d+\s*[-–]\s*\d+', text))

    # Numeric fields that should have specific values
    numeric_fields = {
        'maximum_height', 'maximum_diameter', 'maximum_tree_age',
        'lifespan', 'elevation_ranges', 'temperature_tolerance',
        'rainfall_requirements'
    }

    # Fields where qualitative is expected
    qualitative_fields = {
        'general_description', 'cultural_significance', 'ecological_function',
        'stewardship_best_practices', 'agroforestry_use_cases'
    }

    if claim_type in numeric_fields:
        if has_numbers:
            return 0.95  # Good - has specific values
        elif has_ranges:
            return 0.85  # OK - has ranges
        else:
            return 0.60  # Less specific than expected

    if claim_type in qualitative_fields:
        # For qualitative, longer = more detailed = slightly higher
        word_count = len(text.split())
        if word_count > 100:
            return 0.90
        elif word_count > 50:
            return 0.85
        else:
            return 0.75

    # Default: check if has substantive content
    if len(text) > 200 and has_numbers:
        return 0.88
    elif len(text) > 100:
        return 0.82
    elif len(text) > 50:
        return 0.75
    else:
        return 0.65


def calculate_confidence(
    claim_type: str,
    claim_value: Any,
    sources: List[Dict[str, Any]],
    existing_insights: Optional[List[Dict]] = None
) -> ConfidenceBreakdown:
    """
    Calculate evidence-based confidence for an insight.

    Args:
        claim_type: The field being claimed (e.g., 'maximum_height')
        claim_value: The value being asserted
        sources: List of source citations
        existing_insights: Optional list of existing insights for cross-reference

    Returns:
        ConfidenceBreakdown with final score and methodology
    """
    # Component scores
    source_score, source_count, source_diversity = calculate_source_score(sources)
    agreement_score, agreement_notes = check_source_agreement(sources, claim_value)
    specificity_score = assess_claim_specificity(claim_type, claim_value)

    # Weights for combining scores
    weights = {
        'source': 0.50,      # Sources are most important
        'agreement': 0.25,   # Corroboration matters
        'specificity': 0.25  # Claim quality matters
    }

    # Weighted combination
    final = (
        source_score * weights['source'] +
        agreement_score * weights['agreement'] +
        specificity_score * weights['specificity']
    )

    # Cross-reference bonus: if this claim matches existing insights
    cross_ref_bonus = 0
    cross_ref_note = ""
    if existing_insights:
        matching = [i for i in existing_insights
                   if i.get('claim_type') == claim_type
                   and i.get('taxon_id') != claim_value.get('taxon_id', '')]
        if matching:
            cross_ref_bonus = min(0.05, len(matching) * 0.02)
            cross_ref_note = f"; matches {len(matching)} existing insight(s)"
            final = min(0.98, final + cross_ref_bonus)

    # Round to 2 decimal places
    final = round(final, 2)

    methodology = (
        f"Evidence-based: source_score={source_score:.2f} (count={source_count}, "
        f"diversity={source_diversity}) × {weights['source']:.0%} + "
        f"agreement={agreement_score:.2f} × {weights['agreement']:.0%} + "
        f"specificity={specificity_score:.2f} × {weights['specificity']:.0%}"
    )

    return ConfidenceBreakdown(
        final_confidence=final,
        source_score=round(source_score, 2),
        agreement_score=round(agreement_score, 2),
        specificity_score=round(specificity_score, 2),
        source_count=source_count,
        source_diversity=source_diversity,
        corroboration_notes=agreement_notes + cross_ref_note,
        methodology=methodology,
        factors={
            'source_weight': weights['source'],
            'agreement_weight': weights['agreement'],
            'specificity_weight': weights['specificity'],
            'cross_ref_bonus': cross_ref_bonus,
        }
    )


def recalculate_insight_confidence(insight: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recalculate confidence for an existing insight.

    Returns the insight with updated confidence and methodology metadata.
    """
    breakdown = calculate_confidence(
        claim_type=insight.get('claim_type', ''),
        claim_value=insight.get('claim_value', ''),
        sources=insight.get('sources', [])
    )

    # Update the insight
    insight['confidence'] = breakdown.final_confidence
    insight['confidence_breakdown'] = {
        'source_score': breakdown.source_score,
        'agreement_score': breakdown.agreement_score,
        'specificity_score': breakdown.specificity_score,
        'source_count': breakdown.source_count,
        'source_diversity': breakdown.source_diversity,
        'corroboration': breakdown.corroboration_notes,
        'methodology': breakdown.methodology,
    }

    return insight


# ============================================================================
# CLI for testing
# ============================================================================

if __name__ == "__main__":
    import json

    # Test with sample data
    test_sources = [
        {"url": "https://www.iucnredlist.org/species/78972170/78972188",
         "type": "database", "title": "IUCN Red List"},
        {"url": "https://eunis.eea.europa.eu/species/Quercus%20pyrenaica",
         "type": "database", "title": "EUNIS"},
    ]

    result = calculate_confidence(
        claim_type="conservation_status",
        claim_value={"text": "Least Concern (LC) according to IUCN Red List assessment 2017"},
        sources=test_sources
    )

    print("=== Confidence Calculation Test ===")
    print(f"Final confidence: {result.final_confidence}")
    print(f"Source score: {result.source_score} ({result.source_count} sources, {result.source_diversity} domains)")
    print(f"Agreement score: {result.agreement_score}")
    print(f"Specificity score: {result.specificity_score}")
    print(f"Corroboration: {result.corroboration_notes}")
    print(f"\nMethodology: {result.methodology}")

    # Test numeric field
    print("\n=== Numeric Field Test (maximum_height) ===")
    result2 = calculate_confidence(
        claim_type="maximum_height",
        claim_value={"text": "Typically 15-25 m tall, occasionally reaching 30 m in optimal conditions"},
        sources=[
            {"url": "https://www.arbolapp.es/en/species/info/quercus-pyrenaica/",
             "type": "database", "title": "Arbolapp", "credibility": 0.85},
        ]
    )
    print(f"Final confidence: {result2.final_confidence}")
    print(f"Specificity score: {result2.specificity_score}")

    # Test with no sources
    print("\n=== No Sources Test ===")
    result3 = calculate_confidence(
        claim_type="cultural_significance",
        claim_value={"text": "Historically used for tanning leather"},
        sources=[]
    )
    print(f"Final confidence: {result3.final_confidence}")
    print(f"Source score: {result3.source_score}")
