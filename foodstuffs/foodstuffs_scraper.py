import requests
import csv
import json
import time
import random
import math
import argparse
import logging
import sys
from foodstuffs import mapped_pid_bc as mapping_util
from log_util import get_logger

from http import HTTPStatus
from playwright.sync_api import sync_playwright, Request as PWReq, Response as PWResp
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field



"""
python foodstuffs_scraper.py -s <paknsave or newworld> -i 0 -t 4
python foodstuffs_scraper.py -s <paknsave or newworld> -i 1 -t 4
python foodstuffs_scraper.py -s <paknsave or newworld> -i 2 -t 4
python foodstuffs_scraper.py -s <paknsave or newworld> -i 3 -t 4

max: python foodstuffs_scraper.py -s <paknsave or newworld> -i <n-1> -t <n>
"""


@dataclass(frozen=True)
class Store:
    franchise: str
    key: str
    site: str
    api: str

    dir: str

    @property 
    def start_url(self) -> str: 
        return f"{self.site}/shop/category/fruit-and-vegetables?pg=1"
    @property 
    def search_url(self) -> str: 
        return f"{self.api}/v1/edge/search/paginated/products"
    @property 
    def kick_off_url(self) -> str: 
        return f"{self.site}/api/user/get-current-user"

    def store_url(self, sid: str) -> str:
        return f"{self.api}/v1/edge/cart/store/{sid}"
    def prodcut_url(self, sid: str, pid: str) -> str:
        return f"{self.api}/v1/edge/store/{sid}/product/{pid}"

@dataclass
class Config:
    store: Store

    machine_index: int
    total_machines: int
    CURR_FILE: Path
    OUTPUT_DIR: Path
    DATA_DIR: Path

    PAGE_SIZE: int = 50
    MIN_DELAY: float = 0.6
    MAX_DELAY: float = 1.3
    TOKEN_REFRESH_TIME: int = 12 # seconds before token expiry to refresh
    MAX_RETRIES: int = 3

    curr_time: str = field(default_factory = lambda: datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))

    @property 
    def product_json_dir(self) -> Path: 
        return self.OUTPUT_DIR / "productJson"
    @property 
    def mapping_path(self) -> Path: 
        return self.OUTPUT_DIR / f"mapped_PID_BC_{self.store.key}.csv"
    # log_path = property(lambda self: self.OUTPUT_DIR / f"log_machine_{self.machine_index}" / f"log_{self.curr_time}")

@dataclass
class BrowserSession:
    """the stuff we harvest from the playwright, hence the 15 sec delay at the start"""
    headers: dict[str, str] = field(default_factory=dict[str, str])
    cookies: dict[str|None, str|None] = field(default_factory=dict[str|None, str|None])
    jwt: str|None = None
    user_agent: str|None = None
    sec_ch_ua: str|None = None
    sec_ch_ua_platform: str|None = None
    fingerprint_user: str|None = None
    fingerprint_guest: str|None = None
    expires_time: str|None = None

@dataclass
class TokenState:
    fingerprint_user: str|None = None
    fingerprint_guest: str|None = None
    expires_at: float|None = None


STORES: dict[str, Store] = {
    "paknsave": Store(franchise="paknsave", key="ps", site="https://www.paknsave.co.nz", api="https://api-prod.paknsave.co.nz", dir="paknsave"),
    "newworld": Store(franchise="newworld", key="nw", site="https://www.newworld.co.nz", api="https://api-prod.newworld.co.nz", dir="newWorld")
}

RETRY_STATUS_CODES: list[int] = [
    HTTPStatus.TOO_MANY_REQUESTS, 
    HTTPStatus.INTERNAL_SERVER_ERROR, 
    HTTPStatus.BAD_GATEWAY, 
    HTTPStatus.GATEWAY_TIMEOUT, 
    HTTPStatus.SERVICE_UNAVAILABLE, 
    *range(520, 524+1)] # cloudflare specific    

def parse_iso_time(dateStr: str) -> float:
    return datetime.fromisoformat(dateStr[:-1] + '+00:00').timestamp()

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))




def retry(max_retries: int|None = None):
    def dec(func):
        def enhanced_func(self, *args, **kwargs):
            retries: int = max_retries if (max_retries is not None) else self.config.MAX_RETRIES
            for tri in range(retries+1):
                try:
                    return func(self, *args, **kwargs)
                except Exception as e:
                    self.logger.warning(f"{func.__name__} => {e} => on try {tri}/{retries+1}")
                    if (tri < retries):
                        time.sleep(random.uniform(2, 5)*(tri+1))
            self.logger.error(f"{func.__name__} => FAILED => after {retries+1} trys")
            return None
        return enhanced_func
    return dec
            



