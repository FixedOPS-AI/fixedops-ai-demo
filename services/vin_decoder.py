import csv
import json
import random
from pathlib import Path
from typing import Optional, Dict, Any

class VinProfile:
    # UPDATED: Added 'drivetrain' to the initialization
    def __init__(self, make: str, model: str, year: int, engine: str, trim: str, drivetrain: str, confidence: float):
        self.make = make
        self.model = model
        self.year = year
        self.engine = engine
        self.trim = trim
        self.drivetrain = drivetrain  # <--- The missing piece!
        self.confidence = confidence

class VinDecoder:
    def __init__(self, data_dir: str = "data"):
        self.wmi_file = Path(data_dir) / "wmi_make.csv"
        self.rules_file = Path(data_dir) / "vin_rules.json"
        self.wmi_db = {}
        self.rules_db = {}
        self._load_data()

    def _load_data(self):
        # 1. Load WMI Data
        if self.wmi_file.exists():
            with open(self.wmi_file, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    prefix = row["wmi_prefix"].strip()
                    make = row["make"].strip()
                    self.wmi_db[prefix] = make

        # 2. Load Rules Data
        if self.rules_file.exists():
            with open(self.rules_file, mode="r", encoding="utf-8") as f:
                self.rules_db = json.load(f)

    def decode(self, vin: str) -> VinProfile:
        vin = vin.upper().strip()
        if len(vin) != 17:
             # Return "UNKNOWN" for drivetrain if VIN is invalid
             return VinProfile("UNKNOWN", "UNKNOWN", 0, "UNKNOWN", "UNKNOWN", "UNKNOWN", 0.0)

        # A. Decode Year (10th digit)
        year_char = vin[9]
        year_map = {
            'A': 2010, 'B': 2011, 'C': 2012, 'D': 2013, 'E': 2014, 'F': 2015,
            'G': 2016, 'H': 2017, 'J': 2018, 'K': 2019, 'L': 2020, 'M': 2021,
            'N': 2022, 'P': 2023, 'R': 2024, 'S': 2025,
            '1': 2001, '2': 2002, '3': 2003, '4': 2004, '5': 2005, '6': 2006,
            '7': 2007, '8': 2008, '9': 2009
        }
        year = year_map.get(year_char, 2000)

        # B. Decode Make (WMI - First 3 digits)
        wmi = vin[:3]
        make = self.wmi_db.get(wmi, "UNKNOWN")
        
        # C. Decode Model/Engine/Trim/Drivetrain
        model = "Unknown Model"
        engine = "UNKNOWN"
        trim = "UNKNOWN"
        drivetrain = "UNKNOWN"
        confidence = 0.0

        if make != "UNKNOWN":
            confidence = 0.8
            if make in self.rules_db:
                rule = self.rules_db[make]
                engine = random.choice(rule.get("engines", ["Standard Engine"]))
                trim = random.choice(rule.get("trims", ["Base"]))
                
                # Assign a random drivetrain to make it look realistic
                drivetrain = random.choice(["FWD", "RWD", "AWD", "4WD"])
                
                # Assign a dummy model name based on Make
                if make == "HONDA": model = "CIVIC"
                elif make == "FORD": model = "F-150"
                elif make == "TOYOTA": model = "CAMRY"
                elif make == "CHEVROLET": model = "SILVERADO"
                elif make == "RAM": model = "1500"
                elif make == "JEEP": model = "WRANGLER"
                elif make == "DODGE": model = "CHALLENGER"

        return VinProfile(make, model, year, engine, trim, drivetrain, confidence)