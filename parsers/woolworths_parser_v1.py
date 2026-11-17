import json
import csv
from pathlib import Path
import sys
from decimal import Decimal, ROUND_HALF_UP


CURR_FILE = Path(__file__).parent
WW_DIR = CURR_FILE.parent / "woolworths"
PRODUCT_JSON_PATH = WW_DIR / "output" / "productJson"


def dollars_to_cents(dollars: str|float|int) -> int:
    if (dollars is None):
        return None
    # Convert to string first to avoid float precision issues - GEMINI
    amount = Decimal(str(dollars))
    cents = (amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def _parse_prod(sid_name: str, p: dict[str, object]):
    if (not isinstance(p, dict)) or p.get("type") != "Product":
        return None
    pid = p.get("barcode")
    if (not pid):
        return None
        
    p_unit = p.get("unit")
    p_name = f"{p.get("name")} {p_unit}"
    
    
    p_comp_price = p.get("size") or {}

    p_cup_price = p_comp_price.get("cupPrice")
    p_comp_mesure = p_comp_price.get("cupMeasure")
    p_standard_price_to_size = f"{dollars_to_cents(p_cup_price)}/{p_comp_mesure}" if (p_cup_price and p_comp_mesure) else None
    
    # "originalPrice": 13.65,
    # "salePrice": 12.95,
    # "savePrice": 0.7,
    # "savePercentage": 0.0,
    # "canShowSavings": true,
    # "hasBonusPoints": false,
    # "isClubPrice": true,
    # "isSpecial": true,
    
    p_price_dic = p.get("price") or {}
    p_original_price = p_price_dic.get("originalPrice")
    p_sale_price = p_price_dic.get("salePrice")
    is_club_price = bool(p_price_dic.get("isClubPrice"))

    # can't exactly trust the isSpecial flag all the time, but the numbers dont lie
    has_been_reduced = p_sale_price is not None and p_original_price is not None and p_sale_price < p_original_price

    p_dep = p.get("departments") or []
    p_img_dict = p.get("images") or {}
    
    p_cata = p_dep[0].get("id") if (p_dep) else None
    p_img = p_img_dict.get("big") or p_img_dict.get("small")
    

    data: dict[str, object] = {
        "sid": sid_name,
        "pid": pid,
        "p_name": p_name,
        "p_aval": p.get("availabilityStatus") in ("In Stock", "Low Stock"),
        "p_price_normal": dollars_to_cents(p_original_price),
        "p_price_save": dollars_to_cents(p_sale_price) if (has_been_reduced and not is_club_price) else None,
        "p_price_member": dollars_to_cents(p_sale_price) if (has_been_reduced and is_club_price) else None,
        "p_price_standardized": p_standard_price_to_size,
        "p_cata": p_cata,
        "p_img": p_img
    }

    return data

def parse(sid: Path, json_file_path: Path, skipped_files: list[str]):
    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ps = data["products"]["items"] # list of product specs
    except Exception as e:
        print(f"skipping faulty file {e}")
        print(f"faulty file: {json_file_path}")
        skipped_files.append(str(json_file_path))
        return

    for p in ps:
        if (not isinstance(p, dict)): 
            continue
        row = _parse_prod(sid.name, p)
        if (row):
            yield row
    

def _write_skipped(skipped_files: list[str]):
    if (not skipped_files):
        return
    with open("skipped_files.log", "a") as f:
        f.write("\n".join(skipped_files))
    print(f"total skipped: {len(skipped_files)}")
    skipped_files.clear()

def _total_parser(product_json_path: Path):

    skipped_files: list[str] = []
    product_json_path_obj = product_json_path
    
    if (not product_json_path_obj.exists()):
        print(f"nothing to parse, there needs to be a folder at {product_json_path_obj}, however can not find it, ending ww parsing")
        return


    sids = [x for x in product_json_path_obj.iterdir() if x.is_dir()]
    for sid in sids:
        catas = [x for x in sid.iterdir() if x.is_dir()]
        for cata in catas:
            pages = [x for x in cata.iterdir() if x.is_file() and x.suffix == ".json"]
            for page in pages:
                yield from parse(sid, page, skipped_files)

    _write_skipped(skipped_files)


def total_parser():
    return _total_parser(PRODUCT_JSON_PATH)