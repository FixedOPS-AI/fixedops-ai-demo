import streamlit as st
import pandas as pd
import time
import os
from typing import Dict, Any, List
from services.vin_decoder import VinDecoder
from services.catalog_service import CatalogService
from services.validation_service import ValidationService

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="FixedOPS_AI Demo", page_icon="🤖", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .reportview-container { margin-top: -2em; }
    .stDeployButton {display:none;}
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    .stProgress > div > div > div > div { background-color: #f63366; }
</style>
""", unsafe_allow_html=True)

# --- INITIALIZATION ---
if "vin_decoder" not in st.session_state:
    st.session_state["vin_decoder"] = VinDecoder(data_dir="data")
if "catalog_service" not in st.session_state:
    st.session_state["catalog_service"] = CatalogService(data_dir="data")
if "validation_service" not in st.session_state:
    st.session_state["validation_service"] = ValidationService()
if "current_vehicle" not in st.session_state:
    st.session_state["current_vehicle"] = None

# --- AGENT FUNCTIONS ---

def labor_agent(decoded_notes: str, labor_rate: float, vehicle_profile: Any) -> Dict[str, Any]:
    log: List[str] = []
    log.append(f"Labor Agent: Analyzed input for {vehicle_profile.year} {vehicle_profile.make} ({vehicle_profile.engine}).")
    
    labor_ops: List[Dict[str, Any]] = []
    text = decoded_notes.lower()

    # 1. BRAKES
    if any(x in text for x in ["brake", "grinding", "squeak", "pads", "rotor"]):
        labor_ops.append({
            "operation_code": "RR-BRAKE",
            "description": "Replace rear brake pads and rotors",
            "hours": 2.0,
            "rate": labor_rate,
            "req_qty": 1 
        })
        log.append("✅ Identified 'Brake Service'. Mapped to Op Code: RR-BRAKE (2.0 hrs).")

    # 2. ALTERNATOR
    if any(x in text for x in ["alternator", "charging", "battery", "voltage"]):
        labor_ops.append({
            "operation_code": "ALT-REPL",
            "description": "Alternator replacement",
            "hours": 2.5,
            "rate": labor_rate,
            "req_qty": 1
        })
        log.append("✅ Identified 'Charging System Issue'. Mapped to Op Code: ALT-REPL (2.5 hrs).")

    # 3. TIRES
    if any(x in text for x in ["tire", "tread", "bald", "flat"]):
        labor_ops.append({
            "operation_code": "TIRE-SET",
            "description": "Mount and Balance 4 Tires",
            "hours": 1.5,
            "rate": labor_rate,
            "req_qty": 4
        })
        log.append("✅ Identified 'Tire Replacement'. Mapped to Op Code: TIRE-SET (Qty 4).")

    # 4. SUSPENSION
    # Logic: Look for suspension terms. 
    if any(x in text for x in ["suspension", "strut", "shock", "clunk", "control arm"]):
        labor_ops.append({
            "operation_code": "SUSP-FRONT",
            "description": "Replace Front Suspension Components",
            "hours": 3.5,
            "rate": labor_rate,
            "req_qty": 2 # Left and Right
        })
        log.append("✅ Identified 'Suspension Noise'. Mapped to Op Code: SUSP-FRONT (Qty 2).")

    # 5. COOLING
    # FIX: Removed generic "leak" to prevent overlap with "strut leak" or "oil leak"
    if any(x in text for x in ["coolant", "radiator", "overheat", "water pump"]):
        labor_ops.append({
            "operation_code": "COOLING-SYS",
            "description": "Cooling System Service (Radiator & Flush)",
            "hours": 4.0,
            "rate": labor_rate,
            "req_qty": 1
        })
        log.append("✅ Identified 'Cooling System Failure'. Mapped to Op Code: COOLING-SYS.")

    # 6. OIL LEAKS
    if any(x in text for x in ["oil leak", "burning", "valve cover", "gasket"]):
        qty = 1
        desc = "Reseal Valve Cover Gasket"
        if vehicle_profile and any(eng in vehicle_profile.engine for eng in ["V6", "V8", "HEMI"]):
            qty = 2
            desc = f"Reseal Valve Cover Gaskets (Dual Bank - {vehicle_profile.engine})"
        
        labor_ops.append({
            "operation_code": "OIL-LEAK",
            "description": desc,
            "hours": 3.0,
            "rate": labor_rate,
            "req_qty": qty
        })
        log.append(f"✅ Identified 'Oil Leak'. Mapped to Op Code: OIL-LEAK (Qty {qty}).")

    # 7. TUNE UP (SMART CYLINDER LOGIC)
    if any(x in text for x in ["spark plug", "tune up", "misfire"]):
        # Default to 4 cylinders
        plug_qty = 4
        # Check engine profile
        if "V6" in vehicle_profile.engine:
            plug_qty = 6
        elif "V8" in vehicle_profile.engine or "HEMI" in vehicle_profile.engine:
            plug_qty = 8
            
        labor_ops.append({
            "operation_code": "SPARK-PLUG",
            "description": f"Spark Plug Replacement (Qty {plug_qty})",
            "hours": 1.5,
            "rate": labor_rate,
            "req_qty": plug_qty # Smart Qty passed to Parts Agent
        })
        log.append(f"✅ Identified 'Tune Up'. Engine is {vehicle_profile.engine} -> Ordering {plug_qty} Plugs.")

    # Fallback
    if not labor_ops:
        labor_ops.append({
            "operation_code": "GEN-DIAG",
            "description": "General Diagnosis",
            "hours": 1.0,
            "rate": labor_rate,
            "req_qty": 0
        })
        log.append("⚠️ No specific system matched. Defaulted to General Diagnosis.")

    for op in labor_ops:
        op["line_total"] = round(op["hours"] * op["rate"], 2)

    return {"labor_ops": labor_ops, "log": log}

def parts_agent(vehicle_make: str, labor_ops: List[Dict[str, Any]]) -> Dict[str, Any]:
    log = []
    log.append(f"Parts Agent: Scanning catalogs for {vehicle_make}...")
    parts_lines = []
    catalog = st.session_state["catalog_service"]

    for op in labor_ops:
        op_code = op["operation_code"]
        req_qty = op.get("req_qty", 1)

        if req_qty > 0:
            found_parts = catalog.get_parts_for_op(vehicle_make, op_code)

            if found_parts:
                for part in found_parts:
                    final_qty = req_qty
                    
                    # LOGIC: If part is a Rotor, we almost always need 2 (Axle set), 
                    # even if labor qty is 1 (one job).
                    # But if the part is a "Kit" or "Set" (like pads), we keep it at 1.
                    if "Rotor" in part["description"] and "Kit" not in part["description"] and "Set" not in part["description"]:
                        # Ensure we order at least 2 rotors for a brake job
                         final_qty = 2
                    
                    # LOGIC: If part is a "Set" (like Pad Set), override labor qty back to 1
                    # (Because labor might ask for "2" sides, but the part comes as a box of 4 pads)
                    if "Set" in part["description"] or "Kit" in part["description"]:
                        final_qty = 1 
                    
                    part["qty"] = final_qty
                    part["line_total"] = part["qty"] * part["unit_price"]
                    
                    if "cost_price" in part:
                         part["cost_total"] = part["qty"] * part["cost_price"]
                    else:
                        part["cost_total"] = 0.0

                    parts_lines.append(part)
                    log.append(f"🔹 Match Found: {part['part_number']} - {part['description']} (Qty {final_qty})")
            else:
                # FIX: ADD "make" TO GENERIC PART TO PREVENT CRASH
                generic_part = {
                    "make": vehicle_make, # <--- THIS WAS MISSING
                    "operation_code": op_code,
                    "part_number": "GEN-PART",
                    "description": f"Generic Part for {op_code}",
                    "qty": req_qty,
                    "unit_price": 50.00,
                    "cost_price": 25.00,
                    "stock_source": "Local Auto Parts",
                    "availability": "On Demand"
                }
                generic_part["line_total"] = generic_part["qty"] * generic_part["unit_price"]
                generic_part["cost_total"] = generic_part["qty"] * generic_part["cost_price"]
                parts_lines.append(generic_part)
                log.append(f"⚠️ No Match: Added generic placeholder for {op_code}.")

    return {"parts_lines": parts_lines, "log": log}

def validation_agent(estimate_summary: Dict[str, float], parts_lines: List[Dict[str, Any]]) -> Dict[str, Any]:
    if "validation_service" not in st.session_state:
        return {"status": "pass", "warnings": []}
    return st.session_state["validation_service"].validate_estimate(estimate_summary, parts_lines)

# --- MAIN UI LAYOUT ---

# 1. SIDEBAR
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", width=200)
else:
    st.sidebar.markdown("## 🤖 FixedOPS_AI")
    st.sidebar.caption("Virtual Inspired Co.")

st.sidebar.title("1️⃣ Scenario Setup")
scenario_mode = st.sidebar.selectbox(
    "Choose Scenario:", 
    ["Custom Input", "Brake Noise", "Check Engine Light", "Suspension Clunk", "Coolant Leak"]
)

st.sidebar.markdown("---")
st.sidebar.title("2️⃣ Dealer Config")
labor_rate_input = st.sidebar.number_input("Labor Rate ($/hr)", value=160.00, step=5.0)
shop_fees_flat = st.sidebar.number_input("Shop Fees (Flat $)", value=35.00, step=5.0)
tax_rate_pct = st.sidebar.slider("Sales Tax (%)", 0.0, 10.0, 7.5) / 100.0

# --- MAIN PAGE ---
st.title("FixedOPS_AI Demo")

# TIMELINE VISUAL
st.caption("System Status: Agents Online")
progress_col1, progress_col2 = st.columns([4,1])
with progress_col1:
    st.markdown("`Technician Input` ➔ `VIN Decoding` ➔ `Labor & Parts Agents` ➔ `Validation` ➔ `Final Estimate`")

# 1. VIN SECTION
with st.expander("Vehicle Identification (Multi-Agent Context)", expanded=True):
    c1, c2 = st.columns([3, 1])
    with c2:
        st.write("**Quick Select:**")
        if st.button("Load Honda Civic"):
            st.session_state["vin_input"] = "1HGCM82633A123451"
            st.session_state["current_vehicle"] = None 
        if st.button("Load Ford F-150"):
            st.session_state["vin_input"] = "1FTEW1E45KFA98231"
            st.session_state["current_vehicle"] = None
        if st.button("Load Ram 1500"):
            st.session_state["vin_input"] = "1C6SRFGT8MN542103"
            st.session_state["current_vehicle"] = None

    with c1:
        vin_val = st.session_state.get("vin_input", "1HGCM82633A123451")
        vin_input = st.text_input("Enter VIN:", value=vin_val)

    if st.button("Search / Decode VIN") or st.session_state["current_vehicle"] is None:
        profile = st.session_state["vin_decoder"].decode(vin_input)
        st.session_state["current_vehicle"] = profile
    
    vehicle = st.session_state["current_vehicle"]
    if vehicle and vehicle.make != "UNKNOWN":
        st.success(f"VIN Decoded: {vehicle.year} {vehicle.make} {vehicle.model}")
        vc1, vc2, vc3 = st.columns(3)
        vc1.metric("Engine", vehicle.engine)
        vc2.metric("Trim", vehicle.trim)
        vc3.metric("Drivetrain", vehicle.drivetrain)
    else:
        st.warning("Please decode a valid VIN to proceed.")

# 2. INPUT SECTION
st.header("Technician Input")
default_notes = ""
if scenario_mode == "Brake Noise":
    default_notes = "Customer states grinding noise from rear. Tech inspected and found rear pads metal to metal."
elif scenario_mode == "Check Engine Light":
    default_notes = "Check engine light on. Scanned codes P0300. Found worn spark plugs."
elif scenario_mode == "Suspension Clunk":
    default_notes = "Customer complains of clunking over bumps. Front struts are leaking."
elif scenario_mode == "Coolant Leak":
    default_notes = "Vehicle overheating. Radiator is cracked and leaking coolant."

# TOOLTIP FEATURE
tech_notes = st.text_area(
    "Technician Notes / Multimodal Input:", 
    value=default_notes, 
    height=100,
    help="In production, technicians can upload voice memos, videos (Walkaround), or images. The Video Decoder Agent extracts text from these inputs automatically."
)

if st.button("▶ Run FixedOPS_AI Simulation", type="primary"):
    if not vehicle or vehicle.make == "UNKNOWN":
        st.error("Please decode a VIN first.")
    else:
        with st.spinner("AI Agents working..."):
            # 1. Labor Agent
            labor_result = labor_agent(tech_notes, labor_rate_input, vehicle)

            # 2. Parts Agent
            parts_result = parts_agent(vehicle.make, labor_result["labor_ops"])

            # 3. Calculations
            labor_total = sum(item["line_total"] for item in labor_result["labor_ops"])
            parts_total = sum(item["line_total"] for item in parts_result["parts_lines"])
            subtotal = labor_total + parts_total
            shop_fees_amt = shop_fees_flat
            tax_amt = round((subtotal + shop_fees_amt) * tax_rate_pct, 2)
            grand_total = subtotal + shop_fees_amt + tax_amt

            summary = {
                "labor_subtotal": labor_total,
                "parts_subtotal": parts_total,
                "shop_fees": shop_fees_amt,
                "tax": tax_amt,
                "grand_total": grand_total
            }

            # 4. Validation
            validation_result = validation_agent(summary, parts_result["parts_lines"])

            # --- DISPLAY RESULTS ---
            st.markdown("---")
            st.header("Real-Time Estimate Summary")
            
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Labor", f"${labor_total:,.2f}")
            c2.metric("Parts", f"${parts_total:,.2f}")
            c3.metric("Shop Fees", f"${shop_fees_amt:,.2f}")
            c4.metric("Sales Tax", f"${tax_amt:,.2f}")
            c5.metric("Total", f"${grand_total:,.2f}")

            if validation_result["status"] == "review":
                st.error(f"⚠️ Manager Approval Required")
                for w in validation_result["warnings"]:
                    st.write(f" - {w}")
            else:
                st.success("✅ Auto-Approved")

            # TABS
            tab1, tab2, tab3, tab4 = st.tabs(["Estimate Preview", "Labor Detail", "Parts Detail", "Agent Logs"])

            with tab1:
                st.subheader("Customer Estimate Preview")
                st.markdown("#### Service Operation: Recommended Repairs")
                
                for op in labor_result["labor_ops"]:
                    st.markdown(f"**{op['description']}**")
                    st.caption(f"Op Code: {op['operation_code']} | Time: {op['hours']} hrs")
                    
                    related_parts = [p for p in parts_result["parts_lines"] if p['operation_code'] == op['operation_code']]
                    if related_parts:
                        for p in related_parts:
                            st.text(f"  └─ Part: {p['part_number']} - {p['description']} (Qty {p['qty']}) ... ${p['unit_price']:.2f} ea")
                    else:
                        st.text("  └─ No parts required")
                    st.markdown("---")
                
                st.markdown(f"### **Grand Total: ${grand_total:,.2f}**")

            with tab2:
                df_labor = pd.DataFrame(labor_result["labor_ops"])
                if not df_labor.empty:
                    # INDEX SHIFT START (0 -> 1)
                    df_labor.index = df_labor.index + 1
                    
                    # Formatting
                    df_labor["rate"] = df_labor["rate"].apply(lambda x: f"${x:.2f}")
                    df_labor["line_total"] = df_labor["line_total"].apply(lambda x: f"${x:.2f}")
                    st.dataframe(df_labor)
                else:
                    st.write("No labor operations.")

            with tab3:
                df_parts = pd.DataFrame(parts_result["parts_lines"])
                if not df_parts.empty:
                    # INDEX SHIFT START (0 -> 1)
                    df_parts.index = df_parts.index + 1

                    # RENAMING for "Back of House" View
                    df_view = df_parts.rename(columns={
                        "make": "Make",
                        "part_number": "Part #",
                        "description": "Description",
                        "qty": "Qty",
                        "unit_price": "List Price",
                        "line_total": "List Total",
                        "cost_price": "Dealer Cost",
                        "cost_total": "Total Cost",
                        "availability": "Availability"
                    })
                    
                    # Formatting Currency
                    for col in ["List Price", "List Total", "Dealer Cost", "Total Cost"]:
                        # Safety check if column exists (handles generics safely now)
                        if col in df_view.columns:
                            df_view[col] = df_view[col].apply(lambda x: f"${x:.2f}")

                    # Select specific column order
                    cols = ["Make", "Part #", "Description", "Availability", "Qty", "List Price", "List Total", "Dealer Cost", "Total Cost"]
                    st.dataframe(df_view[cols])
                else:
                    st.write("No parts found.")

            with tab4:
                st.subheader("Agent Decision Logic")
                
                with st.expander("AI Labor Agent Log", expanded=True):
                    for line in labor_result["log"]:
                        st.markdown(f"- {line}")
                
                with st.expander("AI Parts Agent Log", expanded=True):
                    for line in parts_result["log"]:
                        st.markdown(f"- {line}")
                
                with st.expander("Validation Agent Log", expanded=True):
                    for line in validation_result["log"]:
                        if "FLAGGED" in line:
                            st.markdown(f"- :red[{line}]")
                        elif "green" in line:
                             st.markdown(f"- :green[{line.replace(':green[','').replace(']','')}]")
                        else:
                            st.markdown(f"- {line}")

# DISCLAIMER
st.markdown("---")
st.caption("This demo uses simple rule-based logic to simulate FixedOPS_AI’s multi-agent design. In production, each block would be a real AI agent calling Dealertrack or applicable DMS, Xtime, or applicable estimating software/interface and OEM APIs.")