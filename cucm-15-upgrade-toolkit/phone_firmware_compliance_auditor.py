import csv
import re
import pandas as pd
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
input_file = 'Physical_Phone_Device_Default_Discovery_Report.csv'
output_file = 'Phone_Firmware_Compliance_Audit_Report.csv'
cisco_url = "https://www.cisco.com/c/dam/en/us/td/docs/voice_ip_comm/uc_system/unified/communications/system/Compatibility/CSR-Compatibility-Matrix-InteractiveHTML.html"

def extract_model_number(device_string):
    numbers = re.findall(r'\d+', device_string)
    return numbers[0] if numbers else device_string

def clean_cell(value):
    if pd.isna(value) or str(value).strip().lower() == 'nan':
        return ""
    return str(value).strip()

def run_update():
    production_data = []
    unique_devices = set()
    
    print(f"📄 Reading {input_file}...")
    try:
        with open(input_file, mode='r') as infile:
            reader = csv.DictReader(infile)
            headers = reader.fieldnames
            for row in reader:
                production_data.append(row)
                unique_devices.add(row['Device Type'])
    except FileNotFoundError:
        print(f"❌ Error: Could not find {input_file}.")
        return

    print("🌐 Launching headless browser to read the Cisco Matrix (This takes ~10 seconds)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        page.goto(cisco_url)
        page.wait_for_selector("table", timeout=20000) 
        
        html_content = page.content()
        tables = pd.read_html(html_content)
        matrix_df = tables[0] 
        
        browser.close()
        print("✅ Cisco Matrix successfully downloaded and parsed!")

    device_cache = {}
    
    print("🔍 Matching your devices against the Cisco CUCM 15 Matrix...")
    for device in unique_devices:
        model_num = extract_model_number(device)
        
        mask = matrix_df.iloc[:, 0].astype(str).str.contains(model_num, case=False, na=False)
        matches = matrix_df[mask]
        
        if not matches.empty:
            min_ver = clean_cell(matches.iloc[0, 1])
            rec_ver = clean_cell(matches.iloc[0, 2])
            comment = clean_cell(matches.iloc[0, 3])
            
            device_cache[device] = {
                "min": min_ver, 
                "rec": rec_ver,
                "comment": comment
            }
        else:
            device_cache[device] = {
                "min": "Not Found", 
                "rec": "Not Found",
                "comment": "Not Found in Cisco Matrix"
            }

    print(f"💾 Writing updated data to {output_file}...")
    
    new_headers = headers + ['v15 Minimum Version', 'v15 Recommended Version', 'v15 Comment']
    
    with open(output_file, mode='w', newline='') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=new_headers)
        writer.writeheader()
        
        for row in production_data:
            device = row['Device Type']
            
            row['v15 Minimum Version'] = device_cache[device]['min']
            row['v15 Recommended Version'] = device_cache[device]['rec']
            row['v15 Comment'] = device_cache[device]['comment']
            
            writer.writerow(row)
            
    print("🏁 Success! Your firmware report has been fully updated.")

if __name__ == "__main__":
    run_update()