import csv
from pathlib import Path
from typing import List, Dict, Any

class CatalogService:
    def __init__(self, data_dir: str = "data"):
        self.catalog_file = Path(data_dir) / "parts_catalog.csv"
        self.inventory = []
        self._load_catalog()

    def _load_catalog(self):
        """Loads the CSV into memory as a list of dictionaries."""
        if not self.catalog_file.exists():
            print(f"Error: Catalog file not found at {self.catalog_file}")
            return
        
        with open(self.catalog_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert price to float for math later
                try:
                    row["unit_price"] = float(row["unit_price"])
                except ValueError:
                    row["unit_price"] = 0.0
                self.inventory.append(row)

    def lookup_parts(self, make: str, operation_code: str) -> List[Dict[str, Any]]:
        """
        Finds all parts matching the MAKE and OPERATION CODE.
        Example: 'HONDA' + 'RR-BRAKE' -> Returns Pads + Rotors for Honda.
        """
        results = []
        search_make = make.upper()
        
        # Simple fallback: If we don't have parts for this make (e.g., Chevy), 
        # we can optionally return generic parts or empty. 
        # For this demo, we will check exact matches.
        
        for item in self.inventory:
            if item["make"] == search_make and item["operation_code"] == operation_code:
                results.append(item)
        
        return results