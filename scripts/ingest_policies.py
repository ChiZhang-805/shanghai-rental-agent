import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal, init_db
from app.services.policy_service import PolicyService


def main() -> None:
    init_db()
    with SessionLocal() as session:
        result = PolicyService().ingest_directory(session, Path("data/policies"))
    print(f"Ingested {result.documents} policy documents and {result.chunks} chunks.")


if __name__ == "__main__":
    main()
