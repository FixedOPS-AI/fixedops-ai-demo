import json
from typing import List, Dict, Any

import streamlit as st
from services.vin_decoder import VinDecoder
from services.catalog_service import CatalogService
from services.validation_service import ValidationService
# -----------------------------
# Simple domain model & helpers
# -----------------------------

SCENARIOS = {
    "Example: Alternator + brakes + tires + maintenance": (
        "Alternator tested bad, rear brakes 3mm, tires 4/32, no history of spark plug service, "
        "due for timing belt service by mileage and age."
    ),
    "Example: Rear brake job only": "Rear brakes 2mm, pulsation felt, recommend rear brake pads and rotors.",
    "Example: Tire replacement only": "Tires are 3/32, customer reports vibration at highway speeds, recommend 4 new tires and balance."
}


def video_decoder_agent(technician_text: str, has_video: bool) -> Dict[str, Any]:
    """
    Simulate the Video Decoder Agent.
    """
    log: List[str] = []
    if has_video:
        log.append(
            "Video Decoder Agent: Received walkaround video + technician notes. "
            "Transcribing audio and merging with text input."
        )
        decoded_notes = technician_text + " [Video transcript merged into notes.]"
    else:
        log.append("Video Decoder Agent: No video provided. Using technician text only.")
        decoded_notes = technician_text

    return {"decoded_notes": decoded_notes, "log": log}


def labor_agent(decoded_notes: str, labor_rate: float) -> Dict[str, Any]:
    """
    Simulate the AI Labor Agent: Maps tech notes to standardized Labor Ops.
    Now expanded to handle Suspension, Cooling, and Oil Leaks.
    """
    log: List[str] = []
    log.append(f"AI Labor Agent: Interpreting technician notes and mapping to labor operations.")
    
    labor_ops: List[Dict[str, Any]] = []
    
    # Simple Keyword Mapping Logic (The "Brain")
    text = decoded_notes.lower()
    
    # 1. BRAKES
    if any(x in text for x in ["brake", "grinding", "squeak", "pads", "rotor"]):
        labor_ops.append({
            "operation_code": "RR-BRAKE",
            "description": "Replace rear brake pads and rotors",
            "hours": 2.0,
            "rate": labor_rate
        })
        log.append("Added labor line: Rear brake pads & rotors (2.0 hrs).")
        
    # 2. ALTERNATOR / BATTERY
    if any(x in text for x in ["alternator", "charging", "battery", "voltage", "dim lights"]):
        labor_ops.append({
            "operation_code": "ALT-REPL",
            "description": "Alternator replacement",
            "hours": 2.5,
            "rate": labor_rate
        })
        log.append("Added labor line: Alternator replacement (2.5 hrs).")
    
    # 3. TIRES
    if any(x in text for x in ["tire", "tread", "bald", "flat", "puncture"]):
        labor_ops.append({
            "operation_code": "TIRE-SET",
            "description": "Mount and Balance 4 Tires",
            "hours": 1.5,
            "rate": labor_rate
        })
        log.append("Added labor line: Mount and Balance 4 Tires (1.5 hrs).")

    # 4. SUSPENSION (New!)
    if any(x in text for x in ["suspension", "strut", "shock", "clunk", "bumpy", "control arm"]):
        labor_ops.append({
            "operation_code": "SUSP-FRONT",
            "description": "Replace Front Suspension Components (Struts/Arms)",
            "hours": 3.5,
            "rate": labor_rate
        })
        log.append("Added labor line: Front Suspension Overhaul (3.5 hrs).")

    # 5. COOLING SYSTEM (New!)
    if any(x in text for x in ["coolant", "radiator", "overheat", "leaking water", "hoses"]):
        labor_ops.append({
            "operation_code": "COOLING-SYS",
            "description": "Cooling System Service (Radiator & Flush)",
            "hours": 4.0,
            "rate": labor_rate
        })
        log.append("Added labor line: Radiator & Cooling System Service (4.0 hrs).")

    # 6. OIL LEAKS (New!)
    if any(x in text for x in ["oil leak", "burning smell", "valve cover", "gasket", "dripping"]):
        labor_ops.append({
            "operation_code": "OIL-LEAK",
            "description": "Reseal Valve Cover Gaskets",
            "hours": 3.0,
            "rate": labor_rate
        })
        log.append("Added labor line: Engine Oil Leak Repair (3.0 hrs).")

    # 7. TUNE UP
    if any(x in text for x in ["spark plug", "tune up", "misfire", "rough idle"]):
        labor_ops.append({
            "operation_code": "SPARK-PLUG",
            "description": "Spark Plug Replacement & Tune-up",
            "hours": 1.5,
            "rate": labor_rate
        })
        log.append("Added labor line: Spark Plug Service (1.5 hrs).")

    # Fallback if nothing matches
    if not labor_ops:
        labor_ops.append({
            "operation_code": "GEN-DIAG",
            "description": "General Diagnosis (No specific system matched)",
            "hours": 1.0,
            "rate": labor_rate
        })
        log.append("No specific concerns matched. Added generic diagnostic labor line (1.0 hr).")
    
    # Calc totals
    for op in labor_ops:
        op["line_total"] = round(op["hours"] * op["rate"], 2)

    return {"labor_ops": labor_ops, "log": log}


