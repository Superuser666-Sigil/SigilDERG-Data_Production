# unified_llm_processor.py
import re
import time
import logging
import json
from typing import TypedDict, Union, Optional, Dict, Any, List, TYPE_CHECKING
from collections.abc import Callable
from dataclasses import dataclass

if TYPE_CHECKING:
    from typing import Tuple

try:
    import litellm
    from litellm import completion
    from litellm.cost_calculator import cost_per_token
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    logging.warning("LiteLLM not available. Install with: pip install litellm")

from .config import PipelineConfig, CrateMetadata, EnrichedCrate


@dataclass
class LLMConfig:
    """Configuration for LLM providers"""
    provider: str  # "azure", "ollama", "lmstudio", "openai", "anthropic", etc.
    model: str  # Model name/identifier
    api_base: Optional[str] = None  # Base URL for API
    api_key: Optional[str] = None  # API key if required
    temperature: float = 0.2
    max_tokens: int = 256
    timeout: int = 30
    max_retries: int = 3
    
    # Provider-specific settings
    azure_deployment: Optional[str] = None
    azure_api_version: Optional[str] = None
    
    # Ollama specific
    ollama_host: Optional[str] = None
    
    # LM Studio specific
    lmstudio_host: Optional[str] = None


class BudgetManager:
    """Monitors and enforces spending limits for LLM calls."""

    def __init__(self, budget: float = 90.0):
        self.budget = budget
        self.total_cost = 0.0

    def update_cost(self, model: str, completion_tokens: int, prompt_tokens: int) -> None:
        """Update the total cost with the latest API call."""
        try:
            cost, _ = cost_per_token(
                model=model,
                completion_tokens=completion_tokens,
                prompt_tokens=prompt_tokens,
            )
            self.total_cost += cost
        except Exception:
            # If cost cannot be determined, do not track.
            pass

    def is_over_budget(self) -> bool:
        """Check if the cumulative cost has exceeded the budget."""
        return self.total_cost > self.budget

    def get_total_cost(self) -> float:
        """Return the current total cost."""
        return self.total_cost


class Section(TypedDict, total=True):
    heading: str
    content: str
    priority: int


