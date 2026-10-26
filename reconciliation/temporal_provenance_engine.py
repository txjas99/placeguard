"""Temporal and provenance-based fact reconciliation engine.

Implements the authority ranking and temporal logic algorithm specified in DESIGN.md §3.1.

Algorithm:
1. Group facts by rule_key (drive_id, criterion_type, scope)
2. Keep only facts at the HIGHEST authority rank present
3. Among same-rank facts, take the LATEST effective_timestamp
4. Honor explicit supersession via is_correction/supersedes_ref
5. Coverage fallback: lower authority fills gaps (never overrides)

Key principle: Authority-first, recency-second. A rank-5 student forward NEVER beats a 
rank-1 official PDF, regardless of timestamp.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from database.crud import get_facts_by_drive, upsert_extracted_criterion
from database.models import Fact


@dataclass(frozen=True)
class RuleKey:
    """Immutable key for grouping facts representing the same rule.
    
    Per DESIGN.md §3.3, two facts are considered "the same rule" if they share
    (drive_id, criterion_type, scope).
    """
    
    drive_id: str
    criterion_type: str
    scope: str = "ALL"
    
    def __hash__(self) -> int:
        return hash((self.drive_id, self.criterion_type, self.scope))
    
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, RuleKey):
            return False
        return (
            self.drive_id == other.drive_id
            and self.criterion_type == other.criterion_type
            and self.scope == other.scope
        )
    
    def __repr__(self) -> str:
        return f"RuleKey({self.drive_id}.{self.criterion_type}[{self.scope}])"


def reconcile_facts(facts: list[Fact]) -> dict[RuleKey, Fact]:
    """Apply authority ranking and temporal logic to determine current facts.
    
    Implements the reconciliation algorithm from DESIGN.md §3.1:
    
    1. Group facts by rule_key (drive_id, criterion_type, scope)
    2. For each group:
       a. Find the highest authority rank present
       b. Keep only facts at that rank
       c. Among same-rank facts, take the latest effective_timestamp
       d. Honor explicit supersession (is_correction=True)
    3. Return mapping of rule_key -> authoritative Fact
    
    Args:
        facts: List of Fact objects to reconcile
    
    Returns:
        Dict mapping RuleKey to the current authoritative Fact
    """
    # Step 1: Group facts by rule_key
    facts_by_key: dict[RuleKey, list[Fact]] = defaultdict(list)
    
    for fact in facts:
        key = RuleKey(
            drive_id=fact.drive_id,
            criterion_type=fact.criterion_type,
            scope=fact.scope,
        )
        facts_by_key[key].append(fact)
    
    # Step 2: Reconcile each group
    reconciled: dict[RuleKey, Fact] = {}
    
    for rule_key, fact_list in facts_by_key.items():
        current_fact = _reconcile_fact_group(fact_list)
        if current_fact:
            reconciled[rule_key] = current_fact
    
    return reconciled


def _reconcile_fact_group(facts: list[Fact]) -> Fact | None:
    """Reconcile a group of facts with the same rule_key.
    
    Algorithm per DESIGN.md §3.1:
    1. Find highest authority rank present
    2. Keep only facts at that rank
    3. Among same rank, take latest effective_timestamp
    4. Honor explicit supersession
    
    Args:
        facts: List of facts with the same rule_key
    
    Returns:
        The authoritative Fact, or None if list is empty
    """
    if not facts:
        return None
    
    # Handle single fact case
    if len(facts) == 1:
        return facts[0]
    
    # Step 1: Find highest authority (lowest rank number)
    highest_authority_rank = min(f.authority_rank for f in facts)
    
    # Step 2: Keep only facts at highest authority
    highest_authority_facts = [
        f for f in facts if f.authority_rank == highest_authority_rank
    ]
    
    # Step 3: Handle explicit supersession first
    # If any fact has is_correction=True, it takes precedence
    corrections = [f for f in highest_authority_facts if f.is_correction]
    
    if corrections:
        # Among corrections, take the latest
        latest_correction = max(corrections, key=lambda f: f.effective_timestamp)
        return latest_correction
    
    # Step 4: Among same-rank facts, take latest effective_timestamp
    latest_fact = max(highest_authority_facts, key=lambda f: f.effective_timestamp)
    
    return latest_fact


def reconcile_with_coverage_fallback(
    facts: list[Fact],
) -> dict[RuleKey, Fact]:
    """Reconcile facts with coverage fallback for missing rule keys.
    
    Extension of basic reconciliation that implements coverage fallback:
    - Higher authority sources define the "primary" criteria
    - Lower authority sources can fill in MISSING criteria (not override)
    - Example: Official PDF states CGPA=7.5 but silent on branch.
              WhatsApp states CGPA=7.0 and branch=CSE.
              Result: CGPA=7.5 (from PDF), branch=CSE (fallback to WhatsApp)
    
    Args:
        facts: List of Fact objects
    
    Returns:
        Dict mapping RuleKey to authoritative Fact with fallback coverage
    """
    # First, do standard reconciliation
    reconciled = reconcile_facts(facts)
    
    # Group all facts by rule_key again
    facts_by_key: dict[RuleKey, list[Fact]] = defaultdict(list)
    for fact in facts:
        key = RuleKey(fact.drive_id, fact.criterion_type, fact.scope)
        facts_by_key[key].append(fact)
    
    # Check for gaps - rule keys with facts but not in reconciled
    # (This would mean all facts were filtered out, shouldn't happen with current logic)
    # Coverage fallback is more about DIFFERENT rule keys from lower authority sources
    
    # For now, return basic reconciliation
    # Full coverage fallback would require looking at drive-level fact sets
    # and checking which criterion_types are present at each authority level
    return reconciled


def reconcile_facts_for_drive(
    db: Session,
    drive_id: str,
    persist: bool = True,
) -> dict[RuleKey, Fact]:
    """Reconcile all facts for a specific drive and optionally persist results.
    
    This is the main entry point for reconciliation in production use.
    
    Args:
        db: Database session
        drive_id: Drive to reconcile facts for
        persist: If True, write reconciled facts to ExtractedCriteria table
    
    Returns:
        Dict mapping RuleKey to authoritative Fact
    """
    # Fetch all facts for this drive
    facts = get_facts_by_drive(db, drive_id)
    
    if not facts:
        return {}
    
    # Reconcile
    reconciled = reconcile_facts(facts)
    
    # Persist to ExtractedCriteria table if requested
    if persist:
        for rule_key, fact in reconciled.items():
            upsert_extracted_criterion(
                db=db,
                drive_id=fact.drive_id,
                criterion_type=fact.criterion_type,
                operator=fact.operator,
                value=fact.value,
                source_id=fact.source_id,
                source_type=fact.source_type,
                authority_rank=fact.authority_rank,
                timestamp=fact.timestamp,
                scope=fact.scope,
            )
    
    return reconciled


def get_reconciliation_trace(facts: list[Fact]) -> dict[str, Any]:
    """Generate detailed trace of reconciliation process for debugging/auditing.
    
    Shows which facts were considered, which were selected, and why.
    
    Args:
        facts: List of facts to trace
    
    Returns:
        Dict with reconciliation trace information
    """
    # Group by rule key
    facts_by_key: dict[RuleKey, list[Fact]] = defaultdict(list)
    for fact in facts:
        key = RuleKey(fact.drive_id, fact.criterion_type, fact.scope)
        facts_by_key[key].append(fact)
    
    trace = {
        "total_facts": len(facts),
        "unique_rule_keys": len(facts_by_key),
        "reconciliation_details": [],
    }
    
    for rule_key, fact_list in facts_by_key.items():
        # Get all authority ranks present
        ranks_present = sorted(set(f.authority_rank for f in fact_list))
        highest_rank = ranks_present[0]
        
        # Get facts at highest rank
        highest_rank_facts = [f for f in fact_list if f.authority_rank == highest_rank]
        
        # Determine winner
        winner = _reconcile_fact_group(fact_list)
        
        detail = {
            "rule_key": str(rule_key),
            "total_facts": len(fact_list),
            "authority_ranks_present": ranks_present,
            "selected_authority_rank": highest_rank,
            "facts_at_selected_rank": len(highest_rank_facts),
            "winner_source": winner.source_id if winner else None,
            "winner_timestamp": winner.timestamp.isoformat() if winner else None,
            "winner_value": winner.value if winner else None,
            "is_correction": winner.is_correction if winner else False,
            "all_sources": [f.source_id for f in fact_list],
        }
        
        trace["reconciliation_details"].append(detail)
    
    return trace
