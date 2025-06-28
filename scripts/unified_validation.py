#!/usr/bin/env python3
"""
Unified Validation Script

This script consolidates all validation functionality into a single,
comprehensive validation system for the Sigil Protocol implementation.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Any

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rust_crate_pipeline.config import PipelineConfig
from rust_crate_pipeline.core import CanonRegistry, IRLEngine
from rust_crate_pipeline.unified_pipeline import UnifiedSigilPipeline


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('validation.log')
        ]
    )


def validate_rule_zero_compliance() -> Dict[str, Any]:
    """Validate Rule Zero compliance across the system"""
    logger = logging.getLogger(__name__)
    logger.info("🔍 Validating Rule Zero compliance...")
    
    validation_results = {
        "rule_zero_compliant": True,
        "checks": [],
        "errors": [],
        "warnings": []
    }
    
    try:
        # Check 1: Sacred Chain traceability
        logger.info("Checking Sacred Chain traceability...")
        config = PipelineConfig()
        irl_engine = IRLEngine(config)
        
        # Verify execution ID generation
        execution_id = irl_engine.generate_execution_id("test-crate")
        if "exec-" in execution_id and len(execution_id) > 20:
            validation_results["checks"].append({
                "name": "execution_id_generation",
                "status": "PASS",
                "description": "Execution IDs are properly generated"
            })
        else:
            validation_results["checks"].append({
                "name": "execution_id_generation",
                "status": "FAIL",
                "description": "Execution ID format is invalid"
            })
            validation_results["rule_zero_compliant"] = False
            validation_results["errors"].append("Invalid execution ID format")
        
        # Check 2: Canon Registry integrity
        logger.info("Checking Canon Registry integrity...")
        canon_registry = CanonRegistry()
        valid_sources = canon_registry.get_valid_canon_sources()
        
        if len(valid_sources) > 0:
            validation_results["checks"].append({
                "name": "canon_registry_integrity",
                "status": "PASS",
                "description": f"Canon registry has {len(valid_sources)} valid sources"
            })
        else:
            validation_results["checks"].append({
                "name": "canon_registry_integrity",
                "status": "FAIL",
                "description": "No valid canon sources found"
            })
            validation_results["rule_zero_compliant"] = False
            validation_results["errors"].append("No valid canon sources")
        
        # Check 3: Audit trail generation
        logger.info("Checking audit trail generation...")
        audit_summary = irl_engine.get_audit_summary()
        
        if isinstance(audit_summary, dict) and "total_executions" in audit_summary:
            validation_results["checks"].append({
                "name": "audit_trail_generation",
                "status": "PASS",
                "description": "Audit trail generation is working"
            })
        else:
            validation_results["checks"].append({
                "name": "audit_trail_generation",
                "status": "FAIL",
                "description": "Audit trail generation failed"
            })
            validation_results["rule_zero_compliant"] = False
            validation_results["errors"].append("Audit trail generation failed")
        
        # Check 4: Configuration validation
        logger.info("Checking configuration validation...")
        if config.max_retries > 0 and config.n_workers > 0:
            validation_results["checks"].append({
                "name": "configuration_validation",
                "status": "PASS",
                "description": "Configuration parameters are valid"
            })
        else:
            validation_results["checks"].append({
                "name": "configuration_validation",
                "status": "FAIL",
                "description": "Invalid configuration parameters"
            })
            validation_results["rule_zero_compliant"] = False
            validation_results["errors"].append("Invalid configuration parameters")
        
        logger.info("✅ Rule Zero compliance validation completed")
        
    except Exception as e:
        logger.error(f"❌ Rule Zero validation failed: {e}")
        validation_results["rule_zero_compliant"] = False
        validation_results["errors"].append(f"Validation exception: {str(e)}")
    
    return validation_results


def validate_database_hash() -> Dict[str, Any]:
    """Validate database hash integrity"""
    logger = logging.getLogger(__name__)
    logger.info("🔍 Validating database hash integrity...")
    
    validation_results = {
        "database_hash_valid": True,
        "checks": [],
        "errors": [],
        "warnings": []
    }
    
    try:
        # Check for database files
        db_files = [
            "sigil_rag_cache.db",
            "sigil_rag_cache.hash",
            "sigil_rag_cache.sql"
        ]
        
        for db_file in db_files:
            file_path = Path(db_file)
            if file_path.exists():
                file_size = file_path.stat().st_size
                validation_results["checks"].append({
                    "name": f"db_file_exists_{db_file}",
                    "status": "PASS",
                    "description": f"Database file {db_file} exists ({file_size} bytes)"
                })
            else:
                validation_results["checks"].append({
                    "name": f"db_file_exists_{db_file}",
                    "status": "WARN",
                    "description": f"Database file {db_file} not found"
                })
                validation_results["warnings"].append(f"Database file {db_file} not found")
        
        # Check hash file integrity
        hash_file = Path("sigil_rag_cache.hash")
        if hash_file.exists():
            try:
                with open(hash_file, "r") as f:
                    hash_content = f.read().strip()
                
                if len(hash_content) == 64:  # SHA-256 hash length
                    validation_results["checks"].append({
                        "name": "hash_file_integrity",
                        "status": "PASS",
                        "description": "Hash file contains valid SHA-256 hash"
                    })
                else:
                    validation_results["checks"].append({
                        "name": "hash_file_integrity",
                        "status": "FAIL",
                        "description": "Hash file contains invalid hash format"
                    })
                    validation_results["database_hash_valid"] = False
                    validation_results["errors"].append("Invalid hash format")
            except Exception as e:
                validation_results["checks"].append({
                    "name": "hash_file_integrity",
                    "status": "FAIL",
                    "description": f"Failed to read hash file: {e}"
                })
                validation_results["database_hash_valid"] = False
                validation_results["errors"].append(f"Hash file read error: {e}")
        else:
            validation_results["checks"].append({
                "name": "hash_file_integrity",
                "status": "WARN",
                "description": "Hash file not found"
            })
            validation_results["warnings"].append("Hash file not found")
        
        logger.info("✅ Database hash validation completed")
        
    except Exception as e:
        logger.error(f"❌ Database hash validation failed: {e}")
        validation_results["database_hash_valid"] = False
        validation_results["errors"].append(f"Validation exception: {str(e)}")
    
    return validation_results


def validate_pipeline_integration() -> Dict[str, Any]:
    """Validate pipeline integration"""
    logger = logging.getLogger(__name__)
    logger.info("🔍 Validating pipeline integration...")
    
    validation_results = {
        "pipeline_integration_valid": True,
        "checks": [],
        "errors": [],
        "warnings": []
    }
    
    try:
        # Test pipeline initialization
        config = PipelineConfig()
        pipeline = UnifiedSigilPipeline(config)
        
        validation_results["checks"].append({
            "name": "pipeline_initialization",
            "status": "PASS",
            "description": "Pipeline initialized successfully"
        })
        
        # Test pipeline summary generation
        summary = pipeline.get_pipeline_summary()
        if isinstance(summary, dict) and "pipeline_status" in summary:
            validation_results["checks"].append({
                "name": "pipeline_summary_generation",
                "status": "PASS",
                "description": "Pipeline summary generation working"
            })
        else:
            validation_results["checks"].append({
                "name": "pipeline_summary_generation",
                "status": "FAIL",
                "description": "Pipeline summary generation failed"
            })
            validation_results["pipeline_integration_valid"] = False
            validation_results["errors"].append("Pipeline summary generation failed")
        
        # Test component initialization
        components = summary.get("components", {})
        for component, initialized in components.items():
            if initialized:
                validation_results["checks"].append({
                    "name": f"component_{component}",
                    "status": "PASS",
                    "description": f"Component {component} initialized successfully"
                })
            else:
                validation_results["checks"].append({
                    "name": f"component_{component}",
                    "status": "WARN",
                    "description": f"Component {component} not initialized"
                })
                validation_results["warnings"].append(f"Component {component} not initialized")
        
        logger.info("✅ Pipeline integration validation completed")
        
    except Exception as e:
        logger.error(f"❌ Pipeline integration validation failed: {e}")
        validation_results["pipeline_integration_valid"] = False
        validation_results["errors"].append(f"Validation exception: {str(e)}")
    
    return validation_results


def run_comprehensive_validation(verbose: bool = False) -> Dict[str, Any]:
    """Run comprehensive validation of the entire system"""
    setup_logging(verbose)
    logger = logging.getLogger(__name__)
    
    logger.info("🚀 Starting comprehensive validation...")
    
    comprehensive_results = {
        "validation_timestamp": None,
        "overall_status": "PASS",
        "rule_zero_compliance": None,
        "database_hash_validation": None,
        "pipeline_integration": None,
        "summary": {
            "total_checks": 0,
            "passed_checks": 0,
            "failed_checks": 0,
            "warnings": 0,
            "errors": 0
        }
    }
    
    try:
        import time
        comprehensive_results["validation_timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Run all validation checks
        rule_zero_results = validate_rule_zero_compliance()
        db_hash_results = validate_database_hash()
        pipeline_results = validate_pipeline_integration()
        
        comprehensive_results["rule_zero_compliance"] = rule_zero_results
        comprehensive_results["database_hash_validation"] = db_hash_results
        comprehensive_results["pipeline_integration"] = pipeline_results
        
        # Aggregate results
        all_checks = []
        all_errors = []
        all_warnings = []
        
        for result_set in [rule_zero_results, db_hash_results, pipeline_results]:
            all_checks.extend(result_set.get("checks", []))
            all_errors.extend(result_set.get("errors", []))
            all_warnings.extend(result_set.get("warnings", []))
        
        comprehensive_results["summary"]["total_checks"] = len(all_checks)
        comprehensive_results["summary"]["passed_checks"] = len([c for c in all_checks if c["status"] == "PASS"])
        comprehensive_results["summary"]["failed_checks"] = len([c for c in all_checks if c["status"] == "FAIL"])
        comprehensive_results["summary"]["warnings"] = len(all_warnings)
        comprehensive_results["summary"]["errors"] = len(all_errors)
        
        # Determine overall status
        if comprehensive_results["summary"]["failed_checks"] > 0 or comprehensive_results["summary"]["errors"] > 0:
            comprehensive_results["overall_status"] = "FAIL"
        elif comprehensive_results["summary"]["warnings"] > 0:
            comprehensive_results["overall_status"] = "WARN"
        
        logger.info(f"✅ Comprehensive validation completed: {comprehensive_results['overall_status']}")
        logger.info(f"📊 Summary: {comprehensive_results['summary']['passed_checks']}/{comprehensive_results['summary']['total_checks']} checks passed")
        
    except Exception as e:
        logger.error(f"❌ Comprehensive validation failed: {e}")
        comprehensive_results["overall_status"] = "ERROR"
        comprehensive_results["summary"]["errors"] += 1
    
    return comprehensive_results


def main() -> None:
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Unified Validation Script for Sigil Protocol")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--output", "-o", type=str, help="Output file for validation results")
    parser.add_argument("--rule-zero-only", action="store_true", help="Run only Rule Zero compliance validation")
    parser.add_argument("--db-hash-only", action="store_true", help="Run only database hash validation")
    parser.add_argument("--pipeline-only", action="store_true", help="Run only pipeline integration validation")
    
    args = parser.parse_args()
    
    try:
        if args.rule_zero_only:
            results = validate_rule_zero_compliance()
        elif args.db_hash_only:
            results = validate_database_hash()
        elif args.pipeline_only:
            results = validate_pipeline_integration()
        else:
            results = run_comprehensive_validation(args.verbose)
        
        # Output results
        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2)
            print(f"📄 Validation results saved to: {args.output}")
        else:
            print(json.dumps(results, indent=2))
        
        # Exit with appropriate code
        if results.get("overall_status") == "FAIL" or results.get("rule_zero_compliant") == False:
            sys.exit(1)
        elif results.get("overall_status") == "WARN":
            sys.exit(2)
        else:
            sys.exit(0)
            
    except Exception as e:
        print(f"❌ Validation script failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 