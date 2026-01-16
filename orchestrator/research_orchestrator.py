#!/usr/bin/env python3
"""
Adaptive Research Orchestrator Service (Port 5003)

Single intelligent orchestrator that adapts behavior based on context:
- First research: Full coverage of all 35 fields
- Re-research: Focus on gaps, low-confidence, missing fields
- Controversy resolution: Deep dive on specific topics

The orchestrator:
1. Manages the research queue
2. Analyzes existing insights to guide research strategy
3. Calculates evidence-based confidence
4. Handles inline QC during save
5. Syncs insights to species table

Architecture:
┌─────────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR AGENT (Context-Aware)                   │
├─────────────────────────────────────────────────────────────────────────┤
│  1. CHECK CONTEXT → First research? Re-research? Controversial?        │
│  2. ADAPTIVE RESEARCH → Prioritize gaps, skip high-confidence          │
│  3. INLINE QC → Flag contradictions, resolve during research           │
│  4. SYNTHESIZE → Merge with existing, supersede outdated               │
└─────────────────────────────────────────────────────────────────────────┘
"""

import os
import json
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, asdict
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor, Json

# Import confidence calculator
from confidence_calculator import calculate_confidence, recalculate_insight_confidence

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Database connection
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': os.environ.get('DB_PORT', '5432'),
    'database': os.environ.get('DB_NAME', 'treekipedia'),
    'user': os.environ.get('DB_USER', os.environ.get('USER', 'postgres')),
    'password': os.environ.get('DB_PASSWORD', '')
}

# All 35 research fields organized by category
FIELD_CATEGORIES = {
    'identity': [
        'popular_common_name',
        'etymology',
        'synonyms',
        'identification_features'
    ],
    'ecological': [
        'general_description',
        'habitat',
        'elevation_ranges',
        'ecological_function',
        'native_adapted_habitats',
        'conservation_status',
        'compatible_soil_types',
        'climate_tolerance',
        'tolerances',
        'associated_species'
    ],
    'morphological': [
        'growth_form',
        'leaf_type',
        'deciduous_evergreen',
        'flower_color',
        'fruit_type',
        'bark_characteristics',
        'maximum_height',
        'maximum_diameter',
        'lifespan',
        'maximum_tree_age'
    ],
    'stewardship': [
        'stewardship_best_practices',
        'planting_recipes',
        'pruning_maintenance',
        'disease_pest_management',
        'fire_management',
        'propagation_methods',
        'cultural_significance',
        'agroforestry_use_cases',
        'timber_value',
        'non_timber_products',
        'nutritional_caloric_value'
    ]
}

# Flatten for easy lookup
ALL_FIELDS = [f for fields in FIELD_CATEGORIES.values() for f in fields]

# Multi-insight fields (should have multiple atomic insights)
MULTI_INSIGHT_FIELDS = {
    'cultural_significance',
    'tolerances',
    'habitat',
    'ecological_function',
    'non_timber_products',
    'agroforestry_use_cases',
    'disease_pest_management',
    'stewardship_best_practices',
    'associated_species',
    'native_adapted_habitats'
}

# Confidence thresholds
CONFIDENCE_THRESHOLDS = {
    'high': 0.85,      # Skip on re-research
    'medium': 0.70,    # Light refresh
    'low': 0.50,       # Priority research
    'critical': 0.30   # Deep dive required
}


@dataclass
class ResearchContext:
    """Context for adaptive research decisions."""
    taxon_id: str
    species_name: str
    is_first_research: bool
    existing_version: int
    existing_insight_count: int
    high_confidence_fields: List[str]
    low_confidence_fields: List[str]
    missing_fields: List[str]
    controversial_fields: List[str]
    recommended_focus: str  # 'full', 'gaps', 'deep_dive'
    priority_fields: List[str]
    skip_fields: List[str]


def get_db_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)


def get_species_info(taxon_id: str) -> Optional[Dict]:
    """Fetch species info from database."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT taxon_id, species_scientific_name, family,
                       wcvp_native, wcvp_introduced, research_version,
                       research_confidence, researched
                FROM species
                WHERE taxon_id = %s
                LIMIT 1
            """, (taxon_id,))
            return cur.fetchone()
    finally:
        conn.close()


