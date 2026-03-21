# Fixture Detection Logic

Detection is implemented in `corpus/detector.py` using
[Tree-sitter](https://tree-sitter.github.io/tree-sitter/) grammars.
Each language has a dedicated detector function that walks the AST
and matches fixture-defining nodes.

Mock detection is a second pass over the fixture's source text using
compiled regular expressions covering all major mock frameworks per language.
It is intentionally language-agnostic to catch cross-language patterns and
runs after the AST phase.

## Go heuristic

Go has no formal fixture annotation. The detector applies a call-graph
heuristic: a non-test function (not prefixed `Test`, `Benchmark`, or
`Example`) that is called from ≥ 2 `TestXxx` functions in the same file
is classified as a `go_helper` fixture.

This heuristic has lower precision than the annotation-based detectors
for other languages. See [Limitations](11-limitations.md) for the validated
false-positive rate and the manual validation procedure.
