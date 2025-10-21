import os
import subprocess
from radon.complexity import cc_visit

def count_todos(repo_path):
    todos = 0
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith((".py", ".js", ".ts", ".java")):
                with open(os.path.join(root, file), "r", errors="ignore") as f:
                    for line in f:
                        if any(x in line for x in ["TODO", "FIXME", "HACK"]):
                            todos += 1
    return todos

def count_loc(repo_path):
    loc = 0
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith((".py", ".js", ".ts", ".java")):
                with open(os.path.join(root, file), "r", errors="ignore") as f:
                    loc += sum(1 for _ in f)
    return loc

def avg_cyclomatic_complexity(repo_path):
    cc_scores = []
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith((".py", ".js", ".ts", ".java")):
                with open(os.path.join(root, file), "r", errors="ignore") as f:
                    code = f.read()
                    try:
                        cc_results = cc_visit(code)
                        cc_scores.extend([c.complexity for c in cc_results])
                    except Exception:
                        pass
    if cc_scores:
        return sum(cc_scores)/len(cc_scores)
    return 0

def simple_debt_score(loc, todos, complexity):
    return round((todos * 5 + complexity * 2 + loc / 1000), 2)
