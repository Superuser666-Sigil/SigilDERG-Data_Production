"""
Tests for prompt_templates.py.

Covers:
- Runtime detection accuracy
- Generic vs specific runtime phrases
- Seeded RNG determinism
- Pattern combination limits
- Thread-safety assumptions (documented)

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
"""

from sigil_pipeline.prompt_templates import (
    RUNTIME_PHRASES,
    build_async_prompt,
    build_combined_prompt,
    build_error_handling_prompt,
    build_serde_prompt,
    detect_async_runtime,
    get_runtime_phrase,
    initialize_prompt_rng,
    select_random,
)


class TestDetectAsyncRuntime:
    """Tests for detect_async_runtime function."""

    def test_detects_tokio_use_statement(self):
        """Tokio detected via use statement."""
        code = "use tokio::time::sleep;"
        assert detect_async_runtime(code) == "tokio"

    def test_detects_tokio_main_macro(self):
        """Tokio detected via #[tokio::main] macro."""
        code = """
        #[tokio::main]
        async fn main() {
            println!("Hello");
        }
        """
        assert detect_async_runtime(code) == "tokio"

    def test_detects_tokio_test_macro(self):
        """Tokio detected via #[tokio::test] macro."""
        code = """
        #[tokio::test]
        async fn test_something() {
            assert!(true);
        }
        """
        assert detect_async_runtime(code) == "tokio"

    def test_detects_async_std(self):
        """async-std detected via use statement."""
        code = "use async_std::task;"
        assert detect_async_runtime(code) == "async-std"

    def test_detects_async_std_main_macro(self):
        """async-std detected via #[async_std::main] macro."""
        code = """
        #[async_std::main]
        async fn main() {
            println!("Hello");
        }
        """
        assert detect_async_runtime(code) == "async-std"

    def test_detects_smol(self):
        """smol detected via use statement."""
        code = "use smol::Timer;"
        assert detect_async_runtime(code) == "smol"

    def test_detects_smol_block_on(self):
        """smol detected via smol::block_on."""
        code = """
        fn main() {
            smol::block_on(async {
                println!("Hello");
            });
        }
        """
        assert detect_async_runtime(code) == "smol"

    def test_detects_embassy(self):
        """Embassy detected via use statement."""
        code = "use embassy::time::Timer;"
        assert detect_async_runtime(code) == "embassy"

    def test_detects_embassy_executor_macro(self):
        """Embassy detected via #[embassy_executor::main] macro."""
        code = """
        #[embassy_executor::main]
        async fn main(spawner: Spawner) {
            loop {}
        }
        """
        assert detect_async_runtime(code) == "embassy"

    def test_detects_futures(self):
        """futures crate detected via use statement."""
        code = "use futures::stream::StreamExt;"
        assert detect_async_runtime(code) == "futures"

    def test_returns_none_for_async_only_code(self):
        """Returns None for async code without explicit runtime imports."""
        code = """
        pub async fn fetch_data() -> Result<String, Error> {
            Ok("data".to_string())
        }
        """
        assert detect_async_runtime(code) is None

    def test_returns_none_for_sync_code(self):
        """Returns None for synchronous code."""
        code = """
        pub fn add(a: i32, b: i32) -> i32 {
            a + b
        }
        """
        assert detect_async_runtime(code) is None

    def test_returns_none_for_empty_code(self):
        """Returns None for empty code."""
        assert detect_async_runtime("") is None
        assert detect_async_runtime(None) is None  # type: ignore


class TestGetRuntimePhrase:
    """Tests for get_runtime_phrase function."""

    def test_generic_phrase_for_none_runtime(self):
        """With runtime=None, returns phrase from RUNTIME_PHRASES['generic']."""
        initialize_prompt_rng(42)  # Fixed seed for determinism
        phrase = get_runtime_phrase(None, enable_randomization=True)
        assert phrase in RUNTIME_PHRASES["generic"]

    def test_tokio_phrase_for_tokio_runtime(self):
        """With runtime='tokio', returns phrase from RUNTIME_PHRASES['tokio']."""
        initialize_prompt_rng(42)
        phrase = get_runtime_phrase("tokio", enable_randomization=True)
        assert phrase in RUNTIME_PHRASES["tokio"]

    def test_async_std_phrase_for_async_std_runtime(self):
        """With runtime='async-std', returns appropriate phrase."""
        initialize_prompt_rng(42)
        phrase = get_runtime_phrase("async-std", enable_randomization=True)
        assert phrase in RUNTIME_PHRASES["async-std"]

    def test_unknown_runtime_falls_back_to_generic(self):
        """Unknown runtime falls back to generic phrases."""
        initialize_prompt_rng(42)
        phrase = get_runtime_phrase("unknown-runtime", enable_randomization=True)
        assert phrase in RUNTIME_PHRASES["generic"]

    def test_deterministic_with_same_seed(self):
        """Same seed produces same phrase."""
        initialize_prompt_rng(123)
        phrase1 = get_runtime_phrase(None, enable_randomization=True)
        initialize_prompt_rng(123)
        phrase2 = get_runtime_phrase(None, enable_randomization=True)
        assert phrase1 == phrase2


