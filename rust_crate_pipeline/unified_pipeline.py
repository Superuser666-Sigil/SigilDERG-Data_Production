from __future__ import annotations

import asyncio
import json
import logging
import time
import argparse
import os
import tempfile
import aiohttp
import tarfile
import gzip
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, TYPE_CHECKING

from .config import PipelineConfig, CrateMetadata, EnrichedCrate
from .core import IRLEngine, CanonRegistry, SacredChainTrace, TrustVerdict
from .scraping import UnifiedScraper, ScrapingResult
from .crate_analysis import CrateAnalyzer
from rust_crate_pipeline.utils.sanitization import Sanitizer
from rust_crate_pipeline.version import __version__
from utils.serialization_utils import to_serializable

# Import Azure OpenAI enricher if available
try:
    from .azure_ai_processing import AzureOpenAIEnricher
    AZURE_OPENAI_AVAILABLE = True
except ImportError:
    AZURE_OPENAI_AVAILABLE = False
    AzureOpenAIEnricher = None

# Import unified LLM processor
try:
    from .unified_llm_processor import UnifiedLLMProcessor, create_llm_processor_from_args, LLMConfig
    UNIFIED_LLM_AVAILABLE = True
except ImportError:
    UNIFIED_LLM_AVAILABLE = False
    UnifiedLLMProcessor = None
    create_llm_processor_from_args = None
    LLMConfig = None

if TYPE_CHECKING:
    from .azure_ai_processing import AzureOpenAIEnricher
    from .unified_llm_processor import UnifiedLLMProcessor, LLMConfig


