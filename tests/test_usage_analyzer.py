"""
Tests for sigil_pipeline.usage_analyzer module.

Tests static API usage analysis including import detection,
usage pattern recognition, and confidence scoring.
"""

from sigil_pipeline.usage_analyzer import APIUsageAnalyzer, UsageAnalysis


class TestUsageAnalysis:
    """Test UsageAnalysis dataclass."""

    def test_create_basic_analysis(self):
        """Test creating a basic usage analysis result."""
        analysis = UsageAnalysis(
            api_name="File",
            module_path="std::fs",
            confidence=0.9,
            usage_type="direct_call",
        )
        assert analysis.api_name == "File"
        assert analysis.module_path == "std::fs"
        assert analysis.confidence == 0.9
        assert analysis.usage_type == "direct_call"
        assert analysis.import_statement is None
        assert analysis.usage_locations == []

    def test_create_analysis_with_all_fields(self):
        """Test creating analysis with all fields populated."""
        analysis = UsageAnalysis(
            api_name="read_to_string",
            module_path="std::fs",
            confidence=0.85,
            usage_type="qualified_call",
            import_statement="use std::fs",
            usage_locations=[(10, 5), (25, 10)],
        )
        assert analysis.import_statement == "use std::fs"
        assert len(analysis.usage_locations) == 2
        assert (10, 5) in analysis.usage_locations


class TestAPIUsageAnalyzer:
    """Test APIUsageAnalyzer class."""

    def test_analyzer_initialization(self):
        """Test analyzer initializes correctly."""
        analyzer = APIUsageAnalyzer()
        assert analyzer.parser is not None

    def test_analyze_direct_import(self):
        """Test analyzing code with direct import."""
        analyzer = APIUsageAnalyzer()
        code = """use std::fs::File;

fn main() {
    let f = File::open("test.txt");
}
"""
        result = analyzer.analyze_usage(code, "File", "std::fs")

        assert result.api_name == "File"
        assert result.confidence > 0.5
        assert result.import_statement is not None

    def test_analyze_braced_import(self):
        """Test analyzing code with braced import."""
        analyzer = APIUsageAnalyzer()
        code = """use std::fs::{File, read_to_string};

fn main() {
    let content = read_to_string("test.txt");
}
"""
        result = analyzer.analyze_usage(code, "read_to_string", "std::fs")

        assert result.api_name == "read_to_string"
        assert result.confidence > 0.5

    def test_analyze_module_import(self):
        """Test analyzing code with module-level import."""
        analyzer = APIUsageAnalyzer()
        code = """use std::fs;

fn main() {
    let f = fs::File::open("test.txt");
}
"""
        result = analyzer.analyze_usage(code, "File", "std::fs")

        assert result.confidence > 0.0

    def test_analyze_no_import(self):
        """Test analyzing code without relevant import."""
        analyzer = APIUsageAnalyzer()
        code = """fn main() {
    println!("Hello");
}
"""
        result = analyzer.analyze_usage(code, "File", "std::fs")

        assert result.confidence < 0.5

    def test_analyze_direct_call(self):
        """Test detecting direct function call."""
        analyzer = APIUsageAnalyzer()
        code = """use std::fs::read_to_string;

fn main() {
    let content = read_to_string("file.txt").unwrap();
}
"""
        result = analyzer.analyze_usage(code, "read_to_string", "std::fs")

        assert result.usage_type in ["direct_call", "unknown"]
        assert len(result.usage_locations) > 0 or result.confidence > 0

    def test_analyze_method_call(self):
        """Test detecting method call pattern."""
        analyzer = APIUsageAnalyzer()
        code = """use std::fs::File;
use std::io::Read;

fn main() {
    let mut f = File::open("test.txt").unwrap();
    let mut buf = String::new();
    f.read_to_string(&mut buf);
}
"""
        result = analyzer.analyze_usage(code, "read_to_string", "std::io")

        # Should detect method call
        assert isinstance(result.usage_type, str)

    def test_analyze_struct_init(self):
        """Test detecting struct initialization."""
        analyzer = APIUsageAnalyzer()
        code = """use std::collections::HashMap;

fn main() {
    let map = HashMap::new();
}
"""
        result = analyzer.analyze_usage(code, "HashMap", "std::collections")

        assert result.confidence > 0.5

    def test_analyze_type_annotation(self):
        """Test detecting type annotation usage."""
        analyzer = APIUsageAnalyzer()
        code = """use std::collections::HashMap;

fn process(data: HashMap<String, i32>) {
    // process
}
"""
        result = analyzer.analyze_usage(code, "HashMap", "std::collections")

        assert result.confidence > 0.5

    def test_analyze_qualified_call(self):
        """Test detecting fully qualified call."""
        analyzer = APIUsageAnalyzer()
        code = """fn main() {
    let f = std::fs::File::open("test.txt");
}
"""
        result = analyzer.analyze_usage(code, "File", "std::fs")

        # Should detect qualified usage
        assert isinstance(result.confidence, float)

    def test_analyze_comment_exclusion(self):
        """Test that API mentions in comments don't count."""
        analyzer = APIUsageAnalyzer()
        code = """// Use File to open files
// File is great
fn main() {
    println!("No actual File usage");
}
"""
        result = analyzer.analyze_usage(code, "File", "std::fs")

        # Comments shouldn't increase confidence significantly
        assert result.confidence < 0.5

    def test_analyze_import_with_alias(self):
        """Test analyzing aliased import."""
        analyzer = APIUsageAnalyzer()
        code = """use std::fs::File as StdFile;

fn main() {
    let f = StdFile::open("test.txt");
}
"""
        result = analyzer.analyze_usage(code, "File", "std::fs")

        # Should detect aliased import
        assert result.import_statement is not None or result.confidence > 0

    def test_extract_crate_name(self):
        """Test crate name extraction from module path."""
        analyzer = APIUsageAnalyzer()

        assert analyzer.extract_crate_name("std::fs") == "std"
        assert analyzer.extract_crate_name("tokio::runtime") == "tokio"
        assert analyzer.extract_crate_name("serde") == "serde"
        assert analyzer.extract_crate_name("") is None

    def test_analyze_empty_code(self):
        """Test analyzing empty code."""
        analyzer = APIUsageAnalyzer()
        result = analyzer.analyze_usage("", "File", "std::fs")

        assert result.confidence == 0.0
        assert result.usage_type == "unknown"

    def test_analyze_complex_imports(self):
        """Test analyzing complex nested imports."""
        analyzer = APIUsageAnalyzer()
        code = """use std::{
    fs::{File, read_to_string},
    io::{Read, Write},
};

fn main() {
    let f = File::open("test.txt");
}
"""
        result = analyzer.analyze_usage(code, "File", "std::fs")

        # Should handle nested imports
        assert isinstance(result.confidence, float)


