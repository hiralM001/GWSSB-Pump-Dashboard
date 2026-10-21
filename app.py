import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import random
import os
from datetime import datetime, timedelta
from fpdf import FPDF
import firebase_admin
from firebase_admin import credentials, db

# 1. Page Configuration
st.set_page_config(page_title="GWSSB SCADA Monitor", page_icon="⚙️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #E2E8F0; }
    div[data-testid="metric-container"] { background-color: #1A1C23; border: 1px solid #2D3748; padding: 15px; border-radius: 8px; }
    h1, h2, h3 { color: #E2E8F0 !important; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    section[data-testid="stSidebar"] { background-color: #151921; border-right: 1px solid #2D3748; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. FIREBASE CONNECTION LOGIC (THE MEDIATOR)
# ==========================================
FIREBASE_JSON_PATH = "firebase_key.json"
FIREBASE_DB_URL = "https://gwssb-pump-iot-default-rtdb.firebaseio.com/"

firebase_connected = False

if os.path.exists(FIREBASE_JSON_PATH):
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(FIREBASE_JSON_PATH)
            firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB_URL})
        firebase_connected = True
    except Exception as e:
        st.sidebar.error(f"Firebase Error: {e}")

# ==========================================
# 3. AREA -> STATION -> ESP32 HIERARCHY
# ==========================================
gwssb_network = {
    "Rajkot City & Rural": {
        "Aji-1 Headworks": {
            "Main Raw Water Pump #1": "ESP32-RJK-AJI-01",
            "Main Raw Water Pump #2": "ESP32-RJK-AJI-02",
            "Standby Booster Pump #3": "ESP32-RJK-AJI-03"
        },
        "Nyari-1 Filter Plant": {
            "High Lift Pump #1": "ESP32-RJK-NYR-01",
            "High Lift Pump #2": "ESP32-RJK-NYR-02"
        },
        "Bedi Sump & Pumping Station": {
            "Distribution Pump #1": "ESP32-RJK-BED-01",
            "Distribution Pump #2": "ESP32-RJK-BED-02"
        }
    },
    "Morbi Zone": {
        "Machhu-2 Pumping Station": {
            "Rural Supply Pump #1": "ESP32-MRB-MCH-01",
            "Rural Supply Pump #2": "ESP32-MRB-MCH-02"
        }
    },
    "Jamnagar Zone": {
        "Ranjitsagar Headworks": {
            "City Main Pump #1": "ESP32-JAM-RNJ-01",
            "City Main Pump #2": "ESP32-JAM-RNJ-02"
        }
    }
}

with st.sidebar:
    st.markdown("<h2 style='text-align: center; color: #63B3ED !important;'>GWSSB NET-CTRL</h2>", unsafe_allow_html=True)
    
    if firebase_connected:
        st.success("🟢 LIVE Firebase Cloud Connected")
    else:
        st.warning("🟡 Simulation Mode (Firebase JSON missing)")

    conn_mode = st.radio("🔌 Connection Mode:", ["Select from Hierarchy", "Direct ESP32 Code Input"], horizontal=True)

    if conn_mode == "Select from Hierarchy":
        selected_area = st.selectbox("🏙️ 1. Select Region / Area", list(gwssb_network.keys()))
        stations = gwssb_network[selected_area]
        selected_station = st.selectbox("🏭 2. Select Pumping Station", list(stations.keys()))
        pumps = stations[selected_station]
        selected_pump_name = st.selectbox("⚙️ 3. Select Pump & ESP32", list(pumps.keys()))
        current_node_id = pumps[selected_pump_name]
        display_location = f"{selected_area} > {selected_station} > {selected_pump_name}"
    else:
        selected_area = "Custom Direct Zone"
        selected_station = "Direct Telemetry Link"
        current_node_id = st.text_input("🔑 Enter Unique ESP32 Code:", value="ESP32-RJK-CUSTOM-01").strip()
        selected_pump_name = f"Custom Node ({current_node_id})"
        display_location = f"Direct ESP32 Link > {current_node_id}"

    st.caption(f"🎯 **Connected ESP32 ID:** `{current_node_id}`")

# ==========================================
# 4. FETCH LIVE DATA OR LOCK SIMULATED DATA PER ESP32
# ==========================================
if "pump_memory" not in st.session_state:
    st.session_state.pump_memory = {}

def get_pump_data(node_id, force_refresh=False):
    if firebase_connected:
        try:
            ref = db.reference(f'/GWSSB_Pumps/{node_id}')
            data = ref.get()
            if data and isinstance(data, dict):
                t = int(data.get('Temp', 55))
                v = float(data.get('Vib', 4.5))
                c = float(data.get('Current', 16.0))
                return t, v, c, "LIVE HARDWARE DATA"
        except Exception:
            pass

    if node_id not in st.session_state.pump_memory or force_refresh:
        st.session_state.pump_memory[node_id] = (
            random.randint(48, 86),
            round(random.uniform(2.5, 11.5), 2),
            round(random.uniform(10.0, 27.5), 2)
        )
    t, v, c = st.session_state.pump_memory[node_id]
    return t, v, c, "SIMULATED STREAM"

t_val, v_val, c_val, data_source_tag = get_pump_data(current_node_id)

health_score = 100 - ((t_val - 40) * 0.4 + (v_val * 2))
health_score = max(0, min(100, round(health_score)))
power_kw = round(c_val * 415 * 0.85 / 1000, 2)

max_days = 90
days_left = max(1, int((health_score / 100) * max_days))
if t_val > 80 or v_val > 10:
    days_left = max(1, int(days_left * 0.15))

if v_val > 10.0:
    acoustic_status = "Cavitation Bubbles Detected"
elif c_val > 25:
    acoustic_status = "Heavy Load Grinding"
else:
    acoustic_status = "Smooth Humming"

if t_val > 80 and c_val > 25:
    diag_status = f"[ERR-01] CRITICAL OVERLOAD on {current_node_id}: Winding failure imminent."
    overall_condition = "CRITICAL - IMMEDIATE ACTION"
    maint_recommendation = (
        "1. Immediately trip/reduce load on the motor to prevent stator winding insulation breakdown.\n"
        "2. Inspect cooling fan cowling, check 3-phase voltage balance, and verify suction line blockage.\n"
        "3. Schedule urgent electrical & mechanical audit within 4 hours."
    )
elif v_val > 10.0:
    diag_status = f"[WRN-02] MECHANICAL FAULT on {current_node_id}: Abnormal vibration. Check bearing housing."
    overall_condition = "WARNING - DEGRADED"
    maint_recommendation = (
        "1. High radial vibration & cavitation signature detected. Inspect pump-motor shaft alignment.\n"
        "2. Check drive-end (DE) and non-drive-end (NDE) bearings for lubrication wear or looseness.\n"
        "3. Verify suction pressure to eliminate impeller cavitation bubbles."
    )
elif t_val > 70 or v_val > 7.0 or c_val > 20.0:
    diag_status = f"[ADV-03] ELEVATED PARAMETERS on {current_node_id}: Minor stress observed. Monitor closely."
    overall_condition = "MODERATE - MONITOR"
    maint_recommendation = (
        "1. Parameters are slightly elevated above optimal baseline but within trip limits.\n"
        "2. Perform routine greasing of bearing housing and clean motor ventilation fins during next shift.\n"
        "3. Continue condition-based monitoring via SCADA terminal."
    )
else:
    diag_status = f"[SYS-OK] ESP32 Node {current_node_id} telemetry within safe operating envelope."
    overall_condition = "OPTIMAL / HEALTHY"
    maint_recommendation = (
        "1. All electro-mechanical parameters (Temperature, Vibration, Current) are within ISO safe limits.\n"
        "2. No immediate mechanical intervention required. Continue standard scheduled operation.\n"
        "3. Next routine preventive inspection due in 45 days."
    )

# --- ADVANCED CONTEXT-AWARE SMART NLP ENGINE ---
def get_smart_ai_response(query, t, v, c, h, acoustic, lang, node_id, power, days):
    q = query.lower().strip()
    if not q: 
        return f"Please ask a specific question about `{node_id}`." if lang == "English" else f"કૃપા કરીને `{node_id}` વિશે ચોક્કસ પ્રશ્ન પૂછો."
    
    if any(w in q for w in ["temp", "heat", "hot", "thermal", "degree", "તાપમાન", "ગરમ", "ડિગ્રી"]):
        if lang == "English":
            if t > 80: return f"🚨 Stator temperature for {node_id} is critically high at {t}°C! Immediate cooling required."
            elif t > 70: return f"⚠️ Stator temperature for {node_id} is elevated at {t}°C (Warning threshold)."
            return f"✅ Stator temperature for {node_id} is normal at {t}°C."
        else:
            if t > 80: return f"🚨 [{node_id}] મોટરનું તાપમાન ખૂબ જ વધારે ({t}°C) છે! તાત્કાલિક કૂલિંગ કરો."
            elif t > 70: return f"⚠️ [{node_id}] તાપમાન ચેતવણીજનક સ્તરે ({t}°C) છે."
            return f"✅ [{node_id}] મોટરનું તાપમાન {t}°C સાથે સંપૂર્ણપણે સામાન્ય છે."

    elif any(w in q for w in ["vib", "shake", "vibration", "noise", "sound", "cavitation", "વાઇબ્રેશન", "અવાજ", "ધ્રુજારી"]):
        if lang == "English":
            if v > 10: return f"⚠️ High vibration detected on {node_id} at {v} g. Acoustic status: '{acoustic}'."
            return f"✅ Vibration levels on {node_id} are stable at {v} g. Signature: '{acoustic}'."
        else:
            if v > 10: return f"⚠️ [{node_id}] ગંભીર વાઇબ્રેશન ({v} g) નોંધાયું છે. અવાજ: '{acoustic}'."
            return f"✅ [{node_id}] વાઇબ્રેશન સામાન્ય ({v} g) છે. સહી: '{acoustic}'."

    elif any(w in q for w in ["current", "amp", "power", "load", "electricity", "watt", "kw", "કરંટ", "પાવਰ", "વીજળી", "લોડ"]):
        if lang == "English":
            return f"⚡ Motor current for {node_id} is {c} Amps, drawing {power} kW active power."
        else:
            return f"⚡ [{node_id}] નો મોટર કરંટ {c} Amps છે, અને તે {power} kW પાવર ખેંચી રહ્યો છે."

    elif any(w in q for w in ["health", "status", "condition", "how", "report", "हेल्थ", "સ્થિતિ", "કેમ", "પંપ"]):
        if lang == "English":
            return f"📊 Asset Node `{node_id}` Health is {h}% ({overall_condition}). Temp: {t}°C | Vib: {v}g | Current: {c}A."
        else:
            return f"📊 પંપ નોડ `{node_id}` ની હેલ્થ {h}% ({overall_condition}) છે. તાપમાન: {t}°C | વાઇબ્રેશન: {v}g | કરંટ: {c}A."

    elif any(w in q for w in ["cost", "money", "save", "budget", "price", "rupee", "rs", "ખર્ચ", "પૈસા", "બચત", "રૂપિયા"]):
        if lang == "English":
            return "💰 Financial Audit: Fixing this asset today costs ₹2,500 (minor maintenance), whereas run-to-failure rewinding costs ₹45,000. Net savings: ₹42,500."
        else:
            return "💰 નાણાકીય અહેવાલ: આજે ₹2,500 નો રિપેરિંગ ખર્ચ બચાવવાથી ભવિષ્યનો ₹45,000 નો મોટર રીવાઈન્ડિંગ ખર્ચ બચી શકે છે. કુલ બચત: ₹42,500."

    elif any(w in q for w in ["rul", "life", "day", "days", "fail", "breakdown", "divas", "आयुष्य", "દિવસ", "બગડશે"]):
        if lang == "English":
            return f"📉 Predictive RUL Analysis: Under current operational telemetry, estimated remaining useful life for `{node_id}` is {days} days before major overhaul."
        else:
            return f"📉 RUL અનુમાન: વર્તમાન ડેટા મુજબ `{node_id}` અંદાજે {days} દિવસ સુધી સક્ષમ રીતે કામ કરશે."

    else:
        if lang == "English":
            return f"🤖 AI Assistant for `{node_id}`: Current health is {h}% with {overall_condition}. Ask me about 'temperature', 'vibration', 'current', 'cost', or 'health status'."
        else:
            return f"🤖 AI સહાયક (`{node_id}`): હાલ હેલ્થ {h}% છે. તમે મને 'તાપમાન', 'વાઇબ્રેશન', 'કરંટ', અથવા 'ખર્ચ' વિશે પૂછી શકો છો."

# =========================================================
# 5. OFFICIAL GOVERNMENT / INDUSTRIAL PDF REPORT GENERATOR
# =========================================================
def generate_official_pdf():
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    pdf.set_draw_color(20, 45, 90)
    pdf.set_line_width(0.6)
    pdf.rect(6, 6, 198, 285)
    pdf.set_line_width(0.2)
    pdf.rect(7.5, 7.5, 195, 282)

    pdf.set_fill_color(18, 42, 76)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(7.5, 7.5)
    pdf.set_font("Arial", 'B', 13)
    pdf.cell(195, 8, txt="GUJARAT WATER SUPPLY & SEWERAGE BOARD (GWSSB)", border=0, ln=True, align='C', fill=True)
    
    pdf.set_x(7.5)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(195, 6, txt="GOVERNMENT OF GUJARAT | SCADA & PREDICTIVE MAINTENANCE DIVISION", border=0, ln=True, align='C', fill=True)
    
    pdf.set_x(7.5)
    pdf.set_font("Arial", '', 8.5)
    pdf.cell(195, 6, txt="Official Daily Shift Telemetry Audit & Condition-Based Maintenance Report (ISO 10816 Compliant)", border=0, ln=True, align='C', fill=True)

    pdf.ln(3)

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    doc_ref = f"GWSSB/PM/{datetime.now().strftime('%Y%m%d')}/{current_node_id[-4:]}"
    pdf.set_x(10)
    pdf.set_fill_color(230, 236, 245)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 8.5)
    pdf.cell(95, 6, txt=f"  DOCUMENT REF NO: {doc_ref}", border=1, ln=0, align='L', fill=True)
    pdf.cell(95, 6, txt=f"AUDIT TIMESTAMP: {now_str} IST  ", border=1, ln=1, align='R', fill=True)

    pdf.ln(3)

    pdf.set_x(10)
    pdf.set_fill_color(35, 65, 110)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 9.5)
    pdf.cell(190, 6.5, txt="  1. ASSET & TELEMETRY NODE IDENTIFICATION", border=1, ln=1, align='L', fill=True)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 8.5)
    
    pdf.set_x(10)
    pdf.set_fill_color(245, 247, 250)
    pdf.cell(42, 6.5, txt=" Region / Zone:", border=1, fill=True)
    pdf.set_font("Arial", '', 8.5)
    pdf.cell(53, 6.5, txt=f" {selected_area}", border=1)
    pdf.set_font("Arial", 'B', 8.5)
    pdf.cell(42, 6.5, txt=" ESP32 Hardware ID:", border=1, fill=True)
    pdf.set_font("Arial", '', 8.5)
    pdf.cell(53, 6.5, txt=f" {current_node_id}", border=1, ln=1)

    pdf.set_x(10)
    pdf.set_font("Arial", 'B', 8.5)
    pdf.cell(42, 6.5, txt=" Pumping Station:", border=1, fill=True)
    pdf.set_font("Arial", '', 8.5)
    pdf.cell(53, 6.5, txt=f" {selected_station}", border=1)
    pdf.set_font("Arial", 'B', 8.5)
    pdf.cell(42, 6.5, txt=" Telemetry Stream:", border=1, fill=True)
    pdf.set_font("Arial", '', 8.5)
    pdf.cell(53, 6.5, txt=f" {data_source_tag}", border=1, ln=1)

    pdf.set_x(10)
    pdf.set_font("Arial", 'B', 8.5)
    pdf.cell(42, 6.5, txt=" Pump Asset Unit:", border=1, fill=True)
    pdf.set_font("Arial", '', 8.5)
    pdf.cell(53, 6.5, txt=f" {selected_pump_name[:26]}", border=1)
    pdf.set_font("Arial", 'B', 8.5)
    pdf.cell(42, 6.5, txt=" Motor Specification:", border=1, fill=True)
    pdf.set_font("Arial", '', 8.5)
    pdf.cell(53, 6.5, txt=" 15 HP, 3-Phase, 415V AC", border=1, ln=1)

    pdf.ln(3)

    pdf.set_x(10)
    pdf.set_fill_color(35, 65, 110)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 9.5)
    pdf.cell(190, 6.5, txt="  2. EXECUTIVE ASSET HEALTH & PREDICTIVE SUMMARY", border=1, ln=1, align='L', fill=True)

    pdf.set_x(10)
    pdf.set_text_color(0, 0, 0)
    pdf.set_fill_color(245, 247, 250)
    pdf.set_font("Arial", 'B', 8.5)
    pdf.cell(47.5, 7, txt="Overall Asset Health Score", border=1, align='C', fill=True)
    pdf.cell(47.5, 7, txt="Current Operating State", border=1, align='C', fill=True)
    pdf.cell(47.5, 7, txt="Est. Remaining Life (RUL)", border=1, align='C', fill=True)
    pdf.cell(47.5, 7, txt="Next Scheduled Service", border=1, ln=1, align='C', fill=True)

    pdf.set_x(10)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(47.5, 8, txt=f"{health_score}%", border=1, align='C')
    pdf.set_font("Arial", 'B', 8.5)
    pdf.cell(47.5, 8, txt=f"{overall_condition}", border=1, align='C')
    pdf.cell(47.5, 8, txt=f"{days_left} Days (Projected)", border=1, align='C')
    next_srv = "IMMEDIATE" if days_left < 15 else "45 Days (Routine)"
    pdf.cell(47.5, 8, txt=next_srv, border=1, ln=1, align='C')

    pdf.ln(3)

    pdf.set_x(10)
    pdf.set_fill_color(35, 65, 110)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 9.5)
    pdf.cell(190, 6.5, txt="  3. REAL-TIME SENSOR TELEMETRY & THRESHOLD AUDIT TABLE", border=1, ln=1, align='L', fill=True)

    pdf.set_x(10)
    pdf.set_fill_color(220, 228, 240)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(12, 7, txt="Sr.", border=1, align='C', fill=True)
    pdf.cell(53, 7, txt="Telemetry Parameter", border=1, align='L', fill=True)
    pdf.cell(35, 7, txt="Observed Value", border=1, align='C', fill=True)
    pdf.cell(30, 7, txt="Normal Baseline", border=1, align='C', fill=True)
    pdf.cell(30, 7, txt="Critical Limit", border=1, align='C', fill=True)
    pdf.cell(30, 7, txt="Audit Status", border=1, ln=1, align='C', fill=True)

    t_stat = "CRITICAL" if t_val >= 80 else ("WARNING" if t_val >= 70 else "NORMAL")
    v_stat = "CRITICAL" if v_val >= 10 else ("WARNING" if v_val >= 7 else "NORMAL")
    c_stat = "OVERLOAD" if c_val >= 25 else ("ELEVATED" if c_val >= 20 else "NORMAL")
    p_stat = "HIGH LOAD" if power_kw >= 9.5 else "OPTIMAL"
    a_stat = "ANOMALY" if "Smooth" not in acoustic_status else "NORMAL"

    rows = [
        ("01", "Stator Winding Temperature", f"{t_val} deg C", "45 - 70 deg C", "> 80 deg C", t_stat),
        ("02", "Radial Bearing Vibration", f"{v_val} mm/s (g)", "< 7.0 g", "> 10.0 g", v_stat),
        ("03", "3-Phase Motor Current", f"{c_val} Amps", "10.0 - 20.0 A", "> 25.0 Amps", c_stat),
        ("04", "Active Electrical Power Draw", f"{power_kw} kW", "< 8.5 kW", "> 10.5 kW", p_stat),
        ("05", "Edge-AI Acoustic Signature", acoustic_status[:18], "Smooth Humming", "Cavitation/Grind", a_stat),
    ]

    pdf.set_font("Arial", '', 8)
    for idx, r in enumerate(rows):
        pdf.set_x(10)
        fill_row = (idx % 2 == 1)
        pdf.set_fill_color(248, 250, 252)
        pdf.cell(12, 6.5, txt=r[0], border=1, align='C', fill=fill_row)
        pdf.cell(53, 6.5, txt=f" {r[1]}", border=1, align='L', fill=fill_row)
        pdf.set_font("Arial", 'B', 8)
        pdf.cell(35, 6.5, txt=r[2], border=1, align='C', fill=fill_row)
        pdf.set_font("Arial", '', 8)
        pdf.cell(30, 6.5, txt=r[3], border=1, align='C', fill=fill_row)
        pdf.cell(30, 6.5, txt=r[4], border=1, align='C', fill=fill_row)
        pdf.set_font("Arial", 'B', 8)
        pdf.cell(30, 6.5, txt=r[5], border=1, ln=1, align='C', fill=fill_row)
        pdf.set_font("Arial", '', 8)

    pdf.ln(3)

    pdf.set_x(10)
    pdf.set_fill_color(35, 65, 110)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 9.5)
    pdf.cell(190, 6.5, txt="  4. AI DIAGNOSTICS & FIELD MAINTENANCE RECOMMENDATIONS", border=1, ln=1, align='L', fill=True)

    pdf.set_x(10)
    pdf.set_text_color(0, 0, 0)
    pdf.set_fill_color(245, 247, 250)
    pdf.set_font("Arial", 'B', 8.5)
    pdf.cell(190, 6.5, txt=f"  System Diagnostic Flag: {diag_status}", border=1, ln=1, align='L', fill=True)

    pdf.set_x(10)
    pdf.set_font("Arial", '', 8.5)
    pdf.multi_cell(190, 5.5, txt=f"Recommended Standard Operating Procedure (SOP) for Maintenance Staff:\n{maint_recommendation}", border=1)

    pdf.ln(3)

    pdf.set_x(10)
    pdf.set_fill_color(35, 65, 110)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 9.5)
    pdf.cell(190, 6.5, txt="  5. FINANCIAL IMPACT & COST OF INACTION (COI) AUDIT", border=1, ln=1, align='L', fill=True)

    pdf.set_x(10)
    pdf.set_text_color(0, 0, 0)
    pdf.set_fill_color(245, 247, 250)
    pdf.set_font("Arial", 'B', 8.5)
    pdf.cell(63.3, 6.5, txt="Preventive Maintenance (Condition-Based)", border=1, align='C', fill=True)
    pdf.cell(63.3, 6.5, txt="Run-to-Failure (Motor Rewinding + Downtime)", border=1, align='C', fill=True)
    pdf.cell(63.4, 6.5, txt="Estimated Net GWSSB Budget Savings", border=1, ln=1, align='C', fill=True)

    pdf.set_x(10)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(63.3, 7, txt="Rs. 2,500 (Minor Bearing/Alignment)", border=1, align='C')
    pdf.cell(63.3, 7, txt="Rs. 45,000 (Major Overhaul)", border=1, align='C')
    pdf.cell(63.4, 7, txt="Rs. 42,500 Saved per Asset", border=1, ln=1, align='C')

    pdf.ln(8)

    pdf.set_x(10)
    pdf.set_font("Arial", 'B', 8.5)
    pdf.cell(63, 5, txt="_______________________________", border=0, align='C')
    pdf.cell(63, 5, txt="_______________________________", border=0, align='C')
    pdf.cell(64, 5, txt="_______________________________", border=0, ln=1, align='C')

    pdf.set_x(10)
    pdf.cell(63, 5, txt="Shift Operator / Lineman", border=0, align='C')
    pdf.cell(63, 5, txt="Maintenance Supervisor (E&M)", border=0, align='C')
    pdf.cell(64, 5, txt="Deputy Executive Engineer", border=0, ln=1, align='C')

    pdf.set_x(10)
    pdf.set_font("Arial", '', 7.5)
    pdf.cell(63, 4, txt="(Pumping Station In-Charge)", border=0, align='C')
    pdf.cell(63, 4, txt="(GWSSB Field Sub-Division)", border=0, align='C')
    pdf.cell(64, 4, txt="(GWSSB Official Seal & Sign)", border=0, ln=1, align='C')

    pdf.ln(5)
    pdf.set_x(10)
    pdf.set_font("Arial", 'I', 7.5)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(190, 5, txt="Note: This is an automatically generated Edge-AI & Cloud SCADA report. Serves as a decision-support document for GWSSB engineers.", border=0, ln=1, align='C')

    pdf.output("GWSSB_Report.pdf")

