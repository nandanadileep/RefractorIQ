# RefractorIQ/backend/tasks.py

import traceback
import shutil # Ensure shutil is imported
import os
import git
import tempfile
import numpy as np # For FAISS
import pickle # For saving mapping
import faiss # For indexing and search
from sentence_transformers import SentenceTransformer # For embeddings
from .celery_app import celery_app
from .database import SessionLocal
from .models import AnalysisJob
# Import necessary functions/constants from file_utils
from .file_utils import save_report_local, ensure_report_dir_exists, REPORT_STORAGE_PATH
# Import analysis functions
from .analysis import (
    count_loc,
    count_todos,
    avg_cyclomatic_complexity,
    simple_debt_score,
    get_detailed_metrics,
    is_third_party_file, # Import necessary helpers if used directly
    is_test_file
)
from .dependency_analysis import analyze_dependencies, export_graph_data
from .deduplication import analyze_duplicates_minhash

# Helper function to make results JSON serializable (unchanged)
# Helper function to make results JSON serializable
def make_json_serializable(obj):
    """Recursively converts sets to lists and Ellipsis to None."""
    if isinstance(obj, set):
        return list(obj)
    elif obj is Ellipsis:
        return None
    elif isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(elem) for elem in obj]
    elif isinstance(obj, float) and (obj == float('inf') or obj == float('-inf')):
        return str(obj)
    # Handle numpy integers
    elif isinstance(obj, (np.int_, np.intc, np.intp, np.int8,
                        np.int16, np.int32, np.int64, np.uint8,
                        np.uint16, np.uint32, np.uint64)):
        return int(obj)
    # Handle numpy floats (corrected np.float64 duplication)
    elif isinstance(obj, (np.float16, np.float32, np.float64)):
        return float(obj)
    # --- THIS IS THE CORRECTED LINE ---
    # Handle numpy complex numbers using the updated type
    elif isinstance(obj, (np.complex64, np.complex128)): # Replaced np.complex_
        return {'real': obj.real, 'imag': obj.imag}
    # --- END CORRECTION ---
    elif isinstance(obj, (np.ndarray,)): # Handle numpy arrays
        return obj.tolist()
    elif isinstance(obj, np.bool_): # Handle numpy booleans
        return bool(obj)
    elif isinstance(obj, np.void): # Handle numpy void type
        return None
    else:
        # Default case
        return obj

# Worker-specific repo cloning (includes shallow clone fix)
GITHUB_PAT = os.getenv("GITHUB_PAT")
REPO_TO_ANALYZE = os.getenv("REPO_TO_ANALYZE")
def worker_clone_repo(repo_url: str = None):
    """Clones repo specifically for the worker, always creates temp dir, uses shallow clone."""
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
        # Use shallow clone (depth=1)
        git.Repo.clone_from(clone_url, tmpdir, depth=1)
        print(f"Shallow clone successful for {target_repo}")
        return tmpdir
    except Exception as e:
        # Clean up immediately on clone failure
        if tmpdir and os.path.exists(tmpdir):
             shutil.rmtree(tmpdir, ignore_errors=True)
        print(f"Worker failed to clone repo: {str(e)}")
        # Reraise the exception to fail the task
        raise Exception(f"Failed to clone repo: {str(e)}")


