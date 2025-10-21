from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from analysis import count_loc, count_todos, avg_cyclomatic_complexity, simple_debt_score
import os
import requests
import tempfile
import git
from dotenv import load_dotenv

load_dotenv()  

app = FastAPI()

CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
BACKEND_URL = os.getenv("BACKEND_URL") 
GITHUB_PAT = os.getenv("GITHUB_PAT")  # Optional, for private repos

# You can change this for testing any repo
REPO_TO_ANALYZE = "https://github.com/nandanadileep/Salary_Prediction.git"

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

REPO_TO_ANALYZE = os.getenv("REPO_TO_ANALYZE", "https://github.com/nandanadileep/iris_flower.git")
GITHUB_PAT = os.getenv("GITHUB_PAT")  # Optional, for private repos

@app.get("/analyze")
def analyze():
    tmpdir = tempfile.mkdtemp()

    # Prepare repo URL
    if GITHUB_PAT and REPO_TO_ANALYZE.startswith("https://github.com/"):
        # Correct format for private repo cloning via HTTPS
        repo_url = REPO_TO_ANALYZE.replace(
            "https://github.com/",
            f"https://x-access-token:{GITHUB_PAT}@github.com/"
        )
    else:
        repo_url = REPO_TO_ANALYZE

    # Clone the repo
    try:
        git.Repo.clone_from(repo_url, tmpdir)
    except Exception as e:
        return JSONResponse({"error": f"Failed to clone repo: {e}"})

    # Compute metrics
    loc = count_loc(tmpdir)
    todos = count_todos(tmpdir)
    complexity = avg_cyclomatic_complexity(tmpdir)
    debt = simple_debt_score(loc, todos, complexity)

    return JSONResponse({
        "LOC": loc,
        "TODOs/FIXME/HACK": todos,
        "AvgCyclomaticComplexity": complexity,
        "DebtScore": debt
    })