class UnifiedLLMProcessor:
    """
    Unified LLM processor supporting all LiteLLM providers:
    - Azure OpenAI
    - Ollama (local models)
    - LM Studio (local models)
    - OpenAI
    - Anthropic
    - Google AI
    - And all other LiteLLM providers
    """
    
    def __init__(self, config: LLMConfig, budget_manager: Optional[BudgetManager] = None) -> None:
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.budget_manager = budget_manager or BudgetManager()
        
        if not LITELLM_AVAILABLE:
            raise ImportError("LiteLLM is required. Install with: pip install litellm")
        
        # Configure LiteLLM based on provider
        self._configure_litellm()
    
    def _configure_litellm(self) -> None:
        """Configure LiteLLM based on the provider"""
        if self.config.provider == "azure":
            # Azure OpenAI configuration
            if self.config.api_base and self.config.api_key:
                # Azure config is handled in the completion call
                pass
                
        elif self.config.provider == "ollama":
            # Ollama configuration
            if self.config.ollama_host:
                litellm.api_base = self.config.ollama_host
            else:
                litellm.api_base = "http://localhost:11434"
                
        elif self.config.provider == "lmstudio":
            # LM Studio configuration
            if self.config.lmstudio_host:
                litellm.api_base = self.config.lmstudio_host
            else:
                litellm.api_base = "http://localhost:1234/v1"
                
        elif self.config.provider in ["openai", "anthropic", "google"]:
            # These use standard API keys
            if self.config.api_key:
                # API key is set in the completion call
                pass
    
    def _get_model_name(self) -> str:
        """Get the appropriate model name for the provider"""
        if self.config.provider == "azure":
            return f"azure/{self.config.model}"
        elif self.config.provider == "ollama":
            return self.config.model
        elif self.config.provider == "lmstudio":
            return self.config.model
        else:
            return self.config.model
    
    def _get_api_base(self) -> Optional[str]:
        """Get the API base URL for the provider"""
        if self.config.provider == "azure":
            return self.config.api_base
        elif self.config.provider == "ollama":
            return self.config.ollama_host or "http://localhost:11434"
        elif self.config.provider == "lmstudio":
            return self.config.lmstudio_host or "http://localhost:1234/v1"
        else:
            return self.config.api_base
    
    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 characters per token)"""
        return len(text) // 4

    def truncate_content(self, content: str, max_tokens: int = 1000) -> str:
        """Truncate content to fit within token limit"""
        paragraphs = content.split("\n\n")
        result, current_tokens = "", 0

        for para in paragraphs:
            tokens = self.estimate_tokens(para)
            if current_tokens + tokens <= max_tokens:
                result += para + "\n\n"
                current_tokens += tokens
            else:
                break
        return result.strip()

    def smart_truncate(self, content: str, max_tokens: int = 1000) -> str:
        """Intelligently truncate content to preserve the most important parts"""
        if not content:
            return ""

        # If content is short enough, return it all
        if self.estimate_tokens(content) <= max_tokens:
            return content

        # Split into sections based on markdown headers
        sections: List[Section] = []
        current_section: Section = {
            "heading": "Introduction",
            "content": "",
            "priority": 10,
        }

        for line in content.splitlines():
            if re.match(r"^#+\s+", line):  # It's a header
                # Save previous section if not empty
                if current_section["content"].strip():
                    sections.append(current_section)

                # Create new section with appropriate priority
                heading = re.sub(r"^#+\s+", "", line)
                priority = 5  # Default priority

                # Assign priority based on content type
                if re.search(r"\b(usage|example|getting started)\b", heading, re.I):
                    priority = 10
                elif re.search(r"\b(feature|overview|about)\b", heading, re.I):
                    priority = 9
                elif re.search(r"\b(install|setup|config)\b", heading, re.I):
                    priority = 8
                elif re.search(r"\b(api|interface)\b", heading, re.I):
                    priority = 7

                current_section = {
                    "heading": heading,
                    "content": line + "\n",
                    "priority": priority,
                }
            else:
                current_section["content"] += line + "\n"

                # Boost priority if code block is found
                if "```rust" in line or "```no_run" in line:
                    current_section["priority"] = max(current_section["priority"], 8)

        # Add the last section
        if current_section["content"].strip():
            sections.append(current_section)

        # Sort sections by priority (highest first)
        sections.sort(key=lambda x: x["priority"], reverse=True)

        # Build the result, respecting token limits
        result = ""
        tokens_used = 0

        for section in sections:
            section_text = f'## {section["heading"]}\n{section["content"]}\n'
            section_tokens = self.estimate_tokens(section_text)

            if tokens_used + section_tokens <= max_tokens:
                result += section_text
                tokens_used += section_tokens
            elif tokens_used < max_tokens - 100:  # If we can fit a truncated version
                # Take what we can
                remaining_tokens = max_tokens - tokens_used
                # Simple truncation by characters
                max_chars = remaining_tokens * 4
                if len(section_text) > max_chars:
                    result += section_text[:max_chars] + "..."
                else:
                    result += section_text
                break

        return result

    def clean_output(self, output: str, task: str = "general") -> str:
        """Task-specific output cleaning"""
        if not output:
            return ""

        # Remove any remaining prompt artifacts
        output = output.split("<|end|>")[0].strip()

        if task == "classification":
            # For classification tasks, extract just the category
            categories = [
                "AI",
                "Database",
                "Web Framework",
                "Networking",
                "Serialization",
                "Utilities",
                "DevTools",
                "ML",
                "Cryptography",
                "Unknown",
            ]
            for category in categories:
                if re.search(
                    r"\b" + re.escape(category) + r"\b", output, re.IGNORECASE
                ):
                    return category
            return "Unknown"

        elif task == "factual_pairs":
            # For factual pairs, ensure proper formatting
            pairs: List[str] = []
            facts = re.findall(r"✅\s*Factual:?\s*(.*?)(?=❌|\Z)", output, re.DOTALL)
            counterfacts = re.findall(
                r"❌\s*Counterfactual:?\s*(.*?)(?=✅|\Z)", output, re.DOTALL
            )

            # Pair them up
            for i in range(min(len(facts), len(counterfacts))):
                pairs.append(
                    f"✅ Factual: {facts[i].strip()}\n"
                    f"❌ Counterfactual: {counterfacts[i].strip()}"
                )

            return "\n\n".join(pairs)

        return output

    def call_llm(
        self, 
        prompt: str, 
        temperature: Optional[float] = None, 
        max_tokens: Optional[int] = None,
        system_message: str = "You are a helpful AI assistant that analyzes Rust crates and provides insights."
    ) -> Optional[str]:
        """Call the LLM with the given prompt and parameters."""
        
        if self.budget_manager and self.budget_manager.is_over_budget():
            self.logger.warning("Budget exceeded. Skipping LLM call.")
            return None

        model_name = self._get_model_name()
        
        # Prepare arguments for the completion call
        args: Dict[str, Any] = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature if temperature is not None else self.config.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.config.max_tokens,
            "timeout": self.config.timeout
        }
        
        # Provider-specific arguments
        if self.config.provider == "azure":
            args["api_base"] = self.config.api_base
            args["api_key"] = self.config.api_key
            args["api_version"] = self.config.azure_api_version
            # For Azure, model can be just the deployment name
            args["model"] = self.config.azure_deployment or self.config.model
        else:
            args["api_base"] = self._get_api_base()
            args["api_key"] = self.config.api_key

        try:
            response = completion(**args)
            
            # Update budget
            if self.budget_manager:
                completion_tokens = response.usage.completion_tokens # type: ignore
                prompt_tokens = response.usage.prompt_tokens # type: ignore
                self.budget_manager.update_cost(model=model_name, completion_tokens=completion_tokens, prompt_tokens=prompt_tokens)

            return response.choices[0].message.content # type: ignore
            
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            return None

    def validate_and_retry(
        self,
        prompt: str,
        validation_func: Callable[[str], bool],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        retries: Optional[int] = None,
        system_message: str = "You are a helpful AI assistant that analyzes Rust crates and provides insights."
    ) -> Optional[str]:
        """Call LLM with validation and retry logic"""
        max_retries = retries if retries is not None else self.config.max_retries
        
        for attempt in range(max_retries + 1):
            try:
                result = self.call_llm(prompt, temperature, max_tokens, system_message)
                if result and validation_func(result):
                    return result
                    
                if attempt < max_retries:
                    self.logger.warning(f"Validation failed, retrying... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(1 * (attempt + 1))  # Exponential backoff
                    
            except Exception as e:
                self.logger.error(f"Error in attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries:
                    time.sleep(1 * (attempt + 1))
                    
        self.logger.error(f"Failed after {max_retries + 1} attempts")
        return None

    def simplify_prompt(self, prompt: str) -> str:
        """Simplify prompt for better LLM understanding"""
        # Remove excessive whitespace and normalize
        prompt = re.sub(r'\n\s*\n', '\n\n', prompt)
        prompt = re.sub(r' +', ' ', prompt)
        return prompt.strip()

    def validate_classification(self, result: str) -> bool:
        """Validate classification output"""
        categories = ["AI", "Database", "Web Framework", "Networking", "Serialization", 
                     "Utilities", "DevTools", "ML", "Cryptography", "Unknown"]
        return any(cat.lower() in result.lower() for cat in categories)

    def validate_factual_pairs(self, result: str) -> bool:
        """Validate factual pairs output"""
        return "✅" in result and "❌" in result

    def enrich_crate(self, crate: CrateMetadata) -> EnrichedCrate:
        """Enrich a crate with LLM analysis"""
        self.logger.info(f"Enriching crate: {crate.name}")
        
        # Create enriched crate with base metadata
        enriched = EnrichedCrate(**crate.__dict__)
        
        # Summarize README
        if crate.readme:
            readme_summary = self.summarize_features(crate)
            enriched.readme_summary = readme_summary
            
            # Classify use case
            use_case = self.classify_use_case(crate, readme_summary)
            enriched.use_case = use_case
            
            # Generate factual pairs
            factual_pairs = self.generate_factual_pairs(crate)
            enriched.factual_counterfactual = factual_pairs
            
            # Score crate
            score = self.score_crate(crate)
            enriched.score = score
        
        return enriched

    def summarize_features(self, crate: CrateMetadata) -> str:
        """Summarize crate features using LLM"""
        prompt = f"""
        Summarize the key features and capabilities of the Rust crate '{crate.name}' based on its README.
        
        Crate: {crate.name} v{crate.version}
        Description: {crate.description}
        Keywords: {', '.join(crate.keywords)}
        Categories: {', '.join(crate.categories)}
        
        README Content:
        {self.smart_truncate(crate.readme, 2000)}
        
        Provide a concise summary (2-3 sentences) of what this crate does and its main features.
        """
        
        result = self.call_llm(
            self.simplify_prompt(prompt),
            temperature=0.3,
            max_tokens=150,
            system_message="You are an expert Rust developer who summarizes crate features concisely."
        )
        
        return self.clean_output(result or "Unable to summarize features", "general")

    def classify_use_case(self, crate: CrateMetadata, readme_summary: str) -> str:
        """Classify the primary use case of the crate"""
        prompt = f"""
        Classify the primary use case of the Rust crate '{crate.name}' into one of these categories:
        - AI: Machine learning, AI, or data science related
        - Database: Database drivers, ORMs, or data storage
        - Web Framework: Web servers, HTTP, or web development
        - Networking: Network protocols, communication, or system networking
        - Serialization: Data serialization, deserialization, or format handling
        - Utilities: General utilities, helpers, or tools
        - DevTools: Development tools, testing, or debugging
        - ML: Machine learning specific (subset of AI)
        - Cryptography: Security, encryption, or cryptographic operations
        - Unknown: If none of the above categories fit
        
        Crate: {crate.name} v{crate.version}
        Description: {crate.description}
        Summary: {readme_summary}
        Keywords: {', '.join(crate.keywords)}
        Categories: {', '.join(crate.categories)}
        
        Respond with only the category name.
        """
        
        result = self.validate_and_retry(
            self.simplify_prompt(prompt),
            self.validate_classification,
            temperature=0.1,
            max_tokens=50,
            system_message="You are a Rust ecosystem expert who classifies crates accurately."
        )
        
        return self.clean_output(result or "Unknown", "classification")

    def generate_factual_pairs(self, crate: CrateMetadata) -> str:
        """Generate factual and counterfactual statements about the crate"""
        prompt = f"""
        Generate 2-3 pairs of factual and counterfactual statements about the Rust crate '{crate.name}'.
        
        Crate: {crate.name} v{crate.version}
        Description: {crate.description}
        Keywords: {', '.join(crate.keywords)}
        
        README Content:
        {self.smart_truncate(crate.readme, 1500)}
        
        For each pair:
        - ✅ Factual: A true statement about the crate's capabilities or features
        - ❌ Counterfactual: A false statement that sounds plausible but is incorrect
        
        Format each pair as:
        ✅ Factual: [true statement]
        ❌ Counterfactual: [false statement]
        
        Focus on technical capabilities, performance characteristics, and use cases.
        """
        
        result = self.validate_and_retry(
            self.simplify_prompt(prompt),
            self.validate_factual_pairs,
            temperature=0.4,
            max_tokens=300,
            system_message="You are a Rust expert who generates accurate factual statements and plausible counterfactuals."
        )
        
        return self.clean_output(result or "Unable to generate factual pairs", "factual_pairs")

    def score_crate(self, crate: CrateMetadata) -> float:
        """Score the crate based on various factors"""
        prompt = f"""
        Rate the Rust crate '{crate.name}' on a scale of 0.0 to 10.0 based on:
        - Documentation quality (README, examples)
        - Feature completeness
        - Community adoption (downloads, stars)
        - Code quality indicators
        - Practical usefulness
        
        Crate: {crate.name} v{crate.version}
        Description: {crate.description}
        Downloads: {crate.downloads}
        GitHub Stars: {crate.github_stars}
        Keywords: {', '.join(crate.keywords)}
        
        README Content:
        {self.smart_truncate(crate.readme, 1000)}
        
        Respond with only a number between 0.0 and 10.0 (e.g., 7.5).
        """
        
        result = self.call_llm(
            self.simplify_prompt(prompt),
            temperature=0.2,
            max_tokens=10,
            system_message="You are a Rust ecosystem expert who rates crates objectively."
        )
        
        if result:
            try:
                # Extract numeric score
                score_match = re.search(r'(\d+\.?\d*)', result)
                if score_match:
                    score = float(score_match.group(1))
                    return max(0.0, min(10.0, score))  # Clamp between 0-10
            except (ValueError, TypeError):
                pass
        
        return 5.0  # Default score

    def batch_process_prompts(
        self, 
        prompts: "List[Tuple[str, float, int]]", 
        batch_size: int = 4
    ) -> List[Optional[str]]:
        """Process multiple prompts in batches"""
        results = []
        
        for i in range(0, len(prompts), batch_size):
            batch = prompts[i:i + batch_size]
            batch_results = []
            
            for prompt, temp, tokens in batch:
                result = self.call_llm(prompt, float(temp), int(tokens))
                batch_results.append(result)
                
            results.extend(batch_results)
            
            # Small delay between batches
            if i + batch_size < len(prompts):
                time.sleep(0.5)
        
        return results

    def smart_context_management(
        self, context_history: List[str], new_prompt: str
    ) -> str:
        """Manage context intelligently to avoid token limits"""
        # Simple context management - could be enhanced
        total_context = "\n".join(context_history[-3:]) + "\n" + new_prompt
        return self.smart_truncate(total_context, 3000)


def create_llm_processor_from_config(pipeline_config: PipelineConfig) -> UnifiedLLMProcessor:
    """Create LLM processor from pipeline configuration"""
    
    # Determine which provider to use based on config
    if pipeline_config.use_azure_openai:
        llm_config = LLMConfig(
            provider="azure",
            model=pipeline_config.azure_openai_deployment_name,
            api_base=pipeline_config.azure_openai_endpoint,
            api_key=pipeline_config.azure_openai_api_key,
            azure_deployment=pipeline_config.azure_openai_deployment_name,
            azure_api_version=pipeline_config.azure_openai_api_version,
            temperature=0.2,
            max_tokens=pipeline_config.max_tokens,
            timeout=30,
            max_retries=pipeline_config.max_retries
        )
    else:
        # Default to local model
        llm_config = LLMConfig(
            provider="ollama",  # Default local provider
            model="llama2",  # Default model
            temperature=0.2,
            max_tokens=pipeline_config.max_tokens,
            timeout=30,
            max_retries=pipeline_config.max_retries
        )
    
    budget_manager = BudgetManager(budget=pipeline_config.budget) if pipeline_config.budget is not None else None
    
    return UnifiedLLMProcessor(llm_config, budget_manager=budget_manager)


def create_llm_processor_from_args(
    provider: str,
    model: str,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 256,
    budget: Optional[float] = None,
    **kwargs
) -> UnifiedLLMProcessor:
    """Create a UnifiedLLMProcessor from command-line arguments."""
    
    llm_config = LLMConfig(
        provider=provider,
        model=model,
        api_base=api_base,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs
    )
    
    budget_manager = BudgetManager(budget=budget) if budget is not None else None
    
    return UnifiedLLMProcessor(llm_config, budget_manager=budget_manager) 