# def retry(func, max_ret = 3):
#     def wrapper(*args, **kwargs):
        
#         for attempt in range(max_ret+1):
#             try:
#                 return func(*args, **kwargs)
#             except Exception as e:
#                 nwScraperLogger.warning(f"{e},  retrying")
#                 if (attempt < max_ret):
#                     time.sleep(random.uniform(2, 5)*attempt)
#         nwScraperLogger.error(f"failed after {max_ret} retries")
#         return {
#             "access_token:": None,
#             "expires_time": None
#         }
#     return wrapper




class FoodStuffsScraper:
    def __init__(self, config: Config):
        self.config: Config = config
        self.store: Store = config.store
        self.logger: logging.Logger = self._init_logger()
        self.known_pids: set[str] = self._init_curr_mapped_pids()


    def _init_logger(self):
        log_dir_path: Path = self.config.OUTPUT_DIR / f"log_machine_{self.config.machine_index}"
        return get_logger(name=f"FoodStuffsScraper_{self.config.machine_index}",
                   log_dir_path=log_dir_path,
                   wants_console_logger=True)

    def _init_curr_mapped_pids(self) -> set[str]:    
        seed = mapping_util.seed_bc_map();
        
        self.config.mapping_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.config.mapping_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for pid, bc in seed.items():
                writer.writerow([pid, bc])
        return set(seed.keys())
    
    def _request(
            self, 
            session_func,
            url: str, 
            **kwargs) -> requests.Response:
        # basically takes the session.post or .get and adds safety around it
        req_timeout: int = 30
        kwargs.setdefault("timeout", req_timeout)
        name = session_func.__name__.upper()
        max_retries = self.config.MAX_RETRIES
        resp, error = None, None

        for tri in range(max_retries+1):
            error = None
            try:
                resp: requests.Response = session_func(url, **kwargs)
                status_code = resp.status_code
                if (status_code not in RETRY_STATUS_CODES):
                    return resp
                snag = f"status_code {status_code}"
            except requests.RequestException as re:
                resp, error = None, re
                snag = str(error)

            if (tri < max_retries):
                back_off_time = random.uniform(2, 5)*(tri+1) 
                self.logger.warning(f"{name} {url} => {snag} => retrying => on try {tri}/{max_retries+1} in {back_off_time}secs")
                time.sleep(back_off_time)
        self.logger.error(f"{name} {url} => FAILED => after {max_retries+1} trys ({snag})")
        if (error):
            raise error
        return resp

    def get_req_store_ids_and_region(self) -> list[dict[str, str]]:
        all_sids = self.get_all_stores()
        total_ids = len(all_sids)
        if (total_ids == 0):
            return []
        
        part = math.ceil(total_ids / self.config.total_machines)
        start_idx = self.config.machine_index * part;
        end_idx = min(start_idx + part, total_ids)

        # print(f"start {start_idx}, end {end_idx}")
        self.logger.info(f"start {start_idx}, end {end_idx}")
        return all_sids[start_idx:end_idx]

    def get_all_stores(self):
        return [
            {
                "id": s["id"],
                "region": s["region"]
            }
            for s in load_json(self.config.DATA_DIR / "stores.json")["stores"]
        ]

    def _delay(self) -> None:
        time.sleep(random.uniform(self.config.MIN_DELAY, self.config.MAX_DELAY))

    def _catagories(self) -> list[str]:
        return [c["name"] for c in load_json(self.config.DATA_DIR / "catagories.json")]

    @retry()
    def _harvester(self) -> BrowserSession:
        store: Store = self.store
        actual_bs = BrowserSession()

        def on_kickoff_req(request: PWReq) -> None:
            post = request.post_data
            if (request.url == store.kick_off_url and post):
                try:
                    body = json.loads(post)
                except ValueError:
                    self.logger.warning("could not parse the kick off post req body")
                    return
                actual_bs.fingerprint_user = body.get("fingerprintUser")
                actual_bs.fingerprint_guest = body.get("fingerprintGuest")

        def on_kickoff_resp(response: PWResp) -> None:
            if store.kick_off_url == response.url:
                try:
                    actual_bs.expires_time = response.json().get("expires_time")
                except Exception as e:
                    self.logger.warning(f"could not read the kickoff's resp: {e}")
        
        def on_search_req(request: PWReq) -> None:
            if (request.url == store.search_url):
                headers: dict[str, str] = request.headers
                actual_bs.headers = headers
                actual_bs.jwt = headers.get("authorization") # includes Bearer
                actual_bs.sec_ch_ua = headers.get("sec-ch-ua")
                actual_bs.sec_ch_ua_platform = headers.get("sec-ch-ua-platform")
                actual_bs.user_agent = headers.get("user-agent") # should be same as fingerprintGuest


        with sync_playwright() as playwright:
            print("playwright browswer begins")
            start_url = store.start_url
            chrome = playwright.chromium
            browser = chrome.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()
            reloadtime = random.randint(10000, 15000)
            print("stuff set")

            page.on("request", on_kickoff_req)
            page.on("response", on_kickoff_resp)
            page.on("request", on_search_req)

            page.goto(start_url)
            
            page.wait_for_timeout(reloadtime)
            actual_bs.cookies = {
                c.get("name"): c.get("value") for c in context.cookies()
            }
        if (not (actual_bs.expires_time 
                and actual_bs.jwt 
                and actual_bs.user_agent 
                and actual_bs.sec_ch_ua 
                and actual_bs.sec_ch_ua_platform)):
            raise ValueError("playwright harvesting was incomplete")
        return actual_bs

    def _get_headers(self, jwt: str, user_agent: str, sec_fetch_site: str, sec_ch_ua_platform: str, sec_ch_ua: str) -> dict[str, str|bytes]:
        return {
            'accept': '*/*',
            'accept-language': 'en-NZ,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
            'authorization': jwt,
            'content-type': 'application/json',
            'dnt': '1',
            'origin': self.store.site,
            'priority': 'u=1, i',
            'referer': f'{self.store.site}/',
            'sec-ch-ua': sec_ch_ua, #'"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"'
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': sec_ch_ua_platform, #'"Windows"'
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': sec_fetch_site,
            'user-agent': user_agent
            #'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36' docker might flag but if it doesnt work, gotta go back to the windows
        }
    
    def _create_session(self, browser_session: BrowserSession) -> requests.Session:
        s: requests.Session = requests.Session()
        bs_jwt = browser_session.jwt
        bs_ua = browser_session.user_agent
        bs_sec_ch_ua_platform = browser_session.sec_ch_ua_platform
        bs_sec_ch_ua = browser_session.sec_ch_ua
        headers: dict[str, str|bytes] = {}
        if (bs_jwt and bs_ua and bs_sec_ch_ua_platform and bs_sec_ch_ua):
            headers = self._get_headers(
                jwt=bs_jwt, 
                user_agent=bs_ua,
                sec_fetch_site="same-site",
                sec_ch_ua_platform=bs_sec_ch_ua_platform,
                sec_ch_ua=bs_sec_ch_ua
            )
        s.headers.update(headers)
        s.cookies.update(browser_session.cookies)
        return s

    
    def _req_new_token(self, session: requests.Session, token: TokenState) -> dict[object, object]:
        resp = self._request(
            session_func=session.post,
            url=self.store.kick_off_url,
            json={
                "fingerprintGuest": token.fingerprint_guest,
                "fingerprintUser": token.fingerprint_user
            },
            headers = {"sec-fetch-site": "same-origin"}
        )
        stsCode = resp.status_code
        if (stsCode != 200):
            self.logger.fatal(f"REFRESH FAILED: {stsCode}")
            raise ValueError(f"REFRESH FAILED: {stsCode}")
        return resp.json()
    
    def _refresh_token(self, session: requests.Session, token: TokenState):
        self.logger.info("token refreshing")
        try:
            refresh_values = self._req_new_token(session=session, token=token)
        except (ValueError, requests.RequestException) as e:
            self.logger.error(f"token refresh FAILED => {e}")
            return False
        new_access_token = refresh_values.get("access_token")
        new_expires_time = refresh_values.get("expires_time")
        if not (new_access_token and new_expires_time):
            return False
        token.expires_at = parse_iso_time(str(new_expires_time))
        session.headers["authorization"] = f"Bearer {new_access_token}"
        return True

    def _ensure_token_freshness(self, session: requests.Session, token: TokenState):
        if token.expires_at is not None:
            if (time.time() > (token.expires_at - self.config.TOKEN_REFRESH_TIME)):
                self._refresh_token(session, token)

    
    def _payload(self, storeId: str, catagory: str, page: int, region: str) -> dict[str, object]:
        reg = region
        return {
            "algoliaQuery": {
                "attributesToHighlight": [],
                "attributesToRetrieve": [
                    "productID",
                    "Type",
                    "sponsored",
                    f"category0{reg}",
                    f"category1{reg}",
                    f"category2{reg}"
                ],
                "facets": [
                    "brand",
                    f"category1{reg}",
                    "onPromotion",
                    "productFacets",
                    "tobacco"
                ],
                
                "filters": f"stores:{storeId} AND category0{reg}:\"{catagory}\"",
                "highlightPostTag": "__/ais-highlight__",
                "highlightPreTag": "__ais-highlight__",
                "hitsPerPage": 50,
                "maxValuesPerFacet": 100,
                "page": page,
                "analyticsTags": [
                    "fs#WEB:desktop"
                ]
            },
            "algoliaFacetQueries": [],
            "storeId": storeId,
            "hitsPerPage": 50,
            "page": page,
            "sortOrder": f"{reg}_POPULARITY_ASC",
            "tobaccoQuery": False,
            "precisionMedia": {
                "adDomain": "CATEGORY_PAGE",
                "adPositions": [
                    4,
                    8,
                    12
                ],
                "publishImpressionEvent": False,
                "disableAds": True
            }
        }


    def _update_mapping(self, session: requests.Session, sid: str, prods: list[dict]) -> None:
        # look up the barcodes (sku) for any product ids that we havent yet mapped
        new_pids: set[str] = {
            p["productId"] for p in prods if (p.get("productId"))
        } - self.known_pids

        if (not new_pids):
            return

        with open(self.config.mapping_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for pid in new_pids:
                try:
                    response = self._request(session_func=session.get, url=self.store.prodcut_url(sid=sid, pid=pid))
                except requests.RequestException as re:
                    self.logger.warning(f"barcode lookup FAILED => pid={pid}, store={sid}: {re}")
                    continue
                statusCode = response.status_code
                if (statusCode == 200):
                    bc = response.json().get("sku")
                    if (bc):
                        writer.writerow([pid, bc])
                        f.flush()
                        self.known_pids.add(pid)
                        self.logger.info(f"added to mapping: for {pid}=={bc}")
                elif (statusCode == 404):
                    continue # not in that store, ignore
                else:
                    self.logger.warning(f"barcode lookup got {statusCode} for {pid}, store: {sid}")





    def _scrape_catagory(self, session: requests.Session, token: TokenState, store_info: dict[str, str], catagory: str) -> None:
        sid, store_region = store_info.get("id"), store_info.get("region")
        curr_page, total_pages, auth_failures = 0, 1, 0

        cata_dir = self.config.product_json_dir / str(sid) / catagory
        cata_dir.mkdir(parents=True, exist_ok=True)

        while curr_page < total_pages:
            self.logger.info(f"sid: {sid}, catagory: {catagory}, page: {curr_page}")
            self._ensure_token_freshness(session=session, token=token)
            try:
                resp = self._request(session.post,
                        self.store.search_url, 
                        json=self._payload(
                            storeId=sid, 
                            catagory=catagory, 
                            page=curr_page, 
                            region=store_region))
            except requests.RequestException as re:
                self.logger.error(f"search failed for store={sid}, catagory={catagory}, page={curr_page} => {re}, skipping this catagory")
                break
            status_code = resp.status_code
            if (status_code == 401):
                auth_failures+=1
                retries = self.config.MAX_RETRIES
                if (auth_failures > retries):
                    self.logger.error(f"too many 401s (more than {retries}); giving up on catagory: {catagory} in store {sid}")
                    break
                self.logger.warning(f"401 on store {sid}, refresing token")
                self._refresh_token(session=session, token=token)
                continue

            if (status_code != 200):
                self.logger.error(f"Blocked! Status Code: {status_code}")
                break

            auth_failures = 0
            data = resp.json()
            products = data.get("products", [])
            total_pages = math.ceil(data.get("totalHits", 0) / self.config.PAGE_SIZE)
            with open(cata_dir / f"page_{curr_page}.json", "w") as f:
                json.dump(data, f, indent=4)

            self._update_mapping(session=session, sid=sid, prods=products)
            curr_page+=1
            self._delay()
        self._delay()

    def _scrape_store(self, session: requests.Session, token: TokenState, store_info: dict[str, str], catagories: list[str]) -> None:
        sid = store_info.get("id")
        self.logger.info(f"scraping store: {sid}")
        session.cookies["eCom_STORE_ID"] = str(sid)
        session.cookies["STORE_ID_V2"] = f"{sid}|False"

        try:
            resp = self._request(session.post, self.store.store_url(sid))
            if (resp.status_code != 200):
                self.logger.warning(f"store did not switch ({resp.status_code})")
        except requests.RequestException as re:
            self.logger.warning(f"store switch failed for {sid} ({re})")
        for c in catagories:
            self._scrape_catagory(session=session, token=token, store_info=store_info, catagory=c)
        
        self._delay()

    def run(self):
        start_time: float = time.time()
        msg: str = f"machine {self.config.machine_index}/{self.config.total_machines} starting" 
        self.logger.info(msg)
        self.config.product_json_dir.mkdir(parents=True, exist_ok=True)

        browser_session: BrowserSession = self._harvester()
        if (browser_session is None or not browser_session.expires_time or not browser_session.jwt):
            self.logger.error("playwright session couldnt be established")
            sys.exit("ERROR: playwright session couldnt be established")

        session: requests.Session = self._create_session(browser_session=browser_session)
        token: TokenState = TokenState(
            fingerprint_user=browser_session.fingerprint_user, 
            fingerprint_guest=browser_session.fingerprint_guest, 
            expires_at=parse_iso_time(browser_session.expires_time))
        catagories = self._catagories()

        for store_info in self.get_req_store_ids_and_region():
            self._scrape_store(session=session, token=token, store_info=store_info, catagories=catagories)
        end_time: float = time.time()
        total_time = end_time - start_time;
        finished_msg = f"{self.store.franchise} scraping complete on machine {self.config.machine_index} in {total_time}"
        self.logger.info(finished_msg)



        
        
            


def parse_args() -> Config:
    curr_file: Path = Path(__file__).parent
    parser = argparse.ArgumentParser(
        prog="foodstuffs_scraper",
        description="foodstuff scraper (new world and paknsave)"
    )
    parser.add_argument("-s", "--store", required=True, choices=STORES.keys())
    parser.add_argument("-i", "--index", required=True, type=int, help="index of this machine [0..total) remember 0-indexed!")
    parser.add_argument("-t", "--total", required=True, type=int, help="total Number of machines running this job")
    args = parser.parse_args()
    store=STORES[args.store]
    output_dir: Path = curr_file / store.dir /"output"
    data_dir: Path = curr_file / store.dir / "util"

    if (args.index < 0 or args.index >= args.total):
        print(f"ERROR: --index (-i) must be between 0 and {args.total-1}, instead got {args.index}")
        sys.exit(1)

    return Config(
        store=STORES[args.store],
        machine_index=args.index, 
        total_machines=args.total,
        CURR_FILE=curr_file,
        OUTPUT_DIR=output_dir,
        DATA_DIR=data_dir
    )

if __name__ == "__main__":
    config: Config = parse_args();
    scraper = FoodStuffsScraper(config)
    scraper.run();





# def _init_logger(self):
#     log_dir_path: Path = self.config.OUTPUT_DIR / f"log_machine_{self.config.machine_index}"
#     return get_logger(name=f"FoodStuffsScraper_{self.config.machine_index}",
#                log_dir_path=log_dir_path,
#                wants_console_logger=True)

#     # log_dir_path: Path = self.config.OUTPUT_DIR / f"log_machine_{self.config.machine_index}"
#     # log_dir_path.mkdir(parents=True, exist_ok=True)
#     # log_file_path: Path = log_dir_path / f"log_{self.config.curr_time}_UTC.log"

#     # logger: logging.Logger = logging.getLogger(f"FoodStuffsScraper_{self.config.machine_index}");
#     # logger.setLevel(logging.INFO)

#     # logging.Formatter.converter = time.gmtime
#     # log_format: logging.Formatter = logging.Formatter(fmt="[%(levelname)s] => %(asctime)s UTC => %(name)s => %(message)s")
    
#     # file_handler: logging.FileHandler = logging.FileHandler(log_file_path, mode="w", encoding="utf-8")
#     # file_handler.setFormatter(log_format)

#     # console_handler = logging.StreamHandler(sys.stdout)
#     # console_handler.setFormatter(log_format)
    
#     # logger.addHandler(file_handler)
#     # logger.addHandler(console_handler)

#     # # print("LOGGER INITAIALISED OK")
#     # logger.info("LOGGER INITAIALISED OK")
#     # return logger