"""Allow running as python -m refactor_bot.cli."""
import sys

from refactor_bot.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
