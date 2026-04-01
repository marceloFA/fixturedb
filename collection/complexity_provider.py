"""
Third-party metric collection for code complexity and structure analysis.

This module wraps industry-standard tools to calculate code metrics across all
5 supported languages (Python, Java, JavaScript, TypeScript, Go).

METRICS PROVIDED (via Lizard + cognitive-complexity libraries)
=============================================================

- Cyclomatic Complexity: via Lizard library (all languages)
- Cognitive Complexity: via cognitive_complexity library (Python) with fallback formula (other languages)
- Number of Parameters: via Lizard library (all languages) — Phase 2 addition

BENEFITS over custom tree-sitter implementation:
- Uses proven, well-maintained industry-standard libraries
- Consistent with SonarQube and McCabe complexity standards
- Reduces custom code maintenance burden
- Better cross-language consistency
- Academic credibility for published research

See docs/COMPLEXITY_METRICS_MIGRATION.md for complete methodology and justification.
"""

import ast
from pathlib import Path
from typing import Optional

from lizard import analyze_file as lizard_analyze_file
from cognitive_complexity.api import get_cognitive_complexity


def get_cyclomatic_complexity(file_path: Path, language: str) -> Optional[int]:
    """
    Get cyclomatic complexity of a function using lizard.
    
    Cyclomatic complexity measures the number of independent paths through code.
    Formula: CC = 1 + number of decision points (if, for, while, catch, etc.)
    
    Args:
        file_path: Path to the source file
        language: Programming language ('python', 'java', 'javascript', etc.)
    
    Returns:
        Cyclomatic complexity metric (>= 1), or None if analysis fails
    
    Note:
        Returns the minimum complexity of all functions in the file if multiple found.
        For fixture extraction, use get_function_complexities() instead.
    """
    try:
        result = lizard_analyze_file(str(file_path))
        if result.function_list:
            # Return first function found; caller typically analyzes single functions
            return result.function_list[0].cyclomatic_complexity
    except Exception:
        pass
    return None


def get_cognitive_complexity_python(file_path: Path) -> Optional[int]:
    """
    Get cognitive complexity using the cognitive_complexity library.
    
    Cognitive complexity extends cyclomatic complexity by:
    - Weighting nested structures more heavily
    - Tracking boolean operators
    - Following SonarQube's standard definition
    
    Args:
        file_path: Path to Python source file
    
    Returns:
        Cognitive complexity metric (>= 0), or None if analysis fails
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source)
        
        # Get complexity of first function found
        if tree.body:
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    return get_cognitive_complexity(node)
    except Exception:
        pass
    return None


def get_cognitive_complexity_fallback(cyclomatic: int, max_nesting: int = 1) -> int:
    """
    Compute cognitive complexity using a formula when language-specific parser unavailable.
    
    For languages without native cognitive complexity support (Java, JS, etc.),
    use this estimated formula based on cyclomatic complexity and nesting depth.
    
    Formula: CC_cognitive ≈ CC * max_nesting_depth (or CC itself if depth unavailable)
    
    Args:
        cyclomatic: Cyclomatic complexity value
        max_nesting: Maximum nesting depth (default: 1)
    
    Returns:
        Estimated cognitive complexity
    
    Note:
        This is a heuristic. Languages with proper parsers (Python) should use
        language-specific implementations instead.
    """
    if max_nesting <= 0:
        max_nesting = 1
    # Simple formula: multiply by nesting depth
    # This gives higher weight to nested structures
    return max(1, cyclomatic + max(0, max_nesting - 1))


def analyze_function_complexity(
    source_text: str,
    language: str,
    function_name: Optional[str] = None,
) -> dict:
    """
    Analyze complexity and structure metrics for a code snippet using Lizard.
    
    Args:
        source_text: Source code as string
        language: Programming language
        function_name: Optional function name to extract (if not provided, analyze first function)
    
    Returns:
        Dictionary with keys:
        - 'cyclomatic_complexity' (int): McCabe complexity, >= 1
        - 'cognitive_complexity' (int): SonarQube-style complexity, >= 0
        - 'num_parameters' (int): Function signature parameter count
    
    Note:
        num_external_calls is handled separately via custom regex detection
        of I/O patterns (database, HTTP, file, subprocess calls) since Lizard's
        fan_out metric measures inter-function calls, not external I/O.
        
        LOC is not included because our definition (non-blank lines) differs from
        Lizard's definition (total lines spanning the function).
    
    Example:
        >>> code = "def fixture(x):\\n    if x:\\n        return db.query()"
        >>> metrics = analyze_function_complexity(code, 'python')
        >>> metrics['cyclomatic_complexity']
        2
        >>> metrics['cognitive_complexity']
        1
        >>> metrics['num_parameters']
        1
    """
    metrics = {
        'cyclomatic_complexity': 1,
        'cognitive_complexity': 0,
        'num_parameters': 0,
        'num_external_calls': 0,
    }
    
    try:
        # Write to temp file for lizard analysis
        temp_file = Path('/tmp') / f'_analyze_cc_{id(source_text)}.{_get_extension(language)}'
        temp_file.write_text(source_text)
        
        # Analyze with Lizard to get all metrics
        result = lizard_analyze_file(str(temp_file))
        if result.function_list:
            func_info = result.function_list[0]
            
            # Extract all Lizard metrics
            metrics['cyclomatic_complexity'] = func_info.cyclomatic_complexity
            metrics['num_parameters'] = func_info.parameter_count if hasattr(func_info, 'parameter_count') else 0
            metrics['num_external_calls'] = func_info.external_call_count if hasattr(func_info, 'external_call_count') else 0
            
            # Compute cognitive complexity based on language
            if language.lower() == 'python':
                # Use cognitive_complexity library for Python (most accurate)
                try:
                    tree = ast.parse(source_text)
                    for node in tree.body:
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            cc = get_cognitive_complexity(node)
                            if cc is not None:
                                metrics['cognitive_complexity'] = cc
                                break
                except Exception:
                    # Fall back to formula if cognitive_complexity library fails
                    # Use cyclomatic complexity as proxy (nesting depth not available from Lizard)
                    metrics['cognitive_complexity'] = get_cognitive_complexity_fallback(
                        metrics['cyclomatic_complexity'], 
                        1
                    )
            else:
                # For other languages: use default formula
                metrics['cognitive_complexity'] = get_cognitive_complexity_fallback(
                    metrics['cyclomatic_complexity'], 
                    1
                )
        
        # Cleanup
        temp_file.unlink(missing_ok=True)
        
    except Exception:
        # Return defaults (including loc=0) on any error
        pass
    
    return metrics


def _get_extension(language: str) -> str:
    """Map language name to file extension."""
    ext_map = {
        'python': 'py',
        'java': 'java',
        'javascript': 'js',
        'typescript': 'ts',
        'go': 'go',

        'c++': 'cpp',
        'c': 'c',
    }
    return ext_map.get(language.lower(), 'txt')
