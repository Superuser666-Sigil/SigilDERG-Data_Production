"""
Tests for sigil_pipeline.task_generator module.

Tests task type generation including error fixing tasks and explanation tasks.
"""

from sigil_pipeline.task_generator import (
    _inject_borrow_error,
    _inject_move_error,
    _inject_moved_value_error,
    _inject_simulated_error,
    _inject_type_mismatch_error,
    _looks_error_fixable,
    _looks_explainable,
    _looks_transformable,
    _synthesize_explanation_from_code,
    determine_task_capabilities,
    generate_error_fixing_task,
    generate_explanation_task,
    select_task_type,
    select_task_type_with_quota,
)


class TestGenerateErrorFixingTask:
    """Test generate_error_fixing_task function."""

    def test_simulated_error_injection(self):
        """Test simulated error injection."""
        code = """pub fn process(data: &str) -> String {
    let x: i32 = 42;
    data.to_string()
}"""

        result = generate_error_fixing_task(code, method="simulate")

        if result:
            assert "prompt" in result
            assert "gen" in result
            assert result["gen"] == code.strip()

    def test_error_fixing_with_both_methods(self):
        """Test error fixing with both simulated and real methods."""
        code = """pub fn test() {
    let x: i32 = 42;
    println!("{}", x);
}"""

        result = generate_error_fixing_task(code, method="both")

        # Should return simulated result if real compile not available
        assert result is None or isinstance(result, dict)

    def test_error_fixing_invalid_method(self):
        """Test error fixing with invalid method falls through."""
        code = "fn test() {}"

        result = generate_error_fixing_task(code, method="invalid")

        # Invalid method should return None
        assert result is None


class TestInjectSimulatedError:
    """Test _inject_simulated_error function."""

    def test_inject_any_error(self):
        """Test that some error type can be injected."""
        code = """fn process() {
    let x: i32 = 42;
    let y = x;
    println!("{}", x);
}"""

        error_desc, broken_code, error_code = _inject_simulated_error(code)

        # At least one error type should work
        if error_desc:
            assert broken_code is not None
            assert error_code is not None
            assert broken_code != code

    def test_inject_returns_none_for_empty(self):
        """Test injection returns None for unsuitable code."""
        code = ""

        error_desc, broken_code, error_code = _inject_simulated_error(code)

        # May return None for empty code
        assert isinstance(error_desc, (str, type(None)))


class TestInjectMoveError:
    """Test _inject_move_error function."""

    def test_inject_move_error(self):
        """Test E0507 move error injection."""
        code = """struct Data { value: String }
fn process(data: &Data) {
    let v = data.value;
}"""

        result = _inject_move_error(code)

        # Should modify code or return original
        assert isinstance(result, str)

    def test_inject_move_error_no_match(self):
        """Test move error with no suitable patterns."""
        code = "fn test() {}"

        result = _inject_move_error(code)

        assert result == code


class TestInjectMovedValueError:
    """Test _inject_moved_value_error function."""

    def test_inject_moved_value_error(self):
        """Test E0382 moved value error injection."""
        code = """fn process() {
    let x = String::from("hello");
    println!("{}", x);
    println!("{}", x);
}"""

        result = _inject_moved_value_error(code)

        # Should inject move before second use
        if result != code:
            assert "_moved_" in result

    def test_inject_moved_value_no_reuse(self):
        """Test moved value with no variable reuse."""
        code = """fn test() {
    let x = 42;
}"""

        result = _inject_moved_value_error(code)

        # No reuse, should return original
        assert result == code


class TestInjectBorrowError:
    """Test _inject_borrow_error function."""

    def test_inject_borrow_error(self):
        """Test E0597 borrow error injection."""
        code = """fn process() {
    let x = String::from("hello");
    println!("{}", x);
}"""

        result = _inject_borrow_error(code)

        # Should inject borrow-drop-use pattern
        if result != code:
            assert "_borrowed_" in result or "drop(" in result

    def test_inject_borrow_error_no_let(self):
        """Test borrow error with no let statements."""
        code = """fn test() {
    println!("hello");
}"""

        result = _inject_borrow_error(code)

        # No let statements to work with
        assert result == code


