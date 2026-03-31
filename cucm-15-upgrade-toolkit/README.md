# Cisco UC Enterprise Upgrade & Compliance Toolkit

## 📌 The Problem
Upgrading enterprise Cisco Unified Communications environments (managing tens of thousands of endpoints) to a new major release (e.g., CUCM v14 to v15) requires strict adherence to the Cisco Compatibility Matrix. Manually mapping physical hardware chassis, IOS versions, and default phone firmware across multiple clusters is a highly manual, error-prone process that can take weeks of engineering time.

## 💡 The Solution
This toolkit is a suite of Python automation scripts designed to eliminate manual discovery. It leverages **Cisco AXL APIs**, **Netmiko (SSH)**, and **Playwright (headless browser scraping)** to extract live infrastructure data, scrape the live Cisco v15 Compatibility Matrix, and generate mathematically validated compliance reports. 

## 🚀 Business Impact
* **Efficiency:** Reduces a multi-week enterprise audit to minutes of automated execution.
* **Accuracy:** Eliminates human error by programmatically matching extracted PIDs and versions against Cisco's live documentation.
* **Risk Mitigation:** Automatically flags legacy hardware for End-of-Support (EOS) replacement prior to upgrade cutovers.

---

## 🛠️ Architecture & Workflow

The toolkit is broken down into 5 sequential scripts, separating Data Extraction from Compliance Auditing.

### Phase 1: Endpoint & Firmware Discovery
1. **`physical_phone_device_extractor.py`**
   * **Function:** Connects to multiple CUCM clusters via AXL API to extract a clean inventory of physical phones and default firmware loads (explicitly filtering out virtual endpoints like CTI ports).
   * **Output:** `Physical_Phone_&_Device_Default_Discovery_Report.csv`

2. **`phone_firmware_compliance_auditor.py`**
   * **Function:** Reads the discovery CSV, launches a headless browser to scrape the Cisco v15 Matrix, and appends the required minimum and recommended firmware versions for each specific phone model.
   * **Output:** `Phone_Firmware_Compliance_Audit_Report.csv`

### Phase 2: Voice Gateway & Trunk Discovery
3. **`gateway_sip_trunk_ip_extractor.py`**
   * **Function:** Queries the CUCM database to locate all configured voice gateways and trunks, categorizing them into a formatted Excel workbook based on protocol (H.323, MGCP, SIP, Analog VG).
   * **Output:** `Gateway_Sip_Trunk_IP_Discovery_Report.xlsx`

4. **`gateway_hardware_ios_extractor.py`**
   * **Function:** Uses a custom Tkinter GUI to securely SSH (via Netmiko) into the discovered gateway IPs. It extracts the true physical hardware chassis model (PID) and running IOS/IOS-XE version.
   * **Output:** `Gateway_Hardware_IOS_Discovery_Report.csv`

5. **`gateway_ios_compliance_auditor.py`**
   * **Function:** Evaluates the scraped hardware and IOS versions against the Cisco v15 Matrix. It appends explicit hardware EOS flags and calculates mathematical IOS upgrade recommendations.
   * **Output:** `Gateway_IOS_Audit_Report.csv`

---

## ⚙️ Installation & Usage

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/freddyantony/healthcare-uc-automation.git](https://github.com/freddyantony/healthcare-uc-automation.git)
   cd healthcare-uc-automation