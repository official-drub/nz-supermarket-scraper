import psycopg2
import os
import csv
import logging
import sys

import parsers.newworld_parser_v1 as nwp
import parsers.paknsave_parser_v1 as psp
import parsers.woolworths_parser_v1 as wwp

from typing import TypedDict, NamedTuple
from pathlib import Path
from psycopg2.extras import execute_values
from log_util import get_logger
from psycopg2.extensions import connection as PgConnection, cursor as PgCursor

CURR_DIR = Path(__file__).parent
LOG_DIR = CURR_DIR / "parser_to_db_logs"
FS_DIR = CURR_DIR / "foodstuffs"
BATCH_SIZE = 5000
ROWS_PER_INSERT_STATEMENT_SIZE = 5000
STORE_ORDER = ["ww", "ps", "nw"]
MAPPING_CSVS: dict[str, Path] = {
    "ps": FS_DIR / "paknsave" / "output" / "mapped_PID_BC_ps.csv",
    "nw": FS_DIR / "newWorld" / "output" / "mapped_PID_BC_nw.csv"
}

class ProductDict(TypedDict, total=False):
    pid: str|None
    sid: str|None
    p_name: str|None
    p_price_normal: int|None
    p_price_standardized: str|None
    p_aval: bool|None
    p_cata: int|str|None

    # ww only
    p_img: str|None
    p_price_save: int|None
    p_price_member: int|None

class BarcodeNameVal(NamedTuple):
    pid: str
    name: str|None
    img: str|None



def deduper[T: tuple[object, ...]](vals: list[T], *key_idxs: int) -> list[T]:
    seen = {
        tuple(val[i] for i in key_idxs): val for val in vals
    }
    return list(seen.values())


def _insert_into_barcode_name_table(cursor: PgCursor, barcode_name_table_vals: list[BarcodeNameVal]) -> None:
    execute_values(cursor, """
    insert into barcode_name (barcode, product_name, img)
    values %s
    on conflict (barcode)
    do update set
        product_name = EXCLUDED.product_name, 
        img = EXCLUDED.img
    """, barcode_name_table_vals, page_size=ROWS_PER_INSERT_STATEMENT_SIZE)

def _insert_into_woolworths(cursor: PgCursor, woolworth_table_vals: list[tuple[object, ...]]) -> None:
    execute_values(cursor, """
    insert into woolworths as w
        (store_id, barcode, price, save_price, member_price, price_per_unit, stock_level, dep_id) 
    values %s
    on conflict (store_id, barcode)
    do update set
        price = EXCLUDED.price,
        save_price = EXCLUDED.save_price,
        member_price = EXCLUDED.member_price,
        price_per_unit = EXCLUDED.price_per_unit,
        stock_level = EXCLUDED.stock_level,
        dep_id = EXCLUDED.dep_id
    where (
        w.price,
        w.save_price,
        w.member_price,
        w.price_per_unit,
        w.stock_level,
        w.dep_id
    ) is distinct from
    (
        EXCLUDED.price,
        EXCLUDED.save_price,
        EXCLUDED.member_price,
        EXCLUDED.price_per_unit,
        EXCLUDED.stock_level,
        EXCLUDED.dep_id
    )
    """, woolworth_table_vals, page_size=ROWS_PER_INSERT_STATEMENT_SIZE)

def _insert_into_barcode_foodstuff_sku_table(cursor: PgCursor, sku_vals: list[tuple[object, ...]]):
        execute_values(cursor, """
            insert into barcode_foodstuff_sku (internal_sku, barcode) 
            values %s
            on conflict (internal_sku)
            do nothing
        """, sku_vals, page_size=ROWS_PER_INSERT_STATEMENT_SIZE)

def _insert_into_fs_store_fullname_table(fs_store_fullname: str, cursor: PgCursor, fs_vals: list[tuple[object, ...]]):
    # injection prone but it shouldnt matter since there is nothing else using this
    
    execute_values(cursor, f"""
        insert into {fs_store_fullname} as s (store_id, internal_sku, price, price_per_unit, stock_level, dep_id) 
        values %s
        on conflict (store_id, internal_sku)
        do update set
            price = EXCLUDED.price,
            price_per_unit = EXCLUDED.price_per_unit,
            stock_level = EXCLUDED.stock_level,
            dep_id = EXCLUDED.dep_id
        where (
            s.price,
            s.price_per_unit,
            s.stock_level,
            s.dep_id
        ) is distinct from (
            EXCLUDED.price,
            EXCLUDED.price_per_unit,
            EXCLUDED.stock_level,
            EXCLUDED.dep_id
        )
        """, fs_vals, page_size=ROWS_PER_INSERT_STATEMENT_SIZE)

    