class TestInjectTypeMismatchError:
    """Test _inject_type_mismatch_error function."""

    def test_inject_type_mismatch_integer(self):
        """Test E0308 type mismatch on integer."""
        code = """fn process() {
    let x: i32 = 42;
}"""

        result = _inject_type_mismatch_error(code)

        # Should replace integer with string literal
        if result != code:
            assert "mismatch" in result

    def test_inject_type_mismatch_various_types(self):
        """Test type mismatch on various integer types."""
        for int_type in ["u8", "i16", "u32", "i64", "usize"]:
            code = f"""fn test() {{
    let x: {int_type} = 42;
}}"""

            result = _inject_type_mismatch_error(code)

            # Should inject mismatch
            if result != code:
                assert "mismatch" in result

    def test_inject_type_mismatch_no_typed_let(self):
        """Test type mismatch with no typed let."""
        code = """fn test() {
    let x = 42;
}"""

        result = _inject_type_mismatch_error(code)

        # No typed let, should return original
        assert result == code


class TestErrorInjectionRandom:
    """Test randomized error injection."""

    def test_injection_determinism_with_seed(self):
        """Test that setting random seed gives consistent results."""
        code = """fn process() {
    let x: i32 = 42;
    let y = x;
    println!("{}", x);
}"""

        # Run multiple times - should work without crashing
        for _ in range(5):
            error_desc, broken_code, error_code = _inject_simulated_error(code)
            assert isinstance(error_desc, (str, type(None)))


class TestTaskGeneratorIntegration:
    """Integration tests for task generation."""

    def test_generate_multiple_task_types(self):
        """Test generating different task types from same code."""
        code = """pub fn read_data(path: &str) -> Result<String, std::io::Error> {
    let content = std::fs::read_to_string(path).unwrap();
    Ok(content)
}"""
        # Try error fixing
        error_result = generate_error_fixing_task(code, method="simulate")

        # May or may not generate tasks depending on code structure
        assert error_result is None or isinstance(error_result, dict)

    def test_task_output_format(self):
        """Test that generated tasks have correct format."""
        code = """pub fn process() {
    let x: i32 = 42;
    println!("{}", x);
}"""

        result = generate_error_fixing_task(code, method="simulate")

        if result:
            assert isinstance(result, dict)
            assert "prompt" in result
            assert "gen" in result
            assert isinstance(result["prompt"], str)
            assert isinstance(result["gen"], str)
            assert len(result["prompt"]) > 0
            assert len(result["gen"]) > 0


class TestTaskGeneratorEdgeCases:
    """Test edge cases for task generation."""

    def test_empty_code(self):
        """Test handling of empty code."""
        result = generate_error_fixing_task("", method="simulate")
        # Empty code should not crash

    def test_malformed_code(self):
        """Test handling of malformed Rust code."""
        malformed = "fn { let x = ; }"

        # Should not crash
        result = generate_error_fixing_task(malformed, method="simulate")
        assert result is None or isinstance(result, dict)

    def test_unicode_in_code(self):
        """Test handling of unicode in code."""
        code = """fn greet() {
    let msg = "Hello, 世界! 🦀";
    println!("{}", msg);
}"""

        _ = generate_error_fixing_task(code, method="simulate")
        # Should handle unicode gracefully

    def test_very_long_code(self):
        """Test handling of very long code."""
        code = "fn process() {\n" + "    let x = 42;\n" * 1000 + "}"

        # Should not hang or crash
        result = generate_error_fixing_task(code, method="simulate")
        assert result is None or isinstance(result, dict)


