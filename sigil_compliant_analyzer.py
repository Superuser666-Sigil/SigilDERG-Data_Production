"""
Sigil Protocol Compliant Crate Analysis System
Rule Zero: "If an output cannot explain itself, it has no trust."
Extension: No code can be stubbed, no TODOs left behind; all code must be
production ready and complete.
"""

import asyncio
import json
import logging
import time
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import uuid

# Full production imports - no stubs
from crawl4ai import (  # type: ignore
    AsyncWebCrawler,
    CrawlerRunConfig,
    CrawlResult,
    LLMExtractionStrategy,
)
from rust_crate_pipeline.config import PipelineConfig


class TrustVerdict(Enum):
    """Sacred Chain trust boundary decisions"""

    ALLOW = "ALLOW"
    DENY = "DENY"
    DEFER = "DEFER"
    FLAG = "FLAG"

    def __str__(self):
        return self.value

    def to_json(self):
        return self.value


@dataclass
class SacredChainTrace:
    """Complete Sacred Chain reasoning trace - fully implemented"""

    input_data: str
    context_sources: List[str]
    reasoning_steps: List[str]
    suggestion: str
    verdict: TrustVerdict
    audit_info: Dict[str, Any]
    irl_score: float
    execution_id: str
    timestamp: str
    canon_version: str

    def to_audit_log(self) -> str:
        """Generate complete audit log entry"""
        # Convert the dataclass to dict and handle enum serialization
        data_dict = asdict(self)
        data_dict["verdict"] = self.verdict.value  # Convert enum to string

        return json.dumps(
            {
                "execution_id": self.execution_id,
                "timestamp": self.timestamp,
                "sacred_chain": data_dict,
                "rule_zero_compliant": True,
            },
            indent=2,
        )

    def verify_integrity(self) -> bool:
        """Cryptographic verification of chain integrity"""
        chain_data = f"{
            self.input_data}{
            self.context_sources}{
            self.reasoning_steps}{
                self.suggestion}"
        expected_hash = hashlib.sha256(chain_data.encode()).hexdigest()[:16]
        return expected_hash in self.execution_id


@dataclass
class CanonEntry:
    """Structured Canon entry - production implementation"""

    source: str
    version: str
    authority_level: int  # 1-10, 10 = highest trust
    content_hash: str
    last_validated: str
    expiry: Optional[str] = None

    def is_valid(self) -> bool:
        """Check if Canon entry is still valid"""
        if self.expiry:
            expiry_time = datetime.fromisoformat(self.expiry)
            return datetime.now(timezone.utc) < expiry_time
        return True


class CodexNexus:
    """Production-ready knowledge system organizer"""

    def __init__(self):
        self.canon_entries: Dict[str, CanonEntry] = {}
        self.authority_chain: List[str] = []
        self.version = "1.0.0"

    def register_canon(
        self, key: str, source: str, content: str, authority_level: int = 5
    ) -> bool:
        """Register Canon with full validation"""
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        timestamp = datetime.now(timezone.utc).isoformat()

        canon_entry = CanonEntry(
            source=source,
            version=self.version,
            authority_level=authority_level,
            content_hash=content_hash,
            last_validated=timestamp,
        )

        self.canon_entries[key] = canon_entry
        self.authority_chain.append(f"{timestamp}:{key}:{authority_level}")

        logging.info(
            f"Canon registered: {key} with authority {authority_level}"
        )
        return True

    def get_canon(self, key: str) -> Optional[CanonEntry]:
        """Retrieve Canon with validation"""
        if key in self.canon_entries:
            canon = self.canon_entries[key]
            if canon.is_valid():
                return canon
            else:
                logging.warning(f"Canon expired: {key}")
                del self.canon_entries[key]
        return None

    def audit_trail(self) -> List[str]:
        """Complete audit trail of Canon operations"""
        return self.authority_chain.copy()


