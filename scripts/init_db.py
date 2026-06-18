import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import init_db


def main() -> None:
    init_db()
    print("Database initialized with pgvector extension when available.")


if __name__ == "__main__":
    main()
