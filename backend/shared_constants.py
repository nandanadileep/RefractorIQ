FUNCTION_NODE_TYPES = [
    'function_definition',      # Python functions
    'function_declaration',     # JS/TS function declarations
    'method_definition',        # Python/JS class methods
    'arrow_function',          # JS/TS arrow functions
    'method_declaration',      # Java methods
    'constructor_declaration', # Java constructors
    'function',               # Generic function node
    'method'                  # Generic method node
]

COMPLEXITY_THRESHOLDS = {
    'low': (1, 5),
    'medium': (6, 10),
    'high': (11, 20),
    'very_high': (21, float('inf'))
}

# Decision nodes that increase cyclomatic complexity
DECISION_NODE_TYPES = {
    'if_statement', 'elif_clause', 'else_clause',
    'for_statement', 'while_statement',
    'except_clause', 'case_statement', 'switch_statement',
    'conditional_expression', 'ternary_expression',
    'catch_clause', 'finally_clause',
    'boolean_operator', 'binary_expression'
}


