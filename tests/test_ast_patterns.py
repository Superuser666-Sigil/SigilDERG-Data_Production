"""
Tests for sigil_pipeline.ast_patterns module.

Tests AST-based extraction of function signatures, struct fields, and code patterns.
Includes edge cases for nested generics, lifetimes, and complex Rust syntax.
"""

from sigil_pipeline.ast_patterns import (
    detect_code_patterns_ast,
    extract_all_function_signatures,
    extract_function_signature,
    extract_struct_fields,
    extract_struct_name,
    get_detected_pattern_descriptions,
)


class TestFunctionSignatureExtraction:
    """Test extract_function_signature function."""

    def test_simple_function(self):
        """Test extraction of a simple function."""
        code = "pub fn add(a: i32, b: i32) -> i32 { a + b }"
        sig = extract_function_signature(code)

        assert sig is not None
        assert sig.name == "add"
        assert sig.is_pub is True
        assert sig.is_async is False
        assert len(sig.params) == 2
        assert ("a", "i32") in sig.params
        assert ("b", "i32") in sig.params
        assert sig.return_type is not None
        assert "i32" in sig.return_type

    def test_async_function(self):
        """Test extraction of an async function."""
        code = """
        pub async fn fetch_data(url: &str) -> Result<String, Error> {
            // async body
        }
        """
        sig = extract_function_signature(code)

        assert sig is not None
        assert sig.name == "fetch_data"
        assert sig.is_async is True
        assert sig.is_pub is True

    def test_generic_function(self):
        """Test extraction of a generic function."""
        code = """
        pub fn transform<T: Clone>(input: T) -> T {
            input.clone()
        }
        """
        sig = extract_function_signature(code)

        assert sig is not None
        assert sig.name == "transform"
        assert sig.generics is not None
        assert "T" in sig.generics

    def test_function_with_lifetimes(self):
        """Test extraction of function with lifetime parameters."""
        code = """
        pub fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
            if x.len() > y.len() { x } else { y }
        }
        """
        sig = extract_function_signature(code)

        assert sig is not None
        assert sig.name == "longest"
        assert len(sig.lifetimes) > 0

    def test_function_with_where_clause(self):
        """Test extraction of function with where clause."""
        code = """
        pub fn process<T, U>(x: T, y: U) -> T
        where
            T: Clone + Default,
            U: Into<T>,
        {
            x.clone()
        }
        """
        sig = extract_function_signature(code)

        assert sig is not None
        assert sig.name == "process"
        assert sig.where_clause is not None

    def test_nested_generics_in_params(self):
        """Test extraction with nested generic types in parameters."""
        code = """
        pub fn process_map(data: HashMap<String, Vec<i32>>) -> Vec<String> {
            vec![]
        }
        """
        sig = extract_function_signature(code)

        assert sig is not None
        assert sig.name == "process_map"
        # Params should be extracted correctly despite nested >
        assert len(sig.params) >= 1

    def test_no_function(self):
        """Test that None is returned when no function exists."""
        code = "struct Foo { x: i32 }"
        sig = extract_function_signature(code)

        assert sig is None

    def test_function_with_self_param(self):
        """Test extraction of method with self parameter."""
        code = """
        impl Foo {
            pub fn bar(&self, x: i32) -> i32 {
                self.value + x
            }
        }
        """
        sig = extract_function_signature(code)

        assert sig is not None
        assert sig.name == "bar"

    def test_function_no_return_type(self):
        """Test extraction of function without explicit return type."""
        code = """
        pub fn print_hello() {
            println!("Hello");
        }
        """
        sig = extract_function_signature(code)

        assert sig is not None
        assert sig.name == "print_hello"
        # return_type should be None or empty for unit functions

    def test_extract_all_functions(self):
        """Test extraction of multiple functions."""
        code = """
        fn one() {}
        fn two() {}
        fn three() {}
        """
        sigs = extract_all_function_signatures(code)

        assert len(sigs) == 3
        names = [s.name for s in sigs]
        assert "one" in names
        assert "two" in names
        assert "three" in names


