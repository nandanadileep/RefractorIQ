import os
import json
from pathlib import Path
import tempfile
import shutil
import git
from dotenv import load_dotenv

CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
BACKEND_URL = os.getenv("BACKEND_URL")
GITHUB_PAT = os.getenv("GITHUB_PAT")
REPO_TO_ANALYZE = os.getenv("REPO_TO_ANALYZE", "https://github.com/emcie-co/parlant.git")

REPORT_STORAGE_PATH = os.getenv("REPORT_STORAGE_PATH", "./analysis_reports")

def ensure_report_dir_exists():
    """Creates the report storage directory if it doesn't exist."""
    Path(REPORT_STORAGE_PATH).mkdir(parents=True, exist_ok=True)

def save_report_local(report_data: dict, job_id: str) -> str:
    """Saves a JSON report to the local filesystem and returns the file path."""
    try:
        ensure_report_dir_exists()
        file_path = os.path.join(REPORT_STORAGE_PATH, f"{job_id}.json")
        
        with open(file_path, 'w') as f:
            json.dump(report_data, f, indent=2)
            
        return file_path # Return the absolute or relative path
    except Exception as e:
        print(f"Error saving report locally: {e}")
        raise

def get_report_local(file_path: str) -> dict:
    """Loads and parses a JSON report from the local filesystem."""
    try:
        if not os.path.exists(file_path):
             raise FileNotFoundError(f"Report file not found: {file_path}")
             
        with open(file_path, 'r') as f:
            report_data = json.load(f)
        return report_data
    except Exception as e:
        print(f"Error getting report locally: {e}")
        raise 

def get_or_clone_repo(repo_url: str = None):
    """Clone repo or return cached directory"""
    target_repo = repo_url if repo_url else REPO_TO_ANALYZE

    # --- SIMPLIFIED CACHING FOR DEMO ---
    # In a real async setup, managing cache across worker/API is complex.
    # For simplicity here, we might just clone each time in the worker.
    # However, keeping the cache check here for potential API-only use.
    # The task.py logic now explicitly cleans up its own clones.
    # if target_repo in _repo_cache:
    #     print(f"Using cached repo for {target_repo} at {_repo_cache[target_repo]}")
    #     return _repo_cache[target_repo]

    tmpdir = tempfile.mkdtemp()
    print(f"Cloning {target_repo} into {tmpdir}")

    if GITHUB_PAT and target_repo.startswith("https://github.com/"):
        clone_url = target_repo.replace(
            "https://github.com/",
            f"https://x-access-token:{GITHUB_PAT}@github.com/"
        )
    else:
        clone_url = target_repo

    try:
        git.Repo.clone_from(clone_url, tmpdir)
        # We won't cache in the API anymore to avoid conflicts with worker cleanup
        # _repo_cache[target_repo] = tmpdir
        return tmpdir
    except Exception as e:
        shutil.rmtree(tmpdir, ignore_errors=True)
        print(f"Error cloning repo: {str(e)}")
        raise Exception(f"Failed to clone repo: {str(e)}")

def convert_sets_to_lists(obj):
    """Recursively converts sets within a data structure to lists."""
    if isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, dict):
        return {k: convert_sets_to_lists(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_sets_to_lists(elem) for elem in obj]
    else:
        return obj
    