# Helper function for creating and saving the search index
def create_and_save_index(job_id, repo_path, exclude_third_party, exclude_tests):
    """Generates embeddings, creates a FAISS index, saves index and mapping."""
    index_data = [] # Stores {'path': ..., 'content': ...}
    errors = [] # Stores non-fatal errors during indexing

    # Initialize Sentence Transformer model
    try:
        # This model is small and efficient for semantic search tasks
        model = SentenceTransformer('all-MiniLM-L6-v2')
        embedding_dim = model.get_sentence_embedding_dimension()
    except Exception as e:
        print(f"Job {job_id}: CRITICAL - Failed to load SentenceTransformer model: {e}")
        # Cannot proceed without the model
        return None, None, [f"Failed to load embedding model: {e}"]

    print(f"Job {job_id}: Embedding model loaded (dim={embedding_dim}). Starting indexing...")

    # Iterate through files to gather content for indexing
    for root, _, files in os.walk(repo_path):
        for file in files:
            filepath = os.path.join(root, file)
            rel_path = os.path.relpath(filepath, repo_path).replace(os.sep, '/')

            # Apply exclusions using functions from analysis.py
            if exclude_third_party and is_third_party_file(filepath, repo_path):
                continue
            # Note: is_test_file needs repo_path which we have
            if exclude_tests and is_test_file(filepath, repo_path):
                continue

            # Basic file type filter (can be expanded)
            ext = os.path.splitext(file)[1].lower()
            if ext not in [".py", ".js", ".ts", ".java", ".md", ".txt", ".rst", ".yaml", ".yml", ".json"]:
                 continue # Skip binary files, config files etc.

            try:
                # Read file content, limit size for efficiency
                with open(filepath, "r", errors="ignore") as f:
                    # Read up to ~1MB, truncate longer files for indexing speed
                    content = f.read(1024 * 1024)
                if content and len(content.strip()) > 20: # Index files with some meaningful content
                    index_data.append({'path': rel_path, 'content': content})
            except Exception as e:
                # Log non-fatal read errors but continue
                print(f"Job {job_id}: Warning - Could not read file {rel_path} for indexing: {e}")
                errors.append(f"Could not read {rel_path}: {e}")

    if not index_data:
        print(f"Job {job_id}: No suitable content found for indexing after filtering.")
        # Return successfully, but indicate no index was created
        return None, None, errors # Return any read errors encountered

    # Generate embeddings for all collected content
    print(f"Job {job_id}: Generating embeddings for {len(index_data)} documents...")
    try:
        contents = [item['content'] for item in index_data]
        # normalize_embeddings=True is recommended for cosine similarity with IndexFlatIP
        embeddings = model.encode(contents, show_progress_bar=False, normalize_embeddings=True)
        # FAISS requires float32 numpy array
        embeddings_np = np.array(embeddings).astype('float32')
        print(f"Job {job_id}: Embeddings generated with shape {embeddings_np.shape}")
    except Exception as e:
        print(f"Job {job_id}: CRITICAL - Error generating embeddings: {e}")
        return None, None, errors + [f"Embedding generation failed: {e}"]

    # Create and populate FAISS index
    print(f"Job {job_id}: Building FAISS index...")
    try:
        # IndexFlatIP uses Inner Product, which is equivalent to Cosine Similarity for normalized vectors
        index = faiss.IndexFlatIP(embedding_dim)
        index.add(embeddings_np)
        print(f"Job {job_id}: FAISS index built with {index.ntotal} vectors.")
    except Exception as e:
        print(f"Job {job_id}: CRITICAL - Error building FAISS index: {e}")
        return None, None, errors + [f"FAISS index build failed: {e}"]

    # Define paths for saving index and mapping files
    ensure_report_dir_exists() # Make sure the target directory exists
    index_file_path = os.path.join(REPORT_STORAGE_PATH, f"{job_id}_index.faiss")
    mapping_file_path = os.path.join(REPORT_STORAGE_PATH, f"{job_id}_mapping.pkl")

    # Save the index and the mapping (index position -> file path)
    try:
        print(f"Job {job_id}: Saving FAISS index to {index_file_path}")
        faiss.write_index(index, index_file_path)

        # Create mapping from FAISS index position back to the relative file path
        mapping = {i: item['path'] for i, item in enumerate(index_data)}
        print(f"Job {job_id}: Saving mapping ({len(mapping)} items) to {mapping_file_path}")
        with open(mapping_file_path, 'wb') as f:
            pickle.dump(mapping, f)

        print(f"Job {job_id}: Indexing complete and files saved.")
    except Exception as e:
        print(f"Job {job_id}: CRITICAL - Error saving index/mapping files: {e}")
        errors.append(f"Failed to save index/mapping: {e}")
        # Attempt cleanup if saving failed
        if os.path.exists(index_file_path): os.remove(index_file_path)
        if os.path.exists(mapping_file_path): os.remove(mapping_file_path)
        return None, None, errors # Return errors, index creation failed

    # Return paths to the saved files and any non-critical errors
    return index_file_path, mapping_file_path, errors