def get_existing_insights(taxon_id: str) -> List[Dict]:
    """Get all current insights for a species."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, claim_type, claim_value, confidence,
                       sources, version, created_at
                FROM insights
                WHERE taxon_id = %s AND is_current = TRUE
                ORDER BY claim_type, confidence DESC
            """, (taxon_id,))
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def analyze_research_context(taxon_id: str) -> ResearchContext:
    """
    Analyze existing insights to determine research strategy.

    This is the brain of the adaptive orchestrator.
    """
    species = get_species_info(taxon_id)
    if not species:
        raise ValueError(f"Species not found: {taxon_id}")

    existing_insights = get_existing_insights(taxon_id)
    existing_version = species.get('research_version') or 0
    is_first_research = existing_version == 0 or len(existing_insights) == 0

    # Analyze existing insights by field
    field_insights = {}
    for insight in existing_insights:
        claim_type = insight['claim_type']
        if claim_type not in field_insights:
            field_insights[claim_type] = []
        field_insights[claim_type].append(insight)

    # Categorize fields by confidence
    high_confidence = []
    low_confidence = []
    missing = []
    controversial = []

    for field in ALL_FIELDS:
        if field not in field_insights:
            missing.append(field)
        else:
            insights = field_insights[field]
            avg_conf = sum(i['confidence'] or 0 for i in insights) / len(insights)

            if avg_conf >= CONFIDENCE_THRESHOLDS['high']:
                high_confidence.append(field)
            elif avg_conf < CONFIDENCE_THRESHOLDS['low']:
                low_confidence.append(field)

            # Check for contradictions (multiple insights with different values)
            if len(insights) > 1:
                # Simple check: if confidences vary significantly, might be controversial
                confidences = [i['confidence'] or 0 for i in insights]
                if max(confidences) - min(confidences) > 0.3:
                    controversial.append(field)

    # Determine recommended focus
    if is_first_research:
        recommended_focus = 'full'
        priority_fields = ALL_FIELDS.copy()
        skip_fields = []
    elif len(missing) > 10 or len(low_confidence) > 5:
        recommended_focus = 'gaps'
        priority_fields = missing + low_confidence
        skip_fields = high_confidence
    elif controversial:
        recommended_focus = 'deep_dive'
        priority_fields = controversial + low_confidence
        skip_fields = [f for f in high_confidence if f not in controversial]
    else:
        recommended_focus = 'refresh'
        priority_fields = missing + low_confidence
        skip_fields = high_confidence

    return ResearchContext(
        taxon_id=taxon_id,
        species_name=species['species_scientific_name'],
        is_first_research=is_first_research,
        existing_version=existing_version,
        existing_insight_count=len(existing_insights),
        high_confidence_fields=high_confidence,
        low_confidence_fields=low_confidence,
        missing_fields=missing,
        controversial_fields=controversial,
        recommended_focus=recommended_focus,
        priority_fields=priority_fields,
        skip_fields=skip_fields
    )