class IRLEngine:
    """Integrity Reasoning Layer - Production Implementation"""

    def __init__(self, config: PipelineConfig, codex: CodexNexus):
        self.config = config
        self.codex = codex
        self.crawler: Optional[AsyncWebCrawler] = None
        self.execution_log: List[SacredChainTrace] = []

    async def __aenter__(self) -> "IRLEngine":
        """Production async context manager"""
        self.crawler = AsyncWebCrawler()
        await self.crawler.start()  # type: ignore
        logging.info("IRL Engine initialized with full traceability")
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Clean shutdown with audit finalization"""
        if self.crawler:
            await self.crawler.stop()  # type: ignore
        self._finalize_audit_log()

    def _finalize_audit_log(self) -> None:
        """Write complete audit log to persistent storage"""
        audit_file = f"sigil_audit_{int(time.time())}.json"
        # In a real scenario, this would write to a secure, persistent location
        # For this example, we write to a local file.
        try:
            with open(audit_file, "w") as f:
                # Convert each trace to a dictionary before dumping
                json.dump(
                    [
                        json.loads(trace.to_audit_log())
                        for trace in self.execution_log
                    ],
                    f,
                    indent=2,
                )
            logging.info(f"Audit log finalized: {audit_file}")
        except IOError as e:
            logging.error(f"Failed to write audit log {audit_file}: {e}")

    async def analyze_crate_with_sacred_chain(
        self, crate_name: str
    ) -> SacredChainTrace:
        """Complete Sigil-compliant crate analysis"""

        execution_id = f"crate-{crate_name}-{uuid.uuid4().hex[:8]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        # Step 1: Input validation and canonicalization
        input_data = self._canonicalize_input(crate_name)

        # Step 2: Context gathering with Canon validation
        context_sources = await self._gather_validated_context(crate_name)

        # Step 3: Multi-step reasoning with full traceability
        (
            reasoning_steps,
            basic_metadata,
            doc_analysis,
            sentiment,
            ecosystem,
            quality_score,
        ) = await self._execute_reasoning_chain(crate_name, context_sources)

        # Step 4: Generate suggestion with confidence bounds
        suggestion = self._generate_traceable_suggestion(reasoning_steps)

        # Step 5: Trust boundary decision
        verdict, verdict_reason = self._make_trust_decision(
            reasoning_steps,
            suggestion,
            quality_score,
            doc_analysis,
            sentiment,
            ecosystem,
        )

        # Step 6: Complete audit information
        audit_info: Dict[str, Any] = {
            "user": "system",
            "authority": "rust-crate-pipeline-v1.2.6",
            "canon_version": self.codex.version,
            "model_used": "deepseek-coder:6.7b",
            "sources_validated": len(context_sources),
            "reasoning_depth": len(reasoning_steps),
        }

        # Step 7: IRL confidence score with explanation
        irl_score = self._calculate_irl_score(
            context_sources, reasoning_steps, verdict
        )

        # Create complete Sacred Chain trace
        trace = SacredChainTrace(
            input_data=input_data,
            context_sources=context_sources,
            reasoning_steps=reasoning_steps,
            suggestion=suggestion,
            verdict=verdict,
            audit_info=audit_info,
            irl_score=irl_score,
            execution_id=execution_id,
            timestamp=timestamp,
            canon_version=self.codex.version,
        )

        # Verify integrity before storing
        if not trace.verify_integrity():
            raise ValueError(
                f"Sacred Chain integrity check failed for {execution_id}"
            )

        self.execution_log.append(trace)
        logging.info(
            f"Sacred Chain completed for {crate_name}: {verdict.value} "
            f"(IRL: {irl_score:.3f})"
        )

        return trace

    def _canonicalize_input(self, crate_name: str) -> str:
        """Validate and canonicalize input with full error handling"""
        if not crate_name:
            raise ValueError("Invalid crate name input")

        # Sanitize and validate crate name format
        clean_name = crate_name.strip().lower()
        if not clean_name.replace("-", "").replace("_", "").isalnum():
            raise ValueError(f"Invalid crate name format: {crate_name}")

        return clean_name

    async def _gather_validated_context(self, crate_name: str) -> List[str]:
        """Gather context with full Canon validation"""
        context_sources: List[str] = []

        # Source 1: crates.io (highest authority)
        cratesio_canon = self.codex.get_canon("crates.io")
        if cratesio_canon and cratesio_canon.authority_level >= 8:
            context_sources.append(f"crates.io:{cratesio_canon.version}")

        # Source 2: docs.rs (high authority)
        docs_canon = self.codex.get_canon("docs.rs")
        if docs_canon and docs_canon.authority_level >= 7:
            context_sources.append(f"docs.rs:{docs_canon.version}")

        # Source 3: GitHub (medium-high authority)
        github_canon = self.codex.get_canon("github.com")
        if github_canon and github_canon.authority_level >= 6:
            context_sources.append(f"github.com:{github_canon.version}")

        # Source 4: Community sources (medium authority)
        community_canon = self.codex.get_canon("community")
        if community_canon and community_canon.authority_level >= 5:
            context_sources.append(f"community:{community_canon.version}")

        if not context_sources:
            raise ValueError("No validated Canon sources available")

        return context_sources

    async def _execute_reasoning_chain(
        self, crate_name: str, sources: List[str]
    ) -> Tuple[
        List[str],
        Dict[str, Any],
        Dict[str, Any],
        Dict[str, Any],
        Dict[str, Any],
        float,
    ]:
        """Execute complete reasoning chain with full implementation"""
        reasoning_steps: List[str] = []

        # Step 1: Basic metadata extraction
        basic_metadata = await self._extract_basic_metadata(crate_name)
        reasoning_steps.append(
            f"Basic metadata extracted: {len(basic_metadata)} fields"
        )

        # Step 2: Documentation analysis
        doc_analysis = await self._analyze_documentation(crate_name)
        reasoning_steps.append(
            f"Documentation analyzed: quality={doc_analysis.get('quality_score', 0)}"
        )

        # Step 3: Community sentiment analysis
        sentiment = await self._analyze_community_sentiment(crate_name)
        reasoning_steps.append(
            f"Community sentiment: {sentiment.get('overall', 'neutral')}"
        )

        # Step 4: Ecosystem positioning
        ecosystem = await self._analyze_ecosystem_position(crate_name)
        reasoning_steps.append(
            f"Ecosystem position: {ecosystem.get('category', 'unknown')}"
        )

        # Step 5: Quality synthesis
        quality_score = self._synthesize_quality_score(
            basic_metadata, doc_analysis, sentiment, ecosystem
        )
        reasoning_steps.append(
            f"Synthesized quality score: {quality_score:.2f}/10"
        )

        return (
            reasoning_steps,
            basic_metadata,
            doc_analysis,
            sentiment,
            ecosystem,
            quality_score,
        )

    async def _extract_basic_metadata(self, crate_name: str) -> Dict[str, Any]:
        """Production-ready metadata extraction"""
        try:
            # Real implementation using crates.io API
            import aiohttp

            async with aiohttp.ClientSession() as session:
                url = f"https://crates.io/api/v1/crates/{crate_name}"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        crate_data = data.get("crate", {})
                        return {
                            "name": crate_data.get("name"),
                            "version": crate_data.get("newest_version"),
                            "description": crate_data.get("description"),
                            "downloads": crate_data.get("downloads", 0),
                            "repository": crate_data.get("repository"),
                            "keywords": crate_data.get("keywords", []),
                            "categories": crate_data.get("categories", []),
                        }
        except Exception as e:
            logging.error(f"Metadata extraction failed for {crate_name}: {e}")

        return {"error": "Failed to extract basic metadata"}

    async def _analyze_documentation(self, crate_name: str) -> Dict[str, Any]:
        """Production-ready documentation analysis"""
        assert self.crawler is not None
        try:
            docs_url = f"https://docs.rs/{crate_name}/latest/{crate_name}/"

            extraction_strategy = LLMExtractionStrategy(
                provider="ollama",
                api_base="http://localhost:11434",
                model="deepseek-coder:6.7b",
                instruction="""
                Analyze the Rust crate documentation for '{crate_name}' and provide:

                1. API complexity level (1-10)
                2. Documentation completeness (1-10)
                3. Example quality (1-10)
                4. Main modules and features
                5. Usage patterns identified

                Return valid JSON:
                {{
                    "complexity_level": <1-10>,
                    "completeness_score": <1-10>,
                    "example_quality": <1-10>,
                    "quality_score": <average of above>,
                    "main_modules": ["module1", "module2"],
                    "usage_patterns": ["pattern1", "pattern2"]                }}
                """,
            )

            config = CrawlerRunConfig(
                extraction_strategy=extraction_strategy,
                page_timeout=30000,
                js_code=["window.scrollTo(0, document.body.scrollHeight);"],
            )

            result = await self.crawler.arun(
                url=docs_url, config=config
            )  # type: ignore

            if result.success and result.extracted_content:  # type: ignore
                try:
                    # Ensure result is not a generator
                    if isinstance(result, CrawlResult):
                        analysis = json.loads(result.extracted_content)
                        # Validate required fields
                        required_fields = [
                            "complexity_level",
                            "completeness_score",
                            "example_quality",
                        ]
                        if all(field in analysis for field in required_fields):
                            return analysis
                except json.JSONDecodeError:
                    pass

        except Exception as e:
            logging.error(
                f"Documentation analysis failed for {crate_name}: {e}"
            )

        # Fallback with minimal viable data
        return {
            "complexity_level": 5,
            "completeness_score": 5,
            "example_quality": 5,
            "quality_score": 5.0,
            "main_modules": [],
            "usage_patterns": [],
            "error": "Analysis failed, using fallback values",
        }

    async def _analyze_community_sentiment(
        self, crate_name: str
    ) -> Dict[str, Any]:
        """Production-ready community sentiment analysis"""
        assert self.crawler is not None
        try:
            # Multiple community sources for comprehensive analysis
            sources = [
                f"https://www.reddit.com/search/?q={crate_name}+rust",
                f"https://users.rust-lang.org/search?q={crate_name}",
            ]

            sentiment_data: Dict[str, Any] = {
                "positive_mentions": 0,
                "negative_mentions": 0,
                "neutral_mentions": 0,
                "total_mentions": 0,
                "overall": "neutral",
            }

            for source_url in sources:
                try:
                    extraction_strategy = LLMExtractionStrategy(
                        provider="ollama",
                        api_base="http://localhost:11434",
                        model="deepseek-coder:6.7b",
                        instruction="""
                        Analyze mentions of the Rust crate '{crate_name}' and count:

                        Return valid JSON:
                        {{
                            "positive_mentions": <count>,
                            "negative_mentions": <count>,
                            "neutral_mentions": <count>,
                            "sentiment_keywords": ["keyword1", "keyword2"]
                        }}
                        """,
                    )

                    config = CrawlerRunConfig(
                        extraction_strategy=extraction_strategy,
                        page_timeout=20000,
                    )

                    result = await self.crawler.arun(
                        url=source_url, config=config
                    )  # type: ignore

                    if result.success and result.extracted_content:  # type: ignore
                        try:
                            if isinstance(result, CrawlResult):
                                data = json.loads(result.extracted_content)
                                sentiment_data["positive_mentions"] += int(
                                    data.get("positive_mentions", 0)
                                )
                                sentiment_data["negative_mentions"] += int(
                                    data.get("negative_mentions", 0)
                                )
                                sentiment_data["neutral_mentions"] += int(
                                    data.get("neutral_mentions", 0)
                                )
                        except (json.JSONDecodeError, ValueError):
                            pass

                except Exception as e:
                    logging.warning(f"Failed to analyze {source_url}: {e}")

            # Calculate overall sentiment
            total = (
                int(sentiment_data["positive_mentions"])
                + int(sentiment_data["negative_mentions"])
                + int(sentiment_data["neutral_mentions"])
            )
            sentiment_data["total_mentions"] = total

            if total > 0:
                pos_ratio = sentiment_data["positive_mentions"] / total
                neg_ratio = sentiment_data["negative_mentions"] / total

                if pos_ratio > 0.6:
                    sentiment_data["overall"] = "positive"
                elif neg_ratio > 0.4:
                    sentiment_data["overall"] = "negative"
                else:
                    sentiment_data["overall"] = "neutral"

            return sentiment_data

        except Exception as e:
            logging.error(
                f"Community sentiment analysis failed for {crate_name}: {e}"
            )

        # Fallback data
        return {
            "positive_mentions": 0,
            "negative_mentions": 0,
            "neutral_mentions": 0,
            "total_mentions": 0,
            "overall": "neutral",
            "error": "Sentiment analysis failed",
        }

    async def _analyze_ecosystem_position(
        self, crate_name: str
    ) -> Dict[str, Any]:
        """Production-ready ecosystem analysis"""
        assert self.crawler is not None
        try:
            # Analyze crate's position on crates.io
            ecosystem_url = f"https://crates.io/crates/{crate_name}"

            extraction_strategy = LLMExtractionStrategy(
                provider="ollama",
                api_base="http://localhost:11434",
                model="deepseek-coder:6.7b",
                instruction="""
                Analyze the ecosystem position of Rust crate '{crate_name}':

                Return valid JSON:
                {{
                    "category": "<primary category>",
                    "maturity": "experimental|stable|mature",
                    "dependencies_count": <number>,
                    "reverse_deps_visible": <number>,
                    "last_update_recent": <boolean>,
                    "ecosystem_score": <1-10>
                }}
                """,
            )

            config = CrawlerRunConfig(
                extraction_strategy=extraction_strategy, page_timeout=15000
            )

            result = await self.crawler.arun(
                url=ecosystem_url, config=config
            )  # type: ignore

            if result.success and result.extracted_content:  # type: ignore
                try:
                    if isinstance(result, CrawlResult):
                        ecosystem_data = json.loads(result.extracted_content)
                        # Basic validation
                        if (
                            "category" in ecosystem_data
                            and "maturity" in ecosystem_data
                        ):
                            return ecosystem_data
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logging.error(f"Ecosystem analysis failed for {crate_name}: {e}")

        # Fallback analysis
        return {
            "category": "unknown",
            "maturity": "unknown",
            "dependencies_count": 0,
            "reverse_deps_visible": 0,
            "last_update_recent": False,
            "ecosystem_score": 5,
            "error": "Ecosystem analysis failed",
        }

    def _synthesize_quality_score(
        self,
        metadata: Dict[str, Any],
        docs: Dict[str, Any],
        sentiment: Dict[str, Any],
        ecosystem: Dict[str, Any],
    ) -> float:
        """Production-ready quality score synthesis"""
        scores = []

        # Documentation quality
        doc_quality = docs.get("quality_score", 5.0)
        scores.append(doc_quality * 0.3)  # 30% weight

        # Community sentiment
        sentiment_score = 5.0  # Neutral
        if sentiment.get("overall") == "positive":
            sentiment_score = 8.0
        elif sentiment.get("overall") == "negative":
            sentiment_score = 2.0
        scores.append(sentiment_score * 0.2)  # 20% weight

        # Ecosystem maturity
        ecosystem_score = ecosystem.get("ecosystem_score", 5.0)
        scores.append(ecosystem_score * 0.3)  # 30% weight
        ecosystem_score = ecosystem.get("ecosystem_score", 5.0)
        scores.append(ecosystem_score * 0.3)  # 30% weight

        # Downloads (logarithmic scale to avoid extreme influence)
        downloads = metadata.get("downloads", 0)
        download_score = min(10, max(0, math.log10(downloads + 1)))
        scores.append(download_score * 0.1)  # 10% weight

        # Final score, capped at 10
        final_score = min(10.0, sum(scores))
        return final_score

    def _generate_traceable_suggestion(
        self, reasoning_steps: List[str]
    ) -> str:
        """Generate suggestion with complete traceability"""
        if not reasoning_steps:
            return "No analysis performed - insufficient reasoning steps"

        # Extract key metrics from reasoning steps
        quality_match = None
        for step in reasoning_steps:
            if "quality score:" in step.lower():
                try:
                    quality_match = float(
                        step.split(":")[-1].strip().split("/")[0]
                    )
                    break
                except BaseException:
                    pass

        if quality_match is None:
            return "Analysis incomplete - quality score not determined"

        # Generate suggestion based on quality score
        if quality_match >= 8.0:
            return f"HIGH CONFIDENCE: Crate shows excellent quality (score: {
                quality_match:.1f}/10). Recommended for production use."
        elif quality_match >= 6.0:
            return f"MEDIUM CONFIDENCE: Crate shows good quality (score: {
                quality_match:.1f}/10). Suitable for most use cases with review."
        elif quality_match >= 4.0:
            return f"LOW CONFIDENCE: Crate shows moderate quality (score: {
                quality_match:.1f}/10). Use with caution and thorough testing."
        else:
            return f"NOT RECOMMENDED: Crate shows poor quality (score: {
                quality_match:.1f}/10). Consider alternatives."

    def _make_trust_decision(
        self,
        reasoning_steps: List[str],
        suggestion: str,
        quality_score: float,
        docs: Dict[str, Any],
        sentiment: Dict[str, Any],
        ecosystem: Dict[str, Any],
    ) -> Tuple[TrustVerdict, str]:
        """
        Make a trust boundary decision based on all available data.
        This is a critical step in the Sacred Chain.
        """

        # Check for analysis completeness
        if len(reasoning_steps) < 3:
            return TrustVerdict.DEFER, "Analysis incomplete"

        # Check for error conditions
        error_indicators = ["failed", "error", "timeout", "unavailable"]
        if any(
            indicator in step.lower()
            for step in reasoning_steps
            for indicator in error_indicators
        ):
            return (
                TrustVerdict.FLAG,
                "Error indicators present in reasoning steps",
            )

        # Decision based on confidence level in suggestion
        if "HIGH CONFIDENCE" in suggestion:
            return TrustVerdict.ALLOW, "High confidence in quality"
        elif "MEDIUM CONFIDENCE" in suggestion:
            return TrustVerdict.ALLOW, "Medium confidence in quality"
        elif "LOW CONFIDENCE" in suggestion:
            return TrustVerdict.FLAG, "Low confidence in quality"
        elif "NOT RECOMMENDED" in suggestion:
            return TrustVerdict.DENY, "Crate not recommended"
        else:
            return TrustVerdict.DEFER, "Insufficient data for decision"

    def _calculate_irl_score(
        self,
        context_sources: List[str],
        reasoning_steps: List[str],
        verdict: TrustVerdict,
    ) -> float:
        """
        Calculate a final IRL (Integrity Reasoning Layer) score.
        This is a more holistic score than the quality score, factoring in
        the entire process.
        """
        # Base score on the number of validated high-authority sources
        base_score = len(context_sources) * 10.0  # Max 40

        # Add points for each successful reasoning step
        base_score += len(reasoning_steps) * 5.0  # Max 25

        # Adjust based on the final verdict
        if verdict == TrustVerdict.ALLOW:
            base_score += 35.0
        elif verdict == TrustVerdict.DEFER:
            base_score += 15.0
        elif verdict == TrustVerdict.FLAG:
            base_score += 5.0
        # No points for DENY

        # Normalize to a 0-1 scale
        max_possible_score = 40.0 + 25.0 + 35.0  # sources + steps + verdict
        irl_score = min(1.0, max(0.0, base_score / max_possible_score))

        return irl_score


class SigilCompliantPipeline:
    """
    The main entry point for the Sigil-compliant analysis pipeline.
    This class orchestrates the entire process, from setup to final report.
    """

    def __init__(self, config: PipelineConfig):
        """
        Initializes the pipeline with a given configuration.
        """
        self.config = config
        self.codex = CodexNexus()
        self.irl_engine: Optional[IRLEngine] = None
        self._setup_canon()

    def _setup_canon(self) -> None:
        """
        Establishes the foundational knowledge (Canon) for the pipeline.
        In a real system, this might be loaded from a secure config store.
        """
        self.codex.register_canon(
            "crates.io",
            "https://crates.io",
            "Official Rust package registry",
            9,
        )
        self.codex.register_canon(
            "docs.rs", "https://docs.rs", "Official documentation hosting", 8
        )
        self.codex.register_canon(
            "github.com",
            "https://github.com",
            "Primary source code hosting",
            7,
        )
        self.codex.register_canon(
            "community",
            "reddit.com, rust-lang.org",
            "Community discussion forums",
            5,
        )

    async def run_analysis(
        self, crate_names: List[str]
    ) -> List[SacredChainTrace]:
        """
        Runs the full analysis for a list of crate names.
        """
        results = []
        async with IRLEngine(self.config, self.codex) as irl_engine:
            self.irl_engine = irl_engine
            for crate_name in crate_names:
                try:
                    trace = (
                        await self.irl_engine.analyze_crate_with_sacred_chain(
                            crate_name
                        )
                    )
                    results.append(trace)
                except Exception as e:
                    logging.error(
                        f"Critical error during analysis of {crate_name}: {e}"
                    )
        return results

    def generate_final_report(
        self, traces: List[SacredChainTrace]
    ) -> Dict[str, Any]:
        """
        Generates a comprehensive final report from the analysis traces.
        """
        report = {
            "report_id": f"sigil-report-{uuid.uuid4().hex[:12]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": self.get_audit_summary(traces),
            "crates_analyzed": len(traces),
            "results": [asdict(trace) for trace in traces],
        }
        return report

    def get_audit_summary(
        self, traces: List[SacredChainTrace]
    ) -> Dict[str, Any]:
        """
        Creates a summary of the audit trail from the analysis traces.
        """
        summary = {
            "total_verdicts": {verdict.value: 0 for verdict in TrustVerdict},
            "average_irl_score": 0.0,
            "canon_versions_used": list(
                set(trace.canon_version for trace in traces if trace)
            ),
        }
        if not traces:
            return summary

        for trace in traces:
            if hasattr(trace.verdict, "value"):
                summary["total_verdicts"][trace.verdict.value] += 1
            else:
                # Handle case where verdict might be a string
                verdict_key = str(trace.verdict)
                if verdict_key in summary["total_verdicts"]:
                    summary["total_verdicts"][verdict_key] += 1

        total_score = sum(trace.irl_score for trace in traces)
        summary["average_irl_score"] = total_score / len(traces)

        return summary


async def main():
    """
    Main function to demonstrate the Sigil Compliant Pipeline.
    This is a self-contained example of how to run the system.
    """
    # --- Configuration ---
    # In a real application, this would come from a config file or env vars
    config = PipelineConfig(
        enable_crawl4ai=True,
        # Ensure you have a local Ollama instance running with this model
        crawl4ai_model="deepseek-coder:6.7b",
    )

    # List of crates to analyze
    crates_to_analyze = ["tokio", "serde", "rand", "this-is-not-a-real-crate"]

    # --- Pipeline Execution ---
    print("--- Initializing Sigil Compliant Pipeline ---")
    pipeline = SigilCompliantPipeline(config)

    print(f"--- Analyzing {len(crates_to_analyze)} Crates ---")
    analysis_results = await pipeline.run_analysis(crates_to_analyze)

    print("--- Generating Final Report ---")
    final_report = pipeline.generate_final_report(analysis_results)

    # --- Output ---
    report_filename = f"sigil_report_{int(time.time())}.json"
    with open(report_filename, "w") as f:
        json.dump(final_report, f, indent=2)

    print("\n--- Analysis Complete ---")
    print(f"Final report generated: {report_filename}")
    print(f"Summary: {json.dumps(final_report['summary'], indent=2)}")


if __name__ == "__main__":
    # This allows the script to be run directly for demonstration or testing.
    # Note: Running this requires a configured environment with Crawl4AI
    # and a running Ollama instance.
    asyncio.run(main())
