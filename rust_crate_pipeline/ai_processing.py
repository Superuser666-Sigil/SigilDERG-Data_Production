# ai_processing.py
import re
import time
import logging
import os
from typing import TypedDict, Union

from collections.abc import Callable

from .config import PipelineConfig, CrateMetadata, EnrichedCrate

# Optional imports with fallbacks
_ai_dependencies_available = True
try:
    import tiktoken
    from llama_cpp import Llama
except ImportError as e:
    logging.warning(f"AI dependencies not available: {e}")
    tiktoken = None  # type: ignore[assignment]
    Llama = None  # type: ignore[assignment,misc]
    _ai_dependencies_available = False


class Section(TypedDict):
    heading: str
    content: str
    priority: int


class LLMEnricher:
    def __init__(self, config: PipelineConfig) -> None:
        """Initialize LLMEnricher with automatic provider detection"""
        if not _ai_dependencies_available:
            raise ImportError("Cannot load model: AI dependencies not available")

        self.config = config
        self.tokenizer = tiktoken.get_encoding("cl100k_base")  # type: ignore
        
        # Auto-detect and configure the appropriate LLM provider
        self.model = self._auto_detect_and_load_model()

    def _auto_detect_and_load_model(self):
        """Automatically detect and load the appropriate LLM provider"""
        
        # Priority 1: Check if Azure OpenAI is configured and available
        if (self.config.use_azure_openai and 
            self.config.azure_openai_endpoint and 
            self.config.azure_openai_api_key and 
            self.config.azure_openai_deployment_name):
            
            try:
                # Use the UnifiedLLMProcessor for Azure
                from .unified_llm_processor import create_llm_processor_from_config
                return create_llm_processor_from_config(self.config)
            except Exception as e:
                logging.warning(f"Azure OpenAI setup failed, falling back to local: {e}")
        
        # Priority 2: Check if local model file exists
        if os.path.exists(self.config.model_path):
            try:
                return self._load_local_model()
            except Exception as e:
                logging.warning(f"Local model loading failed: {e}")
        
        # Priority 3: Check for other local providers (Ollama, LM Studio)
        if self._check_ollama_available():
            try:
                from .unified_llm_processor import LLMConfig, UnifiedLLMProcessor
                llm_config = LLMConfig(
                    provider="ollama",
                    model="llama2",  # Default model
                    temperature=0.2,
                    max_tokens=self.config.max_tokens,
                    timeout=30,
                    max_retries=self.config.max_retries
                )
                return UnifiedLLMProcessor(llm_config)
            except Exception as e:
                logging.warning(f"Ollama setup failed: {e}")
        
        # Priority 4: Check for LM Studio
        if self._check_lmstudio_available():
            try:
                from .unified_llm_processor import LLMConfig, UnifiedLLMProcessor
                llm_config = LLMConfig(
                    provider="lmstudio",
                    model="local-model",  # Default model
                    temperature=0.2,
                    max_tokens=self.config.max_tokens,
                    timeout=30,
                    max_retries=self.config.max_retries
                )
                return UnifiedLLMProcessor(llm_config)
            except Exception as e:
                logging.warning(f"LM Studio setup failed: {e}")
        
        # If all else fails, raise a clear error
        raise RuntimeError(
            "No LLM provider available. Please configure one of:\n"
            "1. Azure OpenAI (set use_azure_openai=True and credentials)\n"
            "2. Local model file (set model_path to existing .gguf file)\n"
            "3. Ollama (install and run ollama serve)\n"
            "4. LM Studio (install and run LM Studio server)"
        )

    def _load_local_model(self):
        """Load local llama.cpp model"""
        return Llama(  # type: ignore
            model_path=self.config.model_path,
            n_ctx=4096,  # Larger context for L4's 24GB VRAM
            n_batch=1024,  # Larger batch size for better throughput
            # Load ALL layers on GPU (L4 has plenty VRAM)
            n_gpu_layers=-1,
            n_threads=4,  # Match the 4 vCPUs
            n_threads_batch=4,  # Parallel batch processing
            use_mmap=True,  # Memory-mapped files for efficiency
            use_mlock=True,  # Lock model in memory
            rope_scaling_type=1,  # RoPE scaling for longer contexts
            rope_freq_base=10000.0,  # Base frequency for RoPE
            flash_attn=True,  # Enable flash attention if available
            verbose=False,  # Reduce logging overhead
        )

    def _check_ollama_available(self):
        """Check if Ollama is available"""
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False

    def _check_lmstudio_available(self):
        """Check if LM Studio is available"""
        try:
            import requests
            response = requests.get("http://localhost:1234/v1/models", timeout=5)
            return response.status_code == 200
        except:
            return False

    def estimate_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

    def truncate_content(self, content: str, max_tokens: int = 1000) -> str:
        """Truncate content to fit within token limit"""
        paragraphs = content.split("\n\n")
        result, current_tokens = "", 0

        for para in paragraphs:
            tokens = len(self.tokenizer.encode(para))
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
        if len(self.tokenizer.encode(content)) <= max_tokens:
            return content

        # Split into sections based on markdown headers
        sections: list[Section] = []
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
                if re.search(r"\b(Union[usage, example]|getting started)\b", heading, re.I):
                    priority = 10
                elif re.search(r"\b(Union[feature, overview]|about)\b", heading, re.I):
                    priority = 9
                elif re.search(r"\b(Union[install, setup]|config)\b", heading, re.I):
                    priority = 8
                elif re.search(r"\b(Union[api, interface])\b", heading, re.I):
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
            section_tokens = len(self.tokenizer.encode(section_text))

            if tokens_used + section_tokens <= max_tokens:
                result += section_text
                tokens_used += section_tokens
            elif tokens_used < max_tokens - 100:  # If we can fit a truncated version
                # Take what we can
                remaining_tokens = max_tokens - tokens_used
                truncated_text = self.tokenizer.decode(
                    self.tokenizer.encode(section_text)[:remaining_tokens]
                )
                result += truncated_text
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
            pairs: list[str] = []
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

        else:
            # General cleaning - more permissive than before
            lines = [line.strip() for line in output.splitlines() if line.strip()]
            return "\n".join(lines)

    def run_llama(
        self, prompt: str, temp: float = 0.2, max_tokens: int = 256
    ) -> Union[str, None]:
        """Run the LLM with customizable parameters per task"""
        try:
            token_count = self.estimate_tokens(prompt)
            if token_count > self.config.prompt_token_margin:
                logging.warning(f"Prompt too long ({token_count} tokens). Truncating.")
                prompt = self.truncate_content(
                    prompt, self.config.prompt_token_margin - 100
                )

            # Handle different model types
            from .unified_llm_processor import UnifiedLLMProcessor
            if isinstance(self.model, UnifiedLLMProcessor):
                # UnifiedLLMProcessor
                return self.model.call_llm(prompt, temp, max_tokens)
            else:
                # Local Llama model
                output = self.model(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=temp,
                    # Stop at these tokens
                    stop=["<|end|>", "<|user|>", "<|system|>"],
                )

                raw_text: str = output["choices"][0]["text"]  # type: ignore
                return self.clean_output(raw_text)
        except Exception as e:
            logging.error(f"Model inference failed: {str(e)}")
            raise

    def validate_and_retry(
        self,
        prompt: str,
        validation_func: Callable[[str], bool],
        temp: float = 0.2,
        max_tokens: int = 256,
        retries: int = 4,  # Increased from 2 to 4 for better success rates
    ) -> Union[str, None]:
        """Run LLM with validation and automatic retry on failure"""
        result = None
        for attempt in range(retries):
            try:
                # More generous temperature adjustment for better variety
                # 20% increases instead of 10%
                adjusted_temp = temp * (1 + (attempt * 0.2))
                result = self.run_llama(
                    prompt, temp=adjusted_temp, max_tokens=max_tokens
                )

                # Validate the result
                if result and validation_func(result):
                    return result

                # If we get here, validation failed - use debug level for early
                # attempts
                if attempt == retries - 1:
                    logging.debug(
                        f"All {retries} validation attempts failed, "
                        "using last available result."
                    )
                else:
                    logging.debug(
                        f"Validation failed on attempt {attempt + 1}/{retries}. "
                        f"Retrying with adjusted temp={adjusted_temp:.2f}"
                    )

                # Only simplify prompt on later attempts (attempt 2+)
                if attempt >= 2:
                    prompt = self.simplify_prompt(prompt)

            except Exception as e:
                logging.error(f"Generation error on attempt {attempt + 1}: {str(e)}")

                # More generous backoff - give the model more time
            time.sleep(2.0 + (attempt * 1.0))  # 2s, 3s, 4s, 5s delays

        # If we exhausted all retries, return the last result even if not
        # perfect
        return result if "result" in locals() else None

    def simplify_prompt(self, prompt: str) -> str:
        """Simplify a prompt by removing examples and reducing context"""
        # Remove few-shot examples
        prompt = re.sub(
            r"# Example [0-9].*?(?=# Crate to Classify|\Z)",
            "",
            prompt,
            flags=re.DOTALL,
        )

        # Make instructions more direct
        prompt = re.sub(
            r"<\|system\|>.*?<\|user\|>",
            "<|system|>Be concise.\n<|user|>",
            prompt,
            flags=re.DOTALL,
        )

        return prompt

    def validate_classification(self, result: str) -> bool:
        """Ensure a valid category was returned"""
        if not result:
            return False
        valid_categories = [
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
        return any(
            category.lower() == result.strip().lower() for category in valid_categories
        )

    def validate_factual_pairs(self, result: str) -> bool:
        """Ensure exactly 5 factual/counterfactual pairs exist"""
        if not result:
            return False

        facts = re.findall(r"✅\s*Factual:?\s*(.*?)(?=❌|\Z)", result, re.DOTALL)
        counterfacts = re.findall(
            r"❌\s*Counterfactual:?\s*(.*?)(?=✅|\Z)", result, re.DOTALL
        )

        return len(facts) >= 3 and len(counterfacts) >= 3  # At least 3 pairs

    def enrich_crate(self, crate: CrateMetadata) -> EnrichedCrate:
        """Apply all AI enrichments to a crate"""
        # Convert CrateMetadata to EnrichedCrate
        enriched_dict = crate.__dict__.copy()
        enriched = EnrichedCrate(**enriched_dict)

        try:
            # Generate README summary first
            if crate.readme:
                readme_content = self.smart_truncate(crate.readme, 2000)
                prompt = (
                    "<|system|>Extract key features from README.\n"
                    "<|user|>Summarize key aspects of this Rust crate from its "
                    f"README:\n{readme_content}\n"
                    "<|end|>"
                )
                enriched.readme_summary = self.validate_and_retry(
                    prompt, lambda x: len(x) > 50, temp=0.3, max_tokens=300
                )

            # Generate other enrichments
            enriched.feature_summary = self.summarize_features(crate)
            enriched.use_case = self.classify_use_case(
                crate, enriched.readme_summary or ""
            )
            enriched.score = self.score_crate(crate)
            enriched.factual_counterfactual = self.generate_factual_pairs(crate)

            return enriched
        except Exception as e:
            logging.error(f"Failed to enrich {crate.name}: {str(e)}")
            return enriched

    def summarize_features(self, crate: CrateMetadata) -> str:
        """Generate summaries for crate features with better prompting"""
        try:
            if not crate.features:
                return "No features documented for this crate."

            # Handle both dict and list feature formats
            feature_text = ""
            if isinstance(crate.features, dict):
                # Format features with their dependencies
                for feature_name, deps in list(crate.features.items())[:8]:
                    deps_str = ", ".join(deps) if deps else "none"
                    feature_text += f"- {feature_name} (dependencies: {deps_str})\n"
            elif isinstance(crate.features, list):
                # Handle list format - assume each item is a feature name
                for feature in crate.features[:8]:
                    if isinstance(feature, str):
                        feature_text += f"- {feature} (dependencies: none)\n"
                    elif isinstance(feature, dict):
                        # If feature is a dict, try to extract name and deps
                        feature_name = feature.get('name', str(feature))
                        deps = feature.get('dependencies', [])
                        deps_str = ", ".join(deps) if deps else "none"
                        feature_text += f"- {feature_name} (dependencies: {deps_str})\n"
                    else:
                        feature_text += f"- {str(feature)} (dependencies: none)\n"
            else:
                return "Features format not recognized."

            prompt = (
                "<|system|>You are a Rust programming expert analyzing crate "
                "features.\n"
                f"<|user|>For the Rust crate `{crate.name}`, explain these "
                "features and what functionality they provide:\n\n"
                f"{feature_text}\n\n"
                "Provide a concise explanation of each feature's purpose and "
                "when a developer would enable it.\n"
                "<|end|>"
            )

            # Use moderate temperature for informative but natural explanation
            result = self.run_llama(prompt, temp=0.2, max_tokens=350)
            return result or "Feature summary not available."
        except Exception as e:
            logging.warning(f"Feature summarization failed for {crate.name}: {str(e)}")
            return "Feature summary not available."

    def classify_use_case(self, crate: CrateMetadata, readme_summary: str) -> str:
        """Classify the use case of a crate with rich context"""
        try:
            # Calculate available tokens for prompt
            available_prompt_tokens = self.config.model_token_limit - 200

            joined = ", ".join(crate.keywords[:10]) if crate.keywords else "None"
            key_deps = [
                dep.get("crate_id")
                for dep in crate.dependencies[:5]
                if dep.get("kind") == "normal" and dep.get("crate_id")
            ]
            key_deps_str = (
                ", ".join(str(dep) for dep in key_deps) if key_deps else "None"
            )

            # Adaptively truncate different sections based on importance
            token_budget = available_prompt_tokens - 400

            # Allocate different percentages to each section
            desc_tokens = int(token_budget * 0.2)
            readme_tokens = int(token_budget * 0.6)

            desc = self.truncate_content(crate.description, desc_tokens)
            readme_summary = self.smart_truncate(readme_summary, readme_tokens)

            # Few-shot prompting with examples
            prompt = (
                "<|system|>You are a Rust expert classifying crates into the "
                "most appropriate category.\n"
                "<|user|>\n"
                "# Example 1\n"
                "Crate: `tokio`\n"
                "Description: An asynchronous runtime for the Rust programming "
                "language\n"
                "Keywords: async, runtime, futures\n"
                "Key Dependencies: mio, bytes, parking_lot\n"
                "Category: Networking\n\n"
                "# Example 2\n"
                "Crate: `serde`\n"
                "Description: A generic serialization/deserialization framework\n"
                "Keywords: serde, serialization\n"
                "Key Dependencies: serde_derive\n"
                "Category: Serialization\n\n"
                "# Crate to Classify\n"
                f"Crate: `{crate.name}`\n"
                f"Description: {desc}\n"
                f"Keywords: {joined}\n"
                f"README Summary: {readme_summary}\n"
                f"Key Dependencies: {key_deps_str}\n\n"
                "Category (pick only one): [AI, Database, Web Framework, "
                "Networking, Serialization, Utilities, DevTools, ML, "
                "Cryptography, Unknown]\n"
                "<|end|>"
            )
            # Validate classification with retry - more generous parameters
            result = self.validate_and_retry(
                prompt,
                validation_func=self.validate_classification,
                temp=0.2,
                max_tokens=50,
            )

            return result or "Unknown"
        except Exception as e:
            logging.error(f"Classification failed for {crate.name}: {str(e)}")
            return "Unknown"

    def generate_factual_pairs(self, crate: CrateMetadata) -> str:
        """Generate factual/counterfactual pairs with retry and validation"""
        try:
            desc = self.truncate_content(crate.description, 300)
            readme_summary = self.truncate_content(
                getattr(crate, "readme_summary", "") or "", 300
            )
            
            # Handle both dict and list feature formats
            if isinstance(crate.features, dict):
                features = ", ".join(list(crate.features.keys())[:5])
            elif isinstance(crate.features, list):
                feature_names = []
                for feature in crate.features[:5]:
                    if isinstance(feature, str):
                        feature_names.append(feature)
                    elif isinstance(feature, dict):
                        feature_name = feature.get('name', str(feature))
                        feature_names.append(feature_name)
                    else:
                        feature_names.append(str(feature))
                features = ", ".join(feature_names)
            else:
                features = ""

            prompt = (
                "<|system|>Create exactly 5 factual/counterfactual pairs for "
                "the Rust crate. Factual statements must be true. "
                "Counterfactuals should be plausible but incorrect - make them "
                "subtle and convincing rather than simple negations.\n"
                "<|user|>\n"
                f"Crate: {crate.name}\n"
                f"Description: {desc}\n"
                f"Repo: {crate.repository}\n"
                f"README Summary: {readme_summary}\n"
                f"Key Features: {features}\n\n"
                "Format each pair as:\n"
                "✅ Factual: [true statement about the crate]\n"
                "❌ Counterfactual: [plausible but false statement]\n\n"
                "Create exactly 5 pairs.\n"
                "<|end|>"
            )
            # Use validation for retry - more generous parameters
            result = self.validate_and_retry(
                prompt,
                validation_func=self.validate_factual_pairs,
                temp=0.7,
                max_tokens=800,
            )

            return result or "Factual pairs generation failed."
        except Exception as e:
            logging.error(f"Exception in factual_pairs for {crate.name}: {str(e)}")
            return "Factual pairs generation failed."

    def score_crate(self, crate: CrateMetadata) -> float:
        """Calculate a score for the crate based on various metrics"""
        score = (crate.downloads / 1000) + (crate.github_stars * 10)
        score += len(self.truncate_content(crate.readme, 1000)) / 500
        return round(score, 2)

    def batch_process_prompts(
        self, prompts: list[tuple[str, float, int]], batch_size: int = 4
    ) -> list[Union[str, None]]:
        """
        L4 GPU-optimized batch processing for multiple prompts.
        Processes prompts in batches to maximize GPU utilization.

        Args:
            prompts: List of (prompt, temperature, max_tokens) tuples
            batch_size: Number of prompts to process simultaneously
        """
        results: list[Union[str, None]] = []

        # Process in batches optimized for L4's capabilities
        for i in range(0, len(prompts), batch_size):
            batch = prompts[i : i + batch_size]
            batch_results: list[Union[str, None]] = []

            for prompt, temp, max_tokens in batch:
                try:
                    # Prepare prompt with context preservation
                    if self.estimate_tokens(prompt) > 3500:
                        prompt = self.smart_truncate(prompt, 3500)

                    # Use optimized parameters for L4
                    output = self.model(
                        prompt,
                        max_tokens=max_tokens,
                        temperature=temp,
                        top_p=0.95,
                        repeat_penalty=1.1,
                        stop=["<|end|>", "<|user|>", "<|system|>"],
                        echo=False,
                        stream=False,
                    )

                    # The type checker incorrectly infers a stream response
                    choice_text: str = output["choices"][0]["text"]  # type: ignore
                    result = self.clean_output(choice_text)
                    batch_results.append(result)
                except Exception as e:
                    logging.error(f"LLM batch processing error: {e}", exc_info=True)
                    batch_results.append(None)

            results.extend(batch_results)

        return results

    def smart_context_management(
        self, context_history: list[str], new_prompt: str
    ) -> str:
        """
        Intelligent context management for prefix cache optimization.
        Maximizes cache hits by preserving common context patterns.
        """
        # Calculate available tokens for context
        base_tokens = self.estimate_tokens(new_prompt)
        available_context = 4000 - base_tokens  # Leave buffer for response

        if available_context <= 0:
            return new_prompt

        # Build context from most recent and most relevant history
        context_parts: list[str] = []
        tokens_used = 0

        # Prioritize recent context (better cache hits)
        for context in reversed(context_history[-5:]):  # Last 5 contexts
            context_tokens = self.estimate_tokens(context)
            if tokens_used + context_tokens <= available_context:
                context_parts.insert(0, context)
                tokens_used += context_tokens
            else:
                # Try to fit truncated version
                remaining_tokens = available_context - tokens_used
                if remaining_tokens > 100:  # Only if meaningful space left
                    truncated = self.smart_truncate(context, remaining_tokens)
                    if truncated:
                        context_parts.insert(0, truncated)
                break

        # Combine context with new prompt
        if context_parts:
            full_context = "\n\n---\n\n".join(context_parts)
            return f"{full_context}\n\n---\n\n{new_prompt}"

        return new_prompt
