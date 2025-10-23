import os
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_java as tsjava

# Initialize language objects
PY_LANGUAGE = Language(tspython.language())
JS_LANGUAGE = Language(tsjavascript.language())
JAVA_LANGUAGE = Language(tsjava.language())

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

def count_todos(repo_path):
    """Count TODO, FIXME, HACK comments using AST parsing"""
    todos = 0
    for root, _, files in os.walk(repo_path):
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in [".py", ".js", ".ts", ".java"]:
                filepath = os.path.join(root, file)
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

def count_loc(repo_path):
    """Count lines of code (excluding comments and blank lines) using AST"""
    loc = 0
    for root, _, files in os.walk(repo_path):
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in [".py", ".js", ".ts", ".java"]:
                filepath = os.path.join(root, file)
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
    
    # Decision nodes that increase complexity
    decision_nodes = {
        'if_statement', 'elif_clause', 'else_clause',
        'for_statement', 'while_statement',
        'except_clause', 'case_statement', 'switch_statement',
        'conditional_expression', 'ternary_expression',
        'catch_clause', 'finally_clause',
        'boolean_operator', 'binary_expression'
    }
    
    def traverse(n):
        nonlocal complexity
        if n.type in decision_nodes:
            # For boolean operators, check if it's actually 'and'/'or' or '&&'/'||'
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

def analyze_functions(repo_path):
    """Analyze all functions in the repository - single pass for efficiency"""
    results = {
        "complexities": [],
        "total_functions": 0,
        "max_complexity": 0,
        "min_complexity": float('inf'),
        "files_analyzed": 0,
        "complexity_distribution": {
            "low": 0,      # 1-5
            "medium": 0,   # 6-10
            "high": 0,     # 11-20
            "very_high": 0 # 21+
        }
    }
    
    for root, _, files in os.walk(repo_path):
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in [".py", ".js", ".ts", ".java"]:
                filepath = os.path.join(root, file)
                parser, language = get_parser_and_language(ext)
                
                if not parser:
                    continue
                
                try:
                    with open(filepath, "rb") as f:
                        content = f.read()
                    
                    tree = parser.parse(content)
                    results["files_analyzed"] += 1
                    
                    # Find all function-like nodes by traversing the tree
                    def find_functions(node):
                        functions = []
                        # Check if current node is a function
                        if node.type in ['function_definition', 'function_declaration', 
                                       'method_definition', 'arrow_function',
                                       'method_declaration', 'constructor_declaration',
                                       'function', 'method']:
                            functions.append(node)
                        
                        # Recursively check children
                        for child in node.children:
                            functions.extend(find_functions(child))
                        
                        return functions
                    
                    function_nodes = find_functions(tree.root_node)
                    
                    for node in function_nodes:
                        results["total_functions"] += 1
                        complexity = calculate_cyclomatic_complexity(node, content)
                        results["complexities"].append(complexity)
                        results["max_complexity"] = max(results["max_complexity"], complexity)
                        if complexity > 0:
                            results["min_complexity"] = min(results["min_complexity"], complexity)
                        
                        # Categorize complexity
                        if complexity <= 5:
                            results["complexity_distribution"]["low"] += 1
                        elif complexity <= 10:
                            results["complexity_distribution"]["medium"] += 1
                        elif complexity <= 20:
                            results["complexity_distribution"]["high"] += 1
                        else:
                            results["complexity_distribution"]["very_high"] += 1
                        
                except Exception as e:
                    pass  # Skip files that can't be parsed
    
    if results["min_complexity"] == float('inf'):
        results["min_complexity"] = 0
    
    return results

def avg_cyclomatic_complexity(repo_path):
    """Calculate average cyclomatic complexity using AST parsing"""
    results = analyze_functions(repo_path)
    if results["complexities"]:
        return round(sum(results["complexities"]) / len(results["complexities"]), 2)
    return 0

def simple_debt_score(loc, todos, complexity):
    """Calculate technical debt score"""
    return round((todos * 5 + complexity * 2 + loc / 1000), 2)

def get_detailed_metrics(repo_path):
    """Get detailed code metrics including function count, max complexity, etc."""
    results = analyze_functions(repo_path)
    return {
        "total_functions": results["total_functions"],
        "max_complexity": results["max_complexity"],
        "min_complexity": results["min_complexity"],
        "files_analyzed": results["files_analyzed"],
        "complexity_distribution": results["complexity_distribution"]
    }

