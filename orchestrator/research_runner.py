#!/usr/bin/env python3
"""
Treekipedia Research Runner
===========================
Automated research flow for species in the queue.

This script is designed to be run by Claude Code CLI. It:
1. Gets the next species from the queue
2. Runs each of the 4 research agents in sequence
3. Saves insights to the orchestrator
4. Marks the queue item as complete

Usage:
    python orchestrator/research_runner.py --next          # Process next in queue
    python orchestrator/research_runner.py --taxon-id X    # Process specific species
    python orchestrator/research_runner.py --batch 5       # Process N species

The actual research is done by Claude Code CLI using the prompts in research_prompts.py.
This script provides the structure and saves results.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("Warning: requests not installed. Install with: pip install requests")

from research_prompts import (
    get_prompt_for_agent,
    get_fields_for_agent,
    format_prompt,
    get_all_agent_types,
    get_total_fields,
    ALL_FIELDS,
    PREFERRED_SOURCES
)

# Configuration
ORCHESTRATOR_URL = os.environ.get('ORCHESTRATOR_URL', 'http://localhost:5003')

# ============================================================================
# RESEARCH TASK CLASS
# ============================================================================

class ResearchTask:
    """Represents a species research task."""

    def __init__(self, queue_id: int, taxon_id: str, species_name: str,
                 family: str = None, native_range: str = None):
        self.queue_id = queue_id
        self.taxon_id = taxon_id
        self.species_name = species_name
        self.family = family or 'Unknown'
        self.native_range = native_range or 'Unknown'
        self.session_id = f"cli_session_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}_{taxon_id[:10]}"
        self.insights: List[Dict] = []
        self.agent_results: Dict[str, Any] = {}

    def __str__(self):
        return f"ResearchTask({self.species_name}, {self.taxon_id})"

    def get_prompt(self, agent_type: str) -> str:
        """Get formatted prompt for an agent."""
        return format_prompt(agent_type, self.species_name, self.family, self.native_range)

    def add_insights(self, agent_type: str, insights: List[Dict]):
        """Add insights from an agent."""
        self.agent_results[agent_type] = {
            'insights': insights,
            'count': len(insights),
            'timestamp': datetime.now().isoformat()
        }
        self.insights.extend(insights)

    def get_summary(self) -> Dict:
        """Get summary of research progress."""
        return {
            'taxon_id': self.taxon_id,
            'species_name': self.species_name,
            'session_id': self.session_id,
            'total_insights': len(self.insights),
            'expected_fields': get_total_fields(),
            'agents_completed': list(self.agent_results.keys()),
            'agents_remaining': [a for a in get_all_agent_types() if a not in self.agent_results]
        }


# ============================================================================
# QUEUE FUNCTIONS
# ============================================================================

def get_next_from_queue() -> Optional[ResearchTask]:
    """Get the next species to research from the queue."""
    if not HAS_REQUESTS:
        print("Error: requests library required")
        return None

    try:
        response = requests.get(f'{ORCHESTRATOR_URL}/queue/next')
        data = response.json()

        if not data.get('success'):
            print("No pending items in queue.")
            return None

        return ResearchTask(
            queue_id=data['queue_id'],
            taxon_id=data['taxon_id'],
            species_name=data['species_name'],
            family=data.get('family'),
            native_range=data.get('wcvp_native')
        )
    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to orchestrator at {ORCHESTRATOR_URL}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def get_species_by_taxon_id(taxon_id: str) -> Optional[ResearchTask]:
    """Get species info for a specific taxon_id."""
    if not HAS_REQUESTS:
        print("Error: requests library required")
        return None

    try:
        response = requests.get(f'{ORCHESTRATOR_URL}/research/{taxon_id}')
        if response.status_code == 404:
            print(f"Species not found: {taxon_id}")
            return None

        data = response.json()
        return ResearchTask(
            queue_id=0,  # Not from queue
            taxon_id=data['taxon_id'],
            species_name=data['species_name'],
            family=data.get('family'),
            native_range=data.get('wcvp_native')
        )
    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to orchestrator at {ORCHESTRATOR_URL}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def mark_queue_processing(queue_id: int) -> bool:
    """Mark a queue item as processing."""
    if queue_id == 0:
        return True  # Not from queue

    try:
        response = requests.post(f'{ORCHESTRATOR_URL}/queue/{queue_id}/start')
        return response.json().get('success', False)
    except:
        return False


def mark_queue_complete(queue_id: int) -> bool:
    """Mark a queue item as completed."""
    if queue_id == 0:
        return True  # Not from queue

    try:
        response = requests.post(f'{ORCHESTRATOR_URL}/queue/{queue_id}/complete')
        return response.json().get('success', False)
    except:
        return False


def mark_queue_failed(queue_id: int, error: str) -> bool:
    """Mark a queue item as failed."""
    if queue_id == 0:
        return True  # Not from queue

    try:
        response = requests.post(
            f'{ORCHESTRATOR_URL}/queue/{queue_id}/fail',
            json={'error': error}
        )
        return response.json().get('success', False)
    except:
        return False


def save_insights_to_orchestrator(task: ResearchTask) -> Dict:
    """Save all insights to the orchestrator."""
    try:
        response = requests.post(
            f'{ORCHESTRATOR_URL}/research/{task.taxon_id}/save',
            json={
                'session_id': task.session_id,
                'model_version': 'claude-opus-4-5-20251101',
                'insights': task.insights
            }
        )
        return response.json()
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ============================================================================
# DISPLAY FUNCTIONS
# ============================================================================

def print_research_header(task: ResearchTask):
    """Print the research task header."""
    print(f"\n{'='*80}")
    print(f"RESEARCH TASK: {task.species_name}")
    print(f"{'='*80}")
    print(f"  Taxon ID:      {task.taxon_id}")
    print(f"  Family:        {task.family}")
    print(f"  Native to:     {task.native_range[:60] if task.native_range else 'Unknown'}...")
    print(f"  Session ID:    {task.session_id}")
    print(f"  Total fields:  {get_total_fields()}")
    print(f"{'='*80}\n")


def print_agent_header(agent_type: str, task: ResearchTask):
    """Print the header for an agent research phase."""
    fields = get_fields_for_agent(agent_type)
    print(f"\n{'='*80}")
    print(f"{agent_type.upper()} AGENT - {task.species_name}")
    print(f"{'='*80}")
    print(f"Fields to research ({len(fields)}):")
    for i, field in enumerate(fields, 1):
        print(f"  {i}. {field}")
    print(f"\nPreferred sources:")
    for source in PREFERRED_SOURCES[:5]:
        print(f"  - {source}")
    print(f"{'='*80}\n")


def print_agent_prompt(agent_type: str, task: ResearchTask):
    """Print the full prompt for an agent."""
    prompt = task.get_prompt(agent_type)
    print(f"\n--- PROMPT START ---\n")
    print(prompt)
    print(f"\n--- PROMPT END ---\n")


def print_research_summary(task: ResearchTask):
    """Print summary of research completed."""
    summary = task.get_summary()
    print(f"\n{'='*80}")
    print(f"RESEARCH SUMMARY: {task.species_name}")
    print(f"{'='*80}")
    print(f"  Session ID:        {summary['session_id']}")
    print(f"  Total insights:    {summary['total_insights']}/{summary['expected_fields']}")
    print(f"  Agents completed:  {', '.join(summary['agents_completed']) or 'None'}")
    print(f"  Agents remaining:  {', '.join(summary['agents_remaining']) or 'None'}")
    print(f"{'='*80}\n")


# ============================================================================
# RESEARCH WORKFLOW
# ============================================================================

def run_research_workflow(task: ResearchTask, interactive: bool = True):
    """
    Run the full research workflow for a species.

    In interactive mode (when run by Claude Code CLI), this function:
    1. Prints prompts for each agent
    2. Waits for Claude to perform web searches and generate insights
    3. Expects insights to be provided via the save_insights method

    The actual research is performed by Claude Code CLI, not this script.
    """
    print_research_header(task)

    # Mark as processing
    if task.queue_id > 0:
        mark_queue_processing(task.queue_id)
        print(f"Marked queue item {task.queue_id} as 'processing'\n")

    # Run each agent in sequence
    agent_types = get_all_agent_types()

    for agent_type in agent_types:
        print_agent_header(agent_type, task)

        if interactive:
            print(">>> CLAUDE CODE: Please perform web searches to research the fields above.")
            print(">>> Then provide insights in the format shown in the prompt.\n")
            print_agent_prompt(agent_type, task)

    print("\n" + "="*80)
    print("RESEARCH WORKFLOW COMPLETE")
    print("="*80)
    print("""