def supersede_old_insights(taxon_id: str, claim_types: List[str], new_version: int) -> int:
    """Mark old insights as superseded when new ones are saved."""
    if not claim_types:
        return 0

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE insights
                SET is_current = FALSE,
                    supersedes = id
                WHERE taxon_id = %s
                  AND claim_type = ANY(%s)
                  AND is_current = TRUE
                  AND version < %s
                RETURNING id
            """, (taxon_id, claim_types, new_version))
            superseded = cur.fetchall()
            conn.commit()
            return len(superseded)
    finally:
        conn.close()


def save_insights_with_confidence(
    taxon_id: str,
    insights: List[Dict],
    session_id: str,
    model_version: str,
    existing_insights: Optional[List[Dict]] = None
) -> Tuple[int, float]:
    """
    Save insights with calculated confidence scores.

    Returns: (count_saved, average_confidence)
    """
    conn = get_db_connection()
    saved = 0
    total_confidence = 0
    claim_types_saved = set()

    try:
        with conn.cursor() as cur:
            # Get next version
            cur.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 as next_version FROM insights WHERE taxon_id = %s",
                (taxon_id,)
            )
            version = cur.fetchone()['next_version']

            for insight in insights:
                claim_type = insight.get('claim_type')
                claim_value = insight.get('claim_value', {})
                sources = insight.get('sources', [])

                # Calculate evidence-based confidence
                conf_result = calculate_confidence(
                    claim_type=claim_type,
                    claim_value=claim_value,
                    sources=sources,
                    existing_insights=existing_insights
                )

                # Use calculated confidence, not AI self-assessment
                confidence = conf_result.final_confidence

                # Determine category
                category = 'general'
                for cat, fields in FIELD_CATEGORIES.items():
                    if claim_type in fields:
                        category = cat
                        break

                cur.execute("""
                    INSERT INTO insights (
                        taxon_id, claim_type, claim_value, confidence,
                        methodology, sources, model_version, agent_type,
                        version, research_session_id, confidence_breakdown,
                        is_current
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                    RETURNING id
                """, (
                    taxon_id,
                    claim_type,
                    Json(claim_value) if isinstance(claim_value, dict) else claim_value,
                    confidence,
                    conf_result.methodology,
                    Json(sources),
                    model_version,
                    category,
                    version,
                    session_id,
                    Json({
                        'source_score': conf_result.source_score,
                        'agreement_score': conf_result.agreement_score,
                        'specificity_score': conf_result.specificity_score,
                        'source_count': conf_result.source_count,
                        'source_diversity': conf_result.source_diversity,
                        'corroboration': conf_result.corroboration_notes
                    })
                ))

                saved += 1
                total_confidence += confidence
                claim_types_saved.add(claim_type)

            conn.commit()

            # Supersede old insights for the same claim types
            if claim_types_saved:
                supersede_old_insights(taxon_id, list(claim_types_saved), version)

    except Exception as e:
        logger.error(f"Failed to save insights: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

    avg_confidence = total_confidence / saved if saved > 0 else 0
    return saved, avg_confidence


def update_species_research_status(
    taxon_id: str,
    session_id: str,
    avg_confidence: float,
    insight_count: int,
    field_count: int
) -> None:
    """Update species table after research completes."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE species SET
                    research_version = COALESCE(research_version, 0) + 1,
                    research_date = NOW(),
                    research_confidence = %s,
                    researched = TRUE
                WHERE taxon_id = %s
            """, (avg_confidence, taxon_id))
            conn.commit()
    finally:
        conn.close()


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'service': 'research-orchestrator',
        'port': 5003,
        'timestamp': datetime.now().isoformat(),
        'features': ['adaptive-research', 'confidence-calculator', 'inline-qc']
    })


@app.route('/research/<taxon_id>/context', methods=['GET'])
def get_research_context(taxon_id: str):
    """
    Get research context for a species.

    This tells the researching agent:
    - Is this first research or re-research?
    - Which fields to prioritize?
    - Which fields can be skipped?
    - Are there controversies to resolve?
    """
    try:
        context = analyze_research_context(taxon_id)

        return jsonify({
            'success': True,
            'taxon_id': context.taxon_id,
            'species_name': context.species_name,
            'research_mode': context.recommended_focus,
            'is_first_research': context.is_first_research,
            'existing_version': context.existing_version,
            'existing_insight_count': context.existing_insight_count,
            'analysis': {
                'high_confidence_fields': context.high_confidence_fields,
                'low_confidence_fields': context.low_confidence_fields,
                'missing_fields': context.missing_fields,
                'controversial_fields': context.controversial_fields
            },
            'recommendations': {
                'priority_fields': context.priority_fields,
                'skip_fields': context.skip_fields,
                'focus': context.recommended_focus
            },
            'field_categories': FIELD_CATEGORIES,
            'multi_insight_fields': list(MULTI_INSIGHT_FIELDS)
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error analyzing context: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/research/<taxon_id>', methods=['GET'])
def get_research_task(taxon_id: str):
    """
    Get research task info for a species.
    Enhanced with context-aware recommendations.
    """
    try:
        context = analyze_research_context(taxon_id)
        species = get_species_info(taxon_id)

        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        return jsonify({
            'taxon_id': taxon_id,
            'species_name': context.species_name,
            'family': species.get('family'),
            'wcvp_native': species.get('wcvp_native'),
            'wcvp_introduced': species.get('wcvp_introduced'),
            'session_id': session_id,

            # Research context
            'research_mode': context.recommended_focus,
            'is_first_research': context.is_first_research,
            'current_version': context.existing_version,
            'existing_insights': context.existing_insight_count,

            # Field guidance
            'priority_fields': context.priority_fields,
            'skip_fields': context.skip_fields,
            'controversial_fields': context.controversial_fields,

            # All fields for reference
            'field_categories': FIELD_CATEGORIES,
            'total_fields': len(ALL_FIELDS),
            'multi_insight_fields': list(MULTI_INSIGHT_FIELDS),

            'instructions': f"""
Research mode: {context.recommended_focus.upper()}

{"FIRST RESEARCH - Cover all 35 fields comprehensively." if context.is_first_research else f'''
RE-RESEARCH - Focus on:
- Priority fields ({len(context.priority_fields)}): {", ".join(context.priority_fields[:5])}...
- Can skip ({len(context.skip_fields)}): High-confidence fields
- Controversies ({len(context.controversial_fields)}): {", ".join(context.controversial_fields) or "None"}
'''}

Remember: Use ATOMIC insights - multiple insights per field for: {", ".join(list(MULTI_INSIGHT_FIELDS)[:5])}...
"""
        })
    except Exception as e:
        logger.error(f"Error getting research task: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/research/<taxon_id>/save', methods=['POST'])
def save_research(taxon_id: str):
    """
    Save research results with automatic confidence calculation.

    POST /research/<taxon_id>/save
    Body: {
        "session_id": "...",
        "insights": [
            {
                "claim_type": "cultural_significance",
                "claim_value": {"text": "...", "context": "Buddhism"},
                "sources": [{"url": "...", "title": "...", "type": "database"}]
            }
        ]
    }

    Note: confidence is CALCULATED from sources, not provided by AI.
    """
    species = get_species_info(taxon_id)
    if not species:
        return jsonify({'error': f'Species not found: {taxon_id}'}), 404

    data = request.get_json()
    if not data or 'insights' not in data:
        return jsonify({'error': 'Missing insights in request body'}), 400

    session_id = data.get('session_id', f"cli_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    model = data.get('model', 'claude-code-cli')
    insights = data.get('insights', [])

    if not insights:
        return jsonify({'error': 'No insights provided'}), 400

    # Get existing insights for cross-reference
    existing_insights = get_existing_insights(taxon_id)

    # Validate insights have required fields
    for i, insight in enumerate(insights):
        if 'claim_type' not in insight:
            return jsonify({'error': f'Insight {i} missing claim_type'}), 400
        if 'claim_value' not in insight:
            return jsonify({'error': f'Insight {i} missing claim_value'}), 400

    try:
        # Save with confidence calculation
        saved_count, avg_confidence = save_insights_with_confidence(
            taxon_id=taxon_id,
            insights=insights,
            session_id=session_id,
            model_version=model,
            existing_insights=existing_insights
        )

        # Count unique fields
        field_count = len(set(i['claim_type'] for i in insights))

        # Update species status
        update_species_research_status(
            taxon_id=taxon_id,
            session_id=session_id,
            avg_confidence=avg_confidence,
            insight_count=saved_count,
            field_count=field_count
        )

        logger.info(f"Saved {saved_count} insights for {taxon_id} (avg confidence: {avg_confidence:.2f})")

        return jsonify({
            'success': True,
            'taxon_id': taxon_id,
            'session_id': session_id,
            'insights_saved': saved_count,
            'fields_covered': field_count,
            'avg_confidence': round(avg_confidence, 3),
            'new_version': (species.get('research_version') or 0) + 1,
            'note': 'Confidence calculated from source evidence, not AI self-assessment'
        })

    except Exception as e:
        logger.error(f"Failed to save research: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/insights/<taxon_id>', methods=['GET'])
def get_insights(taxon_id: str):
    """Get all current insights for a species."""
    insights = get_existing_insights(taxon_id)

    # Group by claim_type
    by_field = {}
    for insight in insights:
        claim_type = insight['claim_type']
        if claim_type not in by_field:
            by_field[claim_type] = []
        by_field[claim_type].append(insight)

    return jsonify({
        'taxon_id': taxon_id,
        'insight_count': len(insights),
        'field_count': len(by_field),
        'insights': insights,
        'by_field': by_field
    })


@app.route('/insights/<taxon_id>/gaps', methods=['GET'])
def get_insight_gaps(taxon_id: str):
    """Get fields missing or with low confidence."""
    try:
        context = analyze_research_context(taxon_id)

        return jsonify({
            'taxon_id': taxon_id,
            'species_name': context.species_name,
            'missing_fields': context.missing_fields,
            'low_confidence_fields': context.low_confidence_fields,
            'controversial_fields': context.controversial_fields,
            'total_gaps': len(context.missing_fields) + len(context.low_confidence_fields),
            'coverage': {
                'total_fields': len(ALL_FIELDS),
                'covered': len(ALL_FIELDS) - len(context.missing_fields),
                'high_confidence': len(context.high_confidence_fields),
                'low_confidence': len(context.low_confidence_fields),
                'missing': len(context.missing_fields)
            }
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 404


# ============================================================================
# QUEUE ENDPOINTS (unchanged from original)
# ============================================================================

@app.route('/queue', methods=['GET', 'POST'])
def queue_handler():
    if request.method == 'POST':
        return add_to_queue()
    return get_queue_items()


def add_to_queue():
    """Add a species to the research queue."""
    data = request.get_json()
    if not data or not data.get('taxon_id'):
        return jsonify({'error': 'Missing taxon_id'}), 400

    taxon_id = data['taxon_id']
    species = get_species_info(taxon_id)
    if not species:
        return jsonify({'error': f'Species not found: {taxon_id}'}), 404

    species_name = species['species_scientific_name']
    priority = data.get('priority', 50)

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, status FROM research_queue WHERE taxon_id = %s",
                (taxon_id,)
            )
            existing = cur.fetchone()

            if existing:
                if existing['status'] in ('pending', 'processing'):
                    return jsonify({
                        'success': True,
                        'message': f'Already in queue: {existing["status"]}',
                        'queue_id': existing['id'],
                        'taxon_id': taxon_id,
                        'status': existing['status']
                    })
                else:
                    cur.execute("""
                        UPDATE research_queue
                        SET status = 'pending', priority = %s, queued_at = NOW(),
                            started_at = NULL, completed_at = NULL
                        WHERE taxon_id = %s
                        RETURNING id
                    """, (priority, taxon_id))
                    result = cur.fetchone()
                    conn.commit()
                    return jsonify({
                        'success': True,
                        'message': 'Re-queued',
                        'queue_id': result['id'],
                        'taxon_id': taxon_id,
                        'status': 'pending'
                    })
            else:
                cur.execute("""
                    INSERT INTO research_queue (taxon_id, species_name, status, priority, queued_at)
                    VALUES (%s, %s, 'pending', %s, NOW())
                    RETURNING id
                """, (taxon_id, species_name, priority))
                result = cur.fetchone()
                conn.commit()
                return jsonify({
                    'success': True,
                    'message': 'Added to queue',
                    'queue_id': result['id'],
                    'taxon_id': taxon_id,
                    'species_name': species_name,
                    'status': 'pending'
                })
    finally:
        conn.close()


def get_queue_items():
    """Get species from the research queue."""
    limit = request.args.get('limit', 10, type=int)
    status = request.args.get('status', 'pending')

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT rq.id, rq.taxon_id, rq.species_name, rq.status,
                       rq.priority, rq.queued_at, s.family, s.wcvp_native
                FROM research_queue rq
                LEFT JOIN species s ON rq.taxon_id = s.taxon_id
                WHERE rq.status = %s
                ORDER BY rq.priority DESC, rq.queued_at ASC
                LIMIT %s
            """, (status, limit))
            items = cur.fetchall()

            cur.execute("""
                SELECT status, COUNT(*) as count
                FROM research_queue GROUP BY status
            """)
            counts = {row['status']: row['count'] for row in cur.fetchall()}

            return jsonify({
                'queue_items': [dict(i) for i in items],
                'status_counts': counts,
                'total_pending': counts.get('pending', 0)
            })
    finally:
        conn.close()