def insert_ww_prods_batch(batch: list[ProductDict], cursor: PgCursor, seen: set[str]):
    barcode_name_table_vals: list[BarcodeNameVal] = []
    woolworth_table_vals: list[tuple[object, ...]] = []

    for el in batch:
        pid = el.get("pid")
        if (not pid):
            continue
        if (pid not in seen):
            barcode_name_table_vals.append(BarcodeNameVal(pid=pid, name=el.get("p_name"), img=el.get("p_img")))
        woolworth_table_vals.append((
            el.get("sid"), 
            pid, 
            el.get("p_price_normal"), 
            el.get("p_price_save"), 
            el.get("p_price_member"), 
            el.get("p_price_standardized"), 
            el.get("p_aval"), 
            el.get("p_cata")))


    barcode_name_table_vals = deduper(barcode_name_table_vals, 0)
    woolworth_table_vals = deduper(woolworth_table_vals, 0, 1)

    if (barcode_name_table_vals):
        _insert_into_barcode_name_table(cursor=cursor, barcode_name_table_vals=barcode_name_table_vals)

    _insert_into_woolworths(cursor=cursor, woolworth_table_vals=woolworth_table_vals)
    seen.update(val.pid for val in barcode_name_table_vals)
 

def insert_fs_prods(fs_store_fullname: str, batch: list[ProductDict], cursor: PgCursor, seen: set[str]):
    sku_vals: list[tuple[object, ...]] = []
    fs_vals: list[tuple[object, ...]] = []
    barcode_name_updates: list[tuple[object, ...]] = []

    for el in batch:
        pid = el.get("pid")
        if (not pid):
            continue
        
        fs_vals.append(
            (el.get("sid"), 
             pid, 
             el.get("p_price_normal"), 
             el.get("p_price_standardized"), 
             el.get("p_aval"), 
             el.get("p_cata")))
        if (pid not in seen):
            fs_img = f"https://a.fsimg.co.nz/product/retail/fan/image/500x500/{pid.split("-")[0]}.png"
            sku_vals.append((pid, None))
            barcode_name_updates.append((el.get("p_name"), fs_img, pid))


    sku_vals = deduper(sku_vals, 0)
    fs_vals = deduper(fs_vals, 0, 1)
    barcode_name_updates = deduper(barcode_name_updates, 2)

    if (sku_vals):
        _insert_into_barcode_foodstuff_sku_table(cursor, sku_vals)
    _insert_into_fs_store_fullname_table(fs_store_fullname, cursor, fs_vals)

    if (not barcode_name_updates):
        return
    execute_values(cursor, 
        """
            with py_batch as (
                select * from (values %s) as p(p_name, p_img, internal_sku)
            ),

            mapped_batch as (
                select bfs.barcode, p.p_name, p.p_img,
                    row_number() over (partition by bfs.barcode order by p.internal_sku) as row_num
                from py_batch p
                join barcode_foodstuff_sku bfs on bfs.internal_sku = p.internal_sku
                where bfs.barcode is not null
            )

            insert into barcode_name (barcode, product_name, img)
            select barcode, p_name, p_img
            from mapped_batch
            where row_num = 1
            on conflict (barcode) do update set 
                product_name = COALESCE(barcode_name.product_name, EXCLUDED.product_name), 
                img = COALESCE(barcode_name.img, EXCLUDED.img)
        """, barcode_name_updates)
    seen.update(val[0] for val in sku_vals)


    

    
def insert_ps_prods_batch(batch: list[ProductDict], cursor: PgCursor, seen: set[str]):

    insert_fs_prods(fs_store_fullname="paknsave", batch=batch, cursor=cursor, seen=seen)


def insert_nw_prods_batch(batch: list[ProductDict], cursor: PgCursor, seen: set[str]):
    insert_fs_prods(fs_store_fullname="newworld", batch=batch, cursor=cursor, seen=seen)



STORES: dict[str, dict[str, object]] = {
    "ww": {
        "parser": wwp.total_parser,
        "handler": insert_ww_prods_batch
    },
    "ps": {
        "parser": psp.total_parser,
        "handler": insert_ps_prods_batch
    },
    "nw": {
        "parser": nwp.total_parser,
        "handler": insert_nw_prods_batch
    }
}




