import sys
import json

from datetime import datetime

from pathlib import Path
from taf.git import GitRepository
from taf.exceptions import NothingToCommitError
from taf.log import taf_logger

LIB_ROOT_PATH = Path(__file__).parent.parent.parent.parent.parent.parent.parent.expanduser()

MESSAGE_TEMPLATE = f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}]: Updates to Tribal Law"

def process_stdin():
   return sys.stdin.read()

def send_state(state):
    print(json.dumps(state))

data = process_stdin()
data = json.loads(data)

html_repo = GitRepository(library_dir=LIB_ROOT_PATH, name="narf-nill/law-html")
error = None

send_state(data)
print(data)
sys.exit(1)

try:
    html_repo.commit(MESSAGE_TEMPLATE)
except NothingToCommitError as e:
    error = str(e)
    taf_logger.info(f"Nothing to commit: {error}")
    sys.exit(0)
except Exception as e:
    # commit failed, clean and reset to head
    error = e.message or str(e)
    html_repo.clean_and_reset()
    send_state({"error": error})
    sys.exit(1)

try:
    html_repo.push()
except Exception as e:
    error = e.message or str(e)
    send_state({"error": str(error)})
    html_repo.reset_num_of_commits(1)
    sys.exit(1)

exit_code = data.get('exit-code', 0)
if exit_code:
    sys.exit(exit_code)