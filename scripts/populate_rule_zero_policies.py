#!/usr/bin/env python3
"""
Populate Rule Zero Policies Table

This script populates the rule_zero_policies table with policies derived from
the Rule Zero manifesto and current project context.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, Any

# Rule Zero Policies derived from the manifesto
RULE_ZERO_POLICIES = [
    {
        "policy_name": "core_trust_law",
        "policy_type": "foundational",
        "description": "Every output must be traceable to its source, understandable in its logic, and defensible in its action",
        "policy_json": {
            "rule": "Rule Zero",
            "requirements": [
                "No hallucinations",
                "No black boxes", 
                "No silent actions",
                "Only explainable cognition earns trust"
            ],
            "enforcement": "mandatory"
        },
        "enforcement_rank": 10,
        "last_updated": datetime.now().isoformat()
    },
    {
        "policy_name": "reasoning_chain",
        "policy_type": "audit",
        "description": "Every Sigil-aware action must follow the Reasoning Chain: Input → Context → Reasoning → Suggestion → Verdict → Audit → IRL Score",
        "policy_json": {
            "chain_components": [
                "Input - What was submitted by the user or system",
                "Context - What Canon or Nexus informed this response", 
                "Reasoning - Why this path was chosen, with logic trace",
                "Suggestion - What the system proposes or performs",
                "Verdict - The trust boundary crossed: Allow, Deny, Defer, Flag",
                "Audit - Who triggered it, when, and with what authority",
                "IRL Score - A numerical measure of confidence and ethical alignment"
            ],
            "enforcement": "mandatory"
        },
        "enforcement_rank": 9,
        "last_updated": datetime.now().isoformat()
    },
    {
        "policy_name": "canon_memory_scope",
        "policy_type": "data_governance",
        "description": "Memory is schema-bound and LOA-scoped via mnemonic validation. No inference occurs without memory; no memory is accessed without clearance",
        "policy_json": {
            "memory_rules": [
                "Schema-bound access control",
                "LOA-scoped validation",
                "Mnemonic validation required",
                "No inference without memory",
                "No memory access without clearance"
            ],
            "enforcement": "mandatory"
        },
        "enforcement_rank": 8,
        "last_updated": datetime.now().isoformat()
    },
    {
        "policy_name": "irl_integrity_layer",
        "policy_type": "reasoning",
        "description": "IRL performs real-time, traceable reasoning against Canon and policy with justification, confidence score, and explanation",
        "policy_json": {
            "irl_requirements": [
                "Real-time reasoning",
                "Traceable to Canon and policy",
                "Justification for every action",
                "Confidence score for audit",
                "Explanation for devs/users",
                "Cryptographically grounded enforcement"
            ],
            "enforcement": "mandatory"
        },
        "enforcement_rank": 9,
        "last_updated": datetime.now().isoformat()
    },
    {
        "policy_name": "enforcement_reproducibility",
        "policy_type": "enforcement",
        "description": "Every decision must be reproducible, explainable, bound to input/Canon/memory scope, and signed by runtime authority",
        "policy_json": {
            "enforcement_requirements": [
                "Reproducible decisions",
                "Explainable logic",
                "Bound to input, Canon, and memory scope",
                "Signed by runtime authority",
                "No hallucination - only audit and justification"
            ],
            "enforcement": "mandatory"
        },
        "enforcement_rank": 10,
        "last_updated": datetime.now().isoformat()
    },
    {
        "policy_name": "trust_score_calculation",
        "policy_type": "scoring",
        "description": "IRL confidence score affected by Canon alignment, context consistency, memory scope integrity, and LLM volatility",
        "policy_json": {
            "score_factors": [
                "Canon alignment",
                "Context consistency", 
                "Memory scope integrity",
                "LLM volatility (if applicable)"
            ],
            "score_actions": {
                "low_scores": "defer or flag actions",
                "high_scores": "reinforce trust"
            },
            "enforcement": "mandatory"
        },
        "enforcement_rank": 7,
        "last_updated": datetime.now().isoformat()
    },
    {
        "policy_name": "sigil_protocol_foundation",
        "policy_type": "philosophical",
        "description": "Sigil is a protocol, not a product. It is not meant to be owned, but used correctly. There is no trust without trace.",
        "policy_json": {
            "core_principles": [
                "Sigil is a protocol, not a product",
                "Not meant to be owned, but used correctly", 
                "No trust without trace",
                "Foundation of Codex"
            ],
            "enforcement": "guidance"
        },
        "enforcement_rank": 5,
        "last_updated": datetime.now().isoformat()
    }
]

def populate_rule_zero_policies():
    """Populate the rule_zero_policies table with Rule Zero policies"""
    
    db_path = "sigil_rag_cache.db"
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Clear existing policies
        cursor.execute("DELETE FROM rule_zero_policies")
        
        # Insert new policies
        for policy in RULE_ZERO_POLICIES:
            cursor.execute("""
                INSERT INTO rule_zero_policies 
                (policy_name, policy_type, description, policy_json, enforcement_rank, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                policy["policy_name"],
                policy["policy_type"], 
                policy["description"],
                json.dumps(policy["policy_json"]),
                policy["enforcement_rank"],
                policy["last_updated"]
            ))
        
        conn.commit()
        print(f"Populated {len(RULE_ZERO_POLICIES)} Rule Zero policies")
        
        # Verify insertion
        cursor.execute("SELECT COUNT(*) FROM rule_zero_policies")
        count = cursor.fetchone()[0]
        print(f"Total policies in database: {count}")
        
    except Exception as e:
        print(f"Error populating policies: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    populate_rule_zero_policies() 