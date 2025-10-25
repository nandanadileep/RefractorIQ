from fastapi import FastAPI, Request, Query
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from analysis import (
    count_loc, 
    count_todos, 
    avg_cyclomatic_complexity, 
    simple_debt_score,
    get_detailed_metrics
)
from dependency_analysis import (
    analyze_dependencies,
    get_file_dependencies,
    export_graph_data
)
# --- NEW IMPORT ---
from deduplication import analyze_duplicates_minhash
import os
import requests
import tempfile
import git
import shutil
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
BACKEND_URL = os.getenv("BACKEND_URL")
GITHUB_PAT = os.getenv("GITHUB_PAT")
REPO_TO_ANALYZE = os.getenv("REPO_TO_ANALYZE", "https://github.com/emcie-co/parlant.git")

# Cache for temporary directories
_repo_cache = {}

# Create FastAPI app ONCE
app = FastAPI()

# Configure CORS - allow your frontend origin
origins = [
    "https://fluffy-fortnight-pjr95546qg936qrg-3000.app.github.dev",
    "http://localhost:3000",
    "*"  # Allow all origins during development (remove in production)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_or_clone_repo(repo_url: str = None):
    """Clone repo or return cached directory"""
    target_repo = repo_url if repo_url else REPO_TO_ANALYZE
    
    if target_repo in _repo_cache:
        return _repo_cache[target_repo]
    
    tmpdir = tempfile.mkdtemp()
    
    # Prepare repo URL with authentication if needed
    if GITHUB_PAT and target_repo.startswith("https://github.com/"):
        clone_url = target_repo.replace(
            "https://github.com/",
            f"https://x-access-token:{GITHUB_PAT}@github.com/"
        )
    else:
        clone_url = target_repo
    
    # Clone the repo
    try:
        git.Repo.clone_from(clone_url, tmpdir)
        _repo_cache[target_repo] = tmpdir
        return tmpdir
    except Exception as e:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise Exception(f"Failed to clone repo: {str(e)}")

# ---------------- OAuth ---------------- #
@app.get("/login")
def login():
    github_oauth_url = f"https://github.com/login/oauth/authorize?client_id={CLIENT_ID}&scope=repo"
    return RedirectResponse(github_oauth_url)

@app.get("/callback")
def callback(code: str):
    # Exchange code for access token
    token_url = "https://github.com/login/oauth/access_token"
    res = requests.post(
        token_url,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "redirect_uri": f"{BACKEND_URL}/callback"
        },
        headers={"Accept": "application/json"}
    )
    access_token = res.json().get("access_token")
    return JSONResponse({"access_token": access_token})

# --- UPDATED ---
@app.get("/analyze")
def analyze(
    repo_url: str = None, 
    debug: bool = False,
    exclude_third_party: bool = Query(True, description="Exclude third-party libraries from analysis"),
    exclude_tests: bool = Query(True, description="Exclude test files from analysis") # --- NEW ---
):
    """
    Analyze a GitHub repository using Tree-sitter AST parsing
    Query params: 
        - repo_url (optional): if not provided, uses REPO_TO_ANALYZE from env
        - debug (optional): if true, includes additional debug information
        - exclude_third_party (optional): if true, excludes node_modules, venv, etc.
        - exclude_tests (optional): if true, excludes test files
    """
    tmpdir = None
    cleanup = True
    
    try:
        # Use provided repo_url or fall back to env variable
        target_repo = repo_url if repo_url else REPO_TO_ANALYZE
        tmpdir = get_or_clone_repo(target_repo)
        cleanup = False  # Don't cleanup if using cache
        
        # Compute metrics using Tree-sitter
        loc = count_loc(tmpdir, exclude_third_party, exclude_tests)
        todos = count_todos(tmpdir, exclude_third_party, exclude_tests)
        complexity = avg_cyclomatic_complexity(tmpdir, exclude_third_party, exclude_tests)
        debt = simple_debt_score(loc, todos, complexity)
        detailed = get_detailed_metrics(tmpdir, exclude_third_party, exclude_tests)
        
        response = {
            "repository": target_repo,
            "metrics": {
                "LOC": loc,
                "TODOs_FIXME_HACK": todos,
                "AvgCyclomaticComplexity": complexity,
                "DebtScore": debt,
                "TotalFunctions": detailed["total_functions"],
                "MaxComplexity": detailed["max_complexity"],
                "MinComplexity": detailed["min_complexity"],
                "FilesAnalyzed": detailed["files_analyzed"],
                "ComplexityDistribution": detailed["complexity_distribution"]
            },
            "analysis_method": "Tree-sitter AST parsing",
            "excluded_third_party": exclude_third_party,
            "excluded_tests": exclude_tests # --- NEW ---
        }
        
        if debug:
            # Add debug info
            response["debug"] = {
                "temp_dir": tmpdir,
                "note": "Check logs for parsing errors"
            }
        
        return JSONResponse(response)
    
    except Exception as e:
        if tmpdir and cleanup:
            shutil.rmtree(tmpdir, ignore_errors=True)
        return JSONResponse(
            {"error": f"Analysis failed: {str(e)}"}, 
            status_code=500
        )