class TestStructFieldExtraction:
    """Test extract_struct_fields function."""

    def test_simple_struct(self):
        """Test extraction of simple struct fields."""
        code = """
        struct Point {
            x: i32,
            y: i32,
        }
        """
        fields = extract_struct_fields(code)

        assert len(fields) == 2
        names = [f.name for f in fields]
        assert "x" in names
        assert "y" in names

    def test_struct_with_pub_fields(self):
        """Test extraction of struct with public fields."""
        code = """
        pub struct Config {
            pub name: String,
            pub value: i32,
            private_field: bool,
        }
        """
        fields = extract_struct_fields(code)

        assert len(fields) == 3
        pub_fields = [f for f in fields if f.is_pub]
        assert len(pub_fields) == 2

    def test_struct_with_generic_fields(self):
        """Test extraction of struct with generic type fields."""
        code = """
        struct Container<T> {
            items: Vec<T>,
            count: usize,
        }
        """
        fields = extract_struct_fields(code)

        assert len(fields) == 2
        items_field = next(f for f in fields if f.name == "items")
        assert "Vec" in items_field.field_type

    def test_struct_with_nested_types(self):
        """Test extraction of struct with nested generic types."""
        code = """
        struct DataStore {
            data: HashMap<String, Vec<i32>>,
            metadata: Option<Box<Metadata>>,
        }
        """
        fields = extract_struct_fields(code)

        assert len(fields) == 2
        data_field = next(f for f in fields if f.name == "data")
        # Should correctly capture the full nested type
        assert "HashMap" in data_field.field_type

    def test_tuple_struct(self):
        """Test that tuple structs return empty fields (no named fields)."""
        code = "struct Point(i32, i32);"
        fields = extract_struct_fields(code)

        # Tuple structs don't have named fields
        assert len(fields) == 0

    def test_extract_struct_name(self):
        """Test struct name extraction."""
        code = """
        #[derive(Debug)]
        pub struct MyConfig {
            value: i32,
        }
        """
        name = extract_struct_name(code)

        assert name == "MyConfig"

    def test_no_struct(self):
        """Test that empty list is returned when no struct exists."""
        code = "fn foo() {}"
        fields = extract_struct_fields(code)

        assert len(fields) == 0


class TestCodePatternDetection:
    """Test detect_code_patterns_ast function."""

    def test_detects_main_function(self):
        """Test detection of main function."""
        code = 'fn main() { println!("Hello"); }'
        patterns = detect_code_patterns_ast(code)

        assert patterns["has_main"] is True
        assert "main" in patterns["function_names"]

    def test_detects_async(self):
        """Test detection of async code."""
        code = """
        async fn fetch() -> String {
            "data".to_string()
        }
        """
        patterns = detect_code_patterns_ast(code)

        assert patterns["has_async"] is True

    def test_detects_serde_derive(self):
        """Test detection of Serde derives."""
        code = """
        #[derive(Serialize, Deserialize)]
        struct Data {
            value: i32,
        }
        """
        patterns = detect_code_patterns_ast(code)

        assert patterns["has_serde"] is True

    def test_detects_error_handling(self):
        """Test detection of error handling patterns."""
        code = """
        fn process() -> Result<i32, Error> {
            let value = get_value()?;
            Ok(value)
        }
        """
        patterns = detect_code_patterns_ast(code)

        assert patterns["has_error_handling"] is True

    def test_detects_iterators(self):
        """Test detection of iterator usage."""
        code = """
        fn sum_all(items: Vec<i32>) -> i32 {
            items.iter().map(|x| x * 2).filter(|x| *x > 0).collect()
        }
        """
        patterns = detect_code_patterns_ast(code)

        assert patterns["has_iterators"] is True

    def test_detects_collections(self):
        """Test detection of collection types."""
        code = """
        use std::collections::HashMap;
        fn create_map() -> HashMap<String, i32> {
            HashMap::new()
        }
        """
        patterns = detect_code_patterns_ast(code)

        assert patterns["has_collections"] is True

    def test_detects_io(self):
        """Test detection of I/O operations."""
        code = """
        use std::fs::File;
        fn read_file(path: &str) -> String {
            let file = File::open(path).unwrap();
            String::new()
        }
        """
        patterns = detect_code_patterns_ast(code)

        assert patterns["has_io"] is True

    def test_detects_concurrency(self):
        """Test detection of concurrency primitives."""
        code = """
        use std::sync::Arc;
        fn share_data() -> Arc<i32> {
            Arc::new(42)
        }
        """
        patterns = detect_code_patterns_ast(code)

        assert patterns["has_concurrency"] is True

    def test_detects_traits(self):
        """Test detection of trait definitions."""
        code = """
        trait Drawable {
            fn draw(&self);
        }
        """
        patterns = detect_code_patterns_ast(code)

        assert patterns["has_traits"] is True

    def test_detects_impl_blocks(self):
        """Test detection of impl blocks."""
        code = """
        struct Foo;
        impl Foo {
            fn new() -> Self { Foo }
        }
        """
        patterns = detect_code_patterns_ast(code)

        assert patterns["has_impl_blocks"] is True

    def test_detects_unsafe(self):
        """Test detection of unsafe code."""
        code = """
        fn dangerous() {
            unsafe {
                let ptr = 0 as *const i32;
            }
        }
        """
        patterns = detect_code_patterns_ast(code)

        assert patterns["has_unsafe"] is True

    def test_detects_closures(self):
        """Test detection of closures."""
        code = """
        fn apply<F>(f: F) where F: Fn(i32) -> i32 {
            let closure = |x| x + 1;
        }
        """
        patterns = detect_code_patterns_ast(code)

        assert patterns["has_closures"] is True

    def test_combined_patterns(self):
        """Test detection of multiple patterns in one code sample."""
        code = """
        use std::sync::Arc;

        #[derive(Serialize, Deserialize)]
        struct Config {
            value: i32,
        }

        async fn process(config: Config) -> Result<Arc<Config>, Error> {
            let shared = Arc::new(config);
            Ok(shared)
        }
        """
        patterns = detect_code_patterns_ast(code)

        assert patterns["has_async"] is True
        assert patterns["has_serde"] is True
        assert patterns["has_error_handling"] is True
        assert patterns["has_concurrency"] is True

    def test_function_names_extraction(self):
        """Test that function names are properly extracted."""
        code = """
        fn alpha() {}
        fn beta() {}
        fn gamma() {}
        """
        patterns = detect_code_patterns_ast(code)

        assert "alpha" in patterns["function_names"]
        assert "beta" in patterns["function_names"]
        assert "gamma" in patterns["function_names"]