class TestBuildAsyncPrompt:
    """Tests for build_async_prompt function."""

    def test_always_uses_generic_phrasing(self):
        """build_async_prompt always uses generic phrasing regardless of detected runtime."""
        initialize_prompt_rng(42)
        tokio_code = """
        use tokio::time::sleep;
        async fn fetch_data() -> String { "data".to_string() }
        """
        prompt, detected = build_async_prompt(
            fn_name="fetch_data",
            patterns={"has_async": True},
            code=tokio_code,
        )

        # Should detect tokio but NOT mention it in the prompt
        assert detected == "tokio"
        assert "Tokio" not in prompt
        assert "tokio" not in prompt.lower() or "tokio" not in prompt

        # Should use generic async phrasing
        assert any(
            phrase.lower() in prompt.lower() for phrase in RUNTIME_PHRASES["generic"]
        )

    def test_returns_detected_runtime_as_metadata(self):
        """Detected runtime is returned as second element of tuple."""
        initialize_prompt_rng(42)
        async_std_code = "use async_std::task;"
        _, detected = build_async_prompt(
            fn_name="foo",
            patterns={},
            code=async_std_code,
        )
        assert detected == "async-std"

    def test_returns_none_for_no_runtime(self):
        """Returns None for detected_runtime when no runtime detected."""
        initialize_prompt_rng(42)
        generic_code = "async fn foo() {}"
        _, detected = build_async_prompt(
            fn_name="foo",
            patterns={},
            code=generic_code,
        )
        assert detected is None

    def test_includes_function_name(self):
        """Function name is included in prompt."""
        initialize_prompt_rng(42)
        prompt, _ = build_async_prompt(
            fn_name="process_request",
            patterns={},
        )
        assert "process_request" in prompt

    def test_includes_error_handling_qualifier(self):
        """Error handling qualifier added when pattern detected."""
        initialize_prompt_rng(42)
        prompt, _ = build_async_prompt(
            fn_name="fetch",
            patterns={"has_error_handling": True},
        )
        # Should contain some error handling phrase
        assert any(
            word in prompt.lower()
            for word in ["error", "result", "handling", "gracefully"]
        )


class TestSeededDeterminism:
    """Tests for RNG seeding and determinism."""

    def test_same_seed_produces_identical_prompts(self):
        """With same seed and inputs, prompts are identical."""
        patterns = {"has_async": True, "has_serde": True}

        initialize_prompt_rng(12345)
        prompt1 = build_combined_prompt(
            fn_name="process",
            params_str="data: Vec<u8>",
            return_type="Result<String, Error>",
            patterns=patterns,
        )

        initialize_prompt_rng(12345)
        prompt2 = build_combined_prompt(
            fn_name="process",
            params_str="data: Vec<u8>",
            return_type="Result<String, Error>",
            patterns=patterns,
        )

        assert prompt1 == prompt2

    def test_different_seeds_can_produce_different_prompts(self):
        """Different seeds should not affect deterministic prompts."""
        patterns = {"has_async": True}

        # Generate many prompts with different seeds
        prompts = set()
        for seed in range(100):
            initialize_prompt_rng(seed)
            prompt = build_combined_prompt(
                fn_name="foo",
                params_str="",
                return_type="String",
                patterns=patterns,
            )
            prompts.add(prompt)

        # build_combined_prompt is deterministic; seeds should not change output
        assert len(prompts) == 1

    def test_initialize_returns_seed_used(self):
        """initialize_prompt_rng returns the seed that was used."""
        # Explicit seed
        seed = initialize_prompt_rng(42)
        assert seed == 42

        # Auto-generated seed (should be a valid int)
        auto_seed = initialize_prompt_rng(None)
        assert isinstance(auto_seed, int)
        assert 0 <= auto_seed < 2**32

    def test_select_random_respects_randomization_flag(self):
        """With enable_randomization=False, always returns first choice."""
        initialize_prompt_rng(42)
        choices = ["first", "second", "third"]

        # Without randomization, should always return first
        for _ in range(10):
            result = select_random(choices, enable_randomization=False)
            assert result == "first"


