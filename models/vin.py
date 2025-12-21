from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass(frozen=True)
class VinProfile:
    vin: str
    make: str
    model: str
    year: int
    engine: str
    drivetrain: str
    trim: Optional[str] = None
    confidence: float = 0.85
    metadata: Optional[Dict[str, Any]] = None