# --- Main Celery Task ---
@celery_app.task(bind=True)
def run_full_analysis(
    self,
    job_id: str,
    repo_url: str,
    exclude_third_party: bool,
    exclude_tests: bool
):
    """The background task that runs the full analysis, including indexing."""

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

        # 2. Clone the repo (shallow clone)
        tmpdir = worker_clone_repo(repo_url)

        # 3. Run all analyses
        code_metrics = {}
        dep_metrics = {}
        duplication_metrics = {}
        errors_occurred = [] # List to collect errors from all stages

        # --- Code Metrics ---
        try:
            loc = count_loc(tmpdir, exclude_third_party, exclude_tests)
            todos = count_todos(tmpdir, exclude_third_party, exclude_tests)
            complexity = avg_cyclomatic_complexity(tmpdir, exclude_third_party, exclude_tests)
            debt = simple_debt_score(loc, todos, complexity)
            detailed = get_detailed_metrics(tmpdir, exclude_third_party, exclude_tests)
            code_metrics = {
                "LOC": loc, "TODOs_FIXME_HACK": todos, "AvgCyclomaticComplexity": complexity,
                "DebtScore": debt, "TotalFunctions": detailed.get("total_functions"),
                "MaxComplexity": detailed.get("max_complexity"), "MinComplexity": detailed.get("min_complexity"),
                "FilesAnalyzed": detailed.get("files_analyzed"),
                "ComplexityDistribution": detailed.get("complexity_distribution")
            }
            print(f"Job {job_id}: Code metrics calculated.")
        except Exception as e:
            print(f"Job {job_id}: Error calculating code metrics: {traceback.format_exc()}")
            errors_occurred.append(f"Code metrics failed: {str(e)}")
            code_metrics = {"error": str(e)}

        # --- Dependency Metrics & Graph ---
        try:
            dep_metrics = analyze_dependencies(tmpdir, exclude_third_party, exclude_tests)
            print(f"Job {job_id}: Dependency metrics calculated.")
            try:
                graph_json_data = export_graph_data(
                    tmpdir, format='json',
                    exclude_third_party=exclude_third_party,
                    exclude_tests=exclude_tests
                )
                dep_metrics["graph_json"] = graph_json_data # Add graph JSON to results
                print(f"Job {job_id}: Dependency graph JSON generated.")
            except Exception as e_graph:
                print(f"Job {job_id}: Error generating graph JSON: {traceback.format_exc()}")
                errors_occurred.append(f"Graph JSON generation failed: {str(e_graph)}")
                dep_metrics["graph_json"] = None # Ensure key exists
        except Exception as e:
            print(f"Job {job_id}: Error calculating dependency metrics: {traceback.format_exc()}")
            errors_occurred.append(f"Dependency analysis failed: {str(e)}")
            dep_metrics = {"error": str(e), "graph_json": None}

        # --- Duplication Metrics ---
        try:
            duplication_metrics = analyze_duplicates_minhash(tmpdir, exclude_third_party, exclude_tests)
            print(f"Job {job_id}: Duplication metrics calculated.")
        except Exception as e:
            print(f"Job {job_id}: Error calculating duplication metrics: {traceback.format_exc()}")
            errors_occurred.append(f"Duplication analysis failed: {str(e)}")
            duplication_metrics = {"error": str(e)}

        # --- NEW: Create and save search index ---
        # Runs after other analyses, uses the same cloned repo
        index_file, mapping_file, index_errors = create_and_save_index(
            job_id, tmpdir, exclude_third_party, exclude_tests
        )
        if index_errors:
            # Add non-critical indexing errors (like read failures) to the main error list
            # Critical errors (model load, index build/save) will already be there
            errors_occurred.extend(index_errors)
            print(f"Job {job_id}: Indexing completed with errors.")
        elif index_file:
             print(f"Job {job_id}: Indexing completed successfully.")
        else:
             print(f"Job {job_id}: Indexing skipped (no content found).")
        # Note: We don't need to add index_file/mapping_file paths to the main JSON report.
        # The search endpoint will construct these paths based on the job_id.
        # --- END NEW ---

        # 4. Assemble the final report
        final_report = {
            "repository": repo_url,
            "code_metrics": code_metrics,
            "dependency_metrics": dep_metrics,
            "duplication_metrics": duplication_metrics,
            "analysis_method": "Tree-sitter AST + NetworkX + MinHash + Embeddings (Async - Local)", # Updated method
            "excluded_third_party": exclude_third_party,
            "excluded_tests": exclude_tests,
            "analysis_errors": errors_occurred # Consolidates errors from all steps
        }

        # 5. Make the report JSON serializable
        serializable_report = make_json_serializable(final_report)

        # 6. Save main report locally
        report_file_path = save_report_local(serializable_report, job_id)
        print(f"Job {job_id}: Main report saved to {report_file_path}")

        # 7. Update job in DB
        # Consider indexing errors as non-fatal unless index creation itself failed critically
        is_critical_index_error = any(e for e in index_errors if "Failed to load embedding model" in e or "FAISS index build failed" in e or "Failed to save index/mapping" in e)

        if not errors_occurred or (errors_occurred and not any(e for e in errors_occurred if e not in index_errors)) and not is_critical_index_error:
             # Complete if no errors OR only non-critical index errors (like read fails)
            job.status = "COMPLETED"
            print(f"Job {job_id}: Status set to COMPLETED")
            if errors_occurred: # Store non-critical errors if present
                job.error = "; ".join(errors_occurred)[:1000] # Limit error length
                print(f"Job {job_id}: Completed with non-fatal errors: {job.error}")
        else:
            # Fail if critical analysis errors OR critical indexing errors occurred
            job.status = "FAILED"
            job.error = "; ".join(errors_occurred)[:1000] # Limit error length
            print(f"Job {job_id}: Status set to FAILED due to errors: {job.error}")

        job.report_s3_url = report_file_path # Still store the main report path

        # Update summary metrics (unchanged)
        summary_data = {
            "loc": code_metrics.get("LOC"),
            "debt_score": code_metrics.get("DebtScore"),
            "avg_complexity": code_metrics.get("AvgCyclomaticComplexity"),
            "duplicate_pairs": duplication_metrics.get("duplicate_pairs_found") if isinstance(duplication_metrics, dict) else None
        }
        job.summary_metrics = make_json_serializable(summary_data)

        db.commit()

    except Exception as e:
        # Handle critical failures during setup, cloning, or final DB update
        error_details = traceback.format_exc()
        print(f"Critical failure in analysis task for job {job_id}: {error_details}")
        if job:
            try:
              job.status = "FAILED"
              job_error_msg = f"Task execution failed: {str(e)}"
              # Extract core reason for clone failure if applicable
              if "Failed to clone repo" in job_error_msg:
                  parts = job_error_msg.split(': ', 1)
                  job_error_msg = f"Task execution failed: Clone error - {parts[-1]}" if len(parts) > 1 else job_error_msg

              job.error = job_error_msg[:1000] # Limit error length
              db.commit()
            except Exception as db_err:
              print(f"Job {job_id}: Failed to update DB after critical error: {db_err}")
              db.rollback() # Rollback the failed update attempt

    finally:
        # 8. Cleanup cloned repo directory
        if tmpdir and os.path.exists(tmpdir):
            print(f"Cleaning up {tmpdir} for job {job_id}")
            shutil.rmtree(tmpdir, ignore_errors=True)

        # Close DB session
        db.close()
        print(f"Job {job_id}: DB session closed.")