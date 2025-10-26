import os
import requests
import tempfile
import git # Keep for sync endpoints if used
import shutil # Keep for sync endpoints / cleanup
import uuid
import traceback
from fastapi import FastAPI, Request, Query, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from sqlalchemy.orm import Session

# --- Project Imports ---
from .database import engine, Base, get_db
from .models import AnalysisJob
from .tasks import run_full_analysis, make_json_serializable # Import task and helper
from .file_utils import ensure_report_dir_exists, get_report_local

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


# RefractorIQ/backend/main.py
origins = [
    "https://fluffy-fortnight-pjr95546qg936qrg-3000.app.github.dev", # Frontend Origin
    "http://localhost:3000",
    # "*" # You can keep or remove "*" if the specific origin works
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True, # Important if you ever use cookies/auth headers
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Repo Cloning (Mainly for Sync Endpoints if kept) ---
# Note: Caching is removed here to simplify logic with async workers.
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
        git.Repo.clone_from(clone_url, tmpdir)
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

# ---------------- Async Analysis Endpoints ---------------- #

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
        response["summary"] = job.summary_metrics # Already serialized by task
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

    if job.status not in ["COMPLETED", "FAILED"]: # Allow fetching results even if failed
        print(f"Result fetch attempted: Job {job_id} status is {job.status}")
        return JSONResponse({"error": f"Job is {job.status}", "status": job.status}, status_code=400)

    report_file_path = job.report_s3_url # Re-using field name
    if not report_file_path:
        # If job failed early, there might be no report path
        if job.status == "FAILED":
             return JSONResponse({"error": f"Job failed: {job.error}", "status": job.status}, status_code=400)
        print(f"Result fetch error: Job {job_id} {job.status} but no report path found")
        return JSONResponse({"error": f"Job {job.status} but no report file path found"}, status_code=500)

    try:
        print(f"Fetching local report for job {job_id} from {report_file_path}")
        report_data = get_report_local(report_file_path)
        # Apply serialization just in case file wasn't saved perfectly
        serializable_data = make_json_serializable(report_data)
        return JSONResponse(serializable_data)
    except FileNotFoundError:
         print(f"Result fetch error: Report file not found for job {job_id} at {report_file_path}")
         return JSONResponse({"error": f"Report file not found"}, status_code=404)
    except Exception as e:
        print(f"Result fetch error: Failed reading report for job {job_id}: {traceback.format_exc()}")
        return JSONResponse({"error": f"Failed to retrieve local report: {str(e)}"}, status_code=500)


# ---------------- Sync Analysis Endpoints (Deprecated) ---------------- #

@app.get("/analyze")
def analyze(
    repo_url: str = None, debug: bool = False,
    exclude_third_party: bool = Query(True), exclude_tests: bool = Query(True)
):
    """[SYNC - DEPRECATED] Analyze code metrics directly. May timeout."""
    tmpdir = None
    try:
        tmpdir = get_or_clone_repo_sync(repo_url) # Use sync version
        loc = count_loc(tmpdir, exclude_third_party, exclude_tests)
        todos = count_todos(tmpdir, exclude_third_party, exclude_tests)
        complexity = avg_cyclomatic_complexity(tmpdir, exclude_third_party, exclude_tests)
        debt = simple_debt_score(loc, todos, complexity)
        detailed = get_detailed_metrics(tmpdir, exclude_third_party, exclude_tests)
        metrics = {
             "LOC": loc, "TODOs_FIXME_HACK": todos, "AvgCyclomaticComplexity": complexity,
             "DebtScore": debt, "TotalFunctions": detailed.get("total_functions"),
             "MaxComplexity": detailed.get("max_complexity"), "MinComplexity": detailed.get("min_complexity"),
             "FilesAnalyzed": detailed.get("files_analyzed"),
             "ComplexityDistribution": detailed.get("complexity_distribution")
        }
        response = {
            "repository": repo_url or REPO_TO_ANALYZE, "metrics": metrics,
            "analysis_method": "[SYNC] Tree-sitter AST parsing",
            "excluded_third_party": exclude_third_party, "excluded_tests": exclude_tests
        }
        if debug: response["debug"] = {"temp_dir": tmpdir}
        return JSONResponse(make_json_serializable(response)) # Ensure serializable
    except Exception as e:
        print(f"SYNC /analyze error: {traceback.format_exc()}")
        return JSONResponse({"error": f"Sync analysis failed: {str(e)}"}, status_code=500)
    finally:
        if tmpdir: shutil.rmtree(tmpdir, ignore_errors=True)


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
        return JSONResponse(make_json_serializable(response)) # Ensure serializable
    except Exception as e:
        print(f"SYNC /analyze/dependencies error: {traceback.format_exc()}")
        return JSONResponse({"error": f"Sync dependency analysis failed: {str(e)}"}, status_code=500)
    finally:
        if tmpdir: shutil.rmtree(tmpdir, ignore_errors=True)

# --- (Keep other SYNC endpoints like file_deps, dependency_graph if needed) ---

# ---------------- Admin & Health Endpoints ---------------- #

@app.post("/cleanup-cache")
def cleanup_cache():
    """DEPRECATED - Cache is now managed by workers/sync endpoints."""
    # This might still be useful if sync endpoints leave dirs behind on error
    count = 0
    # Add logic here if you want to clean specific temp patterns, but generally not needed
    print("Cleanup cache endpoint called - generally deprecated for async flow.")
    return JSONResponse({"message": f"Cleaned {count} directories (manual cleanup recommended if needed)."})

@app.get("/health")
def health():
    """Health check endpoint."""
    # Basic health check, can be expanded later
    return JSONResponse({"status": "healthy"})

@app.get("/")
def root():
    """Root endpoint with API information."""
    return JSONResponse({
        "message": "Code Analysis API with Tree-sitter and NetworkX (Async - Local Storage)",
        "endpoints": {
            "/analyze/full": "Trigger a full async analysis (GET)",
            "/analyze/status/{job_id}": "Check job status (GET)",
            "/analyze/results/{job_id}": "Get job results (GET)",
            "/login": "GitHub OAuth login",
            "/callback": "GitHub OAuth callback",
            "/health": "Health check",
            # Deprecated sync endpoints:
            "/analyze": "[SYNC - Deprecated] Analyze code metrics directly",
            "/analyze/dependencies": "[SYNC - Deprecated] Analyze dependencies directly",
            # Add others if kept
        }
    })

# --- Direct Run (Optional) ---
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)