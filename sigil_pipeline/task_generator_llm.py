"""
task_generator_llm
==================

Asynchronous helper functions for generating instruction/response pairs
using a large language model (LLM). The default provider is a local
llama-cpp-python model when available, with optional fallbacks to
OpenAI, Gemini, or Claude.

Provider selection:
- SIGIL_LLM_PROVIDER=auto (default): try llama_cpp -> openai -> gemini -> claude
- SIGIL_LLM_PROVIDER=llama_cpp|openai|gemini|claude: force a provider

Local llama-cpp configuration:
- LLAMA_CPP_MODEL_PATH or SIGIL_LLM_MODEL_PATH: required model path
- LLAMA_CPP_N_CTX: context length
- LLAMA_CPP_N_GPU_LAYERS: GPU layers
- LLAMA_CPP_CHAT_FORMAT: chat format name
- LLAMA_CPP_N_THREADS: CPU threads
- LLAMA_CPP_N_BATCH: prompt batch size
- LLAMA_CPP_MAX_TOKENS or SIGIL_LLM_MAX_TOKENS: cap generation length

Cloud configuration:
- OPENAI_API_KEY / OPENAI_MODEL
- GEMINI_API_KEY or GOOGLE_API_KEY / GEMINI_MODEL
- ANTHROPIC_API_KEY / ANTHROPIC_MODEL
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from . import ast_patterns, output_validator, prompt_templates

logger = logging.getLogger(__name__)

# Fill-in-the-Middle (FIM) tokens - standard format compatible with most code models
FIM_PREFIX_TOKEN = "<fim_prefix>"
FIM_SUFFIX_TOKEN = "<fim_suffix>"
FIM_MIDDLE_TOKEN = "<fim_middle>"

# Explicit output constraints for smaller models to reduce hallucinations
_CODE_OUTPUT_RULES = """
RULES:
1. Output ONLY the requested code item
2. Do NOT include imports, use statements, or mod declarations
3. Do NOT include tests or examples
4. Do NOT use todo!(), unimplemented!(), or placeholder comments
5. The code MUST be valid Rust that compiles
"""


# =============================================================================
# Dynamic Few-Shot Example Bank
# =============================================================================
# Examples are organized by code pattern type for context-aware prompt generation
# Each example demonstrates idiomatic Rust for that specific pattern

_FEWSHOT_EXAMPLES = {
    # -------------------------------------------------------------------------
    # Error Handling Examples (Result, ?, Option)
    # -------------------------------------------------------------------------
    "error_handling": {
        "codegen": {
            "input": """fn parse_config(path: &str) -> Result<Config, ConfigError> {
    todo!()
}""",
            "output": """fn parse_config(path: &str) -> Result<Config, ConfigError> {
    let contents = std::fs::read_to_string(path)
        .map_err(|e| ConfigError::IoError(e.to_string()))?;
    let config: Config = toml::from_str(&contents)
        .map_err(|e| ConfigError::ParseError(e.to_string()))?;
    Ok(config)
}""",
        },
        "refactor": {
            "input": """fn read_value(path: &str) -> Result<i32, Box<dyn Error>> {
    let file = File::open(path);
    if file.is_err() {
        return Err(Box::new(file.unwrap_err()));
    }
    let mut contents = String::new();
    let result = file.unwrap().read_to_string(&mut contents);
    if result.is_err() {
        return Err(Box::new(result.unwrap_err()));
    }
    match contents.trim().parse::<i32>() {
        Ok(n) => Ok(n),
        Err(e) => Err(Box::new(e)),
    }
}""",
            "output": """fn read_value(path: &str) -> Result<i32, Box<dyn Error>> {
    let contents = std::fs::read_to_string(path)?;
    let value = contents.trim().parse()?;
    Ok(value)
}""",
        },
        "bugfix": {
            "input": """fn get_first(items: &[i32]) -> Result<i32, &'static str> {
    items[0]
}""",
            "output": """fn get_first(items: &[i32]) -> Result<i32, &'static str> {
    items.first().copied().ok_or("slice is empty")
}""",
        },
    },
    # -------------------------------------------------------------------------
    # Iterator/Functional Examples
    # -------------------------------------------------------------------------
    "iterators": {
        "codegen": {
            "input": """fn sum_even_squares(nums: &[i32]) -> i32 {
    todo!()
}""",
            "output": """fn sum_even_squares(nums: &[i32]) -> i32 {
    nums.iter()
        .filter(|&n| n % 2 == 0)
        .map(|n| n * n)
        .sum()
}""",
        },
        "refactor": {
            "input": """fn double_positives(nums: &Vec<i32>) -> Vec<i32> {
    let mut result = Vec::new();
    for i in 0..nums.len() {
        if nums[i] > 0 {
            result.push(nums[i] * 2);
        }
    }
    return result;
}""",
            "output": """fn double_positives(nums: &Vec<i32>) -> Vec<i32> {
    nums.iter()
        .filter(|&&n| n > 0)
        .map(|&n| n * 2)
        .collect()
}""",
        },
        "bugfix": {
            "input": """fn find_max(items: &[i32]) -> i32 {
    items.iter().max()
}""",
            "output": """fn find_max(items: &[i32]) -> i32 {
    items.iter().copied().max().unwrap_or(i32::MIN)
}""",
        },
    },
    # -------------------------------------------------------------------------
    # Async Examples
    # -------------------------------------------------------------------------
    "async": {
        "codegen": {
            "input": """async fn fetch_data(url: &str) -> Result<String, reqwest::Error> {
    todo!()
}""",
            "output": """async fn fetch_data(url: &str) -> Result<String, reqwest::Error> {
    let response = reqwest::get(url).await?;
    let body = response.text().await?;
    Ok(body)
}""",
        },
        "refactor": {
            "input": """async fn process_items(items: Vec<Item>) -> Vec<Result<Output, Error>> {
    let mut results = Vec::new();
    for item in items {
        let result = process_item(item).await;
        results.push(result);
    }
    results
}""",
            "output": """async fn process_items(items: Vec<Item>) -> Vec<Result<Output, Error>> {
    futures::future::join_all(items.into_iter().map(process_item)).await
}""",
        },
        "bugfix": {
            "input": """async fn fetch_all(urls: &[&str]) -> Vec<String> {
    let mut results = vec![];
    for url in urls {
        results.push(fetch(url).await.unwrap());
    }
    results
}""",
            "output": """async fn fetch_all(urls: &[&str]) -> Vec<String> {
    let mut results = vec![];
    for url in urls {
        if let Ok(data) = fetch(url).await {
            results.push(data);
        }
    }
    results
}""",
        },
    },
    # -------------------------------------------------------------------------
    # Collections Examples (HashMap, Vec, etc.)
    # -------------------------------------------------------------------------
    "collections": {
        "codegen": {
            "input": """fn count_words(text: &str) -> HashMap<String, usize> {
    todo!()
}""",
            "output": """fn count_words(text: &str) -> HashMap<String, usize> {
    let mut counts = HashMap::new();
    for word in text.split_whitespace() {
        *counts.entry(word.to_lowercase()).or_insert(0) += 1;
    }
    counts
}""",
        },
        "refactor": {
            "input": """fn get_or_create(map: &mut HashMap<String, Vec<i32>>, key: &str) -> &mut Vec<i32> {
    if !map.contains_key(key) {
        map.insert(key.to_string(), Vec::new());
    }
    map.get_mut(key).unwrap()
}""",
            "output": """fn get_or_create(map: &mut HashMap<String, Vec<i32>>, key: &str) -> &mut Vec<i32> {
    map.entry(key.to_string()).or_default()
}""",
        },
        "bugfix": {
            "input": """fn merge_maps(a: HashMap<String, i32>, b: HashMap<String, i32>) -> HashMap<String, i32> {
    let mut result = a;
    for (k, v) in b {
        result[&k] = v;
    }
    result
}""",
            "output": """fn merge_maps(a: HashMap<String, i32>, b: HashMap<String, i32>) -> HashMap<String, i32> {
    let mut result = a;
    for (k, v) in b {
        result.insert(k, v);
    }
    result
}""",
        },
    },
    # -------------------------------------------------------------------------
    # Concurrency Examples (Arc, Mutex, threads)
    # -------------------------------------------------------------------------
    "concurrency": {
        "codegen": {
            "input": """fn increment_counter(counter: Arc<Mutex<i32>>) {
    todo!()
}""",
            "output": """fn increment_counter(counter: Arc<Mutex<i32>>) {
    let mut guard = counter.lock().unwrap();
    *guard += 1;
}""",
        },
        "refactor": {
            "input": """fn update_shared(data: Arc<Mutex<Vec<i32>>>, value: i32) {
    let lock = data.lock();
    match lock {
        Ok(mut guard) => {
            guard.push(value);
        }
        Err(_) => {}
    }
}""",
            "output": """fn update_shared(data: Arc<Mutex<Vec<i32>>>, value: i32) {
    if let Ok(mut guard) = data.lock() {
        guard.push(value);
    }
}""",
        },
        "bugfix": {
            "input": """fn spawn_workers(data: Arc<Vec<i32>>) -> Vec<JoinHandle<i32>> {
    let mut handles = vec![];
    for i in 0..4 {
        let data = data.clone();
        handles.push(std::thread::spawn(move || data[i]));
    }
    handles
}""",
            "output": """fn spawn_workers(data: Arc<Vec<i32>>) -> Vec<JoinHandle<i32>> {
    let mut handles = vec![];
    for i in 0..4 {
        let data = data.clone();
        handles.push(std::thread::spawn(move || {
            data.get(i).copied().unwrap_or(0)
        }));
    }
    handles
}""",
        },
    },
    # -------------------------------------------------------------------------
    # I/O Examples (File, fs, Read, Write)
    # -------------------------------------------------------------------------
    "io": {
        "codegen": {
            "input": """fn write_lines(path: &Path, lines: &[&str]) -> io::Result<()> {
    todo!()
}""",
            "output": """fn write_lines(path: &Path, lines: &[&str]) -> io::Result<()> {
    let mut file = File::create(path)?;
    for line in lines {
        writeln!(file, "{}", line)?;
    }
    Ok(())
}""",
        },
        "refactor": {
            "input": """fn read_lines(path: &str) -> Vec<String> {
    let file = File::open(path).unwrap();
    let reader = BufReader::new(file);
    let mut lines = Vec::new();
    for line in reader.lines() {
        lines.push(line.unwrap());
    }
    lines
}""",
            "output": """fn read_lines(path: &str) -> Vec<String> {
    let file = File::open(path).expect("failed to open file");
    BufReader::new(file)
        .lines()
        .filter_map(Result::ok)
        .collect()
}""",
        },
        "bugfix": {
            "input": """fn copy_file(src: &Path, dst: &Path) -> io::Result<()> {
    let contents = std::fs::read(src);
    std::fs::write(dst, contents)
}""",
            "output": """fn copy_file(src: &Path, dst: &Path) -> io::Result<()> {
    let contents = std::fs::read(src)?;
    std::fs::write(dst, contents)
}""",
        },
    },
    # -------------------------------------------------------------------------
    # Closures Examples
    # -------------------------------------------------------------------------
    "closures": {
        "codegen": {
            "input": """fn apply_twice<F>(f: F, x: i32) -> i32
