import requests
import csv
import json
import time
import random
import math
import argparse
import logging
import sys

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from log_util import get_logger



@dataclass(frozen=True)
class Config:
    machine_index: int
    total_machines: int
    CURR_FILE: Path
    OUTPUT_DIR: Path

    MAX_PAGE_SIZE: int = 120
    MIN_DELAY: float = 0.25
    MAX_DELAY: float = 1.0
    WORKERS: int = 2
    curr_time: str = field(default_factory = lambda: datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))

    api_url: str = "https://www.woolworths.co.nz/api/v1/products"


class WWScraper:
    def __init__(self, config: Config) -> None:
        self.config: Config = config
        self.logger: logging.Logger = self.init_logger()

        # will have to manually update
        self.x_ui_ver: str = "7.75.24"
        self.headers: dict[str, str] = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-NZ,en;q=0.9",
            "Referer": "https://www.woolworths.co.nz/",
            "x-requested-with": "OnlineShopping.WebApp",
            "x-ui-ver": self.x_ui_ver   
        }

    def init_logger(self):
        log_dir_path: Path = self.config.OUTPUT_DIR / f"log_machine_{self.config.machine_index}"
        return get_logger(
            name=f"WWScraper_{self.config.machine_index}", 
            log_dir_path=log_dir_path, 
            wants_console_logger=True)


    
    def buildURL(
            self,
            cata: str, 
            currPage: int =1) -> str:
        return(
            f"{self.config.api_url}?"
            f"dasFilter=Department%3B%3B{cata}%3Bfalse"
            f"&target=browse"
            f"&page={currPage}"
            f"&inStockProductsOnly=false"
            f"&size={self.config.MAX_PAGE_SIZE}"
        )

    def session_generator(self) -> requests.Session:
        session: requests.Session = requests.Session()
        session.headers.update(self.headers)
        return session

    def get_all_depts(self):
        return [
            "fruit-veg",
            "meat-poultry",
            "fish-seafood",
            "fridge-deli",
            "bakery",
            "frozen",
            "pantry",
            "beer-wine",
            "drinks",
            "health-body",
            "household",
            "baby-child",
            "pet"
        ]

    

    # TODO add retry from failure this is NOT relaible https://www.youtube.com/watch?v=hFkcP8-Xcek

    def set_store(self, addressId: str, session: requests.Session):
        pickUpAdrURL: str = "https://www.woolworths.co.nz/api/v1/fulfilment/my/pickup-addresses"
        payload: dict[str, str] = {"addressId": addressId}
        s = session.put(url=pickUpAdrURL, json=payload)
        if (s.status_code == 200):
            self.logger.info(f"store {addressId} successfully set: {session.cookies.get("cw-lrkswrdjp")}")
            return True
        else:
            self.logger.error(f"FAILED {s.status_code}, storeid {addressId}")
            return False;

    def save_raw_json(self, dir: Path, data: dict[str, object], page: int) -> None:
        with open(f"{dir}/page_{page}.json", "w", encoding="utf-8") as file:
            json.dump(data, file)
                
    def product_getter(self, catagoryList: list[str], storeId: str, session: requests.Session) -> None:
        if (not self.set_store(addressId=storeId, session=session)):
            self.logger.error(f"skipping store {storeId}, setStore failure")
            return
        
        session.get(url="https://www.woolworths.co.nz/")
        
        for cata in catagoryList:
            productJsonDir = self.config.OUTPUT_DIR / "productJson"
            productJsonDir.mkdir(parents=True, exist_ok=True)
            dir = productJsonDir / str(storeId) / cata
            dir.mkdir(parents=True, exist_ok=True)

            currPage = 1
            while True:
                url = self.buildURL(cata=cata, currPage=currPage)
                self.logger.info(f"storeid: {storeId}, catagory: {cata}, page: {currPage}")
                response = session.get(url=url)

                if (response.status_code!=200):
                    self.logger.error(f"SKIPPING, status code: {response.status_code}, storeid: {storeId} page: {currPage}, catagory: {cata}, url: {url}")
                    break

                data = response.json()
                items = data.get("products", {}).get("items", [])
                if not items:
                    self.logger.info(f"done, total pages: {currPage-1}, no items found in {cata} for {storeId} in {url}")
                    break;
                time.sleep(random.uniform(self.config.MIN_DELAY, self.config.MAX_DELAY))
                
                self.save_raw_json(dir=dir, data=data, page=currPage)
                currPage += 1
            time.sleep(random.uniform(self.config.MIN_DELAY, self.config.MAX_DELAY))



    def get_all_store_ids(self) -> list[str]:
        ids: list[str] = []
        # ids.append(1225718)
        csv_path: Path = self.config.CURR_FILE / "util" / "storesIds.csv"
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                if row:
                    ids.append(row[0])
        return ids


    def get_req_store_ids(self) -> list[str]:
        all_sids: list[str] = self.get_all_store_ids();
        total_ids = len(all_sids)
        if (total_ids == 0):
            return []
        part = math.ceil(total_ids / self.config.total_machines)
        start_idx = self.config.machine_index * part;
        end_idx = min(start_idx + part, total_ids)

        print(f"start {start_idx}, end {end_idx}")
        self.logger.info(f"start {start_idx}, end {end_idx}")
        return all_sids[start_idx:end_idx]

        
    def scrape_store(self, sid: str) -> None:
        session = self.session_generator();
        self.product_getter(catagoryList=self.get_all_depts(), storeId=sid, session=session)

    def run(self) -> None:
        start_time: float = time.time()
        msg: str = f"machine {self.config.machine_index}/{self.config.total_machines} starting" 
        print(msg)
        self.logger.info(msg)

        req_store_ids = self.get_req_store_ids()
        if (not req_store_ids):
            self.logger.warning("no store ids for this machine or csv is empty")
            return;
        with ThreadPoolExecutor(max_workers=self.config.WORKERS) as executor:
            executor.map(self.scrape_store, req_store_ids)
        end_time: float = time.time()
        total_time = end_time - start_time;
        finished_msg = f"woolworths scraping complete on machine {self.config.machine_index} in {total_time}"
        self.logger.info(finished_msg)
        print(finished_msg)