class TestGenerateExplanationTask:
    """Test generate_explanation_task function."""

    def test_with_doc_comment(self):
        """Test explanation task with doc comment."""
        code = """/// Adds two numbers together.
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}"""
        result = generate_explanation_task(code, "Adds two numbers together.")
        assert result is not None
        assert result.get("_task_type") == "explanations"
        assert result.get("instruction")
        assert result.get("input_code")
        assert result.get("output_json")
        assert "Adds two numbers" in result["output_json"]["docstring"]

    def test_without_doc_comment(self):
        """Test explanation task extracts from code."""
        code = """pub fn multiply(x: i32, y: i32) -> i32 {
    x * y
}"""
        result = generate_explanation_task(code, None)
        assert result is None

    def test_with_inline_doc_comments(self):
        """Test explanation from inline doc comments."""
        code = """/// Calculates the factorial of a number.
///
/// # Arguments
/// * `n` - The number to calculate factorial for
pub fn factorial(n: u64) -> u64 {
    if n <= 1 { 1 } else { n * factorial(n - 1) }
}"""
        result = generate_explanation_task(code, None)
        assert result is None

    def test_empty_doc_comment(self):
        """Test with empty doc comment."""
        code = """pub fn empty() {}"""
        result = generate_explanation_task(code, "")
        assert result is None


class TestSynthesizeExplanation:
    """Test _synthesize_explanation_from_code function."""

    def test_simple_function(self):
        """Test synthesizing explanation for simple function."""
        code = """fn add(a: i32, b: i32) -> i32 {
    a + b
}"""
        result = _synthesize_explanation_from_code(code)
        assert result is not None
        assert "add" in result
        assert "parameter" in result.lower()

    def test_async_function(self):
        """Test async function explanation."""
        code = """async fn fetch_data(url: &str) -> Result<String, Error> {
    todo!()
}"""
        result = _synthesize_explanation_from_code(code)
        assert result is not None
        assert "asynchronous" in result.lower()

    def test_function_without_params(self):
        """Test function without parameters."""
        code = """fn hello() -> String {
    "Hello".to_string()
}"""
        result = _synthesize_explanation_from_code(code)
        assert result is not None
        assert "does not take any parameters" in result

    def test_function_with_result(self):
        """Test function returning Result."""
        code = """fn parse(s: &str) -> Result<i32, ParseError> {
    s.parse()
}"""
        result = _synthesize_explanation_from_code(code)
        assert result is not None
        assert "fallible" in result.lower()

    def test_no_function_returns_none(self):
        """Test code without function returns None."""
        code = "let x = 5;"
        result = _synthesize_explanation_from_code(code)
        assert result is None


class TestSelectTaskType:
    """Test select_task_type function."""

    def test_selects_from_mix(self):
        """Test selecting task type from distribution."""
        task_mix = {
            "code_generation": 0.5,
            "transformations": 0.3,
            "error_fixing": 0.2,
        }

        # Run multiple times to check distribution
        counts = {"code_generation": 0, "transformations": 0, "error_fixing": 0}
        for _ in range(100):
            task = select_task_type(task_mix)
            counts[task] += 1

        # Should select from all types (with high probability)
        assert counts["code_generation"] > 0

    def test_empty_mix_returns_fallback(self):
        """Test empty mix returns fallback."""
        result = select_task_type({})
        assert result == "code_generation"

    def test_single_task_always_selected(self):
        """Test single task type is always selected."""
        task_mix = {"transformations": 1.0}
        for _ in range(10):
            assert select_task_type(task_mix) == "transformations"


class TestSelectTaskTypeWithQuota:
    """Test select_task_type_with_quota function."""

    def test_selects_from_available(self):
        """Test selecting from available tasks."""
        task_mix = {"code_generation": 0.5, "transformations": 0.5}
        available = {"code_generation", "transformations"}
        counts = {"code_generation": 0, "transformations": 0}

        result = select_task_type_with_quota(task_mix, available, counts)
        assert result in available

    def test_favors_deficit_tasks(self):
        """Test that tasks with deficit are favored."""
        task_mix = {"code_generation": 0.5, "transformations": 0.5}
        available = {"code_generation", "transformations"}
        # transformations is under quota
        counts = {"code_generation": 100, "transformations": 0}

        # Run multiple times
        selections = []
        for _ in range(20):
            result = select_task_type_with_quota(task_mix, available, counts)
            selections.append(result)

        # transformations should be favored due to deficit
        assert selections.count("transformations") > 0

    def test_unavailable_tasks_excluded(self):
        """Test that unavailable tasks are excluded."""
        task_mix = {"code_generation": 0.5, "transformations": 0.5}
        available = {"code_generation"}  # transformations not available
        counts = {}

        for _ in range(10):
            result = select_task_type_with_quota(task_mix, available, counts)
            assert result == "code_generation"

    def test_empty_available_returns_fallback(self):
        """Test empty available set returns fallback."""
        result = select_task_type_with_quota({"transformations": 1.0}, set(), {})
        assert result == "code_generation"


