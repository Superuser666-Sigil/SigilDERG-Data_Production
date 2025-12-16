from sigil_pipeline.analyzer import parse_assistant_json_output


def test_parse_assistant_json_output_full_json():
    text = '{"code": "fn a() {}", "explanation": "ok"}'
    parsed = parse_assistant_json_output(text)
    assert parsed.get("code") == "fn a() {}"


def test_parse_assistant_json_output_braced():
    text = 'Some preface\n{"code": "fn b() {}", "explanation": "ok"}\ntrailer'
    parsed = parse_assistant_json_output(text)
    assert parsed.get("code") == "fn b() {}"


def test_parse_assistant_json_output_fallback_codeblock():
    text = "Here is the change:\n```rust\nfn c() {}\n```\nExplanation: simple"
    parsed = parse_assistant_json_output(text)
    assert parsed.get("code_after") == "fn c() {}"
    assert parsed.get("explanation") == "simple"
