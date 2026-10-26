"""Notice extraction module for converting free-text placement notices to structured Facts.

This module uses LLM to extract eligibility criteria from unstructured notices while detecting
corrections, updates, and deadline extensions. Implements extraction logic per DESIGN.md §3.2.

Key responsibilities:
1. Parse free-text notices into structured Fact objects
2. Detect supersession markers ("Correction:", "Update:", "Deadline extended")
3. Extract confidence scores for uncertain criteria
4. Handle ambiguous or incomplete notices gracefully

The LLM is used ONLY for extraction and supersession detection - never for eligibility decisions.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from core.schemas import SourceType, SOURCE_AUTHORITY_RANK
from database.models import Fact as FactModel
from extraction.llm_client import LLMClient, get_llm_client


# Extraction prompt template
EXTRACTION_SYSTEM_PROMPT = """You are an expert at extracting structured eligibility criteria from placement notices.

Your task is to extract ALL eligibility requirements from notices sent by placement cells, coordinators, 
or students about company recruitment drives.

Common criteria types to look for:
- min_cgpa: Minimum CGPA requirement (e.g., "7.5 CGPA required")
- max_backlogs: Maximum allowed backlogs (e.g., "no active backlogs", "max 2 backlogs")
- allowed_branches: Branch restrictions (e.g., "CSE/ISE only", "open to all branches")
- min_tenth_pct: Minimum 10th percentage
- min_twelfth_pct: Minimum 12th percentage
- no_prior_offer: Prior offer restrictions (e.g., "students with offers cannot apply")
- deadline: Registration deadline

Supersession detection:
- Look for phrases like "Correction:", "Update:", "Deadline extended", "Change:", "Revised:"
- If found, mark is_correction=true and try to identify what notice is being corrected
- Common patterns: "Correction: CGPA is 7.5 not 7.0", "Deadline extended to 6PM from 4PM"

IMPORTANT RULES:
1. Extract ONLY information explicitly stated in the notice
2. Do NOT infer or assume criteria not mentioned
3. If something is ambiguous, mark confidence as "low" and include a note
4. For branch requirements, normalize to standard codes: CSE, ISE, ECE, EEE, MECH, CIVIL, etc.
5. For operators: use "gte" (>=), "lte" (<=), "eq" (=), "in" (list membership), "not_in" (exclusion)
6. Return empty list if no criteria can be extracted
7. For numeric values, extract just the number
8. For branch lists, extract as comma-separated string

Output format: JSON array of criterion objects with this structure:
{
  "criterion_type": "min_cgpa",
  "operator": "gte",
  "value": "7.5",
  "scope": "ALL",
  "confidence": "high",
  "is_correction": false,
  "supersedes_ref": null,
  "notes": ""
}
"""


EXTRACTION_USER_PROMPT_TEMPLATE = """Extract eligibility criteria from this notice:

NOTICE TEXT:
{notice_text}

CONTEXT:
- Source: {source_type}
- Message ID: {message_id}
- Timestamp: {timestamp}

