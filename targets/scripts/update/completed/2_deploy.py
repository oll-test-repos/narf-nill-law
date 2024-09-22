import sys
import json

from datetime import datetime

from pathlib import Path
from taf.git import GitRepository
from taf.exceptions import NothingToCommitError
from taf.log import taf_logger

LIB_ROOT_PATH = Path(__file__).parent.parent.parent.parent.parent.parent.parent.expanduser()
# LIB_ROOT_PATH = Path("/home/dnikolic/narf")

MESSAGE_TEMPLATE = f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}]: Updates to Tribal Law"

def process_stdin():
   return sys.stdin.read()

def send_state(state):
    print(json.dumps(state))

data = process_stdin()
data = json.loads(data)
# TODO: make html repo initialization more flexible
html_repo = GitRepository(library_dir=LIB_ROOT_PATH, name="narf-nill/law-html")
error = None

try:
    # pull current branch because law-html allows unauthenticated commits
    html_repo.pull()
except Exception as e:
    send_state({"error": str(e)})
    sys.exit(1)
try:
    html_repo.commit(MESSAGE_TEMPLATE)
except NothingToCommitError as e:
    error = str(e)
    taf_logger.info(f"Nothing to commit: {error}")
    sys.exit(0)
except Exception as e:
    # commit failed, clean and reset to head
    error = str(e)
    html_repo.clean_and_reset()
    send_state({"error": error})
    sys.exit(1)

try:
    html_repo.push()
except Exception as e:
    send_state({"error": str(e)})
    html_repo.reset_num_of_commits(1)
    sys.exit(1)