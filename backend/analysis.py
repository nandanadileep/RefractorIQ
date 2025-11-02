import os
import re
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_java as tsjava
from .shared_constants import FUNCTION_NODE_TYPES, COMPLEXITY_THRESHOLDS, DECISION_NODE_TYPES

# Initialize language objects
PY_LANGUAGE = Language(tspython.language())
JS_LANGUAGE = Language(tsjavascript.language())
JAVA_LANGUAGE = Language(tsjava.language())

# Common third-party library directories to exclude
THIRD_PARTY_DIRS = {
    'node_modules',
    'venv',
    'env',
    '.env',
    'virtualenv',
    'site-packages',
    'dist-packages',
    '__pycache__',
    '.venv',
    'vendor',
    'bower_components',
    'target',
    'build',
    'dist',
    '.gradle',
    'lib',
    'libs',
    'packages',
}

# Regex patterns for matching common test file paths
TEST_FILE_PATTERNS = [
    re.compile(r'__tests__/'),         # JS __tests__ directory
    re.compile(r'/tests?/'),          # /test/ or /tests/ directory
    re.compile(r'test_.*\.py$'),      # Python test_ file
    re.compile(r'.*_test\.py$'),      # Python _test file
    re.compile(r'\.spec\.(js|ts)$'),  # JS/TS .spec file
    re.compile(r'\.test\.(js|ts)$'),  # JS/TS .test file
    re.compile(r'Test.*\.java$'),     # Java Test* file
    re.compile(r'.*Test\.java$'),     # Java *Test file
    re.compile(r'src/test/java/'),    # Maven test directory
]

def is_third_party_file(filepath, repo_path):
    """Check if a file is in a third-party directory"""
    try:
        rel_path = os.path.relpath(filepath, repo_path)
        path_parts = rel_path.split(os.sep)
        
        # Check if any part of the path matches third-party directories
        for part in path_parts:
            if part in THIRD_PARTY_DIRS:
                return True
        
        return False
    except Exception:
        return False

def is_test_file(filepath, repo_path):
    """Check if a file is a test file based on common patterns"""
    try:
        rel_path = os.path.relpath(filepath, repo_path).replace(os.sep, '/')
        
        for pattern in TEST_FILE_PATTERNS:
            if pattern.search(rel_path):
                return True
        return False
    except Exception:
        return False


def get_parser_and_language(file_extension):
    """Get appropriate parser and language based on file extension"""
    if file_extension == ".py":
        return Parser(PY_LANGUAGE), PY_LANGUAGE
    elif file_extension in [".js", ".ts"]:
        return Parser(JS_LANGUAGE), JS_LANGUAGE
    elif file_extension == ".java":
        return Parser(JAVA_LANGUAGE), JAVA_LANGUAGE
    else:
        return None, None

