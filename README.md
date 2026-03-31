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
1. **`physical_phone_device_default_extractor.py`**
   * **Function:** Connects to multiple CUCM clusters via AXL API to extract a clean inventory of physical phones and default firmware loads (explicitly filtering out virtual endpoints like CTI ports).
   * **Output:** `Physical_Phone_Device_Default_Discovery_Report.csv`

2. **`phone_firmware_compliance_auditor.py`**
   * **Function:** Reads the discovery CSV, launches a headless browser to scrape the Cisco v15 Matrix, and appends the required minimum and recommended firmware versions for each specific phone model.
   * **Output:** `Phone_Firmware_Compliance_Audit_Report.csv`

### Phase 2: Voice Gateway & Trunk Discovery
3. **`gateway_sip_trunk_ip_extractor.py`**
   * **Function:** Queries the CUCM database via raw SOAP/AXL and RISPort to locate all configured voice gateways and trunks, categorizing them into a formatted Excel workbook based on protocol (H.323, MGCP, SIP, Analog VG).
   * **Output:** `Gateway_Sip_Trunk_IP_Discovery_Report.xlsx`

4. **`gateway_hardware_ios_extractor.py`**
   * **Function:** Uses a custom Tkinter GUI to securely SSH (via Netmiko) into the discovered gateway IPs. It extracts the true physical hardware chassis model (PID) and running IOS/IOS-XE version.
   * **Output:** `Gateway_Hardware_IOS_Discovery_Report.csv`

5. **`gateway_ios_compliance_auditor.py`**
   * **Function:** Evaluates the scraped hardware and IOS versions against the Cisco v15 Matrix. It appends explicit hardware EOS flags and calculates mathematical IOS upgrade recommendations.
   * **Output:** `Gateway_IOS_Audit_Report.csv`

---

## ⚙️ Installation & Usage

### Prerequisites
* Python 3.9 or higher
* Network access to your CUCM Publisher nodes (port 8443) and voice gateways (port 22)
* An AXL-enabled application user on each CUCM cluster
* The Cisco AXL SQL Toolkit WSDL (`AXLAPI.wsdl`) matching your CUCM version, placed in a `schema/` folder alongside the scripts

### 1. Clone the repository
```bash
git clone https://github.com/freddyantony/healthcare-uc-automation.git
cd healthcare-uc-automation/cucm-15-upgrade-toolkit
```

### 2. Install Python dependencies
```bash
pip install requests zeep lxml pandas openpyxl netmiko paramiko playwright
```

### 3. Install the Playwright browser engine
```bash
playwright install chromium
```

### 4. Configure cluster credentials
Edit the `CLUSTER_GROUPS` section at the top of each script with your CUCM Publisher IPs and AXL credentials:
```python
CLUSTER_GROUPS = [
    {
        "user": "your_axl_user",
        "pass": "your_axl_password",
        "clusters": [
            {"name": "Cluster-East", "ip": "cucm-pub-east.yourdomain.local"},
            {"name": "Cluster-West", "ip": "cucm-pub-west.yourdomain.local"},
        ]
    }
]
```

### 5. Run the scripts in sequence
```bash
# Phase 1: Phones
python physical_phone_device_default_extractor.py
python phone_firmware_compliance_auditor.py

# Phase 2: Gateways
python gateway_sip_trunk_ip_extractor.py
python gateway_hardware_ios_extractor.py      # Opens a Tkinter GUI
python gateway_ios_compliance_auditor.py
```

> **Note:** Scripts 2 and 5 (the compliance auditors) use Playwright to scrape the live Cisco Compatibility Matrix. An internet connection is required for those scripts.

---

## 📂 Output Files

| Script | Output File | Format |
|--------|-------------|--------|
| `physical_phone_device_default_extractor.py` | `Physical_Phone_Device_Default_Discovery_Report.csv` | CSV |
| `phone_firmware_compliance_auditor.py` | `Phone_Firmware_Compliance_Audit_Report.csv` | CSV |
| `gateway_sip_trunk_ip_extractor.py` | `Gateway_Sip_Trunk_IP_Discovery_Report.xlsx` | Excel (multi-tab) |
| `gateway_hardware_ios_extractor.py` | `Gateway_Hardware_IOS_Discovery_Report.csv` | CSV |
| `gateway_ios_compliance_auditor.py` | `Gateway_IOS_Audit_Report.csv` | CSV |

---

## 🔒 Security Notes
* Credentials are configured inline for simplicity. For production use, consider using environment variables or a `.env` file (not committed to version control).
* All CUCM connections use HTTPS with SSL verification disabled (`verify=False`) to accommodate self-signed certificates common in enterprise UC environments.
* The Tkinter GUI masks passwords in the display but transmits them in memory to Netmiko for SSH sessions.

---

## 📜 License
This project is licensed under the MIT License. See the [LICENSE](../LICENSE) file for details.
