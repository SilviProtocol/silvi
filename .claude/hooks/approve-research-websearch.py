#!/usr/bin/env python3
"""
Auto-approve WebSearch tool calls for Treekipedia deep species research.

This hook automatically approves WebSearch queries that match botanical research
patterns across ALL languages. Designed to support wide-ranging deep research.

PHILOSOPHY: Cast a wide net. Don't restrict research searches.

Hook Type: PreToolUse
Trigger: WebSearch tool calls

Security: Only blocks clearly malicious/sensitive patterns.
"""

import json
import sys
import re


# Research-relevant patterns (case-insensitive)
# INTENTIONALLY BROAD to support wide-ranging research
RESEARCH_PATTERNS = [
    # Species and taxonomy (scientific names follow Latin patterns)
    r'\b[A-Z][a-z]+\s+[a-z]+\b',  # Matches "Genus species" pattern
    r'\b(species|tree|plant|shrub|palm|vine|genus|family|flora|botanical)\b',
    r'\b(taxonomy|nomenclature|scientific.?name|synonym|basionym)\b',

    # Databases and institutions (any language)
    r'\b(IUCN|GBIF|POWO|WCVP|Kew|FAO|USDA|ICRAF|CIFOR)\b',
    r'\b(Red.?List|Plants.?of.?the.?World|World.?Checklist|World.?Flora)\b',
    r'\b(eflora|florabase|atlas|tropicos|herbarium)\b',
    r'\b(SciELO|REDALYC|Dialnet)\b',  # Spanish/Portuguese databases

    # Ecology and habitat (English)
    r'\b(habitat|ecosystem|biome|ecology|ecological|environment)\b',
    r'\b(distribution|range|native|endemic|introduced|invasive|naturalized)\b',
    r'\b(elevation|altitude|climate|rainfall|temperature|precipitation)\b',
    r'\b(soil|drought|flood|tolerance|hardiness|zone)\b',
    r'\b(conservation|endangered|threatened|vulnerable|extinct|CITES)\b',

    # Morphology (English)
    r'\b(height|diameter|DBH|trunk|crown|canopy|root)\b',
    r'\b(bark|leaf|leaves|flower|fruit|seed|cone|pod|nut)\b',
    r'\b(deciduous|evergreen|growth.?form|habit)\b',
    r'\b(lifespan|longevity|age|maximum|minimum)\b',

    # Stewardship and uses (English)
    r'\b(propagation|cultivation|planting|pruning|maintenance)\b',
    r'\b(agroforestry|timber|wood|lumber|forestry|silviculture)\b',
    r'\b(medicinal|ethnobotany|traditional.?use|cultural|indigenous)\b',
    r'\b(edible|food|fruit|nut|nutritional|toxic)\b',
    r'\b(pest|disease|management|fire)\b',

    # Spanish botanical terms
    r'\b(ecología|hábitat|distribución|nativo|endémico)\b',
    r'\b(uso.?tradicional|etnobotánica|medicinal|cultivo)\b',
    r'\b(conservación|amenazado|en.?peligro)\b',
    r'\b(árbol|arbusto|planta|bosque|selva)\b',

    # Portuguese botanical terms
    r'\b(ecologia|habitat|distribuição|nativo|endêmico)\b',
    r'\b(uso.?tradicional|etnobotânica|medicinal|cultivo)\b',
    r'\b(conservação|ameaçado|em.?perigo)\b',
    r'\b(árvore|arbusto|planta|floresta|mata)\b',

    # French botanical terms
    r'\b(écologie|habitat|distribution|indigène|endémique)\b',
    r'\b(usage.?traditionnel|ethnobotanique|médicinal|culture)\b',
    r'\b(conservation|menacé|en.?danger)\b',
    r'\b(arbre|arbuste|plante|forêt)\b',

    # German botanical terms
    r'\b(Ökologie|Lebensraum|Verbreitung|heimisch|endemisch)\b',
    r'\b(traditionelle.?Nutzung|Ethnobotanik|medizinisch|Anbau)\b',
    r'\b(Naturschutz|gefährdet|bedroht)\b',
    r'\b(Baum|Strauch|Pflanze|Wald)\b',

    # Chinese botanical terms (Unicode)
    r'(生态|栖息地|分布|原生|特有)',
    r'(传统|民族植物|药用|栽培)',
    r'(保护|濒危|受威胁)',
    r'(树|灌木|植物|森林)',

    # Japanese botanical terms (Unicode)
    r'(生態|生息地|分布|自生|固有)',
    r'(伝統|民族植物|薬用|栽培)',
    r'(保全|絶滅危惧|希少)',

    # Common Latin genus names (top tree genera)
    r'\b(Acacia|Quercus|Pinus|Eucalyptus|Ficus|Betula|Acer|Fraxinus)\b',
    r'\b(Salix|Populus|Prunus|Malus|Tilia|Ulmus|Fagus|Castanea)\b',
    r'\b(Cedrus|Abies|Picea|Larix|Sequoia|Taxus|Juniperus|Cupressus)\b',
    r'\b(Ceiba|Swietenia|Tectona|Dalbergia|Shorea|Dipterocarpus)\b',
    r'\b(Coffea|Theobroma|Mangifera|Citrus|Persea|Anacardium)\b',

    # Grey literature indicators
    r'\b(dissertation|thesis|technical.?report|working.?paper)\b',
    r'\b(filetype.?pdf|site.?edu|site.?gov|site.?org)\b',
    r'\b(ProQuest|OpenGrey|NDLTD|repository)\b',

    # Research/academic terms
    r'\b(research|study|survey|inventory|assessment|review)\b',
    r'\b(biodiversity|darkspot|data.?deficient|orphan)\b',
]

# Patterns that should BLOCK the search (security - keep minimal)
BLOCKED_PATTERNS = [
    r'\b(password|passwd|secret|api.?key|token|credential|auth)\b',
    r'\b(credit.?card|ssn|social.?security|bank.?account|routing.?number)\b',
    r'\b(hack|exploit|malware|virus|trojan|ransomware|phishing)\b',
    r'\b(buy.?drugs|purchase.?illegal|dark.?web|silk.?road)\b',
]


def is_research_query(query: str) -> tuple[bool, str]:
    """
    Determine if a WebSearch query is for species research.

    PHILOSOPHY: Be PERMISSIVE. The goal is deep, wide-ranging research.
    Only block clearly malicious queries.

    Returns:
        tuple: (is_approved, reason)
    """
    query_lower = query.lower()

    # Check for blocked patterns first (security)
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            return False, f"Query contains blocked security pattern"

    # Check if query matches any research pattern (very broad)
    for pattern in RESEARCH_PATTERNS:
        try:
            if re.search(pattern, query, re.IGNORECASE | re.UNICODE):
                return True, "Research query approved"
        except re.error:
            continue

    # If query contains a scientific name pattern (Genus species), approve
    if re.search(r'[A-Z][a-z]+\s+[a-z]+', query):
        return True, "Scientific name pattern detected"

    # If query contains site: or filetype: operators, likely research
    if re.search(r'(site:|filetype:)', query_lower):
        return True, "Research operator detected"

    # If query is in non-ASCII (likely Chinese/Japanese/Arabic), approve for deep research
    if any(ord(c) > 127 for c in query):
        return True, "Non-ASCII query (multilingual research)"

    # Default: Don't auto-approve, but don't block either
    # Return False to fall through to normal permission flow
    return False, "Query does not match research patterns - manual approval needed"


def main():
    """Process the PreToolUse hook input."""
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        # If we can't parse input, exit without blocking
        print(json.dumps({
            "error": f"Invalid JSON input: {e}"
        }), file=sys.stderr)
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Only process WebSearch calls
    if tool_name != "WebSearch":
        sys.exit(0)

    query = tool_input.get("query", "")

    if not query:
        sys.exit(0)

    # Check if this is a research query
    is_approved, reason = is_research_query(query)

    if is_approved:
        # Auto-approve the search
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": reason,
            },
            "suppressOutput": True  # Don't clutter output
        }
        print(json.dumps(output))
        sys.exit(0)
    else:
        # Check if blocked for security reasons
        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, query.lower(), re.IGNORECASE):
                output = {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "Security: Query blocked",
                    }
                }
                print(json.dumps(output))
                sys.exit(2)  # Exit 2 = deny

        # For non-matching queries, don't block - fall through to manual approval
        sys.exit(0)


if __name__ == "__main__":
    main()
