import psycopg2
import os
import csv
from urllib import parse
from pathlib import Path
import sys
from psycopg2.extras import execute_values


CURR_DIR = Path(__file__).parent


def init_tables(db_url):
    print("starting schema writing 1")
    try:
        with psycopg2.connect(dsn=db_url) as conn:
            with conn.cursor() as cursor:
                print("starting schema writing 2 conn sucess")

                init_db(cursor)
                print("starting schema writing 3 empty tables done")

                insert_store_name_maps(cursor)
                insert_init_values_barcode_name(cursor)
                insert_mapped_fs_skus(cursor)
                insert_fs_dep(cursor)
                insert_ww_dep_id(cursor)
    except Exception as e:
        print(f"db connection failed {e}")

    print("finished schema writing")


def init_db(cursor):
    with open(CURR_DIR / "products_schema.sql", "r") as f:
        schema = f.read()

    cursor.execute(schema)


def insert_init_values_barcode_name(cursor):
    print("starting init_values_barcode_name")
    tung = Path(__file__).parent / "foodstuffs" / "paknsave" / "output" /"mapped_PID_BC_ps.csv"
    with open(tung, mode='r') as file:
        reader = csv.reader(file)
        l = []
        for row in reader:
            b = (str(row[1]), None, None) # BARCODE, null, null
            print(b)
            l.append(b)
            # cursor.execute("insert into barcode_name (barcode, product_name, img) values(%s,%s,%s) on conflict do nothing", b)
        
        execute_values(cursor, "insert into barcode_name (barcode, product_name, img) values %s on conflict do nothing", l)
    print("finished init_values_barcode_name")

def insert_mapped_fs_skus(cursor):
    print("starting mapped_fs_skus")
    tung = Path(__file__).parent / "foodstuffs" / "paknsave" / "output" /"mapped_PID_BC_ps.csv"
    with open(tung, mode='r') as file:
        reader = csv.reader(file)
        l = []
        for row in reader:
            sku = str(row[0])
            bc = str(row[1])
            b = (sku, bc)
            print(b)
            l.append(b)
            # cursor.execute("insert into barcode_foodstuff_sku values(%s,%s) on conflict (internal_sku) do update set barcode = EXCLUDED.barcode", b)
        execute_values(cursor, "insert into barcode_foodstuff_sku values %s on conflict (internal_sku) do update set barcode = EXCLUDED.barcode", l)
    print("finished mapped_fs_skus")



def insert_fs_dep(cursor):
    x = {
        "Fruit & Vegetables": 1,
        "Meat, Poultry & Seafood": 2,
        "Fridge, Deli & Eggs": 3,
        "Bakery": 4,
        "Frozen": 5,
        "Pantry": 6,
        "Hot & Cold Drinks": 7,
        "Beer, Wine & Cider": 8,
        "Health & Body": 9,
        "Baby & Toddler": 10,
        "Pets": 11,
        "Household & Cleaning": 12,
        "Snacks, Treats & Easy Meals": 13
    }

    print("starting init fs ids")
    for k,v in x.items():
        print(k, v)
        cursor.execute("insert into fs_dep_id values(%s,%s) on conflict do nothing", (v,k))
    print("finishing init fs ids")


def insert_ww_dep_id(cursor):
    x = {
        "dinner": 1,
        "fruit-veg": 2,
        "meat-poultry": 3,
        "fish-seafood": 4,
        "fridge-deli": 5,
        "bakery": 6,
        "frozen": 7,
        "pantry": 8,
        "beer-wine": 9,
        "drinks": 10,
        "health-body": 11,
        "household": 12,
        "baby-child": 13,
        "pet": 14
    }

    print("starting init ww ids")
    for k,v in x.items():
        print(k, v)
        cursor.execute("insert into ww_dep_id values(%s,%s) on conflict do nothing", (v,k))
    print("finishing init ww ids")

# \copy ps_store_id_store_name_mapping (store_name, store_id, store_address, store_island_key) FROM 'stores_ps.csv' WITH (FORMAT csv, HEADER false);
# \copy nw_store_id_store_name_mapping (store_name, store_id, store_address, store_island_key) FROM 'stores_nw.csv' WITH (FORMAT csv, HEADER false);
# \copy ww_store_id_store_name_mapping (store_name, store_id, store_address) FROM 'stores_ww.csv' WITH (FORMAT csv, HEADER false);
def insert_store_name_maps(cursor):
    fs_cols = ('store_name', 'store_id', 'store_address', 'store_island_key')
    ww_cols = ('store_id', 'store_name', 'store_address')

    store_csv_map_to_table = [
        ("ps_store_id_store_name_mapping", CURR_DIR / "stores_ps.csv", fs_cols),
        ("nw_store_id_store_name_mapping", CURR_DIR / "stores_nw.csv", fs_cols),
        ("ww_store_id_store_name_mapping", CURR_DIR / "stores_ww.csv", ww_cols)
    ]
    for store_table_name, csv_file_path, col_type in store_csv_map_to_table:
        cols_string = ", ".join(col_type) 
        sql_query = f"COPY {store_table_name}({cols_string}) FROM STDIN WITH (FORMAT csv, HEADER false)"

        with open(csv_file_path, "r", encoding="utf-8") as f:
            cursor.copy_expert(sql_query, f)


def main():
    main_url = sys.argv[1]

    print(main_url)
    
    print("starting init")
    init_tables(main_url)
    print("success")


if __name__ == "__main__":
    main()