# --- UPDATED ---
@app.get("/analyze/dependencies")
def analyze_deps(
    repo_url: str = None,
    exclude_third_party: bool = Query(True, description="Exclude third-party libraries from analysis"),
    exclude_tests: bool = Query(True, description="Exclude test files from analysis") # --- NEW ---
):
    """
    Analyze repository dependencies and return dependency graph metrics
    Query params: 
        - repo_url (optional): if not provided, uses REPO_TO_ANALYZE from env
        - exclude_third_party (optional): if true, excludes node_modules, venv, etc.
        - exclude_tests (optional): if true, excludes test files
    """
    try:
        target_repo = repo_url if repo_url else REPO_TO_ANALYZE
        tmpdir = get_or_clone_repo(target_repo)
        
        # Analyze dependencies
        dep_metrics = analyze_dependencies(tmpdir, exclude_third_party, exclude_tests)
        
        response = {
            "repository": target_repo,
            "dependency_metrics": dep_metrics,
            "analysis_method": "NetworkX graph analysis with Tree-sitter",
            "excluded_third_party": exclude_third_party,
            "excluded_tests": exclude_tests # --- NEW ---
        }
        
        return JSONResponse(response)
    
    except Exception as e:
        return JSONResponse(
            {"error": f"Dependency analysis failed: {str(e)}"}, 
            status_code=500
        )

# --- UPDATED ---
@app.get("/analyze/file-dependencies")
def file_deps(
    file_path: str = Query(..., description="Relative path to file in repository"),
    repo_url: str = None,
    exclude_third_party: bool = Query(True, description="Exclude third-party libraries from analysis"),
    exclude_tests: bool = Query(True, description="Exclude test files from analysis") # --- NEW ---
):
    """
    Get detailed dependency information for a specific file
    Query params:
        - file_path (required): Relative path to the file (e.g., 'src/main.py')
        - repo_url (optional): if not provided, uses REPO_TO_ANALYZE from env
        - exclude_third_party (optional): if true, excludes node_modules, venv, etc.
        - exclude_tests (optional): if true, excludes test files
    """
    try:
        target_repo = repo_url if repo_url else REPO_TO_ANALYZE
        tmpdir = get_or_clone_repo(target_repo)
        
        # Get file dependencies
        file_dep_data = get_file_dependencies(tmpdir, file_path, exclude_third_party, exclude_tests)
        
        if file_dep_data is None:
            return JSONResponse(
                {"error": f"File not found: {file_path}"}, 
                status_code=404
            )
        
        response = {
            "repository": target_repo,
            "file_dependencies": file_dep_data,
            "analysis_method": "Tree-sitter + NetworkX",
            "excluded_third_party": exclude_third_party,
            "excluded_tests": exclude_tests # --- NEW ---
        }
        
        return JSONResponse(response)
    
    except Exception as e:
        return JSONResponse(
            {"error": f"File dependency analysis failed: {str(e)}"}, 
            status_code=500
        )