def count_todos(repo_path, exclude_third_party=True, exclude_tests=True):
    """Count TODO, FIXME, HACK comments using AST parsing"""
    todos = 0
    for root, _, files in os.walk(repo_path):
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in [".py", ".js", ".ts", ".java"]:
                filepath = os.path.join(root, file)
                
                # Skip third-party files if requested
                if exclude_third_party and is_third_party_file(filepath, repo_path):
                    continue
                
                # Skip test files if requested
                if exclude_tests and is_test_file(filepath, repo_path):
                    continue
                
                parser, language = get_parser_and_language(ext)
                if not parser:
                    continue
                
                try:
                    with open(filepath, "rb") as f:
                        content = f.read()
                    
                    tree = parser.parse(content)
                    
                    # Query for comments
                    query_str = "(comment) @comment"
                    query = language.query(query_str)
                    
                    captures = query.captures(tree.root_node)
                    
                    for node, _ in captures:
                        comment_text = content[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
                        if any(keyword in comment_text.upper() for keyword in ["TODO", "FIXME", "HACK"]):
                            todos += 1
                except Exception as e:
                    # Fallback to simple line-by-line parsing
                    try:
                        with open(filepath, "r", errors="ignore") as f:
                            for line in f:
                                if any(x in line for x in ["TODO", "FIXME", "HACK"]):
                                    todos += 1
                    except Exception:
                        pass
    return todos

def count_loc(repo_path, exclude_third_party=True, exclude_tests=True):
    """Count lines of code (excluding comments and blank lines) using AST"""
    loc = 0
    for root, _, files in os.walk(repo_path):
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in [".py", ".js", ".ts", ".java"]:
                filepath = os.path.join(root, file)
                
                # Skip third-party files if requested
                if exclude_third_party and is_third_party_file(filepath, repo_path):
                    continue
                
                # Skip test files if requested
                if exclude_tests and is_test_file(filepath, repo_path):
                    continue
                
                parser, language = get_parser_and_language(ext)
                
                try:
                    with open(filepath, "rb") as f:
                        content = f.read()
                    
                    if parser:
                        tree = parser.parse(content)
                        # Count lines covered by actual code nodes
                        lines_with_code = set()
                        
                        def traverse(node):
                            # Skip comment nodes
                            if 'comment' not in node.type:
                                start_line = node.start_point[0]
                                end_line = node.end_point[0]
                                for line in range(start_line, end_line + 1):
                                    lines_with_code.add(line)
                            
                            for child in node.children:
                                traverse(child)
                        
                        traverse(tree.root_node)
                        loc += len(lines_with_code)
                    else:
                        # Fallback
                        loc += len([l for l in content.decode('utf-8', errors='ignore').split('\n') if l.strip()])
                except Exception:
                    # Fallback to simple counting
                    try:
                        with open(filepath, "r", errors="ignore") as f:
                            loc += sum(1 for line in f if line.strip())
                    except Exception:
                        pass
    return loc

def calculate_cyclomatic_complexity(node, content):
    """Calculate cyclomatic complexity from AST node"""
    complexity = 1  # Base complexity
    
    def traverse(n):
        nonlocal complexity
        if n.type in DECISION_NODE_TYPES:
            # For boolean operators, check if it's 'and'/'or' or '&&'/'||'
            if n.type in ['boolean_operator', 'binary_expression']:
                try:
                    operator = content[n.start_byte:n.end_byte].decode('utf-8', errors='ignore')
                    if any(op in operator for op in ['&&', '||', ' and ', ' or ']):
                        complexity += 1
                except Exception:
                    pass
            else:
                complexity += 1
        
        for child in n.children:
            traverse(child)
    
    traverse(node)
    return complexity

# --- UPDATED FOR LLM SUGGESTIONS ---
def analyze_functions(repo_path, exclude_third_party=True, exclude_tests=True):
    """Analyze all functions in the repository - single pass for efficiency"""
    results = {
        "complexities": [],
        "total_functions": 0,
        "max_complexity": 0,
        "min_complexity": float('inf'),
        "files_analyzed": 0,
        "complexity_distribution": {
            "low": 0,
            "medium": 0,
            "high": 0,
            "very_high": 0
        },
        "complex_functions": []  # <--- NEW: To store complex functions
    }
    
    for root, _, files in os.walk(repo_path):
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in [".py", ".js", ".ts", ".java"]:
                filepath = os.path.join(root, file)
                
                # Skip third-party files
                if exclude_third_party and is_third_party_file(filepath, repo_path):
                    continue
                
                # Skip test files
                if exclude_tests and is_test_file(filepath, repo_path):
                    continue
                
                parser, language = get_parser_and_language(ext)
                
                if not parser:
                    continue
                
                try:
                    with open(filepath, "rb") as f:
                        content = f.read()
                    
                    tree = parser.parse(content)
                    results["files_analyzed"] += 1
                    
                    # --- NEW: Get rel_path here for context ---
                    rel_path = os.path.relpath(filepath, repo_path)

                    # Find all function-like nodes by traversing the tree
                    def find_functions(node):
                        functions = []
                        if node.type in FUNCTION_NODE_TYPES:
                            functions.append(node)
                        
                        for child in node.children:
                            functions.extend(find_functions(child))
                        
                        return functions
                    
                    function_nodes = find_functions(tree.root_node)
                    
                    for node in function_nodes:
                        results["total_functions"] += 1
                        
                        # --- NEW: Get function name ---
                        func_name = None
                        for child in node.children:
                            if child.type in ['identifier', 'property_identifier']:
                                func_name = content[child.start_byte:child.end_byte].decode('utf-8', errors='ignore')
                                break
                        
                        complexity = calculate_cyclomatic_complexity(node, content)
                        results["complexities"].append(complexity)
                        results["max_complexity"] = max(results["max_complexity"], complexity)
                        if complexity > 0:
                            results["min_complexity"] = min(results["min_complexity"], complexity)

                        # --- NEW: Store complex function details for LLM ---
                        if complexity > COMPLEXITY_THRESHOLDS['medium'][1]: # e.g., > 10
                            function_content = content[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
                            results["complex_functions"].append({
                                "file_path": rel_path.replace(os.sep, '/'), # Normalize path
                                "function_name": func_name or "unknown",
                                "content": function_content,
                                "complexity": complexity
                            })

                        # Categorize complexity
                        if complexity <= COMPLEXITY_THRESHOLDS['low'][1]:
                            results["complexity_distribution"]["low"] += 1
                        elif complexity <= COMPLEXITY_THRESHOLDS['medium'][1]:
                            results["complexity_distribution"]["medium"] += 1
                        elif complexity <= COMPLEXITY_THRESHOLDS['high'][1]:
                            results["complexity_distribution"]["high"] += 1
                        else:
                            results["complexity_distribution"]["very_high"] += 1
                        
                except Exception as e:
                    pass
    
    if results["min_complexity"] == float('inf'):
        results["min_complexity"] = 0
    
    return results

def avg_cyclomatic_complexity(repo_path, exclude_third_party=True, exclude_tests=True):
    """Calculate average cyclomatic complexity using AST parsing"""
    results = analyze_functions(repo_path, exclude_third_party, exclude_tests)
    if results["complexities"]:
        return round(sum(results["complexities"]) / len(results["complexities"]), 2)
    return 0

def simple_debt_score(loc, todos, complexity):
    """Calculate technical debt score"""
    return round((todos * 5 + complexity * 2 + loc / 1000), 2)

def get_detailed_metrics(repo_path, exclude_third_party=True, exclude_tests=True):
    """
    Get detailed code metrics including function count, max complexity, etc.
    This now returns the FULL analysis results, including complex functions.
    """
    # This function now returns the entire dictionary from analyze_functions,
    # which includes the new "complex_functions" list.
    return analyze_functions(repo_path, exclude_third_party, exclude_tests)