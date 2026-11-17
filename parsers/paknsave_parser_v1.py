from pathlib import Path
from . import foodstuff_parser_v1 as fs_parser

CURR_FILE = Path(__file__).parent
PS_DIR = CURR_FILE.parent / "foodstuffs" / "paknsave"
PRODUCT_JSON_PATH = PS_DIR / "output" / "productJson"

def catagories():
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

def total_parser():
    return fs_parser.total_parser(product_json_path=PRODUCT_JSON_PATH, catagories=catagories())
