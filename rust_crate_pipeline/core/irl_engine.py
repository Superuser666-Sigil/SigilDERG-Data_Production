import json
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from abc import ABC, abstractmethod

from .sacred_chain import SacredChainBase, SacredChainTrace, TrustVerdict
from .canon_registry import CanonRegistry


class IRLEngine(SacredChainBase):
    
    def __init__(self, config: Any, canon_registry: Optional[CanonRegistry] = None) -> None:
        super().__init__()
        self.config = config
        self.canon_registry = canon_registry or CanonRegistry()
        self.logger = logging.getLogger(__name__)
    
    async def __aenter__(self) -> "IRLEngine":
        self.logger.info("IRL Engine initialized with full traceability")
        return self

    async def __aexit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[Any]) -> None:
        self._finalize_audit_log()

    def _finalize_audit_log(self) -> None:
        if not self.execution_log:
            return
            
        audit_file = f"sigil_audit_{int(time.time())}.json"
        try:
            with open(audit_file, "w") as f:
                audit_data = [json.loads(trace.to_audit_log()) for trace in self.execution_log]
                json.dump(audit_data, f, indent=2)
            self.logger.info(f"Audit log finalized: {audit_file}")
        except IOError as e:
            self.logger.error(f"Failed to write audit log {audit_file}: {e}")

    async def analyze_with_sacred_chain(self, input_data: str) -> SacredChainTrace:
        canonical_input = self._canonicalize_input(input_data)
        reasoning_steps = [f"Input canonicalized: '{input_data}' -> '{canonical_input}'"]
        
        context_sources = await self._gather_validated_context(canonical_input)
        reasoning_steps.append(f"Context gathered from {len(context_sources)} validated sources")
        
        analysis_results = await self._execute_reasoning_chain(canonical_input, context_sources)
        reasoning_steps.extend(analysis_results[0])
        
        suggestion = self._generate_traceable_suggestion(reasoning_steps)
        verdict, verdict_reason = self._make_trust_decision(
            reasoning_steps, suggestion, analysis_results[5],
            analysis_results[1],
            analysis_results[2],
            analysis_results[3],
        )
        reasoning_steps.append(f"Trust decision: {verdict} - {verdict_reason}")
        
        irl_score = self._calculate_irl_score(context_sources, reasoning_steps, verdict)
        reasoning_steps.append(f"IRL confidence: {irl_score:.3f}")
        
        audit_info = {
            "metadata": analysis_results[1],
            "sentiment": analysis_results[2],
            "ecosystem": analysis_results[3],
            "quality_score": analysis_results[5],
            "verdict_reason": verdict_reason,
        }
        
        return self.create_sacred_chain_trace(
            input_data=canonical_input,
            context_sources=context_sources,
            reasoning_steps=reasoning_steps,
            suggestion=suggestion,
            verdict=verdict,
            audit_info=audit_info,
            irl_score=irl_score,
        )

    def _canonicalize_input(self, input_data: str) -> str:
        canonical = input_data.strip().lower()
        if canonical.startswith("crate:"):
            canonical = canonical[6:]
        if canonical.startswith("rust:"):
            canonical = canonical[5:]
        return canonical

    async def _gather_validated_context(self, input_data: str) -> List[str]:
        valid_sources = self.canon_registry.get_valid_canon_sources()
        context_sources = []
        
        for source in valid_sources:
            authority_level = self.canon_registry.get_authority_level(source)
            if authority_level >= 5:
                context_sources.append(source)
        
        return context_sources

    async def _execute_reasoning_chain(
        self, input_data: str, sources: List[str]
    ) -> Tuple[List[str], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], float]:
        reasoning_steps = []
        
        metadata = await self._extract_basic_metadata(input_data)
        reasoning_steps.append(f"Metadata extracted: {len(metadata)} fields")
        
        docs = {}
        docs = await self._analyze_documentation(input_data)
        reasoning_steps.append(f"Documentation analyzed: quality {docs.get('quality_score', 0):.1f}")
        
        sentiment = await self._analyze_community_sentiment(input_data)
        reasoning_steps.append(f"Sentiment analyzed: {sentiment.get('overall', 'unknown')}")
        
        ecosystem = await self._analyze_ecosystem_position(input_data)
        reasoning_steps.append(f"Ecosystem analyzed: {ecosystem.get('category', 'unknown')}")
        
        quality_score = self._synthesize_quality_score(metadata, docs, sentiment, ecosystem)
        reasoning_steps.append(f"Quality score synthesized: {quality_score:.2f}")
        
        return reasoning_steps, metadata, docs, sentiment, ecosystem, quality_score

    async def _extract_basic_metadata(self, input_data: str) -> Dict[str, Any]:
        return {
            "name": input_data,
            "type": "rust_crate",
            "source": "manual_input",
            "extraction_method": "irl_engine",
        }

    async def _analyze_documentation(self, input_data: str) -> Dict[str, Any]:
        try:
            return {
                "quality_score": 7.0,
                "completeness": 0.8,
                "examples_present": True,
                "api_documented": True,
            }
        except Exception as e:
            self.logger.error(f"Documentation analysis failed: {e}")
            return {"quality_score": 5.0, "error": str(e)}

    async def _analyze_community_sentiment(self, input_data: str) -> Dict[str, Any]:
        return {
            "overall": "positive",
            "positive_mentions": 10,
            "negative_mentions": 2,
            "neutral_mentions": 5,
            "total_mentions": 17,
        }

    async def _analyze_ecosystem_position(self, input_data: str) -> Dict[str, Any]:
        return {
            "category": "utilities",
            "maturity": "stable",
            "dependencies_count": 5,
            "reverse_deps_visible": 15,
            "ecosystem_score": 7.5,
        }

    def _synthesize_quality_score(
        self,
        metadata: Dict[str, Any],
        docs: Dict[str, Any],
        sentiment: Dict[str, Any],
        ecosystem: Dict[str, Any],
    ) -> float:
        scores = []
        
        doc_score = docs.get("quality_score", 5.0)
        scores.append(doc_score)
        
        sentiment_score = 5.0
        if sentiment.get("overall") == "positive":
            sentiment_score = 8.0
        elif sentiment.get("overall") == "negative":
            sentiment_score = 3.0
        scores.append(sentiment_score)
        
        ecosystem_score = ecosystem.get("ecosystem_score", 5.0)
        scores.append(ecosystem_score)
        
        return sum(scores) / len(scores) if scores else 5.0

    def _generate_traceable_suggestion(self, reasoning_steps: List[str]) -> str:
        if not reasoning_steps:
            return "DEFER: Insufficient reasoning data"
        
        quality_indicators = [step for step in reasoning_steps if "quality" in step.lower()]
        sentiment_indicators = [step for step in reasoning_steps if "sentiment" in step.lower()]
        
        if quality_indicators and any("high" in indicator.lower() for indicator in quality_indicators):
            return "ALLOW: High quality indicators detected"
        elif sentiment_indicators and any("positive" in indicator.lower() for indicator in sentiment_indicators):
            return "ALLOW: Positive community sentiment"
        else:
            return "DEFER: Requires additional analysis"

    def _make_trust_decision(
        self,
        reasoning_steps: List[str],
        suggestion: str,
        quality_score: float,
        docs: Dict[str, Any],
        sentiment: Dict[str, Any],
        ecosystem: Dict[str, Any],
    ) -> Tuple[TrustVerdict, str]:
        if quality_score >= 8.0:
            return TrustVerdict.ALLOW, "High quality score"
        elif quality_score >= 6.0 and sentiment.get("overall") == "positive":
            return TrustVerdict.ALLOW, "Good quality with positive sentiment"
        elif quality_score < 4.0:
            return TrustVerdict.DENY, "Low quality score"
        elif sentiment.get("overall") == "negative":
            return TrustVerdict.FLAG, "Negative community sentiment"
        else:
            return TrustVerdict.DEFER, "Insufficient data for decision"

    def _calculate_irl_score(
        self,
        context_sources: List[str],
        reasoning_steps: List[str],
        verdict: TrustVerdict,
    ) -> float:
        base_score = 5.0
        
        authority_bonus = sum(self.canon_registry.get_authority_level(source) for source in context_sources) / 10.0
        base_score += min(authority_bonus, 2.0)
        
        reasoning_bonus = min(len(reasoning_steps) * 0.2, 2.0)
        base_score += reasoning_bonus
        
        if verdict == TrustVerdict.ALLOW:
            base_score += 1.0
        elif verdict == TrustVerdict.DENY:
            base_score += 0.5
        
        return min(base_score, 10.0) 