def parts_agent(labor_ops: List[Dict[str, Any]], vehicle_make: str) -> Dict[str, Any]:
    """
    Simulate the AI Parts Agent by looking up parts in the catalog CSV.
    """
    log: List[str] = []
    log.append(f"AI Parts Agent: Looking up parts for vehicle make: {vehicle_make}")

    parts_lines: List[Dict[str, Any]] = []
    
    # Access the service from session state (or create a temp one if missing)
    catalog = st.session_state.get("catalog_service")
    
    for op in labor_ops:
        op_code = op["operation_code"]
        
        # 1. Try to find specific parts for this Make + OpCode
        found_parts = []
        if catalog:
            found_parts = catalog.lookup_parts(vehicle_make, op_code)
            
        if found_parts:
            # We found real parts in the CSV!
            for p in found_parts:
                parts_lines.append({
                    "operation_code": op_code,
                    "part_number": p["part_number"],
                    "description": p["description"],
                    "qty": 1,  # Default to 1 for this demo
                    "unit_price": p["unit_price"],
                    "stock_source": p["stock_source"],
                    "availability": p["availability"],
                    "line_total": p["unit_price"] * 1  # calc total
                })
            log.append(f"Found {len(found_parts)} parts for operation {op_code}.")
            
        else:
            # 2. Fallback: If no parts in CSV (or generic make), add a generic placeholder
            if op_code != "GEN-DIAG":
                log.append(f"No specific parts found for {op_code} on {vehicle_make}. Adding generic placeholder.")
                parts_lines.append({
                    "operation_code": op_code,
                    "part_number": "GEN-PART",
                    "description": f"Generic Part for {op_code}",
                    "qty": 1,
                    "unit_price": 50.00,
                    "stock_source": "Local Auto Parts",
                    "availability": "On Demand",
                    "line_total": 50.00
                })

    return {"parts_lines": parts_lines, "log": log}

def estimate_generator(
    labor_ops: List[Dict[str, Any]],
    parts_lines: List[Dict[str, Any]],
    shop_fees_pct: float,
    tax_pct: float,
) -> Dict[str, Any]:
    """
    Simulate the Estimate Generator Agent.
    """
    log: List[str] = []
    log.append("Estimate Generator Agent: Summarizing labor and parts into a customer-facing estimate.")

    labor_subtotal = sum(op["line_total"] for op in labor_ops)
    parts_subtotal = sum(p["line_total"] for p in parts_lines)

    subtotal = labor_subtotal + parts_subtotal
    shop_fees = round(subtotal * shop_fees_pct, 2)
    tax = round((subtotal + shop_fees) * tax_pct, 2)
    grand_total = round(subtotal + shop_fees + tax, 2)

    summary = {
        "labor_subtotal": round(labor_subtotal, 2),
        "parts_subtotal": round(parts_subtotal, 2),
        "shop_fees": shop_fees,
        "tax": tax,
        "grand_total": grand_total,
    }

    log.append(f"Computed estimate totals. Grand total: ${grand_total:,.2f}.")

    return {"summary": summary, "log": log}