class TestPatternDescriptions:
    """Test get_detected_pattern_descriptions function."""

    def test_descriptions_for_multiple_patterns(self):
        """Test that descriptions are generated for detected patterns."""
        patterns = {
            "has_async": True,
            "has_serde": True,
            "has_error_handling": True,
            "has_iterators": False,
        }
        descriptions = get_detected_pattern_descriptions(patterns)

        assert "asynchronous operations" in descriptions
        assert "Serde serialization/deserialization" in descriptions
        assert "error handling with Result types" in descriptions
        assert len(descriptions) == 3

    def test_empty_patterns(self):
        """Test that no descriptions are generated for empty patterns."""
        patterns = {
            "has_async": False,
            "has_serde": False,
        }
        descriptions = get_detected_pattern_descriptions(patterns)

        assert len(descriptions) == 0


class TestEdgeCases:
    """Test edge cases and complex scenarios."""

    def test_code_with_comments(self):
        """Test that comments don't interfere with parsing."""
        code = """
        // This is a comment with fn keyword
        /* Another comment with struct */
        fn actual_function() {
            // More comments
        }
        """
        sig = extract_function_signature(code)

        assert sig is not None
        assert sig.name == "actual_function"

    def test_code_with_string_literals(self):
        """Test that string literals don't interfere with parsing."""
        code = """
        fn process() -> String {
            let s = "fn fake_function() {}";
            s.to_string()
        }
        """
        patterns = detect_code_patterns_ast(code)

        # Should only detect the real function, not the one in string
        assert len(patterns["function_names"]) == 1
        assert "process" in patterns["function_names"]

    def test_macro_generated_code(self):
        """Test handling of macro invocations."""
        code = """
        macro_rules! define_fn {
            ($name:ident) => {
                fn $name() {}
            };
        }

        fn real_function() {}
        """
        patterns = detect_code_patterns_ast(code)

        assert patterns["has_macros"] is True
        assert "real_function" in patterns["function_names"]

    def test_deeply_nested_generics(self):
        """Test handling of deeply nested generic types."""
        code = """
        fn complex(data: Option<Result<Vec<HashMap<String, Vec<i32>>>, Error>>) {}
        """
        sig = extract_function_signature(code)

        assert sig is not None
        assert sig.name == "complex"
        assert len(sig.params) == 1

    def test_unicode_identifiers(self):
        """Test handling of non-ASCII but valid Rust identifiers."""
        code = """
        fn αβγ_function() -> i32 {
            42
        }
        """
        # Tree-sitter should handle this, but Rust identifiers are ASCII-only
        # This test verifies graceful handling
        _ = extract_function_signature(code)  # May or may not parse

    def test_empty_code(self):
        """Test handling of empty code."""
        code = ""
        sig = extract_function_signature(code)
        fields = extract_struct_fields(code)
        patterns = detect_code_patterns_ast(code)

        assert sig is None
        assert fields == []
        assert patterns["has_main"] is False

    def test_whitespace_only(self):
        """Test handling of whitespace-only code."""
        code = "   \n\t\n   "
        sig = extract_function_signature(code)

        assert sig is None
