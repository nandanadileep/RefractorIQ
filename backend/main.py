import os
import requests
import tempfile
import git
import shutil
import uuid
import traceback
import pickle
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from fastapi import FastAPI, Request, Query, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from sqlalchemy.orm import Session

# --- Project Imports ---
from .database import engine, Base, get_db
from .models import AnalysisJob
from .tasks import run_full_analysis, make_json_serializable
from .file_utils import ensure_report_dir_exists, get_report_local, REPORT_STORAGE_PATH

# Import analysis functions for potential sync endpoints
from .analysis import (
    count_loc,
    count_todos,
    avg_cyclomatic_complexity,
    simple_debt_score,
    get_detailed_metrics
)
from .dependency_analysis import (
    analyze_dependencies,
    get_file_dependencies,
    export_graph_data
)
# --- END IMPORTS ---

load_dotenv()

# --- Constants ---
CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
BACKEND_URL = os.getenv("BACKEND_URL")
GITHUB_PAT = os.getenv("GITHUB_PAT")
REPO_TO_ANALYZE = os.getenv("REPO_TO_ANALYZE", "https://github.com/emcie-co/parlant.git")

# --- App Initialization ---
app = FastAPI()

# --- Load Search Model on Startup ---
try:
    # This MUST be the same model used in tasks.py
    SEARCH_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
    print("Search model 'all-MiniLM-L6-v2' loaded successfully.")
except Exception as e:
    SEARCH_MODEL = None
    print(f"Warning: Failed to load SentenceTransformer model on startup: {e}")
# --- END NEW ---


# --- App startup event ---
@app.on_event("startup")
def on_startup():
    """Create DB tables and ensure report directory exists on startup."""
    print("Running FastAPI startup tasks...")
    Base.metadata.create_all(bind=engine)
    print("Database tables checked/created.")
    ensure_report_dir_exists()
    print("Report storage directory checked/created.")
    print("Startup complete.")


# --- CORS Configuration ---
origins = [
    "https://fluffy-fortnight-pjr95546qg936qrg-3000.app.github.dev",
    "http://localhost:3000",
    "*" # Allow all in dev
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_build_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(frontend_build_path):
    app.mount("/static", StaticFiles(directory=frontend_build_path), name="static")
    
    # Serve index.html for all frontend routes
    @app.get("/")
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str = ""):
        # Don't serve frontend for API routes
        if full_path.startswith("api/") or full_path.startswith("analyze/"):
            return {"error": "Not found"}
        
        index_path = os.path.join(frontend_build_path, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"error": "Frontend not built"}


# --- Repo Cloning (Mainly for Sync Endpoints if kept) ---
def get_or_clone_repo_sync(repo_url: str = None):
    """Clones repo specifically for synchronous API calls, always creates temp dir."""
    target_repo = repo_url if repo_url else REPO_TO_ANALYZE
    if not target_repo:
         raise ValueError("No repository URL provided or found in environment variables.")

    tmpdir = tempfile.mkdtemp()
    print(f"SYNC cloning {target_repo} into {tmpdir}")

    if GITHUB_PAT and target_repo.startswith("https://github.com/"):
        clone_url = target_repo.replace(
            "https://github.com/",
            f"https://x-access-token:{GITHUB_PAT}@github.com/"
        )
    else:
        clone_url = target_repo

    try:
        # Using depth=1 for a shallow clone, same as worker
        git.Repo.clone_from(clone_url, tmpdir, depth=1)
        return tmpdir
    except Exception as e:
        shutil.rmtree(tmpdir, ignore_errors=True)
        print(f"SYNC failed to clone repo: {str(e)}")
        raise Exception(f"Failed to clone repo: {str(e)}")


# ---------------- OAuth (Unchanged) ---------------- #
@app.get("/login")
def login():
    github_oauth_url = f"https://github.com/login/oauth/authorize?client_id={CLIENT_ID}&scope=repo"
    return RedirectResponse(github_oauth_url)