# --- UPDATED ---
@app.get("/analyze/dependency-graph")
def dependency_graph(
    repo_url: str = None,
    format: str = Query("json", description="Export format: 'json' or 'gexf'"),
    exclude_third_party: bool = Query(True, description="Exclude third-party libraries from analysis"),
    exclude_tests: bool = Query(True, description="Exclude test files from analysis") # --- NEW ---
):
    """
    Export the complete dependency graph for visualization
    Query params:
        - repo_url (optional): if not provided, uses REPO_TO_ANALYZE from env
        - format (optional): 'json' (default) for JSON format, 'gexf' for Gephi format
        - exclude_third_party (optional): if true, excludes node_modules, venv, etc.
        - exclude_tests (optional): if true, excludes test files
    """
    try:
        target_repo = repo_url if repo_url else REPO_TO_ANALYZE
        tmpdir = get_or_clone_repo(target_repo)
        
        # Export graph data
        graph_data = export_graph_data(tmpdir, format, exclude_third_party, exclude_tests)
        
        if graph_data is None:
            return JSONResponse(
                {"error": f"Unsupported format: {format}"}, 
                status_code=400
            )
        
        if format == 'gexf':
            from fastapi.responses import Response
            return Response(
                content=graph_data,
                media_type="application/xml",
                headers={"Content-Disposition": "attachment; filename=dependency_graph.gexf"}
            )
        
        response = {
            "repository": target_repo,
            "graph": graph_data,
            "format": format,
            "excluded_third_party": exclude_third_party,
            "excluded_tests": exclude_tests # --- NEW ---
        }
        
        return JSONResponse(response)
    
    except Exception as e:
        return JSONResponse(
            {"error": f"Graph export failed: {str(e)}"}, 
            status_code=500
        )

# --- NEW ENDPOINT ---
@app.get("/analyze/duplicates")
def analyze_duplication(
    repo_url: str = None,
    threshold: float = Query(0.85, description="Jaccard similarity threshold (0.0 to 1.0)"),
    exclude_third_party: bool = Query(True, description="Exclude third-party libraries"),
    exclude_tests: bool = Query(True, description="Exclude test files")
):
    """
    Analyze code duplication using MinHash + LSH
    Query params:
        - repo_url (optional): if not provided, uses REPO_TO_ANALYZE from env
        - threshold (optional): Similarity threshold, default 0.85
        - exclude_third_party (optional): if true, excludes node_modules, venv, etc.
        - exclude_tests (optional): if true, excludes test files
    """
    try:
        target_repo = repo_url if repo_url else REPO_TO_ANALYZE
        tmpdir = get_or_clone_repo(target_repo)
        
        # Run deduplication analysis
        duplication_metrics = analyze_duplicates_minhash(
            tmpdir, 
            exclude_third_party, 
            exclude_tests,
            threshold=threshold
        )
        
        response = {
            "repository": target_repo,
            "duplication_metrics": duplication_metrics,
            "analysis_method": "MinHash + LSH (datasketch)",
            "excluded_third_party": exclude_third_party,
            "excluded_tests": exclude_tests
        }
        
        return JSONResponse(response)
    
    except Exception as e:
        return JSONResponse(
            {"error": f"Duplication analysis failed: {str(e)}"}, 
            status_code=500
        )