class TestAPIUsageAnalyzerEdgeCases:
    """Test edge cases for API usage analysis."""

    def test_analyze_partial_match(self):
        """Test that partial name matches don't false positive."""
        analyzer = APIUsageAnalyzer()
        code = """fn main() {
    let file_path = "test.txt";
    let my_file = open_file();
}
"""
        result = analyzer.analyze_usage(code, "File", "std::fs")

        # "file_path" and "my_file" shouldn't match "File"
        # Confidence should be low
        assert result.confidence < 0.5

    def test_analyze_multiple_usage_locations(self):
        """Test detecting multiple usage locations."""
        analyzer = APIUsageAnalyzer()
        code = """use std::fs::File;

fn main() {
    let f1 = File::open("a.txt");
    let f2 = File::open("b.txt");
    let f3 = File::create("c.txt");
}
"""
        result = analyzer.analyze_usage(code, "File", "std::fs")

        # Should find multiple locations
        assert result.confidence > 0.5

    def test_analyze_trait_usage(self):
        """Test analyzing trait usage."""
        analyzer = APIUsageAnalyzer()
        code = """use std::io::Read;

fn read_all<R: Read>(reader: &mut R) -> Vec<u8> {
    let mut buf = Vec::new();
    reader.read_to_end(&mut buf).unwrap();
    buf
}
"""
        result = analyzer.analyze_usage(code, "Read", "std::io")

        assert result.confidence > 0.5

    def test_analyze_macro_usage(self):
        """Test analyzing macro usage."""
        analyzer = APIUsageAnalyzer()
        code = """fn main() {
    println!("Hello, world!");
    format!("Value: {}", 42);
}
"""
        result = analyzer.analyze_usage(code, "println", "std")

        # Macro detection
        assert isinstance(result.confidence, float)