@app.get("/callback")
def callback(code: str):
    token_url = "https://github.com/login/oauth/access_token"
    res = requests.post(
        token_url,
        data={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "code": code,
            "redirect_uri": f"{BACKEND_URL}/callback"
        },
        headers={"Accept": "application/json"}
    )
    access_token = res.json().get("access_token")
    return JSONResponse({"access_token": access_token})

# ---------------- Async Analysis Endpoints (Unchanged) ---------------- #

@app.get("/analyze/full")
def full_analysis_start(
    repo_url: str = None,
    exclude_third_party: bool = Query(True, description="Exclude third-party libraries"),
    exclude_tests: bool = Query(True, description="Exclude test files"),
    db: Session = Depends(get_db)
):
    """
    Triggers a full async analysis. Returns a job ID immediately.
    """
    try:
        target_repo = repo_url if repo_url else REPO_TO_ANALYZE
        print(f"Received full analysis request for: {target_repo}")

        new_job = AnalysisJob(repo_url=target_repo, status="PENDING")
        db.add(new_job)
        db.commit()
        db.refresh(new_job)
        job_id = str(new_job.id)
        print(f"Created job {job_id} for {target_repo}")

        # This task now handles code metrics, dependencies, duplication, AND indexing
        run_full_analysis.delay(
            job_id=job_id, repo_url=target_repo,
            exclude_third_party=exclude_third_party, exclude_tests=exclude_tests
        )
        print(f"Dispatched task for job {job_id}")

        status_url = f"/analyze/status/{job_id}" # Use relative path
        print(f"Responding with job_id: {job_id}, status_url: {status_url}")
        return JSONResponse({
            "message": "Analysis started", "job_id": job_id, "status_url": status_url
        }, status_code=202)

    except Exception as e:
        print(f"Error starting analysis: {traceback.format_exc()}")
        return JSONResponse({"error": f"Failed to start analysis: {str(e)}"}, status_code=500)


@app.get("/analyze/status/{job_id}")
def get_analysis_status(job_id: uuid.UUID, db: Session = Depends(get_db)):
    """Checks the status of an analysis job."""
    job = db.query(AnalysisJob).get(job_id)
    if not job:
        print(f"Status check failed: Job {job_id} not found")
        return JSONResponse({"error": "Job not found"}, status_code=404)

    response = {
        "job_id": str(job.id), "status": job.status, "repo_url": job.repo_url,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }
    if job.status == "COMPLETED":
        response["results_url"] = f"/analyze/results/{job_id}"
        response["summary"] = job.summary_metrics
        print(f"Job {job_id} status: COMPLETED")
    elif job.status == "FAILED":
        response["error"] = job.error
        print(f"Job {job_id} status: FAILED - {job.error}")
    else:
         print(f"Job {job_id} status: {job.status}")

    return JSONResponse(response)


@app.get("/analyze/results/{job_id}")
def get_analysis_results(job_id: uuid.UUID, db: Session = Depends(get_db)):
    """Fetches the final JSON report from the local filesystem for a completed job."""
    job = db.query(AnalysisJob).get(job_id)
    if not job:
        print(f"Result fetch failed: Job {job_id} not found")
        return JSONResponse({"error": "Job not found"}, status_code=404)

    # Allow fetching results even if job failed (to see partial data/errors)
    if job.status == "PENDING" or job.status == "RUNNING":
        print(f"Result fetch attempted: Job {job_id} status is {job.status}")
        return JSONResponse({"error": f"Job is {job.status}", "status": "job.status"}, status_code=400)

    report_file_path = job.report_s3_url # Re-using field name for local path
    if not report_file_path:
        if job.status == "FAILED":
             return JSONResponse({"error": f"Job failed: {job.error}", "status": job.status}, status_code=400)
        print(f"Result fetch error: Job {job_id} {job.status} but no report path found")
        return JSONResponse({"error": f"Job {job.status} but no report file path found"}, status_code=500)

    try:
        print(f"Fetching local report for job {job_id} from {report_file_path}")
        report_data = get_report_local(report_file_path)
        serializable_data = make_json_serializable(report_data)
        return JSONResponse(serializable_data)
    except FileNotFoundError:
         print(f"Result fetch error: Report file not found for job {job_id} at {report_file_path}")
         return JSONResponse({"error": "Report file not found"}, status_code=404)
    except Exception as e:
        print(f"Result fetch error: Failed reading report for job {job_id}: {traceback.format_exc()}")
        return JSONResponse({"error": f"Failed to retrieve local report: {str(e)}"}, status_code=500)


