from fastapi import FastAPI, Request, Query
from fastapi.responses import RedirectResponse, JSONResponse
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
GITHUB_PAT = os.getenv("GITHUB_PAT")  # Optional, for private repos
REPO_TO_ANALYZE = os.getenv("REPO_TO_ANALYZE", "https://github.com/emcie-co/parlant.git")

# Cache for temporary directories (to avoid re-cloning for multiple endpoints)
_repo_cache = {}


from fastapi.middleware.cors import CORSMiddleware

# Add this right after creating the FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
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

@app.get("/analyze")
def analyze(repo_url: str = None, debug: bool = False):
    """
    Analyze a GitHub repository using Tree-sitter AST parsing
    Query params: 
        - repo_url (optional): if not provided, uses REPO_TO_ANALYZE from env
        - debug (optional): if true, includes additional debug information
    """
    tmpdir = None
    cleanup = True
    
    try:
        # Use provided repo_url or fall back to env variable
        target_repo = repo_url if repo_url else REPO_TO_ANALYZE
        tmpdir = get_or_clone_repo(target_repo)
        cleanup = False  # Don't cleanup if using cache
        
        # Compute metrics using Tree-sitter
        loc = count_loc(tmpdir)
        todos = count_todos(tmpdir)
        complexity = avg_cyclomatic_complexity(tmpdir)
        debt = simple_debt_score(loc, todos, complexity)
        detailed = get_detailed_metrics(tmpdir)
        
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
            "analysis_method": "Tree-sitter AST parsing"
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

@app.get("/analyze/dependencies")
def analyze_deps(repo_url: str = None):
    """
    Analyze repository dependencies and return dependency graph metrics
    Query params: 
        - repo_url (optional): if not provided, uses REPO_TO_ANALYZE from env
    """
    try:
        target_repo = repo_url if repo_url else REPO_TO_ANALYZE
        tmpdir = get_or_clone_repo(target_repo)
        
        # Analyze dependencies
        dep_metrics = analyze_dependencies(tmpdir)
        
        response = {
            "repository": target_repo,
            "dependency_metrics": dep_metrics,
            "analysis_method": "NetworkX graph analysis with Tree-sitter"
        }
        
        return JSONResponse(response)
    
    except Exception as e:
        return JSONResponse(
            {"error": f"Dependency analysis failed: {str(e)}"}, 
            status_code=500
        )

@app.get("/analyze/file-dependencies")
def file_deps(
    file_path: str = Query(..., description="Relative path to file in repository"),
    repo_url: str = None
):
    """
    Get detailed dependency information for a specific file
    Query params:
        - file_path (required): Relative path to the file (e.g., 'src/main.py')
        - repo_url (optional): if not provided, uses REPO_TO_ANALYZE from env
    """
    try:
        target_repo = repo_url if repo_url else REPO_TO_ANALYZE
        tmpdir = get_or_clone_repo(target_repo)
        
        # Get file dependencies
        file_dep_data = get_file_dependencies(tmpdir, file_path)
        
        if file_dep_data is None:
            return JSONResponse(
                {"error": f"File not found: {file_path}"}, 
                status_code=404
            )
        
        response = {
            "repository": target_repo,
            "file_dependencies": file_dep_data,
            "analysis_method": "Tree-sitter + NetworkX"
        }
        
        return JSONResponse(response)
    
    except Exception as e:
        return JSONResponse(
            {"error": f"File dependency analysis failed: {str(e)}"}, 
            status_code=500
        )

@app.get("/analyze/dependency-graph")
def dependency_graph(
    repo_url: str = None,
    format: str = Query("json", description="Export format: 'json' or 'gexf'")
):
    """
    Export the complete dependency graph for visualization
    Query params:
        - repo_url (optional): if not provided, uses REPO_TO_ANALYZE from env
        - format (optional): 'json' (default) for JSON format, 'gexf' for Gephi format
    """
    try:
        target_repo = repo_url if repo_url else REPO_TO_ANALYZE
        tmpdir = get_or_clone_repo(target_repo)
        
        # Export graph data
        graph_data = export_graph_data(tmpdir, format=format)
        
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
            "format": format
        }
        
        return JSONResponse(response)
    
    except Exception as e:
        return JSONResponse(
            {"error": f"Graph export failed: {str(e)}"}, 
            status_code=500
        )

@app.get("/analyze/full")
def full_analysis(repo_url: str = None):
    """
    Perform complete analysis including code metrics and dependencies
    Query params:
        - repo_url (optional): if not provided, uses REPO_TO_ANALYZE from env
    """
    try:
        target_repo = repo_url if repo_url else REPO_TO_ANALYZE
        tmpdir = get_or_clone_repo(target_repo)
        
        # Code metrics
        loc = count_loc(tmpdir)
        todos = count_todos(tmpdir)
        complexity = avg_cyclomatic_complexity(tmpdir)
        debt = simple_debt_score(loc, todos, complexity)
        detailed = get_detailed_metrics(tmpdir)
        
        # Dependency metrics
        dep_metrics = analyze_dependencies(tmpdir)
        
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
            "analysis_method": "Tree-sitter AST + NetworkX graph analysis"
        }
        
        return JSONResponse(response)
    
    except Exception as e:
        return JSONResponse(
            {"error": f"Full analysis failed: {str(e)}"}, 
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
            "/analyze/full": "Complete analysis with code metrics and dependencies",
            "/cleanup-cache": "Clean up cached repositories (POST)",
            "/login": "GitHub OAuth login",
            "/callback": "GitHub OAuth callback",
            "/health": "Health check"
        }
    })