@app.route('/queue/next', methods=['GET'])
def get_next_in_queue():
    """Get the next species to research with context."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT rq.id, rq.taxon_id, rq.species_name,
                       s.family, s.wcvp_native, s.wcvp_introduced
                FROM research_queue rq
                LEFT JOIN species s ON rq.taxon_id = s.taxon_id
                WHERE rq.status = 'pending'
                ORDER BY rq.priority DESC, rq.queued_at ASC
                LIMIT 1
            """)
            item = cur.fetchone()

            if not item:
                return jsonify({
                    'success': False,
                    'queue_empty': True,
                    'message': 'No pending items in queue'
                })

            # Get research context
            try:
                context = analyze_research_context(item['taxon_id'])
                context_data = {
                    'research_mode': context.recommended_focus,
                    'is_first_research': context.is_first_research,
                    'priority_fields': context.priority_fields,
                    'skip_fields': context.skip_fields,
                    'missing_fields': context.missing_fields,
                    'low_confidence_fields': context.low_confidence_fields
                }
            except:
                context_data = {'research_mode': 'full', 'is_first_research': True}

            return jsonify({
                'success': True,
                'queue_id': item['id'],
                'taxon_id': item['taxon_id'],
                'species_name': item['species_name'],
                'family': item.get('family'),
                'wcvp_native': item.get('wcvp_native'),
                'wcvp_introduced': item.get('wcvp_introduced'),
                'context': context_data,
                'agents': FIELD_CATEGORIES,
                'total_fields': len(ALL_FIELDS),
                'multi_insight_fields': list(MULTI_INSIGHT_FIELDS)
            })
    finally:
        conn.close()