# ---------------- NEW: Search Endpoint ---------------- #

@app.get("/analyze/results/{job_id}/search")
def search_analysis_results(
    job_id: uuid.UUID,
    q: str = Query(..., min_length=3, description="Semantic search query"),
    k: int = Query(10, gt=0, le=50, description="Number of results to return"),
    db: Session = Depends(get_db)
):
    """
    Performs semantic search over the analyzed repository files for a specific job.
    """
    if not SEARCH_MODEL:
        print("Search failed: SentenceTransformer model not loaded.")
        return JSONResponse({"error": "Search model is not available. Check server logs."}, status_code=503)

    # 1. Check if job exists and is completed
    job = db.query(AnalysisJob).get(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job.status != "COMPLETED":
         # Don't allow search if job isn't complete, as index may be missing/partial
         return JSONResponse({"error": "Job is not yet complete. Search is unavailable."}, status_code=400)

    # 2. Define file paths based on job_id
    index_file_path = os.path.join(REPORT_STORAGE_PATH, f"{job_id}_index.faiss")
    mapping_file_path = os.path.join(REPORT_STORAGE_PATH, f"{job_id}_mapping.pkl")

    # 3. Check if index files exist
    if not os.path.exists(index_file_path) or not os.path.exists(mapping_file_path):
        print(f"Search failed: Index files not found for job {job_id}")
        return JSONResponse({"error": "Search index not found for this job. It may have failed during creation."}, status_code=404)

    try:
        # 4. Load index and mapping
        print(f"Loading index from {index_file_path} for search...")
        index = faiss.read_index(index_file_path)
        with open(mapping_file_path, 'rb') as f:
            mapping = pickle.load(f)
        
        # 5. Generate query embedding
        # Must use normalize_embeddings=True to match how the index was created
        query_embedding = SEARCH_MODEL.encode([q], normalize_embeddings=True).astype('float32')
        
        # 6. Search the index
        # D = distances (Inner Product scores), I = indices
        D, I = index.search(query_embedding, k)
        
        # 7. Format results
        results = []
        for i in range(len(I[0])):
            index_pos = I[0][i]
            if index_pos in mapping:
                results.append({
                    "path": mapping[index_pos],
                    "score": float(D[0][i]) # Inner product score (higher is better)
                })
        
        print(f"Search successful, returning {len(results)} results.")
        return JSONResponse({"results": results})

    except Exception as e:
        print(f"Error during search for job {job_id}: {traceback.format_exc()}")
        return JSONResponse({"error": f"Search failed: {str(e)}"}, status_code=500)


# ---------------- Sync Analysis Endpoints (Deprecated) ---------------- #

@app.get("/analyze")
def analyze(
    repo_url: str = None, debug: bool = False,
    exclude_third_party: bool = Query(True), exclude_tests: bool = Query(True)
):
    """[SYNC - DEPRECATED] Analyze code metrics directly. May timeout."""
    tmpdir = None
    try:
        tmpdir = get_or_clone_repo_sync(repo_url)
        loc = count_loc(tmpdir, exclude_third_party, exclude_tests)
        todos = count_todos(tmpdir, exclude_third_party, exclude_tests)
        complexity = avg_cyclomatic_complexity(tmpdir, exclude_third_party, exclude_tests)
        debt = simple_debt_score(loc, todos, complexity)
        # Note: get_detailed_metrics now returns a dict
        detailed_results = get_detailed_metrics(tmpdir, exclude_third_party, exclude_tests)
        metrics = {
             "LOC": loc, "TODOs_FIXME_HACK": todos, "AvgCyclomaticComplexity": complexity,
             "DebtScore": debt,
             "TotalFunctions": detailed_results.get("total_functions"),
             "MaxComplexity": detailed_results.get("max_complexity"),
             "MinComplexity": detailed_results.get("min_complexity"),
             "FilesAnalyzed": detailed_results.get("files_analyzed"),
             "ComplexityDistribution": detailed_results.get("complexity_distribution")
             # Note: "complex_functions" list is excluded from this sync endpoint for brevity
        }
        response = {
            "repository": repo_url or REPO_TO_ANALYZE, "metrics": metrics,
            "analysis_method": "[SYNC] Tree-sitter AST parsing",
            "excluded_third_party": exclude_third_party, "excluded_tests": exclude_tests
        }
        if debug: response["debug"] = {"temp_dir": tmpdir}
        return JSONResponse(make_json_serializable(response))
    except Exception as e:
        print(f"SYNC /analyze error: {traceback.format_exc()}")
        return JSONResponse({"error": f"Sync analysis failed: {str(e)}"}, status_code=500)
    finally:
        if tmpdir and os.path.exists(tmpdir):
            shutil.rmtree(tmpdir, ignore_errors=True)


@app.get("/analyze/dependencies")
def analyze_deps(
    repo_url: str = None, exclude_third_party: bool = Query(True), exclude_tests: bool = Query(True)
):
    """[SYNC - DEPRECATED] Analyze dependencies directly. May timeout."""
    tmpdir = None
    try:
        tmpdir = get_or_clone_repo_sync(repo_url)
        dep_metrics = analyze_dependencies(tmpdir, exclude_third_party, exclude_tests)
        response = {
            "repository": repo_url or REPO_TO_ANALYZE, "dependency_metrics": dep_metrics,
            "analysis_method": "[SYNC] NetworkX graph analysis",
            "excluded_third_party": exclude_third_party, "excluded_tests": exclude_tests
        }
        return JSONResponse(make_json_serializable(response))
    except Exception as e:
        print(f"SYNC /analyze/dependencies error: {traceback.format_exc()}")
        return JSONResponse({"error": f"Sync dependency analysis failed: {str(e)}"}, status_code=500)
    finally:
        if tmpdir and os.path.exists(tmpdir):
            shutil.rmtree(tmpdir, ignore_errors=True)

# ---------------- Admin & Health Endpoints ---------------- #

@app.post("/cleanup-cache")
def cleanup_cache():
    """DEPRECATED - Cache is now managed by workers/sync endpoints."""
    print("Cleanup cache endpoint called - generally deprecated for async flow.")
    return JSONResponse({"message": "Cleaned 0 directories (manual cleanup recommended if needed)."})

@app.get("/health")
def health():
    """Health check endpoint."""
    return JSONResponse({"status": "healthy", "search_model_loaded": SEARCH_MODEL is not None})

@app.get("/")
def root():
    """Root endpoint with API information."""
    return JSONResponse({
        "message": "Code Analysis API with Tree-sitter, NetworkX, and Semantic Search (Async - Local Storage)",
        "endpoints": {
            "/analyze/full": "Trigger a full async analysis (GET)",
            "/analyze/status/{job_id}": "Check job status (GET)",
            "/analyze/results/{job_id}": "Get job results (GET)",
            "/analyze/results/{job_id}/search": "Perform semantic search on job results (GET)",
            "/login": "GitHub OAuth login",
            "/callback": "GitHub OAuth callback",
            "/health": "Health check",
            # Deprecated sync endpoints:
            "/analyze": "[SYNC - Deprecated] Analyze code metrics directly",
            "/analyze/dependencies": "[SYNC - Deprecated] Analyze dependencies directly",
        }
    })