def _write_batch(conn: PgConnection, handler: object, batch: list[dict[str, object]], seen: set[str]):
    try:
        with conn.cursor() as cursor:
            handler(batch, cursor, seen)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

def _try_write_batch(conn: PgConnection, handler: object, batch: list[dict[str, object]], seen: set[str], logger: logging.Logger) -> bool:
    try:
        _write_batch(conn=conn, handler=handler, batch=batch, seen=seen)
        return True
    except Exception as batch_error:
        logger.error(f"batch of {len(batch)} rows failed! {batch_error}")
        return False
    
def run_store(store_key: str, db_url: str, batch_size: int):
    logger: logging.Logger = get_logger(name=f"ParserToDBLogger_{store_key}", 
                                        log_dir_path=LOG_DIR / f"{store_key}_log", 
                                        wants_console_logger=True)

    store: dict[str, object]|None = STORES.get(store_key)
    if (store is None):
        raise ValueError(f"invalid store key {store_key}")
    parser, handler = store["parser"], store["handler"]

    count = 0
    failed_batches = 0
    failed_rows = 0
    seen: set[str] = set()
    batch: list[dict[str, object]] = []
    conn: PgConnection = psycopg2.connect(dsn=db_url)

    def write_batch_to_db():
        nonlocal failed_batches, failed_rows, batch
        if (_try_write_batch(conn=conn, handler=handler, batch=batch, seen=seen, logger=logger)):
            logger.info(f"{store_key}: {count} records done")
            # batch = []
        else:
            failed_batches+=1
            failed_rows += len(batch)
        batch = []

    try:
        for el in parser():
            batch.append(el)
            count+=1
            if (len(batch) >= batch_size):
                write_batch_to_db()
        if (batch):
            write_batch_to_db()
    except Exception as parser_error:
        logger.error(f"parser itteration failed for store {store_key}: {parser_error}")
        raise
    finally:
        conn.close()

    if (failed_batches):
        raise RuntimeError(f"number of failed batches for {store_key} are: {failed_batches}; {failed_rows}/{count} rows not written")

    return count

    
def insert_mapped_fs_skus(conn: PgConnection, csv_path: Path, logger: logging.Logger): 
    if (not csv_path.exists()):
        logger.warning(f"mapping csv not found, skipping {csv_path}")
        return
    rows: list[tuple[str, str]] = []

    with open(csv_path, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        
        for row in reader:
            if (len(row) != 2):
                continue
            sku = str(row[0])
            bc = str(row[1])
            rows.append((sku, bc))

    rows = deduper(rows, 0)
    if not rows:
        return

    logger.info(f"MAPPING {len(rows)} skus to barcodes from {csv_path.name}")
    with conn.cursor() as cursor:        
        execute_values(cursor, """
            insert into barcode_foodstuff_sku (internal_sku, barcode) 
            values %s
            on conflict (internal_sku) do update set barcode = EXCLUDED.barcode
        """, rows, page_size=ROWS_PER_INSERT_STATEMENT_SIZE)

    conn.commit()
    logger.info(f"MAPPED OK {len(rows)} skus to barcodes from {csv_path.name}")


def parse_and_insert():
    logger: logging.Logger = get_logger(name="ParserToDBLogger_parse_and_insert", 
                                        log_dir_path=LOG_DIR / "parse_and_insert_log", 
                                        wants_console_logger=True)
    
    db_url: str|None = os.getenv("DB_URL")
    if (not db_url):
        logger.error("failed because there was no DB_URL in the environment vars, remember DB_URL=<db url>")
        sys.exit(1)

    conn: PgConnection = psycopg2.connect(dsn=db_url)
    try:
        for path in MAPPING_CSVS.values():
            insert_mapped_fs_skus(conn=conn, csv_path=path, logger=logger)
    except Exception as e:
        logger.fatal("sku mapping failed therefore aborting!")
        sys.exit(1)
    finally:
        conn.close()

    failed: list[str] = []
    for store_key in STORES.keys():
        try:
            logger.info(f"{store_key} starting")
            logger.info(f"{store_key} finished succesfully: {run_store(store_key=store_key, db_url=db_url, batch_size=BATCH_SIZE)} RECORDS OK")
        except Exception as e:
            logger.error(f"{store_key} FAILED")
            failed.append(store_key)

    if (failed):
        logger.error(f"stores that failed are: {failed}")
        sys.exit(1)
    logger.info("OK ALL STORES COMPLETED SUCCESSFULLY")


def main():
    print("starting parsing")
    parse_and_insert()
    print("finished parsing")
    

if __name__ == "__main__":
    main()