# --- UPDATED ---
@app.get("/analyze/full")
def full_analysis(
    repo_url: str = None,
    exclude_third_party: bool = Query(True, description="Exclude third-party libraries from analysis"),
    exclude_tests: bool = Query(True, description="Exclude test files from analysis") # --- NEW ---
):
    """
    Perform complete analysis including code metrics and dependencies
    Query params:
        - repo_url (optional): if not provided, uses REPO_TO_ANALYZE from env
        - exclude_third_party (optional): if true, excludes node_modules, venv, etc.
        - exclude_tests (optional): if true, excludes test files
    """
    try:
        target_repo = repo_url if repo_url else REPO_TO_ANALYZE
        tmpdir = get_or_clone_repo(target_repo)
        
        # Code metrics with error handling
        try:
            loc = count_loc(tmpdir, exclude_third_party, exclude_tests)
        except Exception as e:
            print(f"Error in count_loc: {str(e)}")
            loc = 0
            
        try:
            todos = count_todos(tmpdir, exclude_third_party, exclude_tests)
        except Exception as e:
            print(f"Error in count_todos: {str(e)}")
            todos = 0
            
        try:
            complexity = avg_cyclomatic_complexity(tmpdir, exclude_third_party, exclude_tests)
        except Exception as e:
            print(f"Error in avg_cyclomatic_complexity: {str(e)}")
            complexity = 0
            
        debt = simple_debt_score(loc, todos, complexity)
        
        try:
            detailed = get_detailed_metrics(tmpdir, exclude_third_party, exclude_tests)
        except Exception as e:
            print(f"Error in get_detailed_metrics: {str(e)}")
            detailed = {
                "total_functions": 0,
                "max_complexity": 0,
                "min_complexity": 0,
                "files_analyzed": 0,
                "complexity_distribution": {
                    "low": 0,
                    "medium": 0,
                    "high": 0,
                    "very_high": 0
                }
            }
        
        # Dependency metrics with error handling
        try:
            dep_metrics = analyze_dependencies(tmpdir, exclude_third_party, exclude_tests)
        except Exception as e:
            print(f"Error in analyze_dependencies: {str(e)}")
            dep_metrics = {
                "total_files": 0,
                "total_functions": 0,
                "total_classes": 0,
                "total_external_dependencies": 0,
                "total_edges": 0,
                "average_connections_per_node": 0,
                "most_dependent_files": [],
                "most_depended_on_files": [],
                "circular_dependencies": 0,
                "circular_dependency_chains": [],
                "graph_density": 0
            }

        # --- NEW: Add duplication analysis ---
        try:
            duplication_metrics = analyze_duplicates_minhash(
                tmpdir, 
                exclude_third_party, 
                exclude_tests
            )
        except Exception as e:
            print(f"Error in analyze_duplicates_minhash: {str(e)}")
            duplication_metrics = {"error": str(e)}
        
        response = {
            "repository": target_repo,
            "code_metrics": {
                "LOC": loc,
                "TODOs_FIXME_HACK": todos,
                "AvgCyclomaticComplexity": complexity,
                "DebtScore": debt,
                "TotalFunctions": detailed["total_functions"],
                "MaxComplexity": detailed["max_complexity"],
                "MinComplexity": detailed["min_complexity"],
                "FilesAnalyzed": detailed["files_analyzed"],
                "ComplexityDistribution": detailed["complexity_distribution"]
            },
            "dependency_metrics": dep_metrics,
            # --- NEW ---
            "duplication_metrics": duplication_metrics,
            "analysis_method": "Tree-sitter AST + NetworkX + MinHash",
            "excluded_third_party": exclude_third_party,
            "excluded_tests": exclude_tests # --- NEW ---
        }
        
        return JSONResponse(response)
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Full analysis failed: {error_details}")
        return JSONResponse(
            {"error": f"Full analysis failed: {str(e)}", "details": error_details}, 
            status_code=500
        )

@app.post("/cleanup-cache")
def cleanup_cache():
    """Clean up cached repository directories"""
    global _repo_cache
    for tmpdir in _repo_cache.values():
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass
    _repo_cache.clear()
    return JSONResponse({"message": "Cache cleaned successfully"})

@app.get("/health")
def health():
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy", 
        "parser": "tree-sitter",
        "dependency_analysis": "networkx",
        "cached_repos": len(_repo_cache)
    })

@app.get("/")
def root():
    """Root endpoint with API information"""
    return JSONResponse({
        "message": "Code Analysis API with Tree-sitter and NetworkX",
        "endpoints": {
            "/analyze": "Analyze code metrics (LOC, complexity, TODOs)",
            "/analyze/dependencies": "Analyze repository dependency graph",
            "/analyze/file-dependencies": "Get dependencies for a specific file (requires file_path param)",
            "/analyze/dependency-graph": "Export dependency graph (supports 'json' or 'gexf' format)",
            "/analyze/duplicates": "Analyze code duplication", # <-- ADDED
            "/analyze/full": "Complete analysis with code, deps, and duplication", # <-- UPDATED
            "/cleanup-cache": "Clean up cached repositories (POST)",
            "/login": "GitHub OAuth login",
            "/callback": "GitHub OAuth callback",
            "/health": "Health check"
        }
    })

