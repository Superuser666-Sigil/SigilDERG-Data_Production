> **All LLM usage in this project is unified and cross-platform.**
>
> - All LLM calls are routed through the `UnifiedLLMProcessor` and `LLMConfig` abstractions.
> - This ensures support for all major providers (cloud and local) on Mac, Linux, and Windows.
> - **All new LLM features must use this pattern.**
> - The project is future-proof: as [LiteLLM](https://github.com/BerriAI/litellm) adds new providers, you can use them immediately by updating your config/CLI—no code changes needed.

---

# Unified LLM Provider Support for Rust Crate Pipeline

This document describes the comprehensive LLM provider support in the Rust Crate Pipeline, allowing you to use any LiteLLM-compatible provider for AI-powered crate analysis.

## 🚀 Supported Providers

The pipeline supports all LiteLLM providers, including:

### Cloud Providers
- **Azure OpenAI** - Microsoft Azure OpenAI Service
- **OpenAI** - OpenAI API (GPT-4, GPT-3.5-turbo, etc.)
- **Anthropic** - Claude API (Claude-3-Sonnet, Claude-3-Haiku, etc.)
- **Google AI** - Gemini API (Gemini Pro, Gemini Pro Vision, etc.)
- **Cohere** - Cohere API
- **Hugging Face** - Hugging Face Inference API

### Local Providers
- **Ollama** - Local LLM server for open-source models
- **LM Studio** - Local LLM server with GUI for model management

## 📦 Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. For local providers, install the respective software:
   - **Ollama**: [Install Ollama](https://ollama.ai/download)
   - **LM Studio**: [Download LM Studio](https://lmstudio.ai/)

## 🔧 Configuration

### Command-Line Interface

The pipeline provides a unified command-line interface for all providers:

```bash
python run_pipeline_with_llm.py --llm-provider <provider> --llm-model <model> --crates <crate_names>
```

### Provider-Specific Configuration

#### Azure OpenAI

Set the following environment variables:
```bash
export AZURE_OPENAI_ENDPOINT="<your_endpoint>"
export AZURE_OPENAI_API_KEY="<your_api_key>"
export AZURE_OPENAI_DEPLOYMENT_NAME="<your_deployment_name>"
```

Then, run the pipeline:
```bash
python run_pipeline_with_llm.py \
  --llm-provider azure \
  --llm-model gpt-4o \
  --crates tokio serde
```

You can still override these with command-line arguments if needed:
```bash
python run_pipeline_with_llm.py \\
  --llm-provider azure \\
  --llm-model gpt-4o \\
  --llm-api-key YOUR_AZURE_API_KEY \\
  --azure-deployment YOUR_AZURE_DEPLOYMENT \\
  --crates tokio serde
```

#### Ollama (Local)
```bash
# Start Ollama server first
ollama serve

# Run pipeline
python run_pipeline_with_llm.py \
  --llm-provider ollama \
  --llm-model llama2 \
  --crates tokio
```

#### LM Studio (Local)
```bash
# Start LM Studio server first (GUI or API)
# Default endpoint: http://localhost:1234/v1

python run_pipeline_with_llm.py \
  --llm-provider lmstudio \
  --llm-model llama2 \
  --crates serde
```

#### OpenAI API
```bash
python run_pipeline_with_llm.py \
  --llm-provider openai \
  --llm-model gpt-4 \
  --llm-api-key YOUR_OPENAI_API_KEY \
  --crates tokio
```

#### Anthropic Claude
```bash
python run_pipeline_with_llm.py \
  --llm-provider anthropic \
  --llm-model claude-3-sonnet \
  --llm-api-key YOUR_ANTHROPIC_API_KEY \
  --crates serde
```

#### Google AI (Gemini)
```bash
python run_pipeline_with_llm.py \
  --llm-provider google \
  --llm-model gemini-pro \
  --llm-api-key YOUR_GOOGLE_API_KEY \
  --crates tokio
```

## 🎛️ Advanced Configuration

### Model Parameters

All providers support these common parameters:

```bash
--llm-temperature 0.2          # Generation temperature (0.0-1.0)
--llm-max-tokens 256          # Maximum tokens per response
--llm-timeout 30              # API call timeout in seconds
--llm-max-retries 3           # Maximum retry attempts
```

### Custom API Endpoints

For providers with custom endpoints:

```bash
--llm-api-base https://your-custom-endpoint.com/v1
```

### Provider-Specific Options

#### Azure OpenAI
```bash
--azure-deployment your-deployment-name
--azure-api-version 2024-02-15-preview
```

#### Ollama
```bash
--ollama-host http://localhost:11434
```

#### LM Studio
```bash
--lmstudio-host http://localhost:1234/v1
```

## 🔍 Usage Examples

### Single Crate Analysis
```bash
python run_pipeline_with_llm.py \
  --llm-provider azure \
  --llm-model gpt-4o \
  --crates tokio
```

### Batch Analysis
```bash
python run_pipeline_with_llm.py \
  --llm-provider ollama \
  --llm-model codellama \
  --crates tokio serde reqwest actix-web
```

### Verbose Logging
```bash
python run_pipeline_with_llm.py \
  --llm-provider openai \
  --llm-model gpt-4 \
  --verbose \
  --crates tokio
```

### Custom Output Directory
```bash
python run_pipeline_with_llm.py \
  --llm-provider anthropic \
  --llm-model claude-3-sonnet \
  --output-dir ./my_analysis_results \
  --crates serde
```

## 🧪 Testing

Run the test suite to verify provider support:

```bash
python test_unified_llm.py
```

This will test:
- Configuration creation for all providers
- Processor initialization
- Crate enrichment functionality
- Command-line interface parsing
- Provider support validation

## 📊 Output Format

The pipeline generates JSON analysis files for each crate:

```json
{
  "input_data": "crate_name",
  "context_sources": ["crates.io", "github.com"],
  "reasoning_steps": ["Analysis steps..."],
  "suggestion": "Analysis summary",
  "verdict": "ALLOW",
  "audit_info": {
    "ai_enrichment": {
      "provider": "azure",
      "model": "gpt-4o",
      "readme_summary": "Summary of crate features",
      "use_case": "Networking",
      "score": 8.5,
      "factual_counterfactual": "Factual and counterfactual statements"
    }
  },
  "irl_score": 0.85,
  "execution_id": "exec-abc123-def456-1234567890",
  "timestamp": "2024-01-01T12:00:00Z",
  "canon_version": "1.3.0"
}
```

## 🔒 Security Considerations

### API Keys
- Store API keys as environment variables when possible
- Never commit API keys to version control
- Use provider-specific key management when available

### Local Providers
- Ollama and LM Studio run locally - no data leaves your machine
- Ensure proper firewall configuration for local servers
- Use HTTPS for production deployments

## 🚨 Troubleshooting

### Common Issues

#### "LiteLLM not available"
```bash
pip install litellm
```

#### "Provider not supported"
Check the provider name spelling and ensure it's supported by LiteLLM.

#### "API key required"
Ensure you've provided the required API key for cloud providers.

#### "Connection failed"
- For local providers: Ensure the server is running
- For cloud providers: Check network connectivity and API key validity

#### "Model not found"
- Verify the model name is correct for your provider
- Check if the model is available in your region/account

### Debug Mode

Enable verbose logging for detailed error information:

```bash
python run_pipeline_with_llm.py --verbose --llm-provider azure --crates tokio
```

## 🔄 Migration from Azure OpenAI

If you're currently using Azure OpenAI and want to switch providers:

1. **To OpenAI API**:
```bash
# Old (Azure)
python run_pipeline_with_llm.py --llm-provider azure --llm-model gpt-4o --crates tokio

# New (OpenAI)
python run_pipeline_with_llm.py --llm-provider openai --llm-model gpt-4 --crates tokio
```

2. **To Local Ollama**:
```bash
# Install and start Ollama
ollama pull llama2
ollama serve

# Run pipeline
python run_pipeline_with_llm.py --llm-provider ollama --llm-model llama2 --crates tokio
```

## 📚 Additional Resources

- [LiteLLM Documentation](https://docs.litellm.ai/)
- [Ollama Documentation](https://ollama.ai/docs)
- [LM Studio Documentation](https://lmstudio.ai/docs)
- [Azure OpenAI Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [OpenAI API Documentation](https://platform.openai.com/docs)

## 🤝 Contributing

To add support for new providers:

1. Ensure the provider is supported by LiteLLM
2. Add provider-specific configuration options
3. Update the test suite
4. Document the new provider in this README

## 📄 License

This project is licensed under the same terms as the main Rust Crate Pipeline project. 