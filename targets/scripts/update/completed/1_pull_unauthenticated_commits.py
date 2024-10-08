import sys
import json

from pathlib import Path
from taf.git import GitRepository
from taf.log import taf_logger

LIB_ROOT_PATH = Path(__file__).parent.parent.parent.parent.parent.parent.parent.expanduser()
# LIB_ROOT_PATH = Path("/home/dnikolic/narf")

target_repos_with_unauthenticated_commits = ("narf-nill/law-html",)

def process_stdin():
   return sys.stdin.read()

def send_state(state):
    print(json.dumps(state))

data = process_stdin()
data = json.loads(data)

raise NotImplementedError("Test failure")

for repo in target_repos_with_unauthenticated_commits:
    html_repo = GitRepository(library_dir=LIB_ROOT_PATH, name=repo)
    error = None
    try:
        html_repo.pull()
    except Exception as e:
        send_state({"error": str(e)})
        taf_logger.error(f"Pull failed for {repo.name}: {e}")
        sys.exit(1)

send_state(data)