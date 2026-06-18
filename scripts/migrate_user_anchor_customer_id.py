import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text

from app.db import engine


def main() -> None:
    if engine.dialect.name != "postgresql":
        print("Skipped: user_anchors customer_id migration is only needed for PostgreSQL.")
        return

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "user_anchors" not in table_names:
        print("Skipped: user_anchors table does not exist.")
        return
    if "customers" not in table_names:
        print("Skipped: customers table does not exist.")
        return

    columns = {column["name"]: column for column in inspector.get_columns("user_anchors")}
    customer_id = columns.get("customer_id")
    if customer_id is None:
        print("Skipped: user_anchors.customer_id does not exist.")
        return

    column_type = str(customer_id["type"]).lower()
    if "integer" in column_type:
        print("Skipped: user_anchors.customer_id is already integer.")
        return

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE user_anchors DROP CONSTRAINT IF EXISTS user_anchors_customer_id_fkey"))
        conn.execute(text("ALTER TABLE user_anchors ALTER COLUMN customer_id DROP DEFAULT"))
        conn.execute(text("ALTER TABLE user_anchors ALTER COLUMN customer_id TYPE integer USING NULL::integer"))
        conn.execute(
            text(
                "ALTER TABLE user_anchors "
                "ADD CONSTRAINT user_anchors_customer_id_fkey "
                "FOREIGN KEY (customer_id) REFERENCES customers(id)"
            )
        )
    print("Migrated user_anchors.customer_id to integer foreign key.")


if __name__ == "__main__":
    main()