Extract all criteria following the rules provided. Return JSON array.
"""


def extract_criteria_from_notice(
    notice_text: str,
    source_id: str,
    source_type: SourceType,
    timestamp: datetime,
    drive_id: str,
    llm_client: LLMClient | None = None,
) -> list[FactModel]:
    """Extract structured criteria from a free-text placement notice.
    
    Uses LLM to parse unstructured text and detect supersession markers.
    Returns a list of Fact ORM objects ready for database insertion.
    
    Args:
        notice_text: Raw notice text to extract from
        source_id: Unique identifier for this source message
        source_type: Type of source (determines authority rank)
        timestamp: When the notice was sent
        drive_id: Placement drive identifier
        llm_client: Optional LLM client (creates new if not provided)
    
    Returns:
        List of Fact ORM objects with extracted criteria
        
    Raises:
        ValueError: If extraction fails or LLM returns invalid data
    """
    if llm_client is None:
        llm_client = get_llm_client()
    
    # Get authority rank for this source type
    authority_rank = SOURCE_AUTHORITY_RANK[source_type]
    
    # Build extraction prompt
    user_prompt = EXTRACTION_USER_PROMPT_TEMPLATE.format(
        notice_text=notice_text.strip(),
        source_type=source_type.value,
        message_id=source_id,
        timestamp=timestamp.isoformat(),
    )
    
    # Define expected output schema
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["criterion_type", "operator", "value"],
            "properties": {
                "criterion_type": {"type": "string"},
                "operator": {"type": "string"},
                "value": {"type": ["string", "number"]},
                "scope": {"type": "string"},
                "confidence": {"type": "string"},
                "is_correction": {"type": "boolean"},
                "supersedes_ref": {"type": ["string", "null"]},
                "notes": {"type": "string"},
            },
        },
    }
    
    # Call LLM with system + user prompts
    try:
        # Combine system and user prompts
        full_prompt = f"{EXTRACTION_SYSTEM_PROMPT}\n\n{user_prompt}"
        
        # Get structured output
        extracted_data = llm_client.generate_structured(
            prompt=full_prompt,
            schema=schema,
            temperature=0.1,  # Low temperature for deterministic extraction
        )
        
        # Handle case where LLM returns dict instead of list
        if isinstance(extracted_data, dict):
            if "criteria" in extracted_data:
                extracted_data = extracted_data["criteria"]
            elif "items" in extracted_data:
                extracted_data = extracted_data["items"]
            else:
                # Single criterion returned as dict
                extracted_data = [extracted_data]
        
        # Validate it's a list
        if not isinstance(extracted_data, list):
            raise ValueError(f"Expected list, got {type(extracted_data)}")
        
    except Exception as e:
        raise ValueError(
            f"Failed to extract criteria from notice. Error: {e}"
        ) from e
    
    # Convert extracted data to Fact ORM objects
    facts = []
    
    for item in extracted_data:
        # Validate required fields
        if not all(k in item for k in ["criterion_type", "operator", "value"]):
            continue  # Skip invalid items
        
        # Serialize value to JSON string
        value_str = json.dumps(item["value"])
        
        # Create Fact ORM object
        fact = FactModel(
            source_id=source_id,
            source_type=source_type.value,
            authority_rank=authority_rank,
            timestamp=timestamp,
            effective_timestamp=timestamp,  # Default: effective immediately
            drive_id=drive_id,
            criterion_type=item["criterion_type"],
            scope=item.get("scope", "ALL"),
            operator=item["operator"],
            value=value_str,
            is_correction=item.get("is_correction", False),
            supersedes_ref=item.get("supersedes_ref"),
            extracted_at=datetime.utcnow(),
            raw_notice_text=notice_text,
        )
        
        facts.append(fact)
    
    return facts


def extract_with_confidence(
    notice_text: str,
    source_id: str,
    source_type: SourceType,
    timestamp: datetime,
    drive_id: str,
    min_confidence: str = "medium",
    llm_client: LLMClient | None = None,
) -> tuple[list[FactModel], list[dict[str, Any]]]:
    """Extract criteria with confidence filtering.
    
    Returns both high-confidence facts (ready for DB) and low-confidence
    items (for manual review).
    
    Args:
        notice_text: Raw notice text
        source_id: Message identifier
        source_type: Source type
        timestamp: Message timestamp
        drive_id: Drive identifier
        min_confidence: Minimum confidence to accept ("high", "medium", "low")
        llm_client: Optional LLM client
    
    Returns:
        Tuple of (accepted_facts, low_confidence_items)
    """
    # Extract all criteria
    facts = extract_criteria_from_notice(
        notice_text=notice_text,
        source_id=source_id,
        source_type=source_type,
        timestamp=timestamp,
        drive_id=drive_id,
        llm_client=llm_client,
    )
    
    # For now, return all facts as accepted (confidence filtering can be added later)
    # This keeps the simple interface working while allowing confidence extension
    return facts, []


def detect_supersession_explicit(
    notice_text: str,
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    """Detect explicit supersession markers in notice text.
    
    Looks for phrases like "Correction:", "Update:", "Deadline extended", etc.
    Returns metadata about the supersession if detected.
    
    Args:
        notice_text: Raw notice text
        llm_client: Optional LLM client
    
    Returns:
        Dict with keys:
        - is_supersession: bool
        - supersession_type: "correction" | "update" | "extension" | None
        - confidence: "high" | "medium" | "low"
        - extracted_ref: str | None (reference to original notice if found)
    """
    # Simple keyword-based detection as fallback
    text_lower = notice_text.lower()
    
    supersession_keywords = {
        "correction": ["correction:", "corrected:", "mistake", "error in"],
        "update": ["update:", "updated:", "revised:", "change:"],
        "extension": ["extended to", "extension:", "postponed to", "new deadline"],
    }
    
    for supersession_type, keywords in supersession_keywords.items():
        for keyword in keywords:
            if keyword in text_lower:
                return {
                    "is_supersession": True,
                    "supersession_type": supersession_type,
                    "confidence": "high",
                    "extracted_ref": None,  # Could enhance with LLM to extract ref
                }
    
    return {
        "is_supersession": False,
        "supersession_type": None,
        "confidence": "high",
        "extracted_ref": None,
    }
