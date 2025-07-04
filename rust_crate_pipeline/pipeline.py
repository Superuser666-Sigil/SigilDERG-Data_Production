# pipeline.py
import os
import time
import logging
import json
import asyncio
from typing import Any, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict, List, Optional

from .config import PipelineConfig, CrateMetadata, EnrichedCrate
from .network import CrateAPIClient, GitHubBatchClient
from .ai_processing import LLMEnricher
from .analysis import DependencyAnalyzer
from .crate_analysis import CrateAnalyzer

# Import Azure OpenAI enricher
try:
    from .azure_ai_processing import AzureOpenAIEnricher
    AZURE_OPENAI_AVAILABLE = True
except ImportError:
    AZURE_OPENAI_AVAILABLE = False
    AzureOpenAIEnricher = None

# Import enhanced scraping capabilities
try:
    from .scraping.unified_scraper import UnifiedScraper, ScrapingResult
    ENHANCED_SCRAPING_AVAILABLE = True
except ImportError:
    ENHANCED_SCRAPING_AVAILABLE = False
    UnifiedScraper = None  # type: ignore[assignment,misc]
    ScrapingResult = None  # type: ignore[assignment,misc]
    logging.warning("Enhanced scraping not available - using basic methods")


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle non-serializable objects"""
    def default(self, obj):
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            return str(obj)


class CrateDataPipeline:
    """Orchestrates the entire data collection, enrichment, and analysis pipeline."""

    def __init__(self, config: PipelineConfig, crate_list: "List[str] | None" = None, **kwargs) -> None:
        self.config = config
        self.api_client = CrateAPIClient(config)
        self.github_client = GitHubBatchClient(config)
        
        # Initialize the appropriate AI enricher based on configuration
        if config.use_azure_openai and AZURE_OPENAI_AVAILABLE and AzureOpenAIEnricher is not None:
            try:
                self.enricher = AzureOpenAIEnricher(config)
                logging.info("[OK] Using Azure OpenAI enricher")
            except Exception as e:
                logging.warning(f"[WARN] Failed to initialize Azure OpenAI enricher: {e}")
                logging.info("[INFO] Falling back to local LLM enricher")
                self.enricher = LLMEnricher(config)
        else:
            if config.use_azure_openai and not AZURE_OPENAI_AVAILABLE:
                logging.warning("[WARN] Azure OpenAI requested but not available")
            self.enricher = LLMEnricher(config)
            logging.info("[OK] Using local LLM enricher")
        
        # Initialize cargo analyzer
        self.cargo_analyzer = CrateAnalyzer(".")
        
        # Use provided crate_list or load from file
        if crate_list:
            self.crates = crate_list
            logging.info(f"Using provided crate list: {len(crate_list)} crates")
        else:
            self.crates = self._get_crate_list()
        
        self.output_dir = self._create_output_dir()
        self.enhanced_scraper: Any = (
            self._initialize_enhanced_scraper()
        )

    def _initialize_enhanced_scraper(self) -> Any:
        """Initializes the CrateDocumentationScraper if available and enabled."""
        if (
            not ENHANCED_SCRAPING_AVAILABLE
            or not self.config.enable_crawl4ai
            or UnifiedScraper is None
        ):
            return None
        try:
            scraper = UnifiedScraper()
            logging.info("[OK] Enhanced scraping with Crawl4AI enabled")
            return scraper
        except Exception as e:
            logging.warning(f"[ERROR] Failed to initialize enhanced scraping: {e}")
            return None

    def _create_output_dir(self) -> str:
        """Creates a timestamped output directory for pipeline results."""
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        output_dir = os.path.join(self.config.output_path, f"crate_data_{timestamp}")
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def _get_crate_list(self) -> "List[str]":
        """
        Loads the list of crates to process from an external file.
        This approach is more modular and easier to maintain than a hardcoded list.
        """
        crate_list_path = os.path.join(os.path.dirname(__file__), "crate_list.txt")
        try:
            with open(crate_list_path) as f:
                crates = [line.strip() for line in f if line.strip()]
            logging.info(f"Loaded {len(crates)} crates from {crate_list_path}")
            if not crates:
                logging.warning(f"Crate list at {crate_list_path} is empty.")
            return crates
        except FileNotFoundError:
            logging.error(f"Crate list file not found at: {crate_list_path}")
            return []

    def get_crate_list(self) -> "List[str]":
        """
        Public method to get the list of crates.
        Returns the already loaded crate list or loads it if not available.
        """
        if hasattr(self, "crates") and self.crates:
            return self.crates
        else:
            return self._get_crate_list()

    async def fetch_metadata_batch(self, crate_names: "List[str]") -> "List[CrateMetadata]":
        """
        Fetches metadata for a batch of crates using asyncio-based parallel processing.
        """

        async def fetch_single_crate_safe(
            crate_name: str,
        ) -> Union[CrateMetadata, None]:
            try:
                loop = asyncio.get_running_loop()
                data = await loop.run_in_executor(
                    None, self.api_client.fetch_crate_metadata, crate_name
                )
                if not data:
                    return None

                return CrateMetadata(
                    name=data.get("name", ""),
                    version=data.get("version", ""),
                    description=data.get("description", ""),
                    repository=data.get("repository", ""),
                    keywords=data.get("keywords", []),
                    categories=data.get("categories", []),
                    readme=data.get("readme", ""),
                    downloads=data.get("downloads", 0),
                    github_stars=data.get("github_stars", 0),
                    dependencies=data.get("dependencies", []),
                    features=data.get("features", {}),
                    code_snippets=data.get("code_snippets", []),
                    readme_sections=data.get("readme_sections", {}),
                    librs_downloads=data.get("librs_downloads"),
                    source=data.get("source", "crates.io"),
                )

            except Exception as e:
                logging.error(f"Error fetching metadata for {crate_name}: {e}")
                return None

        tasks = [fetch_single_crate_safe(name) for name in crate_names]
        results_raw = await asyncio.gather(*tasks)
        results = [r for r in results_raw if r]
        logging.info(
            f"Fetched metadata for {len(results)} out of "
            f"{len(crate_names)} requested crates."
        )
        return results

    async def enrich_batch(self, batch: "List[CrateMetadata]") -> "List[EnrichedCrate]":
        """Enriches a batch of crates with GitHub stats, enhanced scraping, and AI."""
        # Update GitHub stats
        github_repos = [
            c.repository for c in batch if c.repository and "github.com" in c.repository
        ]
        if github_repos:
            repo_stats = self.github_client.batch_get_repo_stats(github_repos)
            for crate in batch:
                if crate.repository in repo_stats:
                    stats = repo_stats[crate.repository]
                    crate.github_stars = stats.get("stargazers_count", 0)

        # Asynchronously enhance with scraping and AI
        enrichment_tasks = [self._enrich_single_crate(crate) for crate in batch]
        enriched_results = await asyncio.gather(*enrichment_tasks)
        return [result for result in enriched_results if result]

    async def _enrich_single_crate(self, crate: CrateMetadata) -> Union[EnrichedCrate, None]:
        """Helper to enrich a single crate with scraping, AI analysis, and cargo analysis."""
        try:
            # Enhanced scraping if available
            if self.enhanced_scraper:
                await self._enhance_with_scraping(crate)

            # Now enrich with AI
            enriched = self.enricher.enrich_crate(crate)
            
            # Add cargo analysis if we have a local crate directory
            # Note: This would require downloading/cloning the crate first
            # For now, we'll add a placeholder for cargo analysis
            enriched.source_analysis = {
                "cargo_analysis_available": False,
                "note": "Cargo analysis requires local crate source code"
            }
            
            logging.info(f"Enriched {crate.name}")
            return enriched
        except Exception as e:
            logging.error(f"Failed to enrich {crate.name}: {e}")
            # Return a partially enriched crate to avoid data loss
            enriched_dict = crate.to_dict()
            return EnrichedCrate(**enriched_dict)

    async def _enhance_with_scraping(self, crate: CrateMetadata) -> None:
        """
        Enhances a single crate with advanced web scraping data.
        Modifies the crate object in place.
        """
        if not self.enhanced_scraper:
            return

        try:
            scraping_results = await self.enhanced_scraper.scrape_crate_documentation(crate.name)
            if scraping_results:
                self._integrate_scraping_results(crate, scraping_results)
                logging.info(
                    f"Enhanced scraping for {crate.name}: "
                    f"{len(scraping_results)} sources"
                )
        except Exception as e:
            logging.warning(f"Enhanced scraping failed for {crate.name}: {e}")

    def _integrate_scraping_results(
        self,
        crate: CrateMetadata,
        scraping_results: "Dict[str, Any]",
    ) -> None:
        """
        Integrates enhanced scraping results into the crate metadata.
        Modifies the crate object in place.
        """
        crate.enhanced_scraping = {}

        for source, result in scraping_results.items():
            if not result or result.error:
                continue

            crate.enhanced_scraping[source] = {
                "title": result.title,
                "quality_score": result.quality_score,
                "extraction_method": result.extraction_method,
                "structured_data": result.structured_data,
                "content_length": len(result.content),
            }
            # Update README if we got better content
            if source == "docs_rs" and result.quality_score > 0.7:
                if not crate.readme or len(result.content) > len(crate.readme):
                    crate.readme = result.content
                    logging.info(f"Updated README for {crate.name} from {source}")

            # Extract additional metadata from structured data
            structured_data = result.structured_data or {}
            if "features" in structured_data and isinstance(
                structured_data["features"], list
            ):
                crate.enhanced_features = structured_data["features"]
            if "dependencies" in structured_data and isinstance(
                structured_data["dependencies"], list
            ):
                crate.enhanced_dependencies = structured_data["dependencies"]
            if "examples" in structured_data and isinstance(
                structured_data["examples"], list
            ):
                crate.code_snippets.extend(structured_data["examples"])

    def analyze_dependencies(self, crates: "List[EnrichedCrate]") -> "Dict[str, Any]":
        """Analyze dependencies between crates."""
        return DependencyAnalyzer.analyze_dependencies(crates)

    def save_checkpoint(self, data: "List[EnrichedCrate]", prefix: str) -> str:
        """Saves a processing checkpoint to a file."""
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = os.path.join(self.output_dir, f"{prefix}_{timestamp}.jsonl")

        with open(filename, "w") as f:
            for item in data:
                f.write(json.dumps(item.to_dict(), cls=CustomJSONEncoder) + "\n")

        logging.info(f"Saved checkpoint to {filename}")
        return filename

    def save_final_output(
        self, data: "List[EnrichedCrate]", dependency_data: "Dict[str, Any]"
    ) -> None:
        """Saves the final enriched data and analysis reports."""
        timestamp = time.strftime("%Y%m%d-%H%M%S")

        # Save main enriched data
        final_output_path = os.path.join(
            self.output_dir, f"enriched_crate_metadata_{timestamp}.jsonl"
        )
        with open(final_output_path, "w") as f:
            for item in data:
                f.write(json.dumps(item.to_dict(), cls=CustomJSONEncoder) + "\n")

        # Save dependency analysis
        dep_file_path = os.path.join(
            self.output_dir, f"dependency_analysis_{timestamp}.json"
        )
        with open(dep_file_path, "w") as f:
            json.dump(dependency_data, f, indent=2)

        # Generate and save summary report
        self._generate_summary_report(data, dependency_data, timestamp)

        logging.info(f"Results saved to {self.output_dir}/")

    def _generate_summary_report(
        self,
        data: "List[EnrichedCrate]",
        dependency_data: "Dict[str, Any]",
        timestamp: str,
    ) -> None:
        """Generates a summary report of the pipeline run."""
        summary = {
            "total_crates": len(data),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "most_popular": sorted(
                [
                    {
                        "name": c.name,
                        "score": c.score or 0,
                        "downloads": c.downloads,
                        "github_stars": c.github_stars,
                    }
                    for c in data
                ],
                key=lambda x: x.get("score", 0),
                reverse=True,
            )[:10],
            "most_depended_upon": dependency_data.get("most_depended", [])[:10],
        }

        summary_path = os.path.join(self.output_dir, f"summary_report_{timestamp}.json")
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)

    async def run(self) -> Union["tuple[List[EnrichedCrate], Dict[str, Any]]", None]:
        """Main pipeline execution flow."""
        start_time = time.time()
        if not self.crates:
            logging.error("No crates to process. Exiting.")
            return None

        logging.info(f"Processing {len(self.crates)} crates...")

        all_enriched: "List[EnrichedCrate]" = []
        batch_size = self.config.batch_size
        crate_batches = [
            self.crates[i : i + batch_size]
            for i in range(0, len(self.crates), batch_size)
        ]

        for i, batch_names in enumerate(crate_batches):
            logging.info(
                f"Processing batch {i + 1}/{len(crate_batches)} "
                f"({len(batch_names)} crates)"
            )

            # Fetch metadata
            metadata_batch = await self.fetch_metadata_batch(batch_names)
            if not metadata_batch:
                logging.warning(f"Batch {i+1} yielded no metadata. Skipping.")
                continue

            # Enrich the batch
            enriched_batch = await self.enrich_batch(metadata_batch)
            all_enriched.extend(enriched_batch)

            # Save checkpoint
            self.save_checkpoint(all_enriched, f"checkpoint_batch_{i + 1}")
            logging.info(
                f"Completed batch {i + 1}, "
                f"processed {len(all_enriched)}/{len(self.crates)} crates"
            )

        # Final analysis and saving
        logging.info("Analyzing crate dependencies...")
        dependency_analysis = self.analyze_dependencies(all_enriched)
        self.save_final_output(all_enriched, dependency_analysis)

        duration = time.time() - start_time
        logging.info(f"[OK] Done. Enriched {len(all_enriched)} crates in {duration:.2f}s")
        return all_enriched, dependency_analysis
