# Paste this entire script into the Ignition Gateway Script Console and run it.
# Gateway web UI -> Status -> Diagnostics -> Script Console
#
# Change OPC_CONNECTION to match the name you gave your OPC-UA connection in Ignition.

OPC_CONNECTION = "opc-ua-simulator"   # <-- update if your connection has a different name

def opc_tag(name, node_id, data_type="Float8"):
    return {
        "name": name,
        "tagType": "AtomicTag",
        "valueSource": "opc",
        "dataType": data_type,
        "opcServer": OPC_CONNECTION,
        "opcItemPath": "ns=1;s=" + node_id,
        "enabled": True,
    }

def folder(name, children):
    return {
        "name": name,
        "tagType": "Folder",
        "tags": children,
    }

# --- PDUs ---
pdu_tags = lambda d: [
    opc_tag("Voltage_L1_L2",      "PDU." + d + ".Voltage_L1_L2"),
    opc_tag("Voltage_L2_L3",      "PDU." + d + ".Voltage_L2_L3"),
    opc_tag("Voltage_L1_L3",      "PDU." + d + ".Voltage_L1_L3"),
    opc_tag("Current_L1_A",       "PDU." + d + ".Current_L1_A"),
    opc_tag("Current_L2_A",       "PDU." + d + ".Current_L2_A"),
    opc_tag("Current_L3_A",       "PDU." + d + ".Current_L3_A"),
    opc_tag("TotalPower_kW",      "PDU." + d + ".TotalPower_kW"),
    opc_tag("PowerFactor",        "PDU." + d + ".PowerFactor"),
    opc_tag("Frequency_Hz",       "PDU." + d + ".Frequency_Hz"),
    opc_tag("Temperature_C",      "PDU." + d + ".Temperature_C"),
]

# --- UPS ---
ups_tags = lambda d: [
    opc_tag("InputVoltage_V",      "UPS." + d + ".InputVoltage_V"),
    opc_tag("OutputVoltage_V",     "UPS." + d + ".OutputVoltage_V"),
    opc_tag("BatteryCharge_Pct",   "UPS." + d + ".BatteryCharge_Pct"),
    opc_tag("LoadPercent",         "UPS." + d + ".LoadPercent"),
    opc_tag("Temperature_C",       "UPS." + d + ".Temperature_C"),
    opc_tag("InputFrequency_Hz",   "UPS." + d + ".InputFrequency_Hz"),
]

# --- HVAC ---
hvac_tags = lambda d: [
    opc_tag("SupplyAirTemp_C",     "HVAC." + d + ".SupplyAirTemp_C"),
    opc_tag("ReturnAirTemp_C",     "HVAC." + d + ".ReturnAirTemp_C"),
    opc_tag("Humidity_Pct",        "HVAC." + d + ".Humidity_Pct"),
    opc_tag("FanSpeed_RPM",        "HVAC." + d + ".FanSpeed_RPM"),
    opc_tag("CoolingCapacity_kW",  "HVAC." + d + ".CoolingCapacity_kW"),
    opc_tag("CompressorStatus",    "HVAC." + d + ".CompressorStatus", "Boolean"),
]

tag_tree = [
    folder("DataCenter", [
        folder("PDU", [folder(d, pdu_tags(d))  for d in ["PDU_01","PDU_02","PDU_03","PDU_04"]]),
        folder("UPS", [folder(d, ups_tags(d))  for d in ["UPS_01","UPS_02"]]),
        folder("HVAC",[folder(d, hvac_tags(d)) for d in ["HVAC_01","HVAC_02"]]),
    ])
]

result = system.tag.configure("[default]", tag_tree, "o")
print("Tags created. Results:", result)