@app.route('/queue/<int:queue_id>/start', methods=['POST'])
def start_queue_item(queue_id: int):
    """Mark a queue item as processing."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE research_queue
                SET status = 'processing', started_at = NOW()
                WHERE id = %s AND status = 'pending'
                RETURNING taxon_id, species_name
            """, (queue_id,))
            result = cur.fetchone()
            conn.commit()

            if not result:
                return jsonify({'success': False, 'error': 'Not found or not pending'}), 404

            return jsonify({
                'success': True,
                'queue_id': queue_id,
                'taxon_id': result['taxon_id'],
                'species_name': result['species_name'],
                'status': 'processing'
            })
    finally:
        conn.close()


@app.route('/queue/<int:queue_id>/complete', methods=['POST'])
def complete_queue_item(queue_id: int):
    """Mark a queue item as completed."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE research_queue
                SET status = 'completed', completed_at = NOW()
                WHERE id = %s
                RETURNING taxon_id, species_name
            """, (queue_id,))
            result = cur.fetchone()
            conn.commit()

            if not result:
                return jsonify({'success': False, 'error': 'Not found'}), 404

            return jsonify({
                'success': True,
                'queue_id': queue_id,
                'taxon_id': result['taxon_id'],
                'species_name': result['species_name'],
                'status': 'completed'
            })
    finally:
        conn.close()