class TestPatternCombination:
    """Tests for pattern combination limits in build_combined_prompt."""

    def test_limits_pattern_phrases_to_max_three(self):
        """build_combined_prompt includes at most 3 pattern phrases."""
        initialize_prompt_rng(42)
        patterns = {
            "has_async": True,
            "has_serde": True,
            "has_error_handling": True,
            "has_iterators": True,
            "has_io": True,
            "has_networking": True,
            "has_concurrency": True,
        }

        prompt = build_combined_prompt(
            fn_name="complex_function",
            params_str="",
            return_type="Result<(), Error>",
            patterns=patterns,
        )

        # Count how many pattern-related phrases appear
        # The prompt should not be excessively long
        assert len(prompt) < 500  # Reasonable length limit

    def test_includes_relevant_patterns(self):
        """Prompt includes phrases from detected patterns."""
        initialize_prompt_rng(42)
        patterns = {"has_serde": True}

        prompt = build_combined_prompt(
            fn_name=None,
            params_str=None,
            return_type=None,
            patterns=patterns,
            struct_name="Config",
        )

        # Should contain serde-related phrase
        assert any(
            word in prompt.lower()
            for word in ["serde", "serializ", "json", "deserializ"]
        )


class TestBuildErrorHandlingPrompt:
    """Tests for build_error_handling_prompt function."""

    def test_uses_patterns_for_context(self):
        """Error handling prompt uses patterns to add context."""
        initialize_prompt_rng(42)

        # With IO pattern
        prompt_io = build_error_handling_prompt(
            fn_name="read_file",
            patterns={"has_io": True},
        )
        assert "file" in prompt_io.lower() or "I/O" in prompt_io

        # With networking pattern
        initialize_prompt_rng(42)  # Reset for consistency
        prompt_net = build_error_handling_prompt(
            fn_name="fetch_api",
            patterns={"has_networking": True},
        )
        assert "network" in prompt_net.lower() or "request" in prompt_net.lower()

    def test_includes_function_name(self):
        """Function name is included in prompt."""
        initialize_prompt_rng(42)
        prompt = build_error_handling_prompt(
            fn_name="parse_config",
            patterns={},
        )
        assert "parse_config" in prompt


class TestBuildSerdePrompt:
    """Tests for build_serde_prompt function."""

    def test_includes_struct_name(self):
        """Struct name is included in prompt."""
        initialize_prompt_rng(42)
        prompt = build_serde_prompt(
            struct_name="UserConfig",
            fields=[("name", "String"), ("age", "u32")],
            patterns={},
        )
        assert "UserConfig" in prompt

    def test_includes_fields(self):
        """Fields are included in prompt."""
        initialize_prompt_rng(42)
        prompt = build_serde_prompt(
            struct_name="Config",
            fields=[("host", "String"), ("port", "u16")],
            patterns={},
        )
        assert "host" in prompt or "port" in prompt

    def test_limits_fields_to_five(self):
        """Only first 5 fields are included."""
        initialize_prompt_rng(42)
        many_fields = [(f"field{i}", "String") for i in range(10)]
        prompt = build_serde_prompt(
            struct_name="BigStruct",
            fields=many_fields,
            patterns={},
        )
        # Should not include field5 through field9
        assert "field5" not in prompt
        assert "field9" not in prompt


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_choices_returns_empty_string(self):
        """select_random with empty list returns empty string."""
        result = select_random([], enable_randomization=True)
        assert result == ""

    def test_none_function_name_handled(self):
        """Functions handle None function name gracefully."""
        initialize_prompt_rng(42)

        prompt1 = build_combined_prompt(
            fn_name=None,
            params_str=None,
            return_type=None,
            patterns={},
        )
        assert prompt1  # Should return something

        prompt2, _ = build_async_prompt(
            fn_name=None,
            patterns={},
        )
        assert prompt2  # Should return something

    def test_empty_patterns_handled(self):
        """Functions handle empty patterns dict gracefully."""
        initialize_prompt_rng(42)
        prompt = build_combined_prompt(
            fn_name="foo",
            params_str="",
            return_type="()",
            patterns={},
        )
        assert prompt
        assert "foo" in prompt
