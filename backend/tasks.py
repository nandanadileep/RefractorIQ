# RefractorIQ/backend/tasks.py
import traceback
import shutil
import os
import git
import tempfile
from .celery_app import celery_app # Relative import for celery app
from .database import SessionLocal # Relative import for database
from .models import AnalysisJob # Relative import for models
from .file_utils import save_report_local # Relative import for file utils

# Import all your analysis functions using relative imports
from .analysis import (
    count_loc,
    count_todos,
    avg_cyclomatic_complexity,
    simple_debt_score,
    get_detailed_metrics
)
# --- MODIFIED: Import export_graph_data ---
from .dependency_analysis import analyze_dependencies, export_graph_data
from .deduplication import analyze_duplicates_minhash

# --- HELPER FUNCTION (Renamed and Updated) ---
def make_json_serializable(obj):
    """Recursively converts sets to lists and Ellipsis to None."""
    if isinstance(obj, set):
        return list(obj)
    elif obj is Ellipsis: # Handle Ellipsis
        return None # Convert Ellipsis to null in JSON
    elif isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(elem) for elem in obj]
    elif isinstance(obj, float) and (obj == float('inf') or obj == float('-inf')):
        # Handle infinity if it occurs (e.g., in complexity thresholds)
        return str(obj) # Convert infinity to a string like "inf"
    else:
        # Handle other non-serializable types if needed later
        return obj

# --- Re-defined get_or_clone_repo here for worker context ---
# It's often better to have shared utilities, but for clarity
# let's define it within the worker's scope for now.
# Ensure GITHUB_PAT and REPO_TO_ANALYZE are accessible if needed (e.g., via os.getenv)
GITHUB_PAT = os.getenv("GITHUB_PAT")
REPO_TO_ANALYZE = os.getenv("REPO_TO_ANALYZE")

def worker_clone_repo(repo_url: str = None):
    """Clones repo specifically for the worker, always creates temp dir."""
    target_repo = repo_url if repo_url else REPO_TO_ANALYZE
    if not target_repo:
         raise ValueError("No repository URL provided or found in environment variables.")

    tmpdir = tempfile.mkdtemp()
    print(f"Worker cloning {target_repo} into {tmpdir}")

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
        # Clean up immediately on clone failure
        shutil.rmtree(tmpdir, ignore_errors=True)
        print(f"Worker failed to clone repo: {str(e)}")
        # Reraise the exception to fail the task
        raise Exception(f"Failed to clone repo: {str(e)}")


