# RefractorIQ/backend/dependency_analysis.py

import os
import re
import networkx as nx
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_java as tsjava
from collections import defaultdict
from .shared_constants import FUNCTION_NODE_TYPES
from networkx.readwrite import json_graph
# Initialize language objects
PY_LANGUAGE = Language(tspython.language())
JS_LANGUAGE = Language(tsjavascript.language())
JAVA_LANGUAGE = Language(tsjava.language())

# Common third-party library directories to exclude
THIRD_PARTY_DIRS = {
    'node_modules', 'venv', 'env', '.env', 'virtualenv', 'site-packages',
    'dist-packages', '__pycache__', '.venv', 'vendor', 'bower_components',
    'target', 'build', 'dist', '.gradle', 'lib', 'libs', 'packages',
}

# Regex patterns for matching common test file paths
TEST_FILE_PATTERNS = [
    re.compile(r'__tests__/'),
    # --- Corrected Regex ---
    re.compile(r'(^|/)tests?/'), # Matches test/ or tests/ at start or after /
    re.compile(r'test_.*\.py$'),
    re.compile(r'.*_test\.py$'),
    re.compile(r'\.spec\.(js|ts)$'),
    re.compile(r'\.test\.(js|ts)$'),
    re.compile(r'Test.*\.java$'),
    re.compile(r'.*Test\.java$'),
    re.compile(r'src/test/java/'),
]

def is_third_party_file(filepath, repo_path):
    """Check if a file is in a third-party directory"""
    try:
        rel_path = os.path.relpath(filepath, repo_path)
        path_parts = rel_path.split(os.sep)
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
        # print(f"Checking test path: {rel_path}") # Optional logging
        for pattern in TEST_FILE_PATTERNS:
            if pattern.search(rel_path):
                # print(f"  MATCHED by pattern: {pattern.pattern}") # Optional logging
                return True
        # print("  NO MATCH") # Optional logging
        return False
    except Exception as e:
        # print(f"  Error checking test path: {e}") # Optional logging
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

def extract_python_imports(tree, content):
    """Extract import statements from Python code"""
    # --- (Function unchanged) ---
    imports = []
    def traverse(node):
        if node.type == 'import_statement':
            for child in node.children:
                if child.type == 'dotted_name':
                    module = content[child.start_byte:child.end_byte].decode('utf-8', errors='ignore')
                    imports.append({'type': 'import', 'module': module, 'items': []})
        elif node.type == 'import_from_statement':
            module = None; items = []
            for child in node.children:
                if child.type == 'dotted_name': module = content[child.start_byte:child.end_byte].decode('utf-8', errors='ignore')
                elif child.type == 'import_prefix': module = content[child.start_byte:child.end_byte].decode('utf-8', errors='ignore')
                elif child.type in ['dotted_name', 'identifier', 'aliased_import']:
                    item = content[child.start_byte:child.end_byte].decode('utf-8', errors='ignore')
                    if 'import' not in item and 'from' not in item: items.append(item)
            if module: imports.append({'type': 'from_import', 'module': module, 'items': items})
        for child in node.children: traverse(child)
    traverse(tree.root_node); return imports

def extract_javascript_imports(tree, content):
    """Extract import/require statements from JavaScript/TypeScript code"""
    # --- (Function unchanged) ---
    imports = []
    def traverse(node):
        if node.type == 'import_statement':
            module = None; items = []
            for child in node.children:
                if child.type == 'string': module = content[child.start_byte:child.end_byte].decode('utf-8', errors='ignore').strip('"\'')
                elif child.type == 'import_clause': text = content[child.start_byte:child.end_byte].decode('utf-8', errors='ignore'); items.append(text)
            if module: imports.append({'type': 'import', 'module': module, 'items': items})
        elif node.type == 'call_expression':
            func_name = None; module = None
            for child in node.children:
                if child.type == 'identifier': func_name = content[child.start_byte:child.end_byte].decode('utf-8', errors='ignore')
                elif child.type == 'arguments':
                    for arg in child.children:
                        if arg.type == 'string': module = content[arg.start_byte:arg.end_byte].decode('utf-8', errors='ignore').strip('"\'')
            if func_name == 'require' and module: imports.append({'type': 'require', 'module': module, 'items': []})
        for child in node.children: traverse(child)
    traverse(tree.root_node); return imports

