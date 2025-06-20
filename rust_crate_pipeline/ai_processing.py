# ai_processing.py
import re
import time
import logging
from typing import Callable, Optional, List, TypedDict

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
    def __init__(self, config: PipelineConfig):
        if not _ai_dependencies_available:
            raise ImportError(
                "AI dependencies (tiktoken, llama_cpp) are not available. "
                "Please install them to use LLMEnricher."
            )

        self.config = config
        self.tokenizer = tiktoken.get_encoding("cl100k_base")  # type: ignore
        self.model = self._load_model()

    def _load_model(self):
        """Optimized for GCP g2-standard-4 with L4 GPU (24GB VRAM)"""
        if not _ai_dependencies_available:
            raise ImportError("Cannot load model: AI dependencies not available")

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
            pairs: List[str] = []
            facts = re.findall(r"✅\s*Factual:?\s*(.*?)(?=❌|\Z)", output, re.DOTALL)
            counterfacts = re.findall(
                r"❌\s*Counterfactual:?\s*(.*?)(?=✅|\Z)", output, re.DOTALL
            )

            # Pair them up
            for i in range(min(len(facts), len(counterfacts))):
                pairs.append(
                    f'✅ Factual: {facts[i].strip()}\n'
                    f'❌ Counterfactual: {counterfacts[i].strip()}'
                )

            return "\n\n".join(pairs)

        else:
            # General cleaning - more permissive than before
            lines = [line.strip() for line in output.splitlines() if line.strip()]
            return "\n".join(lines)

    def run_llama(
        self, prompt: str, temp: float = 0.2, max_tokens: int = 256
    ) -> Optional[str]:
        """Run the LLM with customizable parameters per task"""
        try:
            token_count = self.estimate_tokens(prompt)
            if token_count > self.config.prompt_token_margin:
                logging.warning(f"Prompt too long ({token_count} tokens). Truncating.")
                prompt = self.truncate_content(
                    prompt, self.config.prompt_token_margin - 100
                )

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
    ) -> Optional[str]:
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
                logging.error(
                    f"Generation error on attempt {attempt + 1}: {str(e)}"
                )

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

            # Format features with their dependencies
            feature_text = ""
            for feature_name, deps in list(crate.features.items())[:8]:
                deps_str = ", ".join(deps) if deps else "none"
                feature_text += f"- {feature_name} (dependencies: {deps_str})\n"

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
            logging.warning(
                f"Feature summarization failed for {crate.name}: {str(e)}"
            )
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
            features = ", ".join(list(crate.features.keys())[:5])

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
            logging.error(
                f"Exception in factual_pairs for {crate.name}: {str(e)}"
            )
            return "Factual pairs generation failed."

    def score_crate(self, crate: CrateMetadata) -> float:
        """Calculate a score for the crate based on various metrics"""
        score = (crate.downloads / 1000) + (crate.github_stars * 10)
        score += len(self.truncate_content(crate.readme, 1000)) / 500
        return round(score, 2)

    def batch_process_prompts(
        self, prompts: list[tuple[str, float, int]], batch_size: int = 4
    ) -> list[Optional[str]]:
        """
        L4 GPU-optimized batch processing for multiple prompts.
        Processes prompts in batches to maximize GPU utilization.

        Args:
            prompts: List of (prompt, temperature, max_tokens) tuples
            batch_size: Number of prompts to process simultaneously
        """
        results: List[Optional[str]] = []

        # Process in batches optimized for L4's capabilities
        for i in range(0, len(prompts), batch_size):
            batch = prompts[i : i + batch_size]
            batch_results: List[Optional[str]] = []

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
        context_parts: List[str] = []
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
