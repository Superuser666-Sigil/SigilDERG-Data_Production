# azure_ai_processing.py
import re
import time
import logging
import json
from typing import TypedDict, Union, Optional
from collections.abc import Callable

import requests  # type: ignore  # May lack stubs in some environments
from .config import PipelineConfig, CrateMetadata, EnrichedCrate  # Ensure these are defined and correct


class Section(TypedDict, total=True):
    heading: str
    content: str
    priority: int


class AzureOpenAIEnricher:
    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.session = requests.Session()  # type: ignore[attr-defined]
        self.session.headers.update({
            "Content-Type": "application/json",
            "api-key": config.azure_openai_api_key
        })
        
        # Construct the Azure OpenAI API URL
        self.api_url = f"{config.azure_openai_endpoint}openai/deployments/{config.azure_openai_deployment_name}/chat/completions"
        self.api_url += f"?api-version={config.azure_openai_api_version}"

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

        return output

    def call_azure_openai(
        self, 
        prompt: str, 
        temperature: float = 0.2, 
        max_tokens: int = 256,
        system_message: str = "You are a helpful AI assistant that analyzes Rust crates and provides insights."
    ) -> Optional[str]:
        """Call Azure OpenAI API"""
        try:
            payload = {
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": 1.0,
                "frequency_penalty": 0.0,
                "presence_penalty": 0.0
            }

            response = self.session.post(
                self.api_url,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                logging.error(f"Azure OpenAI API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logging.error(f"Error calling Azure OpenAI: {e}")
            return None

    def validate_and_retry(
        self,
        prompt: str,
        validation_func: Callable[[str], bool],
        temperature: float = 0.2,
        max_tokens: int = 256,
        retries: int = 4,
        system_message: str = "You are a helpful AI assistant that analyzes Rust crates and provides insights."
    ) -> Optional[str]:
        """Run prompt with validation and retry logic"""
        for attempt in range(retries):
            try:
                result = self.call_azure_openai(prompt, temperature, max_tokens, system_message)
                
                if result and validation_func(result):
                    return result
                    
                # If validation failed, try with a different temperature
                if attempt < retries - 1:
                    temperature = min(0.8, temperature + 0.1)
                    time.sleep(1)  # Brief delay between retries
                    
            except Exception as e:
                logging.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    
        return None

    def simplify_prompt(self, prompt: str) -> str:
        """Simplify complex prompts for better Azure OpenAI performance"""
        # Remove excessive whitespace and newlines
        prompt = re.sub(r'\n\s*\n', '\n\n', prompt)
        prompt = re.sub(r' +', ' ', prompt)
        
        # Truncate if too long (Azure OpenAI has limits)
        if len(prompt) > 8000:  # Conservative limit
            prompt = prompt[:8000] + "..."
            
        return prompt.strip()

    def validate_classification(self, result: str) -> bool:
        """Validate classification output"""
        valid_categories = [
            "AI", "Database", "Web Framework", "Networking", 
            "Serialization", "Utilities", "DevTools", "ML", 
            "Cryptography", "Unknown"
        ]
        return any(cat.lower() in result.lower() for cat in valid_categories)

    def validate_factual_pairs(self, result: str) -> bool:
        """Validate factual pairs output"""
        return "✅" in result and "❌" in result and len(result.split("✅")) > 1

    def enrich_crate(self, crate: CrateMetadata) -> EnrichedCrate:
        """Enrich crate with AI-generated insights using Azure OpenAI"""
        enriched = EnrichedCrate(**crate.__dict__)
        
        # Generate readme summary
        if crate.readme:
            readme_content = self.smart_truncate(crate.readme, 2000)
            prompt = f"""Summarize this Rust crate's README in 2-3 sentences:

{readme_content}

Summary:"""
            
            enriched.readme_summary = self.call_azure_openai(
                prompt, temperature=0.3, max_tokens=150
            )

        # Classify use case
        if crate.readme:
            enriched.use_case = self.classify_use_case(crate, enriched.readme_summary or "")

        # Generate factual pairs
        enriched.factual_counterfactual = self.generate_factual_pairs(crate)

        # Score the crate
        enriched.score = self.score_crate(crate)

        return enriched

    def summarize_features(self, crate: CrateMetadata) -> str:
        """Summarize crate features using Azure OpenAI"""
        if not crate.features:
            return "No specific features documented."

        # Handle both dict and list feature formats
        if isinstance(crate.features, dict):
            features_text = "\n".join([
                f"- {feature}: {', '.join(versions)}"
                for feature, versions in crate.features.items()
            ])
        elif isinstance(crate.features, list):
            features_text = "\n".join([
                f"- {feature}" if isinstance(feature, str) else f"- {str(feature)}"
                for feature in crate.features
            ])
        else:
            return "Features format not recognized."

        prompt = f"""Summarize the key features of this Rust crate in 2-3 sentences:

{features_text}

Summary:"""

        result = self.call_azure_openai(prompt, temperature=0.3, max_tokens=150)
        return result or "Features analysis unavailable."

    def classify_use_case(self, crate: CrateMetadata, readme_summary: str) -> str:
        """Classify crate use case using Azure OpenAI"""
        context = f"""
Crate: {crate.name}
Description: {crate.description}
Summary: {readme_summary}
Keywords: {', '.join(crate.keywords)}
Categories: {', '.join(crate.categories)}
"""

        prompt = f"""Classify this Rust crate into one of these categories:
- AI: Machine learning, AI, neural networks
- Database: Database drivers, ORMs, data storage
- Web Framework: Web servers, HTTP, REST APIs
- Networking: Network protocols, communication
- Serialization: Data formats, JSON, binary
- Utilities: General utilities, helpers
- DevTools: Development tools, debugging
- ML: Machine learning, statistics
- Cryptography: Security, encryption, hashing
- Unknown: Doesn't fit other categories

{context}

Category:"""

        result = self.validate_and_retry(
            prompt, 
            self.validate_classification, 
            temperature=0.1, 
            max_tokens=50
        )
        
        return result or "Unknown"

    def generate_factual_pairs(self, crate: CrateMetadata) -> str:
        """Generate factual/counterfactual pairs using Azure OpenAI"""
        context = f"""
Crate: {crate.name}
Description: {crate.description}
Keywords: {', '.join(crate.keywords)}
Categories: {', '.join(crate.categories)}
"""

        prompt = f"""Generate 2-3 factual statements about this Rust crate, followed by their counterfactual opposites.

Format each pair as:
✅ Factual: [true statement about the crate]
❌ Counterfactual: [opposite/incorrect statement]

{context}

Factual/Counterfactual pairs:"""

        result = self.validate_and_retry(
            prompt, 
            self.validate_factual_pairs, 
            temperature=0.4, 
            max_tokens=300
        )
        
        return result or "Factual analysis unavailable."

    def score_crate(self, crate: CrateMetadata) -> float:
        """Score crate quality using Azure OpenAI"""
        context = f"""
Crate: {crate.name}
Description: {crate.description}
Downloads: {crate.downloads}
GitHub Stars: {crate.github_stars}
Keywords: {', '.join(crate.keywords)}
Categories: {', '.join(crate.categories)}
"""

        prompt = f"""Rate this Rust crate on a scale of 1-10 based on:
- Popularity (downloads, stars)
- Documentation quality
- Usefulness and relevance
- Community adoption

{context}

Score (1-10):"""

        result = self.call_azure_openai(prompt, temperature=0.1, max_tokens=10)
        
        if result:
            # Extract numeric score
            score_match = re.search(r'(\d+(?:\.\d+)?)', result)
            if score_match:
                try:
                    score = float(score_match.group(1))
                    return min(10.0, max(1.0, score))  # Clamp between 1-10
                except ValueError:
                    pass
        
        return 5.0  # Default score

    def batch_process_prompts(
        self, 
        prompts: "list[tuple[str, float, int]]", 
        batch_size: int = 4
    ) -> "list[Optional[str]]":
        """Process multiple prompts in batches"""
        results: "list[Optional[str]]" = []
        
        for i in range(0, len(prompts), batch_size):
            batch = prompts[i:i + batch_size]
            batch_results: "list[Optional[str]]" = []
            
            for prompt_tuple in batch:
                prompt, temp, max_tokens = prompt_tuple
                result = self.call_azure_openai(prompt, temp, max_tokens)
                batch_results.append(result)
                time.sleep(0.1)  # Rate limiting
                
            results.extend(batch_results)
            
        return results

    def smart_context_management(
        self, context_history: "list[str]", new_prompt: str
    ) -> str:
        """Manage context for long conversations"""
        # For Azure OpenAI, we can be more generous with context
        # but still need to manage it carefully
        
        total_context = "\n".join(context_history) + "\n" + new_prompt
        max_context_tokens = 6000  # Conservative limit for Azure OpenAI
        
        if self.estimate_tokens(total_context) <= max_context_tokens:
            return total_context
            
        # If too long, keep most recent context
        recent_context = context_history[-2:] if len(context_history) >= 2 else context_history
        return "\n".join(recent_context) + "\n" + new_prompt 