Next steps:
1. For each agent above, Claude Code should:
   - Perform web searches using the WebSearch tool
   - Extract data for each field
   - Format as JSON insights with sources

2. Save insights by calling:
   curl -X POST {orchestrator}/research/{taxon_id}/save \\
     -H "Content-Type: application/json" \\
     -d '{{"session_id": "{session_id}", "insights": [...]}}'

3. Mark as complete:
   curl -X POST {orchestrator}/queue/{queue_id}/complete
""".format(
        orchestrator=ORCHESTRATOR_URL,
        taxon_id=task.taxon_id,
        session_id=task.session_id,
        queue_id=task.queue_id
    ))


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Treekipedia Research Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python orchestrator/research_runner.py --next
  python orchestrator/research_runner.py --taxon-id "AngMaFaFbCx09076-00"
  python orchestrator/research_runner.py --show-prompts identity

This script provides the research workflow structure.
Actual research is performed by Claude Code CLI.
        """
    )

    parser.add_argument('--next', action='store_true',
                        help='Process next species from queue')
    parser.add_argument('--taxon-id',
                        help='Process specific species by taxon_id')
    parser.add_argument('--show-prompts', choices=['identity', 'ecological', 'morphological', 'stewardship', 'all'],
                        help='Show prompt template(s) for agent type(s)')
    parser.add_argument('--list-fields', action='store_true',
                        help='List all 35 research fields')

    args = parser.parse_args()

    # Show prompts only
    if args.show_prompts:
        if args.show_prompts == 'all':
            for agent_type in get_all_agent_types():
                print(f"\n{'='*80}")
                print(f"{agent_type.upper()} AGENT PROMPT")
                print(f"{'='*80}")
                print(get_prompt_for_agent(agent_type))
        else:
            print(f"\n{'='*80}")
            print(f"{args.show_prompts.upper()} AGENT PROMPT")
            print(f"{'='*80}")
            print(get_prompt_for_agent(args.show_prompts))
        return

    # List all fields
    if args.list_fields:
        print(f"\n{'='*80}")
        print(f"ALL RESEARCH FIELDS ({len(ALL_FIELDS)} total)")
        print(f"{'='*80}\n")

        for agent_type in get_all_agent_types():
            fields = get_fields_for_agent(agent_type)
            print(f"{agent_type.upper()} ({len(fields)} fields):")
            for i, field in enumerate(fields, 1):
                print(f"  {i}. {field}")
            print()
        return

    # Process next from queue
    if args.next:
        task = get_next_from_queue()
        if task:
            run_research_workflow(task)
        return

    # Process specific taxon_id
    if args.taxon_id:
        task = get_species_by_taxon_id(args.taxon_id)
        if task:
            run_research_workflow(task)
        return

    parser.print_help()


if __name__ == '__main__':
    main()