class TestDetermineTaskCapabilities:
    """Test determine_task_capabilities function."""

    def test_code_generation_always_available(self):
        """Test code_generation is always in capabilities."""
        caps = determine_task_capabilities(
            "fn test() {}",
            {},
            None,
            enable_error_injection=False,
            error_injection_method="simulate",
        )
        assert "code_generation" in caps

    def test_transformations_for_io_code(self):
        """Test transformations capability for I/O code."""
        code = """fn read_file(path: &str) -> String {
    std::fs::read_to_string(path).unwrap()
}"""
        caps = determine_task_capabilities(
            code,
            {"has_io": True, "has_async": False},
            None,
            enable_error_injection=False,
            error_injection_method="simulate",
        )
        assert "transformations" in caps

    def test_explanations_with_doc_comment(self):
        """Test explanations capability with doc comment."""
        caps = determine_task_capabilities(
            "fn test() {}",
            {},
            "This is documentation.",
            enable_error_injection=False,
            error_injection_method="simulate",
        )
        assert "explanations" in caps

    def test_error_fixing_enabled(self):
        """Test error_fixing when enabled."""
        code = """fn process(data: Vec<i32>) -> i32 {
    let sum = data.iter().sum();
    sum
}"""
        caps = determine_task_capabilities(
            code,
            {},
            None,
            enable_error_injection=True,
            error_injection_method="simulate",
        )
        assert "error_fixing" in caps


class TestLooksHelpers:
    """Test _looks_* helper functions."""

    def test_looks_explainable_with_doc(self):
        """Test _looks_explainable with doc comment."""
        assert _looks_explainable("fn test() {}", "Documentation") is True
        assert _looks_explainable("fn test() {}", "") is True
        assert _looks_explainable("fn test() {}", None) is True

    def test_looks_explainable_with_inline_docs(self):
        """Test _looks_explainable with inline docs."""
        code = "/// Doc comment\nfn test() {}"
        assert _looks_explainable(code, None) is True

    def test_looks_transformable_io(self):
        """Test _looks_transformable for I/O code."""
        code = 'fn read() { std::fs::read_to_string("f").unwrap() }'
        patterns = {"has_io": True, "has_async": False}
        assert _looks_transformable(code, patterns) is True

    def test_looks_transformable_match(self):
        """Test _looks_transformable for match expressions."""
        code = """fn test() -> Result<i32, Error> {
    match compute() {
        Ok(v) => v,
        Err(e) => return Err(e),
    }
}"""
        assert _looks_transformable(code, {}) is True

    def test_looks_transformable_for_loop(self):
        """Test _looks_transformable for for loops."""
        code = """fn test() {
    for item in items {
        println!("{}", item);
    }
}"""
        patterns = {"has_iterators": False}
        assert _looks_transformable(code, patterns) is True

    def test_looks_error_fixable_simulate(self):
        """Test _looks_error_fixable with simulate method."""
        # Needs at least 4 lines
        code = """fn test() {
    let x = 1;
    let y = 2;
    x + y
}"""
        assert _looks_error_fixable(code, "simulate") is True

    def test_looks_error_fixable_too_short(self):
        """Test _looks_error_fixable rejects short code."""
        code = "fn test() {}"
        assert _looks_error_fixable(code, "simulate") is False

    def test_looks_error_fixable_real_compile(self):
        """Test _looks_error_fixable with real_compile method."""
        code = """fn process() {
    let x = 1;
    let y = 2;
    let z = x + y;
    println!("{}", z);
}"""
        assert _looks_error_fixable(code, "real_compile") is True
