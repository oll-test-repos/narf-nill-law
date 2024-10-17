import sys
import json

from pathlib import Path
from taf.git import GitRepository
from taf.log import taf_logger

LIB_ROOT_PATH = Path(__file__).parent.parent.parent.parent.parent.parent.parent.expanduser()

target_repos_with_unauthenticated_commits = ("narf-nill/law-html",)

def process_stdin():
   return sys.stdin.read()

def send_state(state):
    print(json.dumps(state))

data = process_stdin()
data = json.loads(data)

for repo in target_repos_with_unauthenticated_commits:
    html_repo = GitRepository(library_dir=LIB_ROOT_PATH, name=repo, urls=["git@github.com:narf-nill/law-html.git"])
    error = None
    try:
        html_repo.clone()
    except Exception as e:
        send_state({"error": str(e)})
        taf_logger.error(f"Clone failed for {repo.name}: {e}")
        sys.exit(1)

send_state(data)