where
    F: Fn(i32) -> i32,
{
    todo!()
}""",
            "output": """fn apply_twice<F>(f: F, x: i32) -> i32
where
    F: Fn(i32) -> i32,
{
    f(f(x))
}""",
        },
        "refactor": {
            "input": """fn make_adder(n: i32) -> Box<dyn Fn(i32) -> i32> {
    let closure = move |x: i32| -> i32 { return x + n; };
    return Box::new(closure);
}""",
            "output": """fn make_adder(n: i32) -> impl Fn(i32) -> i32 {
    move |x| x + n
}""",
        },
        "bugfix": {
            "input": """fn filter_by<F>(items: Vec<i32>, pred: F) -> Vec<i32>
where
    F: Fn(i32) -> bool,
{
    items.into_iter().filter(pred).collect()
}""",
            "output": """fn filter_by<F>(items: Vec<i32>, pred: F) -> Vec<i32>
where
    F: Fn(&i32) -> bool,
{
    items.into_iter().filter(|x| pred(x)).collect()
}""",
        },
    },
    # -------------------------------------------------------------------------
    # Default/Simple Examples (fallback)
    # -------------------------------------------------------------------------
    "default": {
        "codegen": {
            "input": """fn add(a: i32, b: i32) -> i32 {
    todo!()
}""",
            "output": """fn add(a: i32, b: i32) -> i32 {
    a + b
}""",
        },
        "refactor": {
            "input": """fn is_positive(n: i32) -> bool {
    if n > 0 {
        return true;
    } else {
        return false;
    }
}""",
            "output": """fn is_positive(n: i32) -> bool {
    n > 0
}""",
        },
        "bugfix": {
            "input": """fn divide(a: i32, b: i32) -> i32 {
    a / b
}""",
            "output": """fn divide(a: i32, b: i32) -> i32 {
    if b == 0 { 0 } else { a / b }
}""",
        },
    },
}


def _select_fewshot_examples(code: str, task_type: str, max_examples: int = 2) -> str:
    """Select relevant few-shot examples based on detected code patterns.

    Analyzes the input code to detect patterns (async, iterators, error handling,
    etc.) and returns appropriate examples that demonstrate idiomatic Rust for
    those specific patterns.

    Args:
        code: The Rust code being processed
        task_type: One of 'codegen', 'refactor', 'bugfix'
        max_examples: Maximum number of examples to include

    Returns:
        Formatted string with relevant few-shot examples
    """
    patterns = ast_patterns.detect_code_patterns_ast(code)

    # Map detected patterns to example categories (in priority order)
    pattern_to_category = [
        ("has_async", "async"),
        ("has_concurrency", "concurrency"),
        ("has_error_handling", "error_handling"),
        ("has_iterators", "iterators"),
        ("has_io", "io"),
        ("has_collections", "collections"),
        ("has_closures", "closures"),
    ]

    selected_categories: list[str] = []
    for pattern_key, category in pattern_to_category:
        if patterns.get(pattern_key) and len(selected_categories) < max_examples:
            if category in _FEWSHOT_EXAMPLES:
                selected_categories.append(category)

    # Always include at least one example (default if nothing matched)
    if not selected_categories:
        selected_categories = ["default"]

    # Build the examples string
    examples_parts = []
    for i, category in enumerate(selected_categories[:max_examples], 1):
        example = _FEWSHOT_EXAMPLES.get(category, {}).get(task_type)
        if example:
            examples_parts.append(
                f"Example {i} ({category.replace('_', ' ')}):\n"
                f"Input:\n{example['input']}\n\n"
                f"Output:\n{example['output']}"
            )

    return "\n\n".join(examples_parts) if examples_parts else ""


# =============================================================================
# Multi-GPU and Single-GPU LLM Instance Management
# =============================================================================

_LLAMA = None
_LLAMA_LOCK = threading.Lock()
_DEFAULT_LLAMA_CPP_MODEL_PATH = (
    "/home/dave/models/deepskeek-coder-v2-lite/"
    "deepseek-coder-v2-lite-instruct-q4_k_m.gguf"
)

# Multi-GPU configuration
_MULTI_GPU_ENABLED: bool = False
_GPU_MODELS: list[Any] = []
_GPU_LOCKS: list[threading.Lock] = []
_GPU_ROUND_ROBIN_INDEX: int = 0
_GPU_ROUND_ROBIN_LOCK = threading.Lock()
_MULTI_GPU_INITIALIZED: bool = False


def detect_cuda_devices() -> int:
    """Detect number of available CUDA GPUs."""
    try:
        import subprocess

        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            gpus = [
                line.strip()
                for line in result.stdout.strip().split("\n")
                if line.strip()
            ]
            return len(gpus)
    except Exception:
        pass

    # Fallback: try torch
    try:
        import torch

        if torch.cuda.is_available():
            return torch.cuda.device_count()
    except ImportError:
        pass

    return 0


def prompt_multi_gpu_setup() -> tuple[bool, int]:
    """Prompt user at runtime for multi-GPU configuration.

    Returns:
        Tuple of (enabled, gpu_count)
    """
    gpu_count = detect_cuda_devices()
    if gpu_count <= 1:
        if gpu_count == 1:
            logger.info("Single GPU detected, using single-GPU inference")
        else:
            logger.info("No GPUs detected, using CPU inference")
        return False, gpu_count

    print("\n" + "=" * 60)
    print("  Multi-GPU Inference Setup")
    print("=" * 60)
    print(f"  Detected {gpu_count} CUDA GPUs")
    print("  Multi-GPU mode enables parallel LLM inference across GPUs")
    print("  for significantly faster dataset generation.")
    print("=" * 60)

    try:
        response = input("Enable multi-GPU inference? [Y/n]: ").strip().lower()
        enabled = response in ("", "y", "yes")

        if enabled:
            default_count = gpu_count
            count_input = input(f"Number of GPUs to use [{default_count}]: ").strip()
            if count_input:
                try:
                    use_count = int(count_input)
                    use_count = min(max(1, use_count), gpu_count)
                except ValueError:
                    use_count = default_count
            else:
                use_count = default_count
            print(f"\n✓ Multi-GPU enabled with {use_count} GPUs\n")
            return True, use_count
        else:
            print("\n✓ Using single-GPU/CPU inference\n")
            return False, 1
    except (EOFError, KeyboardInterrupt):
        print("\n✓ Using single-GPU/CPU inference (non-interactive)\n")
        return False, 1


def initialize_multi_gpu(
    model_path: str | None = None,
    gpu_count: int | None = None,
    force_enabled: bool | None = None,
) -> bool:
    """Initialize multi-GPU inference if enabled.

    Args:
        model_path: Path to GGUF model file. If None, uses environment variable.
        gpu_count: Number of GPUs to use. If None, auto-detects.
        force_enabled: If True/False, skip runtime prompt. If None, prompt user.

    Returns:
        True if multi-GPU is enabled and initialized.
    """
    global _MULTI_GPU_ENABLED, _GPU_MODELS, _GPU_LOCKS, _MULTI_GPU_INITIALIZED

    if _MULTI_GPU_INITIALIZED:
        return _MULTI_GPU_ENABLED

    # Determine if multi-GPU should be enabled
    if force_enabled is None:
        enabled, detected_count = prompt_multi_gpu_setup()
        if gpu_count is None:
            gpu_count = detected_count
    else:
        enabled = force_enabled
        if gpu_count is None:
            gpu_count = detect_cuda_devices()

    if not enabled or gpu_count <= 1:
        _MULTI_GPU_ENABLED = False
        _MULTI_GPU_INITIALIZED = True
        return False

    # Resolve model path
    if model_path is None:
        model_path = os.getenv("LLAMA_CPP_MODEL_PATH") or os.getenv(
            "SIGIL_LLM_MODEL_PATH"
        )
    if not model_path:
        if Path(_DEFAULT_LLAMA_CPP_MODEL_PATH).is_file():
            model_path = _DEFAULT_LLAMA_CPP_MODEL_PATH
        else:
            logger.warning("No model path found for multi-GPU initialization")
            _MULTI_GPU_ENABLED = False
            _MULTI_GPU_INITIALIZED = True
            return False

    try:
        from llama_cpp import Llama
    except ImportError:
        logger.warning("llama-cpp-python not installed, multi-GPU disabled")
        _MULTI_GPU_ENABLED = False
        _MULTI_GPU_INITIALIZED = True
        return False

    # Build common kwargs
    base_kwargs: dict[str, Any] = {}
    n_ctx = _read_int_env("LLAMA_CPP_N_CTX")
    if n_ctx is not None:
        base_kwargs["n_ctx"] = n_ctx
    n_threads = _read_int_env("LLAMA_CPP_N_THREADS")
    if n_threads is not None:
        base_kwargs["n_threads"] = n_threads
    n_batch = _read_int_env("LLAMA_CPP_N_BATCH")
    if n_batch is not None:
        base_kwargs["n_batch"] = n_batch
    chat_format = os.getenv("LLAMA_CPP_CHAT_FORMAT")
    if chat_format:
        base_kwargs["chat_format"] = chat_format

    # Initialize model per GPU
    logger.info(f"Initializing {gpu_count} GPU model instances...")
    _GPU_MODELS = []
    _GPU_LOCKS = []

    for gpu_id in range(gpu_count):
        try:
            # Set CUDA_VISIBLE_DEVICES for this instance
            gpu_kwargs = base_kwargs.copy()
            gpu_kwargs["n_gpu_layers"] = -1  # Offload all layers to GPU
            gpu_kwargs["main_gpu"] = gpu_id

            logger.info(f"Loading model on GPU {gpu_id}...")
            model = Llama(model_path=model_path, **gpu_kwargs)
            _GPU_MODELS.append(model)
            _GPU_LOCKS.append(threading.Lock())
            logger.info(f"✓ GPU {gpu_id} initialized")
        except Exception as e:
            logger.error(f"Failed to initialize GPU {gpu_id}: {e}")
            # Clean up already initialized models
            _GPU_MODELS = []
            _GPU_LOCKS = []
            _MULTI_GPU_ENABLED = False
            _MULTI_GPU_INITIALIZED = True
            return False

    _MULTI_GPU_ENABLED = True
    _MULTI_GPU_INITIALIZED = True
    logger.info(f"Multi-GPU inference enabled with {len(_GPU_MODELS)} GPUs")
    return True


def _get_next_gpu() -> tuple[Any, threading.Lock, int]:
    """Get next available GPU model using round-robin scheduling."""
    global _GPU_ROUND_ROBIN_INDEX

    with _GPU_ROUND_ROBIN_LOCK:
        gpu_id = _GPU_ROUND_ROBIN_INDEX
        _GPU_ROUND_ROBIN_INDEX = (_GPU_ROUND_ROBIN_INDEX + 1) % len(_GPU_MODELS)

    return _GPU_MODELS[gpu_id], _GPU_LOCKS[gpu_id], gpu_id


def _read_int_env(name: str) -> Optional[int]:
    value = os.getenv(name)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        logger.warning(f"Invalid integer for {name}: {value!r}")
        return None


def _normalize_provider(name: str) -> str:
    return name.strip().lower().replace("-", "_")


def _provider_chain() -> list[str]:
    provider = os.getenv("SIGIL_LLM_PROVIDER", "auto")
    provider = _normalize_provider(provider)
    if provider in ("", "auto", "default"):
        return ["llama_cpp", "openai", "gemini", "claude"]
    return [provider]


def _get_llama():
    """Get single-GPU/CPU llama instance (fallback when multi-GPU disabled)."""
    global _LLAMA
    if _LLAMA is not None:
        return _LLAMA

    model_path = os.getenv("LLAMA_CPP_MODEL_PATH") or os.getenv("SIGIL_LLM_MODEL_PATH")
    if not model_path:
        if Path(_DEFAULT_LLAMA_CPP_MODEL_PATH).is_file():
            model_path = _DEFAULT_LLAMA_CPP_MODEL_PATH
        else:
            return None

    try:
        from llama_cpp import Llama
    except ImportError:
        return None

    kwargs: dict[str, Any] = {}
    n_ctx = _read_int_env("LLAMA_CPP_N_CTX")
    if n_ctx is not None:
        kwargs["n_ctx"] = n_ctx
    n_gpu_layers = _read_int_env("LLAMA_CPP_N_GPU_LAYERS")
    if n_gpu_layers is not None:
        kwargs["n_gpu_layers"] = n_gpu_layers
    n_threads = _read_int_env("LLAMA_CPP_N_THREADS")
    if n_threads is not None:
        kwargs["n_threads"] = n_threads
    n_batch = _read_int_env("LLAMA_CPP_N_BATCH")
    if n_batch is not None:
        kwargs["n_batch"] = n_batch
    chat_format = os.getenv("LLAMA_CPP_CHAT_FORMAT")
    if chat_format:
        kwargs["chat_format"] = chat_format

    _LLAMA = Llama(model_path=model_path, **kwargs)
    return _LLAMA


async def _call_llama_cpp(
    system_prompt: str, user_prompt: str, *, temperature: float
) -> Optional[str]:
    """Call llama.cpp model, using multi-GPU if enabled."""
    # Check if multi-GPU is enabled and initialized
    if _MULTI_GPU_ENABLED and _GPU_MODELS:
        return await _call_llama_cpp_multi_gpu(
            system_prompt, user_prompt, temperature=temperature
        )

    # Fallback to single-GPU/CPU
    llama = _get_llama()
    if llama is None:
        return None

    def _run() -> Optional[str]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        call_kwargs: dict[str, Any] = {"temperature": temperature}
        max_tokens = _read_int_env("LLAMA_CPP_MAX_TOKENS") or _read_int_env(
            "SIGIL_LLM_MAX_TOKENS"
        )
        if max_tokens is not None:
            call_kwargs["max_tokens"] = max_tokens
        try:
            with _LLAMA_LOCK:
                response = llama.create_chat_completion(
                    messages=messages, **call_kwargs
                )
        except Exception:
            return None
        if not response or "choices" not in response:
            return None
        choice = response["choices"][0]
        message = choice.get("message") or {}
        content = message.get("content") if isinstance(message, dict) else None
        if not content and "text" in choice:
            content = choice.get("text")
        return content.strip() if content else None

    return await asyncio.to_thread(_run)


async def _call_llama_cpp_multi_gpu(
    system_prompt: str, user_prompt: str, *, temperature: float
) -> Optional[str]:
    """Call llama.cpp using multi-GPU round-robin dispatch."""
    if not _GPU_MODELS:
        return None

    model, lock, gpu_id = _get_next_gpu()

    def _run() -> Optional[str]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        call_kwargs: dict[str, Any] = {"temperature": temperature}
        max_tokens = _read_int_env("LLAMA_CPP_MAX_TOKENS") or _read_int_env(
            "SIGIL_LLM_MAX_TOKENS"
        )
        if max_tokens is not None:
            call_kwargs["max_tokens"] = max_tokens
        try:
            with lock:
                response = model.create_chat_completion(
                    messages=messages, **call_kwargs
                )
        except Exception as e:
            logger.warning(f"Multi-GPU llama_cpp error on GPU {gpu_id}: {e}")
            return None
        choices = response.get("choices", [])
        if not choices:
            return None
        msg = choices[0].get("message", {})
        text = msg.get("content", "")
        return text.strip() if text else None

    return await asyncio.to_thread(_run)


async def _call_openai(
    system_prompt: str, user_prompt: str, *, temperature: float
) -> Optional[str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        import openai
    except ImportError:
        return None

    openai.api_key = api_key
    model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    try:
        response = await openai.ChatCompletion.acreate(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
    except Exception:
        return None

    if not response or not response.choices:
        return None
    content = response.choices[0].message.get("content")
    return content.strip() if content else None


async def _call_gemini(
    system_prompt: str, user_prompt: str, *, temperature: float
) -> Optional[str]:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        import google.generativeai as genai
    except ImportError:
        return None

    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    prompt = f"{system_prompt}\n\n{user_prompt}".strip()

    def _run() -> Optional[str]:
        try:
            response = model.generate_content(
                prompt, generation_config={"temperature": temperature}
            )
        except Exception:
            return None
        text = getattr(response, "text", None)
        return text.strip() if text else None

    return await asyncio.to_thread(_run)


async def _call_claude(
    system_prompt: str, user_prompt: str, *, temperature: float
) -> Optional[str]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
    except ImportError:
        return None

    model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
    max_tokens = int(os.getenv("ANTHROPIC_MAX_TOKENS", "2048"))
    client = anthropic.Anthropic(api_key=api_key)

    def _run() -> Optional[str]:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception:
            return None
        content_blocks = getattr(response, "content", None) or []
        parts = []
        for block in content_blocks:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        text = "".join(parts)
        return text.strip() if text else None

    return await asyncio.to_thread(_run)


def _is_placeholder_response(text: str) -> bool:
    """Check if LLM response is just a placeholder rather than real code."""
    if not text:
        return True
    text_lower = text.lower().strip()
    # Check for common placeholder patterns
    placeholder_indicators = [
        "todo!()",
        "unimplemented!()",
        "// implementation",
        "// todo",
        "// implement here",
        "// add implementation",
        "// your code here",
        "/* implement */",
        "implementation goes here",
        "fill in the implementation",
    ]
    for indicator in placeholder_indicators:
        if indicator in text_lower:
            return True
    # Check if it's just a stub function with empty body
    if text.strip().endswith("{}") or text.strip().endswith("{ }"):
        return True
    # Check if body is just a comment
    import re

    if re.search(r"\{\s*//[^\n]*\s*\}$", text):
        return True
    return False


async def _call_llm_single(
    system_prompt: str, user_prompt: str, *, temperature: float
) -> Optional[str]:
    """Single LLM call attempt with provider fallback."""
    for provider in _provider_chain():
        if provider == "llama_cpp":
            result = await _call_llama_cpp(
                system_prompt, user_prompt, temperature=temperature
            )
        elif provider == "openai":
            result = await _call_openai(
                system_prompt, user_prompt, temperature=temperature
            )
        elif provider == "gemini":
            result = await _call_gemini(
                system_prompt, user_prompt, temperature=temperature
            )
        elif provider == "claude":
            result = await _call_claude(
                system_prompt, user_prompt, temperature=temperature
            )
        else:
            logger.warning(f"Unknown LLM provider: {provider}")
            result = None

        if result:
            return result
    return None


async def _call_llm(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.1,
    max_retries: int = 2,
) -> Optional[str]:
    """Invoke the underlying LLM with retry logic for placeholder responses.

    Uses a lower default temperature (0.1) for more consistent outputs
    from smaller local models like deepseek-coder-v2-lite.

    If the model returns a placeholder response (todo!(), empty body, etc.),
    it will retry with a more explicit prompt up to max_retries times.
    """
    # Reinforcement suffix added on retries
    retry_suffixes = [
        "",  # First attempt - no suffix
        (
            "\n\nIMPORTANT: You MUST provide a complete, working implementation. "
            "Do NOT use todo!(), unimplemented!(), or placeholder comments. "
            "Write the actual code."
        ),
        (
            "\n\nCRITICAL: Provide ONLY the complete Rust code. No placeholders, "
            "no todo!(), no comments saying 'implement here'. Write real, "
            "compilable Rust code that accomplishes the task."
        ),
    ]

    for attempt in range(max_retries + 1):
        suffix = retry_suffixes[min(attempt, len(retry_suffixes) - 1)]
        augmented_prompt = user_prompt + suffix

        result = await _call_llm_single(
            system_prompt, augmented_prompt, temperature=temperature
        )

        if result and not _is_placeholder_response(result):
            return result

        if attempt < max_retries:
            logger.debug(
                f"LLM returned placeholder response, retrying ({attempt + 1}/{max_retries})"
            )

    # Return whatever we got on the last attempt
    return result


def _select_instruction(options: list[str]) -> str:
    return prompt_templates.select_random(
        options, enable_randomization=prompt_templates.is_prompt_randomization_enabled()
    )


def _extract_function_name(code: str) -> str | None:
    signature = ast_patterns.extract_function_signature(code)
    return signature.name if signature else None


def _style_hints(code: str, *, max_hints: int = 2) -> str:
    patterns = ast_patterns.detect_code_patterns_ast(code or "")
    hints: list[str] = []
    if patterns.get("has_async"):
        hints.append("Use async/await patterns where appropriate.")
    if patterns.get("has_error_handling"):
        hints.append("Handle errors with Result types where appropriate.")
    if patterns.get("has_serde"):
        hints.append("Use Serde for serialization/deserialization where it fits.")
    if patterns.get("has_io"):
        hints.append("Handle I/O failures carefully.")
    if patterns.get("has_iterators"):
        hints.append("Prefer iterator-based processing when it fits.")

    if not hints:
        return ""

    if prompt_templates.is_prompt_randomization_enabled():
        rng = prompt_templates.get_prompt_rng()
        rng.shuffle(hints)
        return " ".join(hints[:max_hints])
    return hints[0]


def _find_function_body_range(code: str) -> tuple[int, int] | None:
    """Find the line range of the function body (inside braces).

    Returns (start_line, end_line) as 0-based line indices, or None if not found.
    """
    if not code:
        return None
    try:
        import tree_sitter_rust as ts_rust
        from tree_sitter import Language, Parser

        rust_language = Language(ts_rust.language())
        try:
            parser = Parser(rust_language)
        except TypeError:
            parser = Parser()
            parser.set_language(rust_language)
        tree = parser.parse(code.encode("utf-8"))
        root = tree.root_node

        for child in root.children:
            if child.type != "function_item":
                continue
            body = child.child_by_field_name("body")
            if body is None:
                continue
            # Get line numbers (0-based)
            start_line = body.start_point[0]
            end_line = body.end_point[0]
            # Skip the opening and closing braces themselves
            if end_line > start_line + 1:
                return (start_line + 1, end_line)
            return None
        return None
    except Exception:
        # Fallback: use brace matching
        lines = code.splitlines()
        open_brace_line = None
        close_brace_line = None
        for i, line in enumerate(lines):
            if "{" in line and open_brace_line is None:
                open_brace_line = i
            if "}" in line:
                close_brace_line = i
        if (
            open_brace_line is not None
            and close_brace_line is not None
            and close_brace_line > open_brace_line + 1
        ):
            return (open_brace_line + 1, close_brace_line)
        return None


def _explanation_subject(code: str) -> str:
    chunk_type = output_validator.classify_chunk_type(code) or "code"
    name = _extract_function_name(code)
    if chunk_type == "function":
        return f"Rust function `{name}`" if name else "Rust function"
    if chunk_type == "struct":
        struct_name = ast_patterns.extract_struct_name(code)
        return f"Rust struct `{struct_name}`" if struct_name else "Rust struct"
    if chunk_type == "enum":
        return "Rust enum"
    if chunk_type == "trait":
        return "Rust trait"
    if chunk_type == "type":
        return "Rust type alias"
    if chunk_type == "impl_block":
        return "Rust impl block"
    if chunk_type == "module":
        return "Rust module"
    return "Rust code"


async def generate_refactoring_task(
    code: str, context: str = ""
) -> Optional[Dict[str, Any]]:
    """Generate a transformation task for the given Rust ``code``."""
    # Detect patterns and select relevant examples
    patterns = ast_patterns.detect_code_patterns_ast(code)
    fewshot = _select_fewshot_examples(code, "refactor")

    # Build pattern-aware refactoring hints
    refactor_hints = []
    if patterns.get("has_iterators") or "for" in code:
        refactor_hints.append("Consider using iterator chains")
    if patterns.get("has_error_handling"):
        refactor_hints.append("Simplify error handling with ? operator")
    if patterns.get("has_collections"):
        refactor_hints.append("Use entry API for HashMap operations")
    if "unwrap()" in code:
        refactor_hints.append("Replace unwrap() with proper error handling")
    if "return " in code and "return Ok(" not in code:
        refactor_hints.append("Consider implicit returns")

    base = _select_instruction(
        [
            "Refactor this function to be more idiomatic Rust.",
            "Improve this function's style while preserving behavior.",
            "Make this function cleaner and more Rust-idiomatic.",
        ]
    )

    hint_str = " ".join(refactor_hints) if refactor_hints else ""
    instruction = f"{base} Keep the same signature. {hint_str}".strip()

    system_prompt = (
        "You are an expert Rust programmer who refactors code for idiomatic style. "
        "You improve readability, use iterators where appropriate, and follow Rust "
        "conventions. You keep the exact same function signature and behavior. "
        "Output only the refactored function." + _CODE_OUTPUT_RULES
    )

    user_prompt = f"{instruction}\n\n{fewshot}\n\nNow refactor this:\n\n{code}"
    if context:
        user_prompt += f"\n\n// Available context:\n{context}"

    completion = await _call_llm(system_prompt, user_prompt)
    if not completion:
        return None

    return {
        "prompt": instruction + "\n\n" + code,
        "gen": completion,
        "_task_type": "transformations",
    }


async def generate_bug_fixing_task(
    code: str, context: str = ""
) -> Optional[Dict[str, Any]]:
    """Generate an error-fixing task for the given Rust ``code``."""
    # Detect patterns and select relevant examples
    patterns = ast_patterns.detect_code_patterns_ast(code)
    fewshot = _select_fewshot_examples(code, "bugfix")

    # Identify likely error categories based on code patterns
    error_hints = []
    if patterns.get("has_error_handling"):
        error_hints.append("Check for missing ? operators or incorrect Result handling")
    if patterns.get("has_iterators"):
        error_hints.append("Check iterator type mismatches")
    if "unwrap()" in code:
        error_hints.append("The unwrap() calls may panic on None/Err")
    if "[" in code and "]" in code:
        error_hints.append("Check for potential index out of bounds")
    if "&" in code or "*" in code:
        error_hints.append("Check borrow checker violations")

    base = _select_instruction(
        [
            "Fix the compile error or bug in this Rust function.",
            "This function has an error. Identify and fix it.",
            "Correct this broken Rust function.",
        ]
    )

    hint_str = " ".join(error_hints) if error_hints else ""
    instruction = f"{base} Keep the same signature. {hint_str}".strip()

    system_prompt = (
        "You are an expert Rust compiler assistant who fixes code errors. "
        "You identify and fix compile errors, type mismatches, borrow checker "
        "violations, and logic bugs. You keep the same function signature. "
        "Output only the fixed function." + _CODE_OUTPUT_RULES
    )

    user_prompt = f"{instruction}\n\n{fewshot}\n\nNow fix this:\n\n{code}"
    if context:
        user_prompt += f"\n\n// Available context:\n{context}"

    completion = await _call_llm(system_prompt, user_prompt)
    if not completion:
        return None

    return {
        "prompt": instruction + "\n\n" + code,
        "gen": completion,
        "_task_type": "error_fixing",
    }


async def generate_documentation_task(
    code: str, context: str = ""
) -> Optional[Dict[str, Any]]:
    """Generate an explanation task for the given Rust ``code``."""
    subject = _explanation_subject(code)
    instruction = _select_instruction(
        [
            f"In plain English, explain what this {subject} does. Keep it brief and in paragraph form.",
            f"Describe the purpose and behavior of this {subject} in a short, plain-language paragraph.",
            f"Give a concise explanation of this {subject} in plain text. Avoid lists or markdown.",
            f"Summarize what this {subject} does in a few plain sentences.",
            f"Explain this {subject} to a Rust developer in a short paragraph.",
            f"Briefly explain the intent and behavior of this {subject} in plain language.",
            f"Provide a short, plain-English summary of this {subject}.",
            f"Write a compact explanation of this {subject} using plain sentences only.",
            f"Describe what this {subject} does in a brief paragraph of plain text.",
            f"Explain the role of this {subject} in clear, plain language.",
        ]
    )
    user_prompt = code
    if context:
        user_prompt += "\n\n// Context:\n" + context

    completion = await _call_llm(
        "You are an expert technical writer who explains Rust code clearly.",
        instruction + "\n\n" + user_prompt,
    )
    if not completion:
        return None

    return {
        "prompt": instruction + "\n\n" + code,
        "gen": completion,
        "_task_type": "explanations",
    }


async def generate_code_generation_task(
    code: str, context: str = ""
) -> Optional[Dict[str, Any]]:
    """Generate a code completion task for the given Rust ``code``."""
    # Detect patterns and select relevant examples
    patterns = ast_patterns.detect_code_patterns_ast(code)
    fewshot = _select_fewshot_examples(code, "codegen")

    # Build pattern-aware instruction
    pattern_hints = []
    if patterns.get("has_async"):
        pattern_hints.append("Use async/await patterns correctly")
    if patterns.get("has_error_handling"):
        pattern_hints.append("Use the ? operator for error propagation")
    if patterns.get("has_iterators"):
        pattern_hints.append("Use iterator chains idiomatically")

    base = _select_instruction(
        [
            "Complete the Rust function by implementing its body.",
            "Implement the function body with idiomatic Rust.",
            "Fill in the function body with correct, working code.",
        ]
    )

    hints = _style_hints(code)
    pattern_hint_str = ". ".join(pattern_hints) + "." if pattern_hints else ""
    instruction = f"{base} {hints} {pattern_hint_str}".strip()

    system_prompt = (
        "You are an expert Rust programmer. You complete function bodies with "
        "correct, idiomatic Rust code. You never use todo!(), unimplemented!(), "
        "or placeholder comments. Output only the completed function."
        + _CODE_OUTPUT_RULES
    )

    user_prompt = f"{instruction}\n\n{fewshot}\n\nNow complete this:\n\n{code}"
    if context:
        user_prompt += f"\n\n// Available context:\n{context}"

    completion = await _call_llm(system_prompt, user_prompt)
    if not completion:
        return None

    return {
        "prompt": instruction + "\n\n" + code,
        "gen": completion,
        "_task_type": "code_generation",
    }


async def generate_fim_task(code: str, context: str = "") -> Optional[Dict[str, Any]]:
    """Generate a fill-in-the-middle task for the given Rust function.

    Uses standard FIM tokens (<fim_prefix>, <fim_suffix>, <fim_middle>) that
    are compatible with most code models including StarCoder, CodeLlama, and
    DeepSeek-Coder.

    The task removes a contiguous section from the middle of the function body
    and asks the model to predict it given the surrounding context.
    """
    body_range = _find_function_body_range(code)
    if body_range is None:
        return None

    body_start, body_end = body_range
    lines = code.splitlines(keepends=True)

    # Ensure we have enough lines in the body to create a meaningful gap
    body_lines = body_end - body_start
    if body_lines < 3:
        return None

    # Calculate gap position and size (middle third of body, minimum 1 line)
    gap_size = max(1, body_lines // 3)
    mid_point = body_start + body_lines // 2
    gap_start = max(body_start, mid_point - gap_size // 2)
    gap_end = min(body_end, gap_start + gap_size)

    # Ensure gap is valid
    if gap_end <= gap_start:
        return None

    # Split into prefix, middle (to predict), suffix
    prefix = "".join(lines[:gap_start])
    middle = "".join(lines[gap_start:gap_end])
    suffix = "".join(lines[gap_end:])

    # Validate the extracted middle section
    if not middle.strip():
        return None

    # Format prompt with FIM tokens
    prompt = f"{FIM_PREFIX_TOKEN}{prefix}{FIM_SUFFIX_TOKEN}{suffix}{FIM_MIDDLE_TOKEN}"

    return {
        "prompt": prompt,
        "gen": middle,
        "_task_type": "fill_in_middle",
    }


__all__ = [
    "generate_refactoring_task",
    "generate_bug_fixing_task",
    "generate_documentation_task",
    "generate_code_generation_task",
    "generate_fim_task",
    "FIM_PREFIX_TOKEN",
    "FIM_SUFFIX_TOKEN",
    "FIM_MIDDLE_TOKEN",
]
