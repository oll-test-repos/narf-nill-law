import sys
import json

from pathlib import Path
from taf.git import GitRepository
from taf.log import taf_logger

LIB_ROOT_PATH = Path(__file__).parent.parent.parent.parent.parent.parent.parent.expanduser()

def process_stdin():
   return sys.stdin.read()

def send_state(state):
    print(json.dumps(state))

data = process_stdin()
data = json.loads(data)

html_repo = GitRepository(library_dir=LIB_ROOT_PATH, name="narf-nill/law-html", urls=["git@github.com:oll-test-repos/narf-nill-law-html.git"])
try:
    html_repo.clone()
except Exception as e:
    send_state({"error": str(e)})
    taf_logger.error(f"Clone failed for {html_repo.name}: {e}")
    sys.exit(1)

send_state(data["state"])