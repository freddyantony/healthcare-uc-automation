import pandas as pd
import re
from io import StringIO
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
input_file = 'Gateway_Hardware_IOS_Discovery_Report.csv'
output_file = 'Gateway_IOS_Audit_Report.csv'
cisco_url = "https://www.cisco.com/c/dam/en/us/td/docs/voice_ip_comm/uc_system/unified/communications/system/Compatibility/CSR-Compatibility-Matrix-InteractiveHTML.html"

def clean_cell(value):
    if pd.isna(value) or str(value).strip().lower() == 'nan':
        return ""
    return str(value).strip()

def get_search_terms(raw_model):
    base_model = str(raw_model).upper().replace('/K9', '').replace('-CHASSIS', '').strip()
    
    exact_term = base_model
    match_exact = re.search(r'^(?:CISCO|ISR)(\d{4}.*)$', base_model)
    if match_exact:
        exact_term = match_exact.group(1)
        
    group_term = base_model
    if 'VG' in base_model:
        group_term = base_model.split('-')[0] 
    else:
        match_group = re.search(r'(\d{2})\d{2}', base_model)
        if match_group:
            prefix = match_group.group(1)
            if prefix in ['43', '44']:
                group_term = "4000"
            else:
                group_term = f"{prefix}00"
                
    return exact_term, group_term

def run_update():
    print(f"📄 Reading {input_file}...")
    try:
        df = pd.read_csv(input_file)
    except Exception as e:
        print(f"❌ Error reading CSV file: {e}")
        return

    model_col = 'Device_Model'
    version_col = 'Current_Version'

    if model_col not in df.columns or version_col not in df.columns:
        print(f"❌ Error: Could not find '{model_col}' or '{version_col}' in your CSV.")
        return

    unique_devices = df[model_col].dropna().unique()
    print(f"🔍 Found {len(unique_devices)} unique gateway models. Normalizing names for Cisco Matrix...")

    print("\n🌐 Launching headless browser to read the Cisco Matrix (Takes ~10 seconds)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(cisco_url)
        page.wait_for_selector("table", timeout=20000) 
        html_content = page.content()
        tables = pd.read_html(StringIO(html_content))
        matrix_df = tables[0] 
        browser.close()
        print("✅ Cisco Matrix successfully downloaded!")

    device_cache = {}
    
    print("\n⚙️ Matching your gateways against the CUCM 15 Matrix...")
    for raw_device in unique_devices:
        exact_term, group_term = get_search_terms(raw_device)
        
        print(f"    🔍 [Pass 1] Exact Search: '{exact_term}'")
        mask = matrix_df.iloc[:, 0].astype(str).str.contains(exact_term, case=False, na=False)
        matches = matrix_df[mask]
        
        if matches.empty and exact_term != group_term:
            print(f"    ⚠️ Exact not found. [Pass 2] Group Search: '{group_term}'")
            mask = matrix_df.iloc[:, 0].astype(str).str.contains(group_term, case=False, na=False)
            matches = matrix_df[mask]
        
        if not matches.empty:
            min_ver = clean_cell(matches.iloc[0, 1])
            rec_ver = clean_cell(matches.iloc[0, 2])
            comment = clean_cell(matches.iloc[0, 3])
            
            device_cache[str(raw_device).strip()] = {
                "v15 Minimum Version": min_ver, 
                "v15 Recommended Version": rec_ver,
                "v15 Comment": comment
            }
        else:
            device_cache[str(raw_device).strip()] = {
                "v15 Minimum Version": "Not Found", 
                "v15 Recommended Version": "Not Found",
                "v15 Comment": "Not Found in Matrix"
            }

    print(f"\n💾 Compiling data and performing compliance check...")
    
    df['v15 Minimum Version'] = df[model_col].apply(lambda x: device_cache.get(str(x).strip(), {}).get("v15 Minimum Version", ""))
    df['v15 Recommended Version'] = df[model_col].apply(lambda x: device_cache.get(str(x).strip(), {}).get("v15 Recommended Version", ""))
    df['v15 Comment'] = df[model_col].apply(lambda x: device_cache.get(str(x).strip(), {}).get("v15 Comment", ""))

    def check_hardware(row):
        model = str(row.get(model_col, '')).upper()
        min_v15 = str(row.get('v15 Minimum Version', '')).strip()
        rec_v15 = str(row.get('v15 Recommended Version', '')).strip()
        comment = str(row.get('v15 Comment', '')).strip()
        
        if re.search(r'(28|29|38|39)\d{2}', model):
            return "🚨 End of Support (Hardware Replacement)"
            
        if "End of Support" in min_v15 or "End of Support" in rec_v15 or "End of Support" in comment:
            return "🚨 End of Support"
        if "Not Found" in min_v15:
            return "❓ Unknown Hardware (Not in Matrix)"
            
        return "✅ Supported"

    def check_ios(row):
        hw_status = check_hardware(row)
        
        if "End of Support" in hw_status:
            return "🛑 N/A (Hardware EOS)"
            
        current = str(row.get(version_col, '')).strip()
        min_v15 = str(row.get('v15 Minimum Version', '')).strip()
        rec_v15 = str(row.get('v15 Recommended Version', '')).strip()
        
        target = rec_v15 if rec_v15 and "End of Support" not in rec_v15 else min_v15
        
        if not current or current == 'nan': return "❓ Unknown Current Version"
        if not target or "End of Support" in target or "Not Found" in target: return "❓ No Target Version Listed"
        if current == target: return "✅ Matches Target"
            
        match_curr = re.search(r'(\d+\.\d+)', current)
        match_tgt = re.search(r'(\d+\.\d+)', target)
        
        if match_curr and match_tgt:
            curr_val = float(match_curr.group(1))
            tgt_val = float(match_tgt.group(1))
            if curr_val > tgt_val: return f"✅ Good (Newer Base Version)"
            elif curr_val < tgt_val: return f"⚠️ Upgrade Needed (Target: {target})"
                
        return f"⚠️ Review Minor Release (Current: {current} | Target: {target})"

    df['Hardware Support Status'] = df.apply(check_hardware, axis=1)
    df['IOS Upgrade Status'] = df.apply(check_ios, axis=1)

    df.to_csv(output_file, index=False, encoding='utf-8-sig')
            
    print(f"🏁 Success! Your updated data is ready in: {output_file}")

if __name__ == "__main__":
    run_update()