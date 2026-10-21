# GWSSB Predictive Maintenance & SCADA Dashboard

A condition-based monitoring and predictive maintenance web application built for the Gujarat Water Supply & Sewerage Board (GWSSB) rural water distribution network. This repository contains the cloud SCADA interface, telemetry analytics engine, bilingual operator assistant, and automated PDF audit generator.

**Live Prototype:** [Insert Streamlit Cloud URL Here]

---

## 1. Background & Problem Statement
Rural water supply networks across Gujarat rely heavily on high-capacity 3-phase induction motors and centrifugal pumps at Gram Panchayat and regional headworks. Currently, most stations operate on a reactive (run-to-failure) maintenance schedule. Unexpected bearing failures, cavitation, or stator winding burnouts lead to prolonged water supply disruptions and expensive motor rewinding costs.

This system bridges low-cost IoT edge nodes (ESP32) with a centralized Streamlit dashboard to track electro-mechanical health, predict Remaining Useful Life (RUL), and generate standardized maintenance work orders before catastrophic failure occurs.

---

## 2. System Architecture

1. **Edge Telemetry Layer (ESP32):** Captures Stator Winding Temperature (°C), Radial Bearing Vibration (mm/s / g), and 3-Phase Load Current (Amps).
2. **Cloud Mediator (Firebase RTDB):** Synchronizes node-level sensor packets using unique hardware identifiers (e.g., `ESP32-RJK-AJI-01`).
3. **Analytics & SCADA Frontend (Streamlit):** Computes composite asset health scores, maps virtual thermal distribution, projects RUL degradation curves, and evaluates Cost of Inaction (COI).
4. **Reporting Engine (FPDF):** Compiles shift telemetry against ISO 10816 vibration and thermal baselines into a printable GWSSB audit document.

---

## 3. Repository Structure

    ├── .streamlit/
    │   └── config.toml          # UI theme and server configuration
    ├── app.py                   # Main Streamlit SCADA application & NLP logic
    ├── requirements.txt         # Python package dependencies
    └── README.md                # Project documentation

---

## 4. Technical Modules

* **Hierarchical & Direct Node Routing:** Switch between regional pumping stations or query an ESP32 node directly via its hardware ID.
* **Real-Time Telemetry & Thermal Mapping:** Interactive Plotly gauges with warning/critical thresholds and a 2D Gaussian virtual thermal heatmap of the motor housing.
* **RUL & Cost of Inaction (COI) Engine:** Linear degradation projection estimating days until breakdown, paired with a financial comparison between minor preventive servicing (Rs. 2,500) and full motor rewinding (Rs. 45,000).
* **Bilingual Operator Assistant (English / Gujarati):** Context-aware query parser allowing local linemen and operators to check pump status, load, and repair costs in Gujarati or English.
* **ISO-Compliant PDF Audit Generator:** Generates a formatted A4 shift report complete with telemetry tables, diagnostic flags (`[SYS-OK]`, `[WRN-02]`, `[ERR-01]`), standard operating procedures (SOPs), and signature blocks for GWSSB field engineers.

---

## 5. Local Installation & Usage

Ensure you have Python 3.9+ installed on your system.

1. Clone the repository:

    git clone https://github.com/hiralM001/GWSSB-Pump-Dashboard.git
    cd GWSSB-Pump-Dashboard

2. Install required dependencies:

    pip install -r requirements.txt

3. Launch the Streamlit server:

    streamlit run app.py

The dashboard will open automatically at `http://localhost:8501`.

---

## 6. Field Rollout Roadmap

* **Phase 1 - Rural Pilot (Months 1-3):** Physical installation of ESP32 sensor nodes on select village pumps, Gram Panchayat telemetry sync, and threshold calibration.
* **Phase 2 - Local Integration (Months 4-6):** Cloud linkage with Village Water & Sanitation Committees (VWSC) and GWSSB sub-divisions; field testing of the Gujarati operator interface.
* **Phase 3 - Regional Scale-Up (Months 7-9):** Multi-district expansion, validation of RUL degradation models under seasonal load variations, and COI budget auditing.
* **Phase 4 - Pan-Gujarat Rollout (Months 10-12):** State-wide deployment across rural pumping stations with automated SMS/WhatsApp fault ticketing to the Sarpanch and Deputy Executive Engineers.
