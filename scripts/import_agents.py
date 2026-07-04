"""CLI entry point to (re)import the 16 master agents. Usage: python -m scripts.import_agents"""

from src.agent_seed import sync_master_agents
from src.database import SessionLocal


def main() -> None:
    db = SessionLocal()
    try:
        result = sync_master_agents(db)
        print(f"Agentes creados: {result.created} | actualizados: {result.updated} | total: {result.total}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