def validation_agent(
    estimate_summary: Dict[str, float], 
    labor_ops: List[Dict[str, Any]], 
    parts_lines: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Simulate the Validation Agent by applying business rules (Profit/Compliance).
    """
    # Default to a generic pass if service is missing
    if "validation_service" not in st.session_state:
         return {"status": "pass", "warnings": []}

    # Call the real service
    validator = st.session_state["validation_service"]
    result = validator.validate_estimate(estimate_summary, parts_lines)
    
    return result


def run_full_pipeline(
    technician_text: str,
    has_video: bool,
    labor_rate: float,
    shop_fees_pct: float,
    tax_pct: float,
    vehicle_make: str = "HONDA"  # Default if no VIN decoded
) -> Dict[str, Any]:
    """
    Run the complete FixedOPS_AI pipeline from input through validation.
    """
    video = video_decoder_agent(technician_text, has_video)
    labor = labor_agent(video["decoded_notes"], labor_rate)
    
    # --- CHANGED: Pass the vehicle_make to the parts agent ---
    parts = parts_agent(labor["labor_ops"], vehicle_make)
    
    estimate = estimate_generator(labor["labor_ops"], parts["parts_lines"], shop_fees_pct, tax_pct)
    validation = validation_agent(estimate["summary"], labor["labor_ops"], parts["parts_lines"])

    return {
        "input": {
            "technician_text": technician_text,
            "has_video": has_video,
            "labor_rate": labor_rate,
            "shop_fees_pct": shop_fees_pct,
            "tax_pct": tax_pct,
            "vehicle_make": vehicle_make
        },
        "video_decoder": video,
        "labor": labor,
        "parts": parts,
        "estimate": estimate,
        "validation": validation,
    }


# -----------------------------
# Streamlit app (UI layer)
# -----------------------------

st.set_page_config(
    page_title="FixedOPS_AI – Real-Time Estimation Demo",
    layout="wide",
)

st.title("FixedOPS_AI – Real-Time Parts & Labor Estimation Demo")
st.caption(
    "Interactive simulation of your AI-driven automated parts & labor estimation system for dealership fixed operations."
)
# --- CATALOG SERVICE BLOCK (Added Step 2) ---
if "catalog_service" not in st.session_state:
    st.session_state["catalog_service"] = CatalogService(data_dir="data")
# --- VALIDATION SERVICE BLOCK (Added Step 3) ---
if "validation_service" not in st.session_state:
    st.session_state["validation_service"] = ValidationService()
# --- VIN DECODER BLOCK (Added Step 1) ---
if "vin_decoder" not in st.session_state:
    st.session_state["vin_decoder"] = VinDecoder(data_dir="data")

with st.expander("Vehicle Identification", expanded=True):
    col_vin, col_btn = st.columns([3, 1])
    with col_vin:
        vin_input = st.text_input("Enter VIN (Try: 1HGCM82633A123451)", value="1HGCM82633A123451")
    
    if vin_input:
        # Run the decoder
        profile = st.session_state["vin_decoder"].decode(vin_input)
        st.session_state["vin_profile"] = profile
        
        # Check if it worked (Confidence > 0)
        if profile.confidence > 0:
            st.success(f"VIN Decoded: {profile.year} {profile.make} {profile.model}")
            
            # Display details in 3 nice columns
            c1, c2, c3 = st.columns(3)
            c1.metric("Engine", profile.engine)
            c2.metric("Trim", profile.trim)
            c3.metric("Drivetrain", profile.drivetrain)
        else:
            st.error("Could not decode VIN. Please try a valid Honda, Ford, or Toyota VIN.")
# ---------------------------------------


if "pipeline_result" not in st.session_state:
    st.session_state["pipeline_result"] = None

with st.sidebar:
    st.header("1️⃣ Technician Scenario")

    scenario = st.selectbox(
        "Choose a starting scenario:",
        ["Use my own notes"] + list(SCENARIOS.keys()),
    )

    has_video = st.checkbox(
        "Include walkaround video? (activates Video Decoder Agent)", value=True
    )

    st.header("2️⃣ Dealership Settings")

    labor_rate = st.number_input(
        "Standard labor rate ($/hr)",
        min_value=50.0,
        max_value=300.0,
        value=160.0,
        step=5.0,
    )

    shop_fees_pct = st.slider(
        "Shop fees (% of labor + parts subtotal)",
        min_value=0.0,
        max_value=10.0,
        value=5.0,
        step=0.5,
    )

    tax_pct = st.slider(
        "Sales tax (%)",
        min_value=0.0,
        max_value=12.0,
        value=0.0,
        step=0.25,
    )

    st.markdown("---")
    st.caption("This demo uses simple rule-based logic to **simulate** your multi-agent design. "
               "In production, each block would be a real AI agent calling DMS, Xtime, and OEM APIs.")


default_notes = SCENARIOS.get(scenario, "")

st.subheader("Technician Input (\"three C's\": concern, cause, correction)")
technician_text = st.text_area(
    "What does the technician tell FixedOPS_AI?",
    value=default_notes,
    height=180,
    help="This represents the technician typing or dictating their notes into the integrated NLP portal.",
)

run_clicked = st.button("▶️ Run FixedOPS_AI Simulation")

if run_clicked:
    if not technician_text.strip():
        st.warning("Please enter some technician notes or choose an example scenario from the sidebar.")
    else:
        # Determine the make from the VIN decoder (or default to HONDA)
        detected_make = "HONDA"
        if "vin_profile" in st.session_state and st.session_state["vin_profile"]:
             # Use the decoded make if available
             if st.session_state["vin_profile"].confidence > 0:
                 detected_make = st.session_state["vin_profile"].make

        # Run the pipeline with the detected make
        result = run_full_pipeline(
            technician_text=technician_text.strip(),
            has_video=has_video,
            labor_rate=float(labor_rate),
            shop_fees_pct=shop_fees_pct / 100.0,
            tax_pct=tax_pct / 100.0,
            vehicle_make=detected_make  # <--- The final connection!
        )
        st.session_state["pipeline_result"] = result

result = st.session_state.get("pipeline_result")

if result:
    estimate_summary = result["estimate"]["summary"]
    validation = result["validation"]

    st.subheader("Real-Time Estimate Summary")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Labor subtotal", f"${estimate_summary['labor_subtotal']:,.2f}")
    col2.metric("Parts subtotal", f"${estimate_summary['parts_subtotal']:,.2f}")
    col3.metric("Shop fees", f"${estimate_summary['shop_fees']:,.2f}")
    col4.metric("Estimate total", f"${estimate_summary['grand_total']:,.2f}")

    if validation["status"] == "pass":
        st.success("Validation Agent: Estimate is within policy and ready to present to the customer.")
    else:
        st.warning("Validation Agent: Estimate requires review before sending to the customer.")
        for w in validation["warnings"]:
            st.write(f"- {w}")

    tabs = st.tabs(["Agent Timeline", "Labor Ops", "Parts", "Estimate Preview", "Agent Audit Log"])

    with tabs[0]:
        st.markdown("### Agent Timeline")
        st.markdown("1. **Technician Input Interface** receives notes (and optional video).")
        st.markdown("2. **Video Decoder Agent** merges video/audio with text.")
        st.markdown("3. **AI Labor Agent** maps notes to standardized labor ops and times.")
        st.markdown("4. **AI Parts Agent** pulls part numbers, prices, and availability.")
        st.markdown("5. **Estimate Generator Agent** compiles totals and customer-facing estimate.")
        st.markdown("6. **Validation Agent** checks against dealership rules and flags issues.")
        st.info(
            "In production, each step would hit real systems (DMS, Xtime, OEM catalogs) via API or middleware. "
            "Here you're seeing a conceptual end-to-end run."
        )

    with tabs[1]:
        st.markdown("### Labor Operations Generated by AI Labor Agent")
        st.dataframe(result["labor"]["labor_ops"])

    with tabs[2]:
        st.markdown("### Parts Lines Generated by AI Parts Agent")
        if result["parts"]["parts_lines"]:
            st.dataframe(result["parts"]["parts_lines"])
        else:
            st.info("No parts were generated for this scenario.")

    with tabs[3]:
        st.markdown("### Customer-Facing Estimate Preview")
        st.write("This simulates the 'print preview' screen that a technician or advisor would see in Xtime/DMS.")
        st.markdown("**Labor Lines**")
        st.table(
            [
                {
                    "Op Code": op["operation_code"],
                    "Description": op["description"],
                    "Hours": op["hours"],
                    "Rate": op["rate"],
                    "Line Total": op["line_total"],
                }
                for op in result["labor"]["labor_ops"]
            ]
        )

        st.markdown("**Parts Lines**")
        if result["parts"]["parts_lines"]:
            st.table(
                [
                    {
                        "Op Code": p["operation_code"],
                        "Part #": p["part_number"],
                        "Description": p["description"],
                        "Qty": p["qty"],
                        "Unit Price": p["unit_price"],
                        "Line Total": p["line_total"],
                        "Availability": p["availability"],
                    }
                    for p in result["parts"]["parts_lines"]
                ]
            )
        else:
            st.write("No parts on this estimate.")

        st.markdown("**Totals**")
        st.json(estimate_summary)

        export_payload = {
            "technician_input": result["input"],
            "labor_ops": result["labor"]["labor_ops"],
            "parts_lines": result["parts"]["parts_lines"],
            "totals": estimate_summary,
            "validation": validation,
        }

        st.download_button(
            "Download estimate payload (JSON)",
            data=json.dumps(export_payload, indent=2),
            file_name="fixedops_ai_demo_estimate.json",
            mime="application/json",
        )

    with tabs[4]:
        st.markdown("### Agent Audit Log (Explainability Layer)")
        with st.expander("Video Decoder Agent Log", expanded=False):
            st.write("\n".join(result["video_decoder"]["log"]))

        with st.expander("AI Labor Agent Log", expanded=True):
            st.write("\n".join(result["labor"]["log"]))

        with st.expander("AI Parts Agent Log", expanded=True):
            st.write("\n".join(result["parts"]["log"]))

        with st.expander("Estimate Generator Agent Log", expanded=False):
            st.write("\n".join(result["estimate"]["log"]))

        with st.expander("Validation Agent Log", expanded=False):
            st.write("\n".join(result["validation"]["log"]))

else:
    st.info("Enter technician notes above and click **Run FixedOPS_AI Simulation** to see your system in action.")