def extract_java_imports(tree, content):
    """Extract import statements from Java code"""
    # --- (Function unchanged) ---
    imports = []
    def traverse(node):
        if node.type == 'import_declaration':
            import_text = content[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
            import_text = import_text.replace('import', '').replace(';', '').strip()
            imports.append({'type': 'import', 'module': import_text, 'items': []})
        for child in node.children: traverse(child)
    traverse(tree.root_node); return imports

def extract_functions_and_classes(tree, content, language_type):
    """Extract function and class definitions using shared FUNCTION_NODE_TYPES constant"""
    # --- (Function unchanged) ---
    entities = {'functions': [], 'classes': []}
    def traverse(node):
        if node.type in FUNCTION_NODE_TYPES:
            name = None
            for child in node.children:
                if child.type in ['identifier', 'property_identifier']:
                    name = content[child.start_byte:child.end_byte].decode('utf-8', errors='ignore'); break
            if name: entities['functions'].append(name)
        elif node.type in ['class_definition', 'class_declaration']:
            name = None
            for child in node.children:
                if child.type == 'identifier':
                    name = content[child.start_byte:child.end_byte].decode('utf-8', errors='ignore'); break
            if name: entities['classes'].append(name)
        for child in node.children: traverse(child)
    traverse(tree.root_node); return entities

def export_graph_data(repo_path, format='json', exclude_third_party=True, exclude_tests=True):
    """Export graph in various formats for visualization"""

    # --- Ensure build_dependency_graph is called correctly ---
    G, file_data = build_dependency_graph(repo_path, exclude_tests=exclude_tests)

    if exclude_third_party:
        external_nodes = [node for node in G.nodes() if G.nodes[node].get('type') == 'external']
        G.remove_nodes_from(external_nodes)

    if format == 'json':
        # --- THIS IS THE CORRECTED LINE ---
        # Call node_link_data with only the graph G.
        # It should use default keys ('source', 'target', 'id', 'links').
        return json_graph.node_link_data(G)
        # --- END CORRECTION ---

    elif format == 'gexf':
        # GEXF generation remains the same
        fd, path = tempfile.mkstemp(suffix='.gexf')
        nx.write_gexf(G, path)
        data = ""
        try:
            with open(path, 'r') as f:
                data = f.read()
        finally:
            os.close(fd)
            os.unlink(path)
        return data
    else:
        return None

# --- MODIFIED: Restored exclude_tests parameter and the check ---
def build_dependency_graph(repo_path, exclude_tests=True):
    """Build a comprehensive dependency graph using networkx, respecting the exclude_tests flag."""
    G = nx.DiGraph()
    file_data = {}

    # First pass: collect all files and their entities
    for root, _, files in os.walk(repo_path):
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in [".py", ".js", ".ts", ".java"]:
                filepath = os.path.join(root, file)

                # Always skip third-party directories for graph *building*
                if is_third_party_file(filepath, repo_path):
                    continue

                # --- RESTORED THE CHECK FOR is_test_file ---
                if exclude_tests and is_test_file(filepath, repo_path):
                    continue
                # --- END RESTORED CHECK ---

                rel_path = os.path.relpath(filepath, repo_path).replace(os.sep, '/') # Use forward slash

                parser, language = get_parser_and_language(ext)
                if not parser:
                    continue

                try:
                    with open(filepath, "rb") as f:
                        content = f.read()

                    tree = parser.parse(content)

                    # Extract imports based on language
                    if ext == ".py": imports = extract_python_imports(tree, content)
                    elif ext in [".js", ".ts"]: imports = extract_javascript_imports(tree, content)
                    elif ext == ".java": imports = extract_java_imports(tree, content)
                    else: imports = []

                    # Extract functions and classes
                    entities = extract_functions_and_classes(tree, content, ext)

                    # Add file node to graph
                    G.add_node(rel_path, type='file', language=ext)

                    file_data[rel_path] = {
                        'imports': imports,
                        'functions': entities['functions'],
                        'classes': entities['classes']
                    }

                    # Add entity nodes
                    for func in entities['functions']:
                        node_id = f"{rel_path}::{func}"
                        G.add_node(node_id, type='function', name=func, file=rel_path)
                        G.add_edge(rel_path, node_id, relationship='defines')

                    for cls in entities['classes']:
                        node_id = f"{rel_path}::{cls}"
                        G.add_node(node_id, type='class', name=cls, file=rel_path)
                        G.add_edge(rel_path, node_id, relationship='defines')

                except Exception as e:
                    print(f"Error processing file {rel_path} for graph: {e}")

    # Second pass: build dependency edges
    # --- (This part remains unchanged) ---
    for file_path, data in file_data.items():
        for import_info in data['imports']:
            module = import_info['module']
            resolved = False
            potential_relative_path = None
            if module.startswith('.'):
                 current_dir = os.path.dirname(file_path)
                 potential_relative_path = os.path.normpath(os.path.join(current_dir, module)).replace(os.sep, '/')

            for potential_file in file_data.keys():
                match = False
                potential_file_base = os.path.splitext(potential_file)[0]
                module_as_path = module.replace('.', '/')

                if potential_file == module: match = True
                elif potential_file_base == module: match = True
                elif potential_file.endswith(module_as_path + '.js'): match = True
                elif potential_file.endswith(module_as_path + '.ts'): match = True
                elif potential_file.endswith(module_as_path + '.py'): match = True
                elif potential_file.endswith(module_as_path + '.java'): match = True
                elif potential_file_base.endswith('/' + module_as_path): match = True
                elif potential_relative_path and (potential_file == potential_relative_path or potential_file_base == potential_relative_path): match = True

                if match:
                    G.add_edge(file_path, potential_file, relationship='imports', module=module)
                    resolved = True
                    break

            if not resolved:
                ext_node = f"external::{module}"
                if not G.has_node(ext_node):
                    G.add_node(ext_node, type='external', module=module)
                G.add_edge(file_path, ext_node, relationship='imports', module=module)

    return G, file_data

# --- MODIFIED: Restored exclude_tests parameter ---
def analyze_dependencies(repo_path, exclude_third_party=True, exclude_tests=True):
    """Analyze dependencies and return metrics"""

    # --- MODIFIED: Pass exclude_tests to build_dependency_graph ---
    G, file_data = build_dependency_graph(repo_path, exclude_tests=exclude_tests)

    # --- (Rest of the function is unchanged) ---
    external_nodes = [node for node in G.nodes() if G.nodes[node].get('type') == 'external']
    total_external = len(external_nodes)
    if exclude_third_party: G.remove_nodes_from(external_nodes); total_external = 0

    total_files = sum(1 for node in G.nodes() if G.nodes[node].get('type') == 'file')
    total_functions = sum(1 for node in G.nodes() if G.nodes[node].get('type') == 'function')
    total_classes = sum(1 for node in G.nodes() if G.nodes[node].get('type') == 'class')

    file_nodes = [node for node in G.nodes() if G.nodes[node].get('type') == 'file']
    most_dependent = []; most_depended_on = []
    if file_nodes:
        in_degrees = {node: G.in_degree(node) for node in file_nodes}
        out_degrees = {node: G.out_degree(node) for node in file_nodes}
        most_dependent = sorted(out_degrees.items(), key=lambda x: x[1], reverse=True)[:5]
        most_depended_on = sorted(in_degrees.items(), key=lambda x: x[1], reverse=True)[:5]

    try: cycles = list(nx.simple_cycles(G)); file_cycles = [cycle for cycle in cycles if all(G.nodes[node].get('type') == 'file' for node in cycle)]
    except: file_cycles = []

    try: avg_degree = sum(dict(G.degree()).values()) / len(G.nodes()) if G.nodes() else 0
    except: avg_degree = 0

    return {
        "total_files": total_files, "total_functions": total_functions, "total_classes": total_classes,
        "total_external_dependencies": total_external, "total_edges": G.number_of_edges(),
        "average_connections_per_node": round(avg_degree, 2),
        "most_dependent_files": [{"file": f, "dependencies": d} for f, d in most_dependent],
        "most_depended_on_files": [{"file": f, "dependents": d} for f, d in most_depended_on],
        "circular_dependencies": len(file_cycles),
        "circular_dependency_chains": file_cycles[:10] if file_cycles else [],
        "graph_density": round(nx.density(G), 4) if G.nodes() else 0
    }


# --- MODIFIED: Restored exclude_tests parameter ---
def get_file_dependencies(repo_path, file_path, exclude_third_party=True, exclude_tests=True):
    """Get detailed dependencies for a specific file"""

    # --- MODIFIED: Pass exclude_tests to build_dependency_graph ---
    G, file_data = build_dependency_graph(repo_path, exclude_tests=exclude_tests)

    # --- (Rest of the function is unchanged) ---
    if exclude_third_party:
        external_nodes = [node for node in G.nodes() if G.nodes[node].get('type') == 'external']
        G.remove_nodes_from(external_nodes)

    if file_path not in file_data: return None

    dependencies = []
    for target in G.successors(file_path):
        edge_data = G.get_edge_data(file_path, target)
        dependencies.append({ "target": target, "type": G.nodes[target].get('type'), "relationship": edge_data.get('relationship')})

    dependents = []
    for source in G.predecessors(file_path):
        edge_data = G.get_edge_data(source, file_path)
        dependents.append({ "source": source, "type": G.nodes[source].get('type'), "relationship": edge_data.get('relationship')})

    return {
        "file": file_path, "imports": file_data[file_path]['imports'],
        "functions": file_data[file_path]['functions'], "classes": file_data[file_path]['classes'],
        "dependencies": dependencies, "dependents": dependents
    }

