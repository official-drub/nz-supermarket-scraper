# NZ Supermarket Product Data Scraper

Scrapes product and pricing data from the big 3 supermarkets in nz
- Woolworths (WW)
- Paknsave (PS)
- NewWorld (NW)
Then normalises it and loads it into PostgreSQL so prices can be compared by barcode across franchises and stores

|Franchise|Site|How its scraped|
|---------|----|---------------|
|Woolworths|https://www.woolworths.co.nz/|Plain requests against the products api*|
|Paknsave|https://www.paknsave.co.nz/|Playwright harvests an auth session then requests against the api|
|NewWorld|https://www.newworld.co.nz/|Same as Paknsave (Both run on the foodstuffs platform)|


*this may break in the future from recent updates to their site, however it works currently

Status: work in progress. The happy path (BUILD->SCRAPE->PARSE->DB) has been run end-to-end successfully; TODO


How it works:
![how it works](how_it_works.png)
1. Scraping: each scraper go through its list/slice of stores and catagories and dumps the raw API responses to disk as `page_X.json`.
2. Parsing: (per franchise) parsers stream those JSON files and yield flat product dicts (also prices are converted to integer cents, not short because there are expenive items in supermarkets).
3. Write To DB: `parser_to_db.py` batches the rows and upserts them into Postgres. A row is updated when a value has actually changed this ensures less useless writes.

## Barcodes are the common key:
WW returns a real barcode for each product. However the foodstuffs stores only expose an internal sku (e.g 5269559-EA-000,9420027623036)
- To respect the servers and avoid hammering the endpoints the FS scraper seeds a set of already known sku to barcode pairs upon start (from a csv or the db; env vars)
- Looks up the barcode only for skus that havent been seen
- appends new pairs mapped_PID_BC_<ps|nw>.csv in its output folder

parser_to_db.py loads that CSVs into the barcode_foodstuffs_sku table before loading any of the products, so Foodstuffs rows can be joined to barcode_name

**(WARNING: if neither PID_MAP_CSV_PATH nor DB_URL env vars are avalible, the Foodstuffs scraper starts with an empty map and will request a barcode for each product (this is hammering) and you will get banned. So dont do this. To clarify this is not a bug, you are warned, this should only be done if you are establishing an inital set of pairs (however it is in this repo already), if you are establishing then increase the time per request)**


## Requirments
- Docker
- Bash (on windows use git bash or wsl)
- A (reachable) PostgreSQL instance
- Optional: Python 3.13 if running anything outside of Docker

Setup
1. Env
Create an `.env` file at the project root
e.g `DB_URL=postgresql://postgres:postgres@host.docker.internal:5432/SUPERMARKET_DB`

2. DB
create the db then init it - this reqs Python 3.13
`python init_product_db.py`
The schema is in products_schema.sql. store mapping tables; *_store_id_store_name_mapping and department tables (ww_dep_id, fs_dep_id) are referenced by FKs from price tables **hence they must be populated prior to parsing** or else inserts will fail. However do not fret! if you didnt do this but still ran the scraper, if you remember previously in the How it works section your data will not be lost! as its all just Jsons!

3. Build, scrape, parse
`INDEX=0 TOTAL_MACHINES=100 ./run.sh build`
`INDEX=0 TOTAL_MACHINES=100 ./run.sh scrape`
`INDEX=0 TOTAL_MACHINES=100 ./run.sh parse`
they can also be chained: `INDEX=0 TOTAL_MACHINES=100 ./run.sh build scrape` or `INDEX=0 TOTAL_MACHINES=100 ./run.sh build scrape parse` 
however you want `INDEX=0 TOTAL_MACHINES=100 ./run.sh <build|scrape|parse>`


## Running on Multiple Machines
To effeciently scrape you should treat machines as nodes and use a centeral db
Stores are split evenly between machines. Give each machine a unique index (`INDEX=0`) and the same number of machines (`TOTAL_MACHINES=100`)
e.g you have 4 machines/nodes (A, B, C, D):
```
INDEX=0 TOTAL_MACHINES=4 ./run.sh build scrape parse        <--- Might be on machine A
INDEX=1 TOTAL_MACHINES=4 ./run.sh build scrape parse        <--- Might be on machine B
INDEX=2 TOTAL_MACHINES=4 ./run.sh build scrape parse        <--- Might be on machine C
INDEX=3 TOTAL_MACHINES=4 ./run.sh build scrape parse        <--- Might be on machine D
```
this addresses the issue with having a singluar IP hitting the endpoint too many times, by splitting the work load between different ips

The default is `INDEX=0` `TOTAL_MACHINES=1` which is a singular machine

## Running with docker
```
# woolworths
python -m woolworths.wwscraper -i 0 -t 1

# fs (ps and nw)
python -m foodstuffs.foodstuffs_scraper -s paknsave -i 0 -t 1
python -m foodstuffs.foodstuffs_scraper -s newworld -i 0 -t 1
```
outside of docker the output is written to the scrapers own output folder; `woolworths/output`, `foodstuffs/paknsave/output`, `foodstuffs/newworld/output`

## ENV VARS
vars:
- DB_URL, postgres url connection string, scraper needs it to seed (the sku-barcode pairs) and parser needs it to know where to write to
- PID_MAP_CSV_PATH, is used by the foodstuffs scrapers, this is optional, seeds the sku-barcode pairs via a csv given a path

## CLI
|flag|Details|
|----|-------|
|`-i`, `--index`| machine index |
|`-t`, `--total`| total num of machines running the job |
|`-s`, `--store`| foodstuffs only paknsave or newworld are the only valid options |

## Disclaimer
this project does talk to unoffical APIs. Intended for personal and educuation use only


## TODO
- [ ] clean up `init_product_db.py` works needs tidying
- [ ] Add tests; parser unit testing against the sample page_x.json, dollars_to_cents edge cases, deduper, and the batch upsert handlers against local test db
- [ ] adding retries to wwscraper.py
- [ ] clean up everything once more








