"""Allow ``python -m scholarpath``."""

import sys

from scholarpath.app import main

if __name__ == "__main__":
    sys.exit(main())
