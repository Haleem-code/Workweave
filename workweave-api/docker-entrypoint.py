"""Initialize a fresh mounted data directory, then run as the app user."""
import os
from pathlib import Path
import pwd
import sys


def main():
    if os.geteuid() == 0:
        account = pwd.getpwnam("workweave")
        directory = Path(os.environ.get("WORKWEAVE_DATA_DIR", "/data/workweave"))
        directory.mkdir(parents=True, exist_ok=True)
        # A new Fly volume is owned by root. Existing credential files are not
        # traversed or read; only the mount directory's ownership is initialized.
        os.chown(directory, account.pw_uid, account.pw_gid)
        os.setgroups([])
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
