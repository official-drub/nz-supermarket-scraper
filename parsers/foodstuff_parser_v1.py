import json

from pathlib import Path




def default_fs_catagories() -> dict[str, int]:
    return {
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



def _product_name(p: dict[str, object]) -> str:
    p_name = f"{p.get("brand")} {p.get("name")} {p.get("displayName")}"
    return p_name

def _price_per_unit(p_price_dic: dict[str, object]):
    p_comp_price = p_price_dic.get("comparativePrice") or {}
    p_price_per_unit = p_comp_price.get("pricePerUnit")
    p_mesure_per_unit = p_comp_price.get("measureDescription")
    p_price_standardized = f"{p_price_per_unit}/{p_mesure_per_unit}" if (p_price_per_unit and p_mesure_per_unit) else None
    return p_price_standardized

def _catagory_id(p: dict[str, object], catagories: dict[str, int]) -> int|None:
    p_cata_list = p.get("categoryTrees") or []
    if (not p_cata_list):
        return None
    return catagories.get((p_cata_list[0] or {}).get("level0"))
    

def parse_prod(sid_name: str, p: dict[str, object], catagories: dict[str, int]) -> dict[str, object]:
    pid = p.get("productId")
    if (not pid):
        return None
    p_price_dic = p.get("singlePrice") or {}
    return {
        "sid": sid_name,
        "pid": pid,
        "p_name": _product_name(p),
        "p_aval": "IN_STORE" in (p.get("availability") or []),
        "p_price_normal": p_price_dic.get("price"),
        "p_price_standardized": _price_per_unit(p_price_dic),
        "p_cata": _catagory_id(p, catagories)
    }




def parse(sid: Path, json_file_path: Path, catagories: dict[str, int], skipped_files: list[str]):
    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            ps: list[object] = json.load(f)["products"] or [] # list of product specs
    except Exception as e:
        print(f"skipping faulty file {e}")
        print(f"faulty file: {json_file_path}")
        skipped_files.append(str(json_file_path))
        return

    for p in ps: 
        if (not isinstance(p, dict)): 
            continue
        row = parse_prod(sid.name, p, catagories)
        if (row):
            yield row

def _write_skipped(skipped_files: list[str]):
    if (not skipped_files):
        return
    with open("skipped_files.log", "a") as f:
        f.write("\n".join(skipped_files))
    print(f"total skipped: {len(skipped_files)}")
    skipped_files.clear()
    
def total_parser(product_json_path: Path, catagories: dict[str, int]):
    skipped_files: list[str] = []
    
    product_json_path_obj = product_json_path
    
    if (not product_json_path_obj.exists()):
        print(f"nothing to parse, there needs to be a folder at {product_json_path_obj}, however can not find it, ending fs parsing")
        return

    sids = [x for x in product_json_path_obj.iterdir() if x.is_dir()]
    for sid in sids:
        catas = [x for x in sid.iterdir() if x.is_dir()]
        for cata in catas:
            pages = [x for x in cata.iterdir() if x.is_file() and x.suffix == ".json"]
            for page in pages:
                yield from parse(sid, page, catagories, skipped_files)

    _write_skipped(skipped_files)

    


