from typing import Dict, Any, List

class ValidationService:
    def __init__(self):
        # --- YOUR CUSTOM RULES ---
        self.MIN_PARTS_MARGIN = 0.25
        self.MAX_AUTO_APPROVAL = 4000.00
    
    def validate_estimate(self, estimate_summary: Dict[str, float], parts_lines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Reviews the estimate against business rules.
        Returns: Status (Pass/Review), Warnings, and a Log.
        """
        warnings = []
        log = []
        status = "pass"
        
        log.append("Validation Service: Starting compliance check...")

        # Extract totals
        labor_total = estimate_summary.get("labor_subtotal", 0.0)
        shop_fees = estimate_summary.get("shop_fees", 0.0)
        tax_amount = estimate_summary.get("tax", 0.0)
        grand_total = estimate_summary.get("grand_total", 0.0)

        # RULE 1: The "Profit Thief" (Shop Supplies & Tax)
        if labor_total > 0:
            if shop_fees <= 0.01:
                msg = "Profit Alert: Shop Supplies are set to $0.00."
                warnings.append(msg)
                # ADDED: :red[...] makes the text red in the app
                log.append(f":red[FLAGGED: {msg}]")
            
            if tax_amount <= 0.01:
                msg = "Compliance Alert: Sales Tax is currently $0.00."
                warnings.append(msg)
                log.append(f":red[FLAGGED: {msg}]")

        # RULE 2: The "Big Ticket" Review
        if grand_total > self.MAX_AUTO_APPROVAL:
            status = "review"
            msg = f"Manager Approval Required: Estimate (${grand_total:,.2f}) exceeds limit."
            warnings.append(msg)
            log.append(f":red[FLAGGED: {msg}]")

        # RULE 3: Parts Margin Check
        for part in parts_lines:
            if "TIRE" in part.get("part_number", "") and part.get("unit_price", 0) > 200:
                msg = f"Margin Check: High-value tire ({part['part_number']}) detected."
                warnings.append(msg)
                log.append(f":red[FLAGGED: {msg}]")

        # Final Decision
        if warnings and status == "pass":
            status = "review"
        
        if status == "pass":
            log.append(":green[Validation Complete: Estimate looks good.]")
        else:
            log.append(f":red[Validation Complete: Found {len(warnings)} issues.]")

        return {
            "status": status,
            "warnings": warnings,
            "log": log
        }