def parse_args() -> Config:
    curr_file: Path = Path(__file__).parent
    output_dir: Path = curr_file / "output"
    parser = argparse.ArgumentParser(
        prog="wwscraper",
        description="wwscraper that can be parallelized"
    )

    parser.add_argument("-i", "--index", required=True, type=int, help="index of this machine [0..total) remember 0-indexed!")
    parser.add_argument("-t", "--total", required=True, type=int, help="total Number of machines running this job")
    args = parser.parse_args()

    if (args.index < 0 or args.index >= args.total):
        print(f"ERROR: --index (-i) must be between 0 and {args.total-1}, instead got {args.index}")
        sys.exit(1)

    return Config(
        machine_index=args.index, 
        total_machines=args.total,
        CURR_FILE=curr_file,
        OUTPUT_DIR=output_dir
    )



if __name__ == "__main__":
    config: Config = parse_args();
    scraper = WWScraper(config)
    scraper.run();



# def init_logger(self):
#     log_dir_path: Path = self.config.OUTPUT_DIR / f"log_machine_{self.config.machine_index}"
#     return get_logger(
#         name=f"WWScraper_{self.config.machine_index}", 
#         log_dir_path=log_dir_path, 
#         wants_console_logger=True)
    
#     # log_dir_path: Path = self.config.OUTPUT_DIR / f"log_machine_{self.config.machine_index}"
#     # log_dir_path.mkdir(parents=True, exist_ok=True)
#     # log_file_path: Path = log_dir_path / f"log_{self.config.curr_time}.log"

#     # logger: logging.Logger = logging.getLogger(f"WWScraper_{self.config.machine_index}");
#     # logger.setLevel(logging.INFO)

#     # file_handler: logging.FileHandler = logging.FileHandler(log_file_path, mode="w", encoding="utf-8")
#     # log_format: str = "[%(levelname)s] => %(asctime)s => %(name)s => %(message)s"
#     # file_handler.setFormatter(logging.Formatter(fmt=log_format))
#     # logger.addHandler(file_handler);

#     # print("LOGGER INITAIALISED OK")
#     # logger.info("LOGGER INITAIALISED OK")
#     # return logger
    