@celery_app.task(bind=True)
def run_full_analysis(
    self,
    job_id: str,
    repo_url: str,
    exclude_third_party: bool,
    exclude_tests: bool
):
    """The background task that runs the full analysis."""

    db = SessionLocal()
    job = None
    tmpdir = None

    try:
        # 1. Get Job and set status to RUNNING
        job = db.query(AnalysisJob).get(job_id)
        if not job:
            raise Exception(f"Job {job_id} not found in database.")

        job.status = "RUNNING"
        db.commit()
        print(f"Job {job_id} status set to RUNNING")

        # 2. Clone the repo using worker-specific function
        tmpdir = worker_clone_repo(repo_url)

        # 3. Run all analyses (Wrap each in try-except for better error isolation)
        code_metrics = {}
        dep_metrics = {}
        duplication_metrics = {}
        errors_occurred = []

        try:
            loc = count_loc(tmpdir, exclude_third_party, exclude_tests)
            todos = count_todos(tmpdir, exclude_third_party, exclude_tests)
            complexity = avg_cyclomatic_complexity(tmpdir, exclude_third_party, exclude_tests)
            debt = simple_debt_score(loc, todos, complexity)
            detailed = get_detailed_metrics(tmpdir, exclude_third_party, exclude_tests)

            code_metrics = {
                "LOC": loc,
                "TODOs_FIXME_HACK": todos,
                "AvgCyclomaticComplexity": complexity,
                "DebtScore": debt,
                "TotalFunctions": detailed.get("total_functions"),
                "MaxComplexity": detailed.get("max_complexity"),
                "MinComplexity": detailed.get("min_complexity"),
                "FilesAnalyzed": detailed.get("files_analyzed"),
                "ComplexityDistribution": detailed.get("complexity_distribution")
            }
            print(f"Job {job_id}: Code metrics calculated.")
        except Exception as e:
            print(f"Job {job_id}: Error calculating code metrics: {traceback.format_exc()}")
            errors_occurred.append(f"Code metrics failed: {str(e)}")
            code_metrics = {"error": str(e)} # Store error in result

        try:
            # --- MODIFIED: This block is updated ---
            dep_metrics = analyze_dependencies(tmpdir, exclude_third_party, exclude_tests)
            print(f"Job {job_id}: Dependency metrics calculated.")

            # --- NEW: Generate graph JSON data ---
            try:
                # Use your existing export function
                graph_json_data = export_graph_data(
                    tmpdir, 
                    format='json', 
                    exclude_third_party=exclude_third_party, 
                    exclude_tests=exclude_tests
                )
                # Add the graph data directly to the dep_metrics dictionary
                dep_metrics["graph_json"] = graph_json_data
                print(f"Job {job_id}: Dependency graph JSON generated.")
            except Exception as e:
                print(f"Job {job_id}: Error generating graph JSON: {traceback.format_exc()}")
                errors_occurred.append(f"Graph JSON generation failed: {str(e)}")
                dep_metrics["graph_json"] = None # Ensure key exists even if failed
            # --- END NEW ---

        except Exception as e:
            print(f"Job {job_id}: Error calculating dependency metrics: {traceback.format_exc()}")
            errors_occurred.append(f"Dependency analysis failed: {str(e)}")
            # --- MODIFIED: Ensure graph_json key exists on failure ---
            dep_metrics = {"error": str(e), "graph_json": None}

        try:
            duplication_metrics = analyze_duplicates_minhash(tmpdir, exclude_third_party, exclude_tests)
            print(f"Job {job_id}: Duplication metrics calculated.")
        except Exception as e:
            print(f"Job {job_id}: Error calculating duplication metrics: {traceback.format_exc()}")
            errors_occurred.append(f"Duplication analysis failed: {str(e)}")
            duplication_metrics = {"error": str(e)}

        # 4. Assemble the final report
        final_report = {
            "repository": repo_url,
            "code_metrics": code_metrics,
            "dependency_metrics": dep_metrics, # This dict now contains the graph_json
            "duplication_metrics": duplication_metrics,
            "analysis_method": "Tree-sitter AST + NetworkX + MinHash (Async - Local Storage)",
            "excluded_third_party": exclude_third_party,
            "excluded_tests": exclude_tests,
            "analysis_errors": errors_occurred # Include any errors encountered
        }

        # 5. Make the report JSON serializable (Handles sets, Ellipsis, etc.)
        serializable_report = make_json_serializable(final_report)

        # 6. Save report locally
        report_file_path = save_report_local(serializable_report, job_id)
        print(f"Job {job_id}: Report saved to {report_file_path}")

        # 7. Update job in DB
        if not errors_occurred:
            job.status = "COMPLETED"
            print(f"Job {job_id}: Status set to COMPLETED")
        else:
            job.status = "FAILED" # Mark as failed if any part had an error
            job.error = "; ".join(errors_occurred)
            print(f"Job {job_id}: Status set to FAILED due to errors: {job.error}")

        job.report_s3_url = report_file_path # Store local path

        # Create serializable summary
        summary_data = {
            "loc": code_metrics.get("LOC"),
            "debt_score": code_metrics.get("DebtScore"),
            "avg_complexity": code_metrics.get("AvgCyclomaticComplexity"),
            "duplicate_pairs": duplication_metrics.get("duplicate_pairs_found") if isinstance(duplication_metrics, dict) else None # Check if dict
        }
        job.summary_metrics = make_json_serializable(summary_data)

        db.commit()

    except Exception as e:
        # Handle failures during setup or final DB update
        error_details = traceback.format_exc()
        print(f"Critical failure in analysis task for job {job_id}: {error_details}")
        if job: # Check if job was fetched before the critical error
            try: # Try to update DB even on critical failure
              job.status = "FAILED"
              job.error = f"Task execution failed: {str(e)}"
              db.commit()
            except Exception as db_err:
              print(f"Job {job_id}: Failed to update DB after critical error: {db_err}")
              db.rollback() # Rollback if update fails

    finally:
        # 8. Cleanup cloned repo directory
        if tmpdir:
            print(f"Cleaning up {tmpdir} for job {job_id}")
            shutil.rmtree(tmpdir, ignore_errors=True)
            # No need to manage API cache here, worker clones are independent

        # Close DB session
        db.close()
        print(f"Job {job_id}: DB session closed.")