class UnifiedSigilPipeline:
    
    def __init__(self, config: PipelineConfig, llm_config: Optional[Any] = None) -> None:
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.irl_engine: Optional[IRLEngine] = None
        self.scraper: Optional[UnifiedScraper] = None
        self.canon_registry: CanonRegistry = CanonRegistry()
        self.sanitizer = Sanitizer(enabled=False)
        
        # Initialize AI components
        self.ai_enricher: Optional[Any] = None
        self.unified_llm_processor: Optional[Any] = None
        self.crate_analyzer: Optional[CrateAnalyzer] = None
        
        # Store LLM config for later use
        self.llm_config = llm_config
        
        self._initialize_components()
    
    def _initialize_components(self) -> None:
        try:
            self.irl_engine = IRLEngine(self.config, self.canon_registry)
            self.logger.info("✅ IRL Engine initialized successfully")
            
            scraper_config = {
                "verbose": False,
                "word_count_threshold": 10,
                "crawl_config": {
                }
            }
            self.scraper = UnifiedScraper(scraper_config)
            self.logger.info("✅ Unified Scraper initialized successfully")
            
            # Initialize unified LLM processor if available
            if UNIFIED_LLM_AVAILABLE and self.llm_config:
                try:
                    if UnifiedLLMProcessor is not None:
                        self.unified_llm_processor = UnifiedLLMProcessor(self.llm_config)
                        self.logger.info(f"✅ Unified LLM Processor initialized with provider: {self.llm_config.provider}")
                    else:
                        self.logger.warning("⚠️  UnifiedLLMProcessor is None at runtime; skipping initialization.")
                except Exception as e:
                    self.logger.warning(f"⚠️  Failed to initialize Unified LLM Processor: {e}")
            
            # Initialize Azure OpenAI enricher if available and configured (fallback)
            elif AZURE_OPENAI_AVAILABLE and self.config.use_azure_openai:
                try:
                    if AzureOpenAIEnricher is not None:
                        self.ai_enricher = AzureOpenAIEnricher(self.config)
                        self.logger.info("✅ Azure OpenAI Enricher initialized successfully")
                    else:
                        self.logger.warning("⚠️  AzureOpenAIEnricher is None at runtime; skipping initialization.")
                except Exception as e:
                    self.logger.warning(f"⚠️  Failed to initialize Azure OpenAI Enricher: {e}")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize pipeline components: {e}")
            raise
    
    async def __aenter__(self) -> "UnifiedSigilPipeline":
        if self.irl_engine:
            await self.irl_engine.__aenter__()
        if self.scraper:
            await self.scraper.__aenter__()
        return self
    
    async def __aexit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[Any]) -> None:
        if self.irl_engine:
            await self.irl_engine.__aexit__(exc_type, exc_val, exc_tb)
        if self.scraper:
            await self.scraper.__aexit__(exc_type, exc_val, exc_tb)
    
    async def analyze_crate(self, crate_name: str, crate_version: Optional[str] = None) -> SacredChainTrace:
        if not crate_name or not isinstance(crate_name, str):
            raise ValueError("crate_name must be a non-empty string")
        
        self.logger.info(f"🔍 Starting analysis of crate: {crate_name}")
        
        try:
            if crate_version is None:
                crate_version = await self._get_latest_crate_version(crate_name)
                if not crate_version:
                    raise RuntimeError(f"Could not determine latest version for {crate_name}")
            
            documentation_results = await self._gather_documentation(crate_name)
            
            sacred_chain_trace = await self._perform_sacred_chain_analysis(
                crate_name, crate_version, documentation_results
            )
            
            await self._generate_analysis_report(crate_name, sacred_chain_trace)
            
            self.logger.info(f"✅ Analysis completed for {crate_name}")
            return sacred_chain_trace
            
        except Exception as e:
            self.logger.error(f"❌ Analysis failed for {crate_name}: {e}")
            raise RuntimeError(f"Analysis failed for {crate_name}: {str(e)}")
    
    async def _gather_documentation(self, crate_name: str) -> Dict[str, ScrapingResult]:
        if not self.scraper:
            raise RuntimeError("Scraper not initialized")
        
        self.logger.info(f"📚 Gathering documentation for {crate_name}")
        
        try:
            results = await self.scraper.scrape_crate_documentation(crate_name)
            
            successful_sources = [source for source, result in results.items() 
                                if result.error is None]
            failed_sources = [source for source, result in results.items() 
                            if result.error is not None]
            
            self.logger.info(f"✅ Successfully scraped {len(successful_sources)} sources: {successful_sources}")
            if failed_sources:
                self.logger.warning(f"⚠️  Failed to scrape {len(failed_sources)} sources: {failed_sources}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"❌ Documentation gathering failed: {e}")
            raise
    
    async def _perform_sacred_chain_analysis(
        self, crate_name: str, crate_version: str, documentation_results: Dict[str, ScrapingResult]
    ) -> SacredChainTrace:
        if not self.irl_engine:
            raise RuntimeError("IRL Engine not initialized")
        
        self.logger.info(f"🔗 Performing Sacred Chain analysis for {crate_name}")
        
        try:
            sanitized_docs = self.sanitizer.sanitize_data(documentation_results)
            
            async with self.irl_engine as irl_engine:
                trace = await irl_engine.analyze_with_sacred_chain(crate_name)

            # Storing sanitized docs in the trace for later use by enrichment functions
            trace.audit_info['sanitized_documentation'] = sanitized_docs

            await self._add_crate_analysis_results(crate_name, crate_version, trace)

            if self.unified_llm_processor:
                await self._add_unified_llm_enrichment(crate_name, crate_version, trace)
            elif self.ai_enricher:
                await self._add_ai_enrichment(crate_name, crate_version, trace)
            
            return trace
            
        except Exception as e:
            self.logger.error(f"❌ Sacred Chain analysis failed: {e}")
            raise
    
    async def _add_crate_analysis_results(self, crate_name: str, crate_version: str, trace: SacredChainTrace) -> None:
        """Add cargo analysis results to the sacred chain trace"""
        try:
            self.logger.info(f"🔍 Adding crate analysis results for {crate_name} v{crate_version}")
            
            with tempfile.TemporaryDirectory() as temp_dir_str:
                temp_dir = Path(temp_dir_str)
                crate_source_path = await self._download_and_extract_crate(crate_name, crate_version, temp_dir)

                if not crate_source_path:
                    trace.audit_info["crate_analysis"] = {"status": "error", "note": "Failed to download or extract crate."}
                    return

                check_results = await self._run_cargo_command(
                    ["cargo", "check", "--message-format=json"],
                    cwd=crate_source_path
                )
                
                clippy_results = await self._run_cargo_command(
                    ["cargo", "clippy", "--message-format=json"],
                    cwd=crate_source_path
                )

                audit_results = await self._run_cargo_audit(crate_source_path)

                trace.audit_info["crate_analysis"] = self.sanitizer.sanitize_data({
                    "status": "completed",
                    "check": check_results,
                    "clippy": clippy_results,
                    "audit": audit_results,
                    "note": "Crate analysis performed."
                })

        except Exception as e:
            self.logger.warning(f"⚠️  Failed to add crate analysis results: {e}")
            trace.audit_info["crate_analysis"] = {"status": "error", "note": str(e)}
    
    async def _download_and_extract_crate(self, crate_name: str, crate_version: str, target_dir: Path) -> Optional[Path]:
        """Downloads and extracts a crate from crates.io."""
        crate_url = f"https://static.crates.io/crates/{crate_name}/{crate_name}-{crate_version}.crate"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(crate_url) as response:
                    if response.status != 200:
                        self.logger.error(f"Failed to download {crate_url}: HTTP {response.status}")
                        return None
                    
                    # Save the .crate file
                    crate_file_path = target_dir / f"{crate_name}-{crate_version}.crate"
                    with open(crate_file_path, "wb") as f:
                        f.write(await response.read())
                    
                    # Extract the tarball
                    with gzip.open(crate_file_path, 'rb') as gz_file:
                        with tarfile.open(fileobj=gz_file, mode='r') as tar_file:
                            tar_file.extractall(path=target_dir)
                    
                    # The crate is usually extracted into a directory named `{crate_name}-{crate_version}`
                    crate_source_dir = target_dir / f"{crate_name}-{crate_version}"
                    if crate_source_dir.is_dir():
                        return crate_source_dir
                    else:
                        self.logger.error(f"Could not find extracted directory: {crate_source_dir}")
                        return None

        except Exception as e:
            self.logger.error(f"Error downloading or extracting crate {crate_name}: {e}")
            return None
    
    async def _get_latest_crate_version(self, crate_name: str) -> Optional[str]:
        """Fetches the latest version of a crate from crates.io API."""
        api_url = f"https://crates.io/api/v1/crates/{crate_name}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    if response.status != 200:
                        self.logger.error(f"Failed to fetch crate info from {api_url}: HTTP {response.status}")
                        return None
                    data = await response.json()
                    return data.get("crate", {}).get("max_version")
        except Exception as e:
            self.logger.error(f"Error fetching latest crate version for {crate_name}: {e}")
            return None
    
    async def _run_cargo_command(self, command: List[str], cwd: Path) -> List[Dict[str, Any]]:
        """Runs a cargo command and returns the parsed JSON output."""
        self.logger.info(f"Running command: {' '.join(command)} in {cwd}")
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            self.logger.warning(f"Cargo command failed with exit code {process.returncode}")
            self.logger.warning(f"Stderr: {stderr.decode(errors='ignore')}")

        results = []
        if stdout:
            for line in stdout.decode(errors='ignore').splitlines():
                if line.strip():
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        self.logger.warning(f"Could not parse JSON line: {line}")
        return results
    
    async def _run_cargo_audit(self, cwd: Path) -> Optional[Dict[str, Any]]:
        """Runs cargo audit and returns the parsed JSON output."""
        command = ["cargo", "audit", "--json"]
        self.logger.info(f"Running command: {' '.join(command)} in {cwd}")
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            # cargo-audit exits with a non-zero status code if vulnerabilities are found.
            # We still want to parse the output.
            self.logger.info(f"Cargo audit finished with exit code {process.returncode}")
        
        if stdout:
            try:
                return json.loads(stdout)
            except json.JSONDecodeError:
                self.logger.warning(f"Could not parse cargo audit JSON output: {stdout.decode(errors='ignore')}")
        
        if stderr:
             self.logger.warning(f"Stderr from cargo audit: {stderr.decode(errors='ignore')}")

        return None
    
    async def _add_ai_enrichment(self, crate_name: str, crate_version: str, trace: SacredChainTrace) -> None:
        """Add AI enrichment results to the sacred chain trace"""
        # Use unified LLM processor if available, otherwise fall back to Azure OpenAI
        if self.unified_llm_processor:
            await self._add_unified_llm_enrichment(crate_name, crate_version, trace)
        elif self.ai_enricher:
            await self._add_azure_openai_enrichment(crate_name, trace)
        else:
            self.logger.info("ℹ️  No AI enricher available, skipping AI enrichment")
    
    async def _add_unified_llm_enrichment(self, crate_name: str, crate_version: str, trace: SacredChainTrace) -> None:
        """Add enrichment using unified LLM processor"""
        if not self.unified_llm_processor:
            return
            
        try:
            self.logger.info(f"🤖 Adding unified LLM enrichment for {crate_name}")
            
            # Get scraped data from trace
            scraped_data = trace.audit_info.get('sanitized_documentation', {})
            crates_io_data = scraped_data.get('crates.io', {}).get('data', {})
            
            crate_metadata = CrateMetadata(
                name=crate_name,
                version=crate_version,
                description=crates_io_data.get('description', trace.suggestion or "No description available"),
                repository=crates_io_data.get('repository', ""),
                keywords=crates_io_data.get('keywords', []),
                categories=crates_io_data.get('categories', []),
                readme=crates_io_data.get('readme', ""),
                downloads=crates_io_data.get('downloads', 0),
                github_stars=0, # This would ideally come from a GitHub specific scrape
                dependencies=crates_io_data.get('dependencies', []),
                features=crates_io_data.get('features', {}),
                code_snippets=[],
                readme_sections={},
                librs_downloads=scraped_data.get('librs.org', {}).get('data', {}).get('downloads_total', None),
                source="crates.io",
                enhanced_scraping={},
                enhanced_features=[],
                enhanced_dependencies=[]
            )
            
            # Store the metadata used for enrichment
            trace.audit_info["crate_metadata"] = crate_metadata.to_dict()

            # Enrich the crate using unified LLM processor
            enriched_crate = self.unified_llm_processor.enrich_crate(crate_metadata)
            
            # Add enrichment results to trace
            trace.audit_info["enriched_crate"] = self.sanitizer.sanitize_data(
                enriched_crate.to_dict()
            )
            self.logger.info(f"✅ Enriched data for {crate_name} using Unified LLM")
            
        except Exception as e:
            self.logger.warning(f"⚠️  Failed to add unified LLM enrichment: {e}")
    
    async def _add_azure_openai_enrichment(self, crate_name: str, trace: SacredChainTrace) -> None:
        """Add enrichment using Azure OpenAI"""
        if not self.ai_enricher:
            return
            
        try:
            self.logger.info(f"🤖 Adding Azure OpenAI enrichment for {crate_name}")
            
            # Get scraped data from trace
            scraped_data = trace.audit_info.get('sanitized_documentation', {})
            crates_io_data = scraped_data.get('crates.io', {}).get('data', {})

            crate_metadata = CrateMetadata(
                name=crate_name,
                version="unknown",
                description=crates_io_data.get('description', trace.suggestion or "No description available"),
                repository=crates_io_data.get('repository', ""),
                keywords=crates_io_data.get('keywords', []),
                categories=crates_io_data.get('categories', []),
                readme=crates_io_data.get('readme', ""),
                downloads=crates_io_data.get('downloads', 0),
                github_stars=0, # This would ideally come from a GitHub specific scrape
                dependencies=crates_io_data.get('dependencies', []),
                features=crates_io_data.get('features', {}),
                code_snippets=[],
                readme_sections={},
                librs_downloads=scraped_data.get('librs.org', {}).get('data', {}).get('downloads_total', None),
                source="crates.io",
                enhanced_scraping={},
                enhanced_features=[],
                enhanced_dependencies=[]
            )
            
            # Store the metadata used for enrichment
            trace.audit_info["crate_metadata"] = crate_metadata.to_dict()

            # Enrich the crate using Azure OpenAI
            enriched_crate = self.ai_enricher.enrich_crate(crate_metadata)
            
            # Add enrichment results to trace
            trace.audit_info["enriched_crate"] = self.sanitizer.sanitize_data(
                enriched_crate.to_dict()
            )
            self.logger.info(f"✅ Enriched data for {crate_name} using Azure OpenAI")
            
        except Exception as e:
            self.logger.warning(f"⚠️  Failed to add Azure OpenAI enrichment: {e}")
    
    async def _generate_analysis_report(self, crate_name: str, trace: SacredChainTrace) -> None:
        """Generate analysis report and save to file"""
        try:
            self.logger.info(f"📊 Generating analysis report for {crate_name}")

            # Ensure the output directory exists
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)
            
            report_path = output_dir / f"{crate_name}_analysis_report.json"
            
            report_data = to_serializable(trace.to_dict())

            # Manually handle MarkdownGenerationResult
            enrichment_path = report_data.get('audit_info', {}).get('llm_enrichment')
            if enrichment_path is not None and not isinstance(
                enrichment_path, (dict, list, str, int, float, bool, type(None))
            ):
                # Fallback: convert to string to guarantee JSON serialization
                report_data['audit_info']['llm_enrichment'] = str(enrichment_path)
            
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=4, default=str)

            self.logger.info(f"📊 Analysis report generated at {report_path}")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to generate analysis report for {crate_name}: {e}")
    
    async def analyze_multiple_crates(self, crate_names: List[str]) -> Dict[str, SacredChainTrace]:
        if not crate_names:
            return {}
        
        self.logger.info(f"🚀 Starting concurrent analysis of {len(crate_names)} crates")
        
        semaphore = asyncio.Semaphore(self.config.n_workers)
        
        async def analyze_single_crate(crate_name: str) -> "tuple[str, SacredChainTrace]":
            async with semaphore:
                try:
                    trace = await self.analyze_crate(crate_name)
                    return crate_name, trace
                except Exception as e:
                    self.logger.error(f"❌ Analysis failed for {crate_name}: {e}")
                    error_trace = SacredChainTrace(
                        input_data=crate_name,
                        context_sources=[],
                        reasoning_steps=[f"Analysis failed: {str(e)}"],
                        suggestion="DEFER: Analysis failed",
                        verdict=TrustVerdict.DEFER,
                        audit_info={"error": str(e)},
                        irl_score=0.0,
                        execution_id=f"error-{int(time.time())}",
                        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        canon_version=__version__,
                    )
                    return crate_name, error_trace
        
        tasks = [analyze_single_crate(name) for name in crate_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        analysis_results: Dict[str, SacredChainTrace] = {}
        for result in results:
            if isinstance(result, tuple):
                crate_name, trace = result
                analysis_results[crate_name] = trace
            else:
                self.logger.error(f"❌ Unexpected result type: {type(result)}")
        
        self.logger.info(f"✅ Completed analysis of {len(analysis_results)} crates")
        return analysis_results
    
    def get_pipeline_summary(self) -> Dict[str, Any]:
        """Get a summary of the pipeline configuration and status"""
        summary = {
            "pipeline_version": __version__,
            "components": {
                "irl_engine": self.irl_engine is not None,
                "scraper": self.scraper is not None,
                "canon_registry": self.canon_registry is not None,
            },
            "ai_components": {
                "unified_llm_processor": self.unified_llm_processor is not None,
                "azure_openai_enricher": self.ai_enricher is not None,
                "crate_analyzer": self.crate_analyzer is not None,
            },
            "configuration": {
                "max_tokens": self.config.max_tokens,
                "checkpoint_interval": self.config.checkpoint_interval,
                "batch_size": self.config.batch_size,
                "enable_crawl4ai": self.config.enable_crawl4ai,
            }
        }
        
        # Add LLM configuration if available
        if self.llm_config:
            summary["llm_configuration"] = {
                "provider": self.llm_config.provider,
                "model": self.llm_config.model,
                "temperature": self.llm_config.temperature,
                "max_tokens": self.llm_config.max_tokens,
                "timeout": self.llm_config.timeout,
                "max_retries": self.llm_config.max_retries
            }
        elif self.config.use_azure_openai:
            summary["llm_configuration"] = {
                "provider": "azure_openai",
                "model": self.config.azure_openai_deployment_name,
                "endpoint": self.config.azure_openai_endpoint,
                "max_tokens": self.config.max_tokens
            }
        
        return summary


def create_pipeline_from_args(args: argparse.Namespace) -> UnifiedSigilPipeline:
    """Create pipeline from command line arguments"""
    # Create base config
    config = PipelineConfig()
    
    # Create LLM config if LLM arguments are provided
    llm_config = None
    if hasattr(args, 'llm_provider') and args.llm_provider:
        if UNIFIED_LLM_AVAILABLE and LLMConfig is not None:
            llm_config_params = {
                "provider": args.llm_provider,
                "model": args.llm_model or "gpt-4o",
                "api_base": getattr(args, 'llm_api_base', None),
                "api_key": getattr(args, 'llm_api_key', None),
                "temperature": getattr(args, 'llm_temperature', 0.2),
                "max_tokens": getattr(args, 'llm_max_tokens', 256),
                "timeout": getattr(args, 'llm_timeout', 30),
                "max_retries": getattr(args, 'llm_max_retries', 3),
                "azure_deployment": getattr(args, 'azure_deployment', None),
                "azure_api_version": getattr(args, 'azure_api_version', None),
                "ollama_host": getattr(args, 'ollama_host', None),
                "lmstudio_host": getattr(args, 'lmstudio_host', None),
            }
            # Filter out None values so that default values in LLMConfig are used
            llm_config_params = {k: v for k, v in llm_config_params.items() if v is not None}
            llm_config = LLMConfig(**llm_config_params)
        else:
            logging.warning("Unified LLM processor not available, falling back to Azure OpenAI")
    
    return UnifiedSigilPipeline(config, llm_config)


def add_llm_arguments(parser: argparse.ArgumentParser) -> None:
    """Add LLM-related command line arguments to the parser"""
    llm_group = parser.add_argument_group('LLM Configuration')
    
    llm_group.add_argument(
        '--llm-provider',
        choices=['azure', 'ollama', 'lmstudio', 'openai', 'anthropic', 'google', 'cohere', 'huggingface'],
        help='LLM provider to use (default: azure)'
    )
    
    llm_group.add_argument(
        '--llm-model',
        default='gpt-4o',
        help='Model name/identifier (e.g., gpt-4, llama2, claude-3)'
    )
    
    llm_group.add_argument(
        '--llm-api-base',
        help='API base URL (for local providers or custom endpoints)'
    )
    
    llm_group.add_argument(
        '--llm-api-key',
        help='API key (if required by provider)'
    )
    
    llm_group.add_argument(
        '--llm-temperature',
        type=float,
        default=0.2,
        help='Temperature for LLM generation (default: 0.2)'
    )
    
    llm_group.add_argument(
        '--llm-max-tokens',
        type=int,
        default=256,
        help='Maximum tokens for LLM generation (default: 256)'
    )
    
    llm_group.add_argument(
        '--llm-timeout',
        type=int,
        default=30,
        help='Timeout for LLM API calls in seconds (default: 30)'
    )
    
    llm_group.add_argument(
        '--llm-max-retries',
        type=int,
        default=3,
        help='Maximum retries for LLM API calls (default: 3)'
    )
    
    # Provider-specific arguments
    azure_group = parser.add_argument_group('Azure OpenAI Configuration')
    azure_group.add_argument(
        '--azure-deployment',
        help='Azure OpenAI deployment name'
    )
    azure_group.add_argument(
        '--azure-api-version',
        help='Azure OpenAI API version'
    )
    
    ollama_group = parser.add_argument_group('Ollama Configuration')
    ollama_group.add_argument(
        '--ollama-host',
        default='http://localhost:11434',
        help='Ollama host URL (default: http://localhost:11434)'
    )
    
    lmstudio_group = parser.add_argument_group('LM Studio Configuration')
    lmstudio_group.add_argument(
        '--lmstudio-host',
        default='http://localhost:1234/v1',
        help='LM Studio host URL (default: http://localhost:1234/v1)'
    )


async def quick_analyze_crate(crate_name: str, config: Optional[PipelineConfig] = None, llm_config: Optional[Any] = None) -> SacredChainTrace:
    """Quick analysis of a single crate"""
    if config is None:
        config = PipelineConfig()
    
    async with UnifiedSigilPipeline(config, llm_config) as pipeline:
        return await pipeline.analyze_crate(crate_name)


async def batch_analyze_crates(crate_names: List[str], config: Optional[PipelineConfig] = None, llm_config: Optional[Any] = None) -> Dict[str, SacredChainTrace]:
    """Batch analysis of multiple crates"""
    if config is None:
        config = PipelineConfig()
    
    async with UnifiedSigilPipeline(config, llm_config) as pipeline:
        return await pipeline.analyze_multiple_crates(crate_names) 