@app.route('/queue/<int:queue_id>/fail', methods=['POST'])
def fail_queue_item(queue_id: int):
    """Mark a queue item as failed."""
    data = request.get_json() or {}
    error_message = data.get('error', 'Unknown error')

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE research_queue
                SET status = 'failed', completed_at = NOW(), error_message = %s
                WHERE id = %s
                RETURNING taxon_id, species_name
            """, (error_message, queue_id))
            result = cur.fetchone()
            conn.commit()

            if not result:
                return jsonify({'success': False, 'error': 'Not found'}), 404

            return jsonify({
                'success': True,
                'queue_id': queue_id,
                'taxon_id': result['taxon_id'],
                'status': 'failed',
                'error': error_message
            })
    finally:
        conn.close()


@app.route('/queue/status', methods=['GET'])
def get_queue_status():
    """Get queue statistics."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT status, COUNT(*) as count
                FROM research_queue GROUP BY status
            """)
            counts = {row['status']: row['count'] for row in cur.fetchall()}

            cur.execute("SELECT COUNT(*) as total FROM research_queue")
            total = cur.fetchone()['total']

            return jsonify({
                'total': total,
                'pending': counts.get('pending', 0),
                'processing': counts.get('processing', 0),
                'completed': counts.get('completed', 0),
                'failed': counts.get('failed', 0)
            })
    finally:
        conn.close()


@app.route('/progress', methods=['GET'])
def get_progress():
    """Get overall research progress."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Species progress
            cur.execute("""
                SELECT
                    COUNT(*) as total_species,
                    COUNT(CASE WHEN researched = TRUE THEN 1 END) as researched,
                    COUNT(CASE WHEN researched = FALSE OR researched IS NULL THEN 1 END) as unresearched,
                    AVG(research_confidence) as avg_confidence
                FROM species
            """)
            species_stats = dict(cur.fetchone())

            # Insights progress
            cur.execute("""
                SELECT
                    COUNT(*) as total_insights,
                    COUNT(DISTINCT taxon_id) as species_with_insights,
                    COUNT(DISTINCT claim_type) as unique_fields,
                    AVG(confidence) as avg_confidence
                FROM insights
                WHERE is_current = TRUE
            """)
            insight_stats = dict(cur.fetchone())

            return jsonify({
                'species': species_stats,
                'insights': insight_stats
            })
    finally:
        conn.close()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5003))
    logger.info(f"Starting Adaptive Research Orchestrator on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)
