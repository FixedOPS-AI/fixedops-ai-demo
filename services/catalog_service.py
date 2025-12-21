import csv
from pathlib import Path
from typing import List, Dict, Any

class CatalogService:
    def __init__(self, data_dir: str = "data"):
        self.catalog_file = Path(data_dir) / "parts_catalog.csv"
        self.db = []
        self._load_catalog()

    def _load_catalog(self):
        if self.catalog_file.exists():
            with open(self.catalog_file, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Convert price to float safely
                    try:
                        row["unit_price"] = float(row["unit_price"])
                    except ValueError:
                        row["unit_price"] = 0.0
                    
                    # NEW: Capture Cost Price safely (for Margin Logic)
                    try:
                        row["cost_price"] = float(row.get("cost_price", 0.0))
                    except ValueError:
                        row["cost_price"] = 0.0
                        
                    self.db.append(row)

    def get_parts_for_op(self, make: str, op_code: str) -> List[Dict[str, Any]]:
        """
        Finds parts in the CSV catalog matching the vehicle make and operation code.
        """
        matches = []
        for row in self.db:
            # Case-insensitive match for MAKE
            if row["make"].upper() == make.upper() and row["operation_code"] == op_code:
                # Create a copy to return so we don't mutate the db
                item = row.copy()
                item["qty"] = 1 # Default qty
                # Calculate initial line total (will be updated by agent later)
                item["line_total"] = item["qty"] * item["unit_price"]
                matches.append(item)
        return matches
    
# Force Cloud Update V2.0