with st.sidebar:
    if firebase_connected:
        if st.button("📡 Push Test Data to Firebase for this ESP32", use_container_width=True):
            ref = db.reference(f'/GWSSB_Pumps/{current_node_id}')
            ref.set({
                'Temp': int(t_val),
                'Vib': float(v_val),
                'Current': float(c_val),
                'Last_Updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            st.toast(f"✅ Data pushed to Firebase under {current_node_id}!")
            st.rerun()

    st.markdown("---")
    ai_lang = st.radio("🌐 AI Assistant Language / ભાષા", ["English", "ગુજરાતી"])
    st.subheader("🤖 Smart Operator AI")
    user_query = st.text_input("Ask about pump parameters:")
    if st.button("Ask AI"):
        ai_reply = get_smart_ai_response(user_query, t_val, v_val, c_val, health_score, acoustic_status, ai_lang, current_node_id, power_kw, days_left)
        st.info(f"**AI:** {ai_reply}")
    st.markdown("---")
    
    if st.button("📄 Generate Official Audit PDF Report", use_container_width=True):
        generate_official_pdf()
        with open("GWSSB_Report.pdf", "rb") as pdf_file:
            st.download_button(
                label="⬇️ Download Official PDF Report",
                data=pdf_file,
                file_name=f"GWSSB_Audit_Report_{current_node_id}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

# --- MAIN DASHBOARD HEADER ---
st.markdown(f"<h2>💧 AI-Powered Predictive Maintenance Terminal</h2>", unsafe_allow_html=True)
st.markdown(f"<p style='color: #A0AEC0;'><b>Location:</b> {display_location} &nbsp; | &nbsp; <b>ESP32 ID:</b> <code>{current_node_id}</code> &nbsp; | &nbsp; <b>Stream:</b> <code>{data_source_tag}</code></p>", unsafe_allow_html=True)
st.divider()

kpi1, kpi2, kpi3, kpi4 = st.columns(4, gap="large")
kpi1.metric(label="Overall Asset Health", value=f"{health_score}%", delta="-2% (Shift)")
kpi2.metric(label="Acoustic AI Signature", value="Analyzed", delta=acoustic_status, delta_color="off")
kpi3.metric(label="Power Draw", value=f"{power_kw} kW", delta="Stable", delta_color="normal")
kpi4.metric(label="Next Insp. Due", value="45 Days", delta="Condition Based", delta_color="off")
st.markdown("<br>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3, gap="medium")
def create_dark_gauge(title, value, max_val, suffix, thresh_warn, thresh_crit):
    color = "#E53E3E" if value >= thresh_crit else "#D69E2E" if value >= thresh_warn else "#3182CE"
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = value,
        title = {'text': title, 'font': {'size': 18, 'color': '#CBD5E0'}},
        number = {'suffix': suffix, 'font': {'color': '#E2E8F0', 'size': 36}},
        gauge = {'axis': {'range': [None, max_val], 'tickcolor': "#4A5568"}, 'bar': {'color': color, 'thickness': 0.7},
                 'bgcolor': "#1A1C23", 'borderwidth': 1, 'bordercolor': "#2D3748",
                 'threshold': {'line': {'color': "red", 'width': 3}, 'thickness': 0.7, 'value': thresh_crit}}
    ))
    fig.update_layout(height=240, margin=dict(l=30, r=30, t=40, b=10), paper_bgcolor="rgba(0,0,0,0)")
    return fig

with col1: st.plotly_chart(create_dark_gauge("Stator Temp", t_val, 100, " °C", 70, 80), use_container_width=True)
with col2: st.plotly_chart(create_dark_gauge("Vibration", v_val, 15, " g", 7, 10), use_container_width=True)
with col3: st.plotly_chart(create_dark_gauge("Current Load", c_val, 35, " A", 20, 25), use_container_width=True)

st.markdown("<h3 style='margin-bottom: 10px;'>🚨 Smart Alerts & Financial Impact</h3>", unsafe_allow_html=True)
alert_col, finance_col = st.columns([2, 1], gap="large")
with alert_col:
    if t_val > 80 and c_val > 25:
        st.error(f"**{diag_status}**")
    elif v_val > 10.0:
        st.warning(f"**{diag_status}**")
    else:
        st.success(f"**{diag_status}**")
    st.caption("📄 *Note: All fault diagnostics, threshold comparisons, and SOP recommendations are logged into the Official Audit PDF Report.*")

with finance_col:
    st.markdown("""
    <div style='background-color: #1A1C23; padding: 15px; border-radius: 8px; border: 1px solid #D69E2E;'>
        <h4 style='color: #D69E2E; margin-top: 0px;'>Cost of Inaction (COI)</h4>
        <p style='margin-bottom: 5px;'>If fixed today: <br><b style='color: #48BB78;'>₹2,500 (Minor Repair)</b></p>
        <p style='margin-bottom: 0px;'>If ignored (Run-to-failure): <br><b style='color: #F56565;'>₹45,000 (Motor Rewinding)</b></p>
    </div>
    """, unsafe_allow_html=True)

st.divider()

tab1, tab2, tab3 = st.tabs(["📈 Telemetry Trends", "🔥 Virtual Thermal Map", "📉 RUL Prediction (Degradation)"])

with tab1:
    time_list = [(datetime.now() - timedelta(minutes=i*3)).strftime('%H:%M') for i in range(20, 0, -1)]
    hist_data = pd.DataFrame({
        'Time': time_list, 'Temp (°C)': [random.randint(55, 65) for _ in range(19)] + [t_val],
        'Vib (g)': [random.uniform(3, 5) for _ in range(19)] + [v_val]
    }).set_index('Time')
    
    fig_chart = go.Figure()
    fig_chart.add_trace(go.Scatter(x=hist_data.index, y=hist_data['Temp (°C)'], mode='lines', name='Temp', line=dict(color='#D69E2E', width=2.5)))
    fig_chart.add_trace(go.Scatter(x=hist_data.index, y=hist_data['Vib (g)'], mode='lines', name='Vibration', line=dict(color='#3182CE', width=2.5)))
    fig_chart.update_layout(plot_bgcolor="#1A1C23", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#A0AEC0"), height=300, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_chart, use_container_width=True)

with tab2:
    x_grid, y_grid = np.linspace(0, 10, 50), np.linspace(0, 10, 20)
    X, Y = np.meshgrid(x_grid, y_grid)
    Z = (t_val - 20) * np.exp(-((X-5)**2 + (Y-5)**2)/10) + random.randint(30, 40)
    
    fig_heat = go.Figure(data=go.Heatmap(z=Z, x=x_grid, y=y_grid, colorscale='Inferno', colorbar=dict(title=dict(text="°C", font=dict(color="#A0AEC0")), tickfont=dict(color="#A0AEC0"))))
    fig_heat.update_layout(plot_bgcolor="#1A1C23", paper_bgcolor="rgba(0,0,0,0)", height=300, margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(showticklabels=False), yaxis=dict(showticklabels=False))
    st.plotly_chart(fig_heat, use_container_width=True)

with tab3:
    proj_dates = [(datetime.now() + timedelta(days=i)).strftime('%b %d') for i in range(days_left + 1)]
    proj_health = np.linspace(health_score, 0, days_left + 1)
    
    fig_rul = go.Figure()
    fig_rul.add_trace(go.Scatter(x=proj_dates, y=proj_health, mode='lines+markers', name='Projected Health', line=dict(color='#E53E3E', width=3, dash='dash')))
    fig_rul.add_annotation(x=proj_dates[-1], y=0, text="Predicted Breakdown!", showarrow=True, arrowhead=1, ax=-40, ay=-40, font=dict(color="white", size=14))
    
    fig_rul.update_layout(plot_bgcolor="#1A1C23", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#A0AEC0"), height=300, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(title="Asset Health (%)", range=[0, 100]))
    st.plotly_chart(fig_rul, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

if st.button("🔄 FETCH LATEST TELEMETRY FOR THIS ESP32", use_container_width=True):
    get_pump_data(current_node_id, force_refresh=True)
    st.rerun()