#!/usr/bin/env python3
"""
Export Treekipedia insights to RDF triples for knowledge graph and ML training.

Supports:
- RDF/Turtle output for SPARQL endpoints
- N-Quads with provenance graphs (nanopublication-compatible)
- JSON-LD for web applications
- JSONL for ML training datasets

Usage:
    python export_to_rdf.py --format turtle --output insights.ttl
    python export_to_rdf.py --format nquads --output insights.nq
    python export_to_rdf.py --format jsonl --output training.jsonl
    python export_to_rdf.py --taxon-id AngMaFaFgCx14880-00 --format turtle
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, Generator, Optional
from urllib.parse import quote

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("Error: psycopg2 not installed. Run: pip3 install psycopg2-binary")
    sys.exit(1)

# Namespace prefixes for RDF
PREFIXES = {
    "treekipedia": "https://treekipedia.silvi.earth/species/",
    "tkp": "https://treekipedia.silvi.earth/ontology#",
    "dwc": "http://rs.tdwg.org/dwc/terms/",
    "envo": "http://purl.obolibrary.org/obo/ENVO_",
    "pato": "http://purl.obolibrary.org/obo/PATO_",
    "dcterms": "http://purl.org/dc/terms/",
    "prov": "http://www.w3.org/ns/prov#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "schema": "https://schema.org/",
}

# Map claim_types to Darwin Core / ENVO / PATO ontology terms
ONTOLOGY_MAPPING = {
    # Identity fields
    "general_description": {"predicate": "tkp:generalDescription", "range": "xsd:string"},
    "common_name": {"predicate": "dwc:vernacularName", "range": "xsd:string"},
    "species_scientific_name": {"predicate": "dwc:scientificName", "range": "xsd:string"},
    "taxonomic_notes": {"predicate": "tkp:taxonomicNotes", "range": "xsd:string"},

    # Ecological fields
    "habitat": {"predicate": "dwc:habitat", "range": "xsd:string"},
    "native_adapted_habitats": {"predicate": "tkp:nativeHabitats", "range": "xsd:string"},
    "elevation_ranges": {"predicate": "tkp:elevationRange", "range": "xsd:string"},
    "climate_zones": {"predicate": "tkp:climateZones", "range": "xsd:string"},
    "temperature_tolerance": {"predicate": "tkp:temperatureTolerance", "range": "xsd:string"},
    "rainfall_requirements": {"predicate": "tkp:rainfallRequirements", "range": "xsd:string"},
    "ecological_function": {"predicate": "tkp:ecologicalFunction", "range": "xsd:string"},
    "associated_species": {"predicate": "tkp:associatedSpecies", "range": "xsd:string"},
    "conservation_status": {"predicate": "dwc:occurrenceStatus", "range": "xsd:string"},
    "threatened_status": {"predicate": "tkp:threatenedStatus", "range": "xsd:string"},

    # Morphological fields
    "growth_form": {"predicate": "tkp:growthForm", "range": "xsd:string"},
    "leaf_type": {"predicate": "tkp:leafType", "range": "xsd:string"},
    "deciduous_evergreen": {"predicate": "tkp:deciduousEvergreen", "range": "xsd:string"},
    "flower_color": {"predicate": "tkp:flowerColor", "range": "xsd:string"},
    "fruit_type": {"predicate": "tkp:fruitType", "range": "xsd:string"},
    "bark_characteristics": {"predicate": "tkp:barkCharacteristics", "range": "xsd:string"},
    "maximum_height": {"predicate": "dwc:measurementValue", "range": "xsd:string"},
    "maximum_diameter": {"predicate": "tkp:maximumDiameter", "range": "xsd:string"},
    "lifespan": {"predicate": "tkp:lifespan", "range": "xsd:string"},
    "maximum_tree_age": {"predicate": "tkp:maximumTreeAge", "range": "xsd:string"},

    # Stewardship fields
    "stewardship_best_practices": {"predicate": "tkp:stewardshipPractices", "range": "xsd:string"},
    "agroforestry_use_cases": {"predicate": "tkp:agroforestryUses", "range": "xsd:string"},
    "compatible_soil_types": {"predicate": "tkp:compatibleSoilTypes", "range": "xsd:string"},
    "planting_recipes": {"predicate": "tkp:plantingRecipes", "range": "xsd:string"},
    "pruning_maintenance": {"predicate": "tkp:pruningMaintenance", "range": "xsd:string"},
    "disease_pest_management": {"predicate": "tkp:diseasePestManagement", "range": "xsd:string"},
    "fire_management": {"predicate": "tkp:fireManagement", "range": "xsd:string"},
    "cultural_significance": {"predicate": "tkp:culturalSignificance", "range": "xsd:string"},

    # Economic fields
    "uses": {"predicate": "tkp:uses", "range": "xsd:string"},
    "timber_value": {"predicate": "tkp:timberValue", "range": "xsd:string"},
    "non_timber_products": {"predicate": "tkp:nonTimberProducts", "range": "xsd:string"},
}


def get_db_connection():
    """Get PostgreSQL connection using environment or defaults."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "treekipedia"),
        user=os.getenv("DB_USER", os.getenv("USER", "postgres")),
        password=os.getenv("DB_PASSWORD", ""),
    )


def fetch_insights(
    taxon_id: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0
) -> Generator[dict, None, None]:
    """Fetch insights from database."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    query = """
        SELECT
            i.id,
            i.taxon_id,
            i.claim_type,
            i.claim_value,
            i.confidence,
            i.methodology,
            i.sources,
            i.model_version,
            i.agent_type,
            i.created_at,
            i.version,
            s.species_scientific_name,
            s.common_name
        FROM insights i
        LEFT JOIN species s ON i.taxon_id = s.taxon_id
        WHERE i.is_current = TRUE
    """
    params = []

    if taxon_id:
        query += " AND i.taxon_id = %s"
        params.append(taxon_id)

    query += " ORDER BY i.taxon_id, i.claim_type"

    if limit:
        query += f" LIMIT {limit} OFFSET {offset}"

    cur.execute(query, params)

    for row in cur:
        yield dict(row)

    cur.close()
    conn.close()


def escape_literal(value: Any) -> str:
    """Escape string for Turtle literal."""
    if value is None:
        return '""'
    s = str(value)
    # Escape backslashes, quotes, and newlines
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    return f'"{s}"'


def get_claim_text(claim_value: Any) -> str:
    """Extract text from claim_value JSONB."""
    if isinstance(claim_value, str):
        return claim_value
    if isinstance(claim_value, dict):
        # Common patterns in our JSONB
        if "text" in claim_value:
            return claim_value["text"]
        if "value" in claim_value:
            return str(claim_value["value"])
        # Return JSON string for complex structures
        return json.dumps(claim_value)
    return str(claim_value)


def insight_to_turtle(insight: dict) -> str:
    """Convert single insight to Turtle triples."""
    taxon_id = insight["taxon_id"]
    claim_type = insight["claim_type"]
    claim_value = insight["claim_value"]
    confidence = insight.get("confidence", 0.0)
    sources = insight.get("sources", [])
    model = insight.get("model_version", "unknown")
    created_at = insight.get("created_at")
    insight_id = str(insight["id"])

    # Get ontology mapping
    mapping = ONTOLOGY_MAPPING.get(claim_type, {
        "predicate": f"tkp:{claim_type}",
        "range": "xsd:string"
    })

    # Species URI
    species_uri = f"treekipedia:{quote(taxon_id)}"

    # Insight/assertion URI - use full URI to avoid prefix issues with /
    insight_uri = f"<https://treekipedia.silvi.earth/ontology#insight_{quote(insight_id)}>"

    # Claim text
    claim_text = get_claim_text(claim_value)

    lines = []

    # Main assertion triple
    lines.append(f"{species_uri} {mapping['predicate']} {escape_literal(claim_text)} .")

    # Provenance triples (reification pattern)
    lines.append(f"{insight_uri} a tkp:Insight ;")
    lines.append(f"    tkp:aboutSpecies {species_uri} ;")
    lines.append(f"    tkp:claimType {escape_literal(claim_type)} ;")
    lines.append(f"    tkp:confidence \"{confidence}\"^^xsd:decimal ;")
    lines.append(f"    prov:wasGeneratedBy {escape_literal(model)} ;")

    if created_at:
        iso_date = created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at)
        lines.append(f"    dcterms:created \"{iso_date}\"^^xsd:dateTime ;")

    # Track source URIs to add references
    source_uris = []
    source_triples = []

    # Build source data first
    if sources and isinstance(sources, list):
        for i, source in enumerate(sources):
            source_uri = f"<https://treekipedia.silvi.earth/ontology#source_{quote(insight_id)}_{i}>"
            source_uris.append(source_uri)
            url = source.get("url", "")
            title = source.get("title", "")
            source_type = source.get("type", "")
            credibility = source.get("credibility", 0.0)

            # Source details as separate statements
            source_triples.append(f"{source_uri} a tkp:Source ;")
            source_triples.append(f"    schema:url {escape_literal(url)} ;")
            source_triples.append(f"    dcterms:title {escape_literal(title)} ;")
            source_triples.append(f"    tkp:sourceType {escape_literal(source_type)} ;")
            source_triples.append(f"    tkp:credibility \"{credibility}\"^^xsd:decimal .")

    # Add source references to insight
    for source_uri in source_uris:
        lines.append(f"    dcterms:source {source_uri} ;")

    # Close the insight statement
    if lines[-1].endswith(";"):
        lines[-1] = lines[-1][:-1] + "."

    # Add source triples after insight is closed
    lines.extend(source_triples)

    return "\n".join(lines)


def insight_to_nquads(insight: dict) -> str:
    """Convert insight to N-Quads format with named graphs (nanopub-compatible)."""
    taxon_id = insight["taxon_id"]
    claim_type = insight["claim_type"]
    claim_value = insight["claim_value"]
    confidence = insight.get("confidence", 0.0)
    model = insight.get("model_version", "unknown")
    insight_id = str(insight["id"])

    mapping = ONTOLOGY_MAPPING.get(claim_type, {
        "predicate": f"<https://treekipedia.silvi.earth/ontology#{claim_type}>",
        "range": "xsd:string"
    })

    # Full URIs for N-Quads
    species_uri = f"<https://treekipedia.silvi.earth/species/{quote(taxon_id)}>"
    assertion_graph = f"<https://treekipedia.silvi.earth/assertion/{quote(insight_id)}>"
    provenance_graph = f"<https://treekipedia.silvi.earth/provenance/{quote(insight_id)}>"

    claim_text = get_claim_text(claim_value)
    predicate = mapping["predicate"]
    if not predicate.startswith("<"):
        # Expand prefix
        prefix, local = predicate.split(":")
        predicate = f"<{PREFIXES.get(prefix, PREFIXES['tkp'])}{local}>"

    lines = []

    # Assertion graph (the actual claim)
    lines.append(f'{species_uri} {predicate} {escape_literal(claim_text)} {assertion_graph} .')

    # Provenance graph
    lines.append(f'{assertion_graph} <http://www.w3.org/ns/prov#wasGeneratedBy> {escape_literal(model)} {provenance_graph} .')
    lines.append(f'{assertion_graph} <https://treekipedia.silvi.earth/ontology#confidence> "{confidence}"^^<http://www.w3.org/2001/XMLSchema#decimal> {provenance_graph} .')

    return "\n".join(lines)


def insight_to_jsonl(insight: dict) -> str:
    """Convert insight to JSONL for ML training."""
    claim_text = get_claim_text(insight.get("claim_value", ""))

    record = {
        "taxon_id": insight["taxon_id"],
        "species_name": insight.get("species_scientific_name", ""),
        "common_name": insight.get("common_name", ""),
        "claim_type": insight["claim_type"],
        "claim_value": claim_text,
        "confidence": insight.get("confidence", 0.0),
        "model": insight.get("model_version", ""),
        "sources": [
            {"url": s.get("url", ""), "title": s.get("title", ""), "credibility": s.get("credibility", 0.0)}
            for s in (insight.get("sources") or [])
        ]
    }

    return json.dumps(record, ensure_ascii=False)


def insight_to_jsonld(insight: dict) -> dict:
    """Convert insight to JSON-LD format."""
    taxon_id = insight["taxon_id"]
    claim_type = insight["claim_type"]
    claim_value = insight["claim_value"]
    claim_text = get_claim_text(claim_value)

    mapping = ONTOLOGY_MAPPING.get(claim_type, {
        "predicate": f"tkp:{claim_type}",
        "range": "xsd:string"
    })

    return {
        "@context": {
            "tkp": "https://treekipedia.silvi.earth/ontology#",
            "dwc": "http://rs.tdwg.org/dwc/terms/",
            "prov": "http://www.w3.org/ns/prov#",
            "dcterms": "http://purl.org/dc/terms/",
            "schema": "https://schema.org/"
        },
        "@id": f"https://treekipedia.silvi.earth/species/{taxon_id}",
        "@type": "tkp:Species",
        mapping["predicate"]: claim_text,
        "tkp:insight": {
            "@id": f"https://treekipedia.silvi.earth/insight/{insight['id']}",
            "tkp:confidence": insight.get("confidence", 0.0),
            "prov:wasGeneratedBy": insight.get("model_version", ""),
            "dcterms:created": insight.get("created_at").isoformat() if insight.get("created_at") else None,
            "dcterms:source": [
                {
                    "schema:url": s.get("url", ""),
                    "dcterms:title": s.get("title", ""),
                    "tkp:credibility": s.get("credibility", 0.0)
                }
                for s in (insight.get("sources") or [])
            ]
        }
    }


def write_turtle_header(f):
    """Write Turtle file prefixes."""
    for prefix, uri in PREFIXES.items():
        f.write(f"@prefix {prefix}: <{uri}> .\n")
    f.write("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Export Treekipedia insights to RDF formats"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["turtle", "nquads", "jsonl", "jsonld"],
        default="turtle",
        help="Output format (default: turtle)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--taxon-id", "-t",
        help="Export only specific taxon_id"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        help="Limit number of insights"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print statistics instead of exporting"
    )

    args = parser.parse_args()

    if args.stats:
        # Print statistics
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM insights WHERE is_current = TRUE")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT taxon_id) FROM insights WHERE is_current = TRUE")
        species_count = cur.fetchone()[0]

        cur.execute("SELECT claim_type, COUNT(*) FROM insights WHERE is_current = TRUE GROUP BY claim_type ORDER BY COUNT(*) DESC")
        by_type = cur.fetchall()

        print(f"Total current insights: {total}")
        print(f"Species with insights: {species_count}")
        print("\nInsights by type:")
        for claim_type, count in by_type:
            print(f"  {claim_type}: {count}")

        cur.close()
        conn.close()
        return

    # Open output file or stdout
    if args.output:
        f = open(args.output, "w", encoding="utf-8")
    else:
        f = sys.stdout

    try:
        # Write format-specific header
        if args.format == "turtle":
            write_turtle_header(f)
        elif args.format == "jsonld":
            f.write("[\n")

        # Process insights
        first = True
        count = 0

        for insight in fetch_insights(args.taxon_id, args.limit):
            if args.format == "turtle":
                f.write(insight_to_turtle(insight))
                f.write("\n\n")
            elif args.format == "nquads":
                f.write(insight_to_nquads(insight))
                f.write("\n")
            elif args.format == "jsonl":
                f.write(insight_to_jsonl(insight))
                f.write("\n")
            elif args.format == "jsonld":
                if not first:
                    f.write(",\n")
                json.dump(insight_to_jsonld(insight), f, indent=2, default=str)
                first = False

            count += 1

        # Write format-specific footer
        if args.format == "jsonld":
            f.write("\n]\n")

        # Print summary to stderr
        if args.output:
            print(f"Exported {count} insights to {args.output}", file=sys.stderr)

    finally:
        if args.output:
            f.close()


if __name__ == "__main__":
    main()
