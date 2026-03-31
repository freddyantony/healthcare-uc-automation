import urllib3
import csv
from pathlib import Path
from requests import Session
from requests.auth import HTTPBasicAuth
from zeep import Client, Settings
from zeep.transports import Transport
from zeep.exceptions import Fault

# Disable SSL warnings for self-signed CUCM certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- GROUPED CLUSTER CONFIGURATION ---
CLUSTER_GROUPS = [
    {
        "user": "api_admin",        # <-- UPDATE THIS
        "pass": "your_password",    # <-- UPDATE THIS
        "clusters": [
            {"name": "Cluster-US-East", "ip": "cucm-pub-01.example.local"},
            {"name": "Cluster-US-West", "ip": "cucm-pub-02.example.local"},
        ]
    }
]

# --- WSDL CONFIGURATION ---
# Assumes the 'schema' folder is located in the same directory as this script
wsdl_path = Path("./schema/AXLAPI.wsdl")
WSDL_FILE = wsdl_path.absolute().as_uri()

master_data_list = []

sql_query = """
SELECT count(d.pkid) as configured_devices, tp.name as device_type, df.loadinformation as default_firmware 
FROM device d
INNER JOIN typeproduct tp ON d.tkmodel = tp.tkmodel 
LEFT JOIN defaults df ON tp.tkmodel = df.tkmodel 
WHERE d.tkclass = 1 
AND tp.name NOT IN ('CTI Port', 'Universal Device Template', 'Cisco Voice Mail Port', 'CTI Route Point', 'Gatekeeper')
GROUP BY tp.name, df.loadinformation
"""

for group in CLUSTER_GROUPS:
    axl_user = group["user"]
    axl_pass = group["pass"]
    
    for cluster in group["clusters"]:
        cluster_name = cluster["name"]
        cucm_ip = cluster["ip"]
        
        print(f"\n[{cluster_name}] Connecting to {cucm_ip}...")
        
        AXL_URL = f'https://{cucm_ip}:8443/axl/'
        
        session = Session()
        session.verify = False
        session.auth = HTTPBasicAuth(axl_user, axl_pass)
        
        transport = Transport(session=session, timeout=15)
        settings = Settings(strict=False, xml_huge_tree=True)
        
        try:
            client = Client(WSDL_FILE, settings=settings, transport=transport)
            service = client.create_service('{http://www.cisco.com/AXLAPIService/}AXLAPIBinding', AXL_URL)
            
            response = service.executeSQLQuery(sql=sql_query)
            
            if response['return'] is not None:
                device_count = len(response['return']['row'])
                print(f"[{cluster_name}] ✅ Success! Retrieved {device_count} device types.")
                
                for row in response['return']['row']:
                    count = row[0].text if row[0].text else "0"
                    device_type = row[1].text if row[1].text else "Unknown"
                    firmware = row[2].text if row[2].text else "None"
                    
                    master_data_list.append([cluster_name, count, device_type, firmware])
            else:
                print(f"[{cluster_name}] ⚠️ Query successful, but no phones found.")

        except Fault as fault:
            print(f"[{cluster_name}] ❌ CUCM rejected the query: {fault.message}")
        except Exception as e:
            print(f"[{cluster_name}] ❌ Connection failed: {e}")

if master_data_list:
    filename = 'Physical_Phone_&_Device_Default_Discovery_Report.csv'
    print(f"\nWriting all data to {filename}...")
    
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Cluster Name', 'Configured Devices', 'Device Type', 'Default Firmware Load'])
        
        for row_data in master_data_list:
            writer.writerow(row_data)
            
    print("🏁 Multi-Cluster Script Complete!")
else:
    print("\n⚠️ Script finished, but no data was collected from any clusters to write to the CSV.")
