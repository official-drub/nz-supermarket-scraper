import csv
import os
from pathlib import Path
import psycopg2

def load_map_from_csv(csv_path: str) -> dict[str,str]:
    map: dict[str, str] = {}
    if (not Path(csv_path).exists()):
        raise ValueError("csv path doesnt exist")

    with open(csv_path, "r") as f:
        reader = csv.reader(f)
        for row in reader:
            if (len(row) < 2):
                continue

            pid = row[0]
            bc = row[1]

            map[pid] = bc

    return map

def load_map_from_db(db_url: str) -> dict[str, str]:
    map: dict[str, str] = {}
    try:
        with psycopg2.connect(dsn=db_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    select internal_sku, barcode 
                    from barcode_foodstuff_sku 
                    where barcode is not null
                """)
                for el in cursor.fetchall():
                    pid = el[0]
                    bc = el[1]
                    map[pid] = bc
    except Exception as e:
        print(f"somthing in the db writing failed {e}")

    return map


def seed_bc_map() -> dict[str,str]:
    user_csv: str|None = os.getenv("PID_MAP_CSV_PATH")
    if (user_csv):
        mapped_pid_bc = load_map_from_csv(user_csv)
        print("sucessfully loaded from csv (FOODSTUFFS)")
        return mapped_pid_bc

    db_url = os.getenv("DB_URL")
    if (db_url):
        mapped_pid_bc = load_map_from_db(db_url)
        print("sucessfully loaded from db (FOODSTUFFS)")
        return mapped_pid_bc

    print("no successful loads, end this please, you will get blocked (FOODSTUFFS) as this case will add spam the endpoint")
    return {}