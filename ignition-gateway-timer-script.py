def handleTimerEvent():
    OPC_SERVER = "Simulator"   # default server; override per-entry with "opcServer"
    DB_CONN    = "TimeScaleCloud"

    SQL = ("INSERT INTO ts.telemetry "
           "(ts, tag_id, asset_id, producer_id, ims_id, value_double) "
           "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING")

    def to_f(c):
        return c * 9.0 / 5.0 + 32.0

    def fan_pct(rpm):
        return min(100.0, (rpm / 2500.0) * 100.0)

    TAG_MAP = [
        # PDU_01
        {"nodeId": "ns=1;s=PDU.PDU_01.Voltage_L1_L2",     "tag_id": 10575, "asset_id": 343, "producer_id": 195, "ims_id": "IMS-01"},
        {"nodeId": "ns=1;s=PDU.PDU_01.Voltage_L2_L3",     "tag_id": 10576, "asset_id": 343, "producer_id": 195, "ims_id": "IMS-01"},
        {"nodeId": "ns=1;s=PDU.PDU_01.Voltage_L1_L3",     "tag_id": 10577, "asset_id": 343, "producer_id": 195, "ims_id": "IMS-01"},
        {"nodeId": "ns=1;s=PDU.PDU_01.Current_L1_A",      "tag_id": 10579, "asset_id": 343, "producer_id": 195, "ims_id": "IMS-01"},
        {"nodeId": "ns=1;s=PDU.PDU_01.Current_L2_A",      "tag_id": 10580, "asset_id": 343, "producer_id": 195, "ims_id": "IMS-01"},
        {"nodeId": "ns=1;s=PDU.PDU_01.Current_L3_A",      "tag_id": 10581, "asset_id": 343, "producer_id": 195, "ims_id": "IMS-01"},
        {"nodeId": "ns=1;s=PDU.PDU_01.TotalPower_kW",     "tag_id": 10582, "asset_id": 343, "producer_id": 195, "ims_id": "IMS-01"},
        {"nodeId": "ns=1;s=PDU.PDU_01.PowerFactor",       "tag_id": 10585, "asset_id": 343, "producer_id": 195, "ims_id": "IMS-01"},
        {"nodeId": "ns=1;s=PDU.PDU_01.Frequency_Hz",      "tag_id": 10578, "asset_id": 343, "producer_id": 195, "ims_id": "IMS-01"},
        # UPS_01
        {"nodeId": "ns=1;s=UPS.UPS_01.InputVoltage_V",    "tag_id": 10192, "asset_id": 341, "producer_id": 194, "ims_id": "IMS-01"},
        {"nodeId": "ns=1;s=UPS.UPS_01.OutputVoltage_V",   "tag_id": 10198, "asset_id": 341, "producer_id": 194, "ims_id": "IMS-01"},
        {"nodeId": "ns=1;s=UPS.UPS_01.BatteryCharge_Pct", "tag_id": 10207, "asset_id": 341, "producer_id": 194, "ims_id": "IMS-01"},
        {"nodeId": "ns=1;s=UPS.UPS_01.LoadPercent",       "tag_id": 10203, "asset_id": 341, "producer_id": 194, "ims_id": "IMS-01"},
        {"nodeId": "ns=1;s=UPS.UPS_01.Temperature_C",     "tag_id": 10486, "asset_id": 341, "producer_id": 194, "ims_id": "IMS-01"},
        {"nodeId": "ns=1;s=UPS.UPS_01.InputFrequency_Hz", "tag_id": 10442, "asset_id": 341, "producer_id": 194, "ims_id": "IMS-01"},
        # HVAC_01
        {"nodeId": "ns=1;s=HVAC.HVAC_01.ReturnAirTemp_C",    "tag_id": 10646, "asset_id": 345, "producer_id": 197, "ims_id": "IMS-01", "convert": to_f},
        {"nodeId": "ns=1;s=HVAC.HVAC_01.SupplyAirTemp_C",    "tag_id": 10644, "asset_id": 345, "producer_id": 197, "ims_id": "IMS-01", "convert": to_f},
        {"nodeId": "ns=1;s=HVAC.HVAC_01.CoolingCapacity_kW", "tag_id": 10658, "asset_id": 345, "producer_id": 197, "ims_id": "IMS-01"},
        {"nodeId": "ns=1;s=HVAC.HVAC_01.FanSpeed_RPM",       "tag_id": 10652, "asset_id": 345, "producer_id": 197, "ims_id": "IMS-01", "convert": fan_pct},
        # WhiteRPP2  (Janitza UMG 800 @ 172.17.20.98)  -- producer_id needs to be filled in from TimescaleDB
        {"nodeId": "ns=2;i=131100", "opcServer": "RPP", "tag_id": 154128, "asset_id": 9987, "producer_id": 0, "ims_id": "IMS-01"},  # Voltage_Frequency_RMS
        {"nodeId": "ns=2;i=135600", "opcServer": "RPP", "tag_id": 154146, "asset_id": 9987, "producer_id": 0, "ims_id": "IMS-01"},  # Voltage_LN_RMS_L1
        {"nodeId": "ns=2;i=137600", "opcServer": "RPP", "tag_id": 154147, "asset_id": 9987, "producer_id": 0, "ims_id": "IMS-01"},  # Voltage_LN_RMS_L2
        {"nodeId": "ns=2;i=139600", "opcServer": "RPP", "tag_id": 154153, "asset_id": 9987, "producer_id": 0, "ims_id": "IMS-01"},  # Voltage_LN_RMS_L3
        {"nodeId": "ns=2;i=135700", "opcServer": "RPP", "tag_id": 154129, "asset_id": 9987, "producer_id": 0, "ims_id": "IMS-01"},  # Voltage_LL_RMS_L12
        {"nodeId": "ns=2;i=137700", "opcServer": "RPP", "tag_id": 154136, "asset_id": 9987, "producer_id": 0, "ims_id": "IMS-01"},  # Voltage_LL_RMS_L23
        {"nodeId": "ns=2;i=139700", "opcServer": "RPP", "tag_id": 154138, "asset_id": 9987, "producer_id": 0, "ims_id": "IMS-01"},  # Voltage_LL_RMS_L31
        {"nodeId": "ns=2;i=131500", "opcServer": "RPP", "tag_id": 154158, "asset_id": 9987, "producer_id": 0, "ims_id": "IMS-01"},  # Voltage_Unbalance
        {"nodeId": "ns=2;i=131800", "opcServer": "RPP", "tag_id": 154142, "asset_id": 9987, "producer_id": 0, "ims_id": "IMS-01"},  # AvgPhases_LN_RMS
        {"nodeId": "ns=2;i=131900", "opcServer": "RPP", "tag_id": 154133, "asset_id": 9987, "producer_id": 0, "ims_id": "IMS-01"},  # AvgPhases_LL_RMS
        # RED_PDUv6 Branch_Meter (asset_id 9999)  -- producer_id needs to be filled in from TimescaleDB
        {"nodeId": "4/20116", "opcServer": "RED_PDU", "tag_id": 154429, "asset_id": 9999, "producer_id": 0, "ims_id": "IMS-01"},  # Current_Neutral_Current_RMS
        {"nodeId": "4/20362", "opcServer": "RED_PDU", "tag_id": 154426, "asset_id": 9999, "producer_id": 0, "ims_id": "IMS-01"},  # Current_PhaseA_Current_RMS
        {"nodeId": "4/20412", "opcServer": "RED_PDU", "tag_id": 154427, "asset_id": 9999, "producer_id": 0, "ims_id": "IMS-01"},  # Current_PhaseB_Current_RMS
        {"nodeId": "4/20462", "opcServer": "RED_PDU", "tag_id": 154428, "asset_id": 9999, "producer_id": 0, "ims_id": "IMS-01"},  # Current_PhaseC_Current_RMS
        {"nodeId": "4/4912",  "opcServer": "RED_PDU", "tag_id": 154431, "asset_id": 9999, "producer_id": 0, "ims_id": "IMS-01"},  # Voltage_PhaseAB_Voltage_LL_RMS
        {"nodeId": "4/4906",  "opcServer": "RED_PDU", "tag_id": 154433, "asset_id": 9999, "producer_id": 0, "ims_id": "IMS-01"},  # Voltage_PhaseA_Voltage_LN_RMS
        {"nodeId": "4/4914",  "opcServer": "RED_PDU", "tag_id": 154432, "asset_id": 9999, "producer_id": 0, "ims_id": "IMS-01"},  # Voltage_PhaseBC_Voltage_LL_RMS
        {"nodeId": "4/4908",  "opcServer": "RED_PDU", "tag_id": 154435, "asset_id": 9999, "producer_id": 0, "ims_id": "IMS-01"},  # Voltage_PhaseB_Voltage_LN_RMS
        {"nodeId": "4/4916",  "opcServer": "RED_PDU", "tag_id": 154430, "asset_id": 9999, "producer_id": 0, "ims_id": "IMS-01"},  # Voltage_PhaseCA_Voltage_LL_RMS
        {"nodeId": "4/4910",  "opcServer": "RED_PDU", "tag_id": 154434, "asset_id": 9999, "producer_id": 0, "ims_id": "IMS-01"},  # Voltage_PhaseC_Voltage_LN_RMS
        # RED_PDUv6 CB01 (asset_id 10000)
        {"nodeId": "4/15312", "opcServer": "RED_PDU", "tag_id": 154462, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Current_Current_RMS_Avg
        {"nodeId": "4/15320", "opcServer": "RED_PDU", "tag_id": 154464, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Current_Current_RMS_Max
        {"nodeId": "4/15316", "opcServer": "RED_PDU", "tag_id": 154463, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Current_Neutral_Current_RMS_Avg
        {"nodeId": "4/15362", "opcServer": "RED_PDU", "tag_id": 154467, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Current_PhaseA_Current_RMS
        {"nodeId": "4/15370", "opcServer": "RED_PDU", "tag_id": 154468, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Current_PhaseA_Current_RMS_Max
        {"nodeId": "4/15412", "opcServer": "RED_PDU", "tag_id": 154471, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Current_PhaseB_Current_RMS
        {"nodeId": "4/15420", "opcServer": "RED_PDU", "tag_id": 154472, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Current_PhaseB_Current_RMS_Max
        {"nodeId": "4/15462", "opcServer": "RED_PDU", "tag_id": 154475, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Current_PhaseC_Current_RMS
        {"nodeId": "4/15470", "opcServer": "RED_PDU", "tag_id": 154476, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Current_PhaseC_Current_RMS_Max
        {"nodeId": "4/15324", "opcServer": "RED_PDU", "tag_id": 154465, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Demand_Current_RMS_Avg
        {"nodeId": "4/15328", "opcServer": "RED_PDU", "tag_id": 154466, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Demand_Current_RMS_Max
        {"nodeId": "4/15374", "opcServer": "RED_PDU", "tag_id": 154469, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Demand_PhaseA_Current_RMS
        {"nodeId": "4/15378", "opcServer": "RED_PDU", "tag_id": 154470, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Demand_PhaseA_Current_RMS_Max
        {"nodeId": "4/15376", "opcServer": "RED_PDU", "tag_id": 154502, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Demand_PhaseA_Power_Demand
        {"nodeId": "4/15380", "opcServer": "RED_PDU", "tag_id": 154503, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Demand_PhaseA_Power_Demand_Max
        {"nodeId": "4/15424", "opcServer": "RED_PDU", "tag_id": 154473, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Demand_PhaseB_Current_RMS
        {"nodeId": "4/15428", "opcServer": "RED_PDU", "tag_id": 154474, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Demand_PhaseB_Current_RMS_Max
        {"nodeId": "4/15426", "opcServer": "RED_PDU", "tag_id": 154505, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Demand_PhaseB_Power_Demand
        {"nodeId": "4/15430", "opcServer": "RED_PDU", "tag_id": 154504, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Demand_PhaseB_Power_Demand_Max
        {"nodeId": "4/15474", "opcServer": "RED_PDU", "tag_id": 154477, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Demand_PhaseC_Current_RMS
        {"nodeId": "4/15478", "opcServer": "RED_PDU", "tag_id": 154478, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Demand_PhaseC_Current_RMS_Max
        {"nodeId": "4/15476", "opcServer": "RED_PDU", "tag_id": 154501, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Demand_PhaseC_Power_Demand
        {"nodeId": "4/15480", "opcServer": "RED_PDU", "tag_id": 154500, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Demand_PhaseC_Power_Demand_Max
        {"nodeId": "4/15326", "opcServer": "RED_PDU", "tag_id": 154499, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Demand_Power_Demand_Avg
        {"nodeId": "4/15330", "opcServer": "RED_PDU", "tag_id": 154506, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Demand_Power_Demand_Max
        {"nodeId": "4/15336", "opcServer": "RED_PDU", "tag_id": 154439, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Energy_Active_Energy_Avg
        {"nodeId": "4/15332", "opcServer": "RED_PDU", "tag_id": 154488, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Energy_Energy_Active_Conditional_Avg
        {"nodeId": "4/15300", "opcServer": "RED_PDU", "tag_id": 154483, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Energy_Energy_Active_Total
        {"nodeId": "4/15304", "opcServer": "RED_PDU", "tag_id": 154493, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Energy_Energy_Apparent_Total
        {"nodeId": "4/15302", "opcServer": "RED_PDU", "tag_id": 154498, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Energy_Energy_Reactive_Total
        {"nodeId": "4/15388", "opcServer": "RED_PDU", "tag_id": 154436, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Energy_PhaseA_Active_Energy_Cumulative
        {"nodeId": "4/15382", "opcServer": "RED_PDU", "tag_id": 154489, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Energy_PhaseA_Energy_Active_Conditional
        {"nodeId": "4/15350", "opcServer": "RED_PDU", "tag_id": 154486, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Energy_PhaseA_Energy_Active_Cumulative
        {"nodeId": "4/15354", "opcServer": "RED_PDU", "tag_id": 154491, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Energy_PhaseA_Energy_Apparent_Cumulative
        {"nodeId": "4/15352", "opcServer": "RED_PDU", "tag_id": 154496, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Energy_PhaseA_Energy_Reactive_Cumulative
        {"nodeId": "4/15438", "opcServer": "RED_PDU", "tag_id": 154437, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Energy_PhaseB_Active_Energy_Cumulative
        {"nodeId": "4/15432", "opcServer": "RED_PDU", "tag_id": 154490, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Energy_PhaseB_Energy_Active_Conditional
        {"nodeId": "4/15400", "opcServer": "RED_PDU", "tag_id": 154485, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Energy_PhaseB_Energy_Active_Cumulative
        {"nodeId": "4/15404", "opcServer": "RED_PDU", "tag_id": 154492, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Energy_PhaseB_Energy_Apparent_Cumulative
        {"nodeId": "4/15402", "opcServer": "RED_PDU", "tag_id": 154495, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Energy_PhaseB_Energy_Reactive_Cumulative
        {"nodeId": "4/15488", "opcServer": "RED_PDU", "tag_id": 154438, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Energy_PhaseC_Active_Energy_Cumulative
        {"nodeId": "4/15482", "opcServer": "RED_PDU", "tag_id": 154487, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Energy_PhaseC_Energy_Active_Conditional
        {"nodeId": "4/15450", "opcServer": "RED_PDU", "tag_id": 154484, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Energy_PhaseC_Energy_Active_Cumulative
        {"nodeId": "4/15454", "opcServer": "RED_PDU", "tag_id": 154494, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Energy_PhaseC_Energy_Apparent_Cumulative
        {"nodeId": "4/15452", "opcServer": "RED_PDU", "tag_id": 154497, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Energy_PhaseC_Energy_Reactive_Cumulative
        {"nodeId": "4/15334", "opcServer": "RED_PDU", "tag_id": 154455, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_Quality_Current_Crest_Factor_Avg
        {"nodeId": "4/15318", "opcServer": "RED_PDU", "tag_id": 154481, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_Quality_Current_THD_Avg
        {"nodeId": "4/15366", "opcServer": "RED_PDU", "tag_id": 154453, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_Quality_PhaseA_Current_Angle
        {"nodeId": "4/15384", "opcServer": "RED_PDU", "tag_id": 154457, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_Quality_PhaseA_Current_Crest_Factor
        {"nodeId": "4/15368", "opcServer": "RED_PDU", "tag_id": 154479, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_Quality_PhaseA_Current_THD
        {"nodeId": "4/15416", "opcServer": "RED_PDU", "tag_id": 154454, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_Quality_PhaseB_Current_Angle
        {"nodeId": "4/15434", "opcServer": "RED_PDU", "tag_id": 154456, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_Quality_PhaseB_Current_Crest_Factor
        {"nodeId": "4/15418", "opcServer": "RED_PDU", "tag_id": 154482, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_Quality_PhaseB_Current_THD
        {"nodeId": "4/15466", "opcServer": "RED_PDU", "tag_id": 154452, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_Quality_PhaseC_Current_Angle
        {"nodeId": "4/15484", "opcServer": "RED_PDU", "tag_id": 154458, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_Quality_PhaseC_Current_Crest_Factor
        {"nodeId": "4/15468", "opcServer": "RED_PDU", "tag_id": 154480, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_Quality_PhaseC_Current_THD
        {"nodeId": "4/15306", "opcServer": "RED_PDU", "tag_id": 154440, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_Active_Power_Total
        {"nodeId": "4/15322", "opcServer": "RED_PDU", "tag_id": 154447, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_Active_Power_Total_Max
        {"nodeId": "4/15310", "opcServer": "RED_PDU", "tag_id": 154450, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_Apparent_Power_Total
        {"nodeId": "4/15356", "opcServer": "RED_PDU", "tag_id": 154446, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_PhaseA_Active_Power
        {"nodeId": "4/15372", "opcServer": "RED_PDU", "tag_id": 154441, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_PhaseA_Active_Power_Max
        {"nodeId": "4/15360", "opcServer": "RED_PDU", "tag_id": 154448, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_PhaseA_Apparent_Power
        {"nodeId": "4/15364", "opcServer": "RED_PDU", "tag_id": 154507, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_PhaseA_Power_Factor
        {"nodeId": "4/15358", "opcServer": "RED_PDU", "tag_id": 154511, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_PhaseA_Reactive_Power
        {"nodeId": "4/15406", "opcServer": "RED_PDU", "tag_id": 154442, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_PhaseB_Active_Power
        {"nodeId": "4/15422", "opcServer": "RED_PDU", "tag_id": 154445, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_PhaseB_Active_Power_Max
        {"nodeId": "4/15410", "opcServer": "RED_PDU", "tag_id": 154451, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_PhaseB_Apparent_Power
        {"nodeId": "4/15414", "opcServer": "RED_PDU", "tag_id": 154509, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_PhaseB_Power_Factor
        {"nodeId": "4/15408", "opcServer": "RED_PDU", "tag_id": 154512, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_PhaseB_Reactive_Power
        {"nodeId": "4/15456", "opcServer": "RED_PDU", "tag_id": 154443, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_PhaseC_Active_Power
        {"nodeId": "4/15472", "opcServer": "RED_PDU", "tag_id": 154444, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_PhaseC_Active_Power_Max
        {"nodeId": "4/15460", "opcServer": "RED_PDU", "tag_id": 154449, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_PhaseC_Apparent_Power
        {"nodeId": "4/15464", "opcServer": "RED_PDU", "tag_id": 154508, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_PhaseC_Power_Factor
        {"nodeId": "4/15458", "opcServer": "RED_PDU", "tag_id": 154513, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_PhaseC_Reactive_Power
        {"nodeId": "4/15314", "opcServer": "RED_PDU", "tag_id": 154510, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_Power_Factor_Total
        {"nodeId": "4/15308", "opcServer": "RED_PDU", "tag_id": 154514, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Power_Reactive_Power_Total
        {"nodeId": "4/15386", "opcServer": "RED_PDU", "tag_id": 154459, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Status_PhaseA_Current_Load_Pct
        {"nodeId": "4/15436", "opcServer": "RED_PDU", "tag_id": 154461, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Status_PhaseB_Current_Load_Pct
        {"nodeId": "4/15486", "opcServer": "RED_PDU", "tag_id": 154460, "asset_id": 10000, "producer_id": 0, "ims_id": "IMS-01"},  # Status_PhaseC_Current_Load_Pct
    ]

    logger = system.util.getLogger("opc-telemetry")
    now    = system.date.now()
    count  = 0

    for m in TAG_MAP:
        qv = system.opc.readValue(m.get("opcServer", OPC_SERVER), m["nodeId"])
        if not qv.quality.isGood() or qv.value is None:
            logger.warn("Bad quality: " + m["nodeId"] + " -> " + str(qv.quality))
            continue
        raw   = float(qv.value)
        value = m["convert"](raw) if "convert" in m else raw
        ts    = qv.timestamp if qv.timestamp is not None else now
        system.db.runPrepUpdate(SQL, [ts, m["tag_id"], m["asset_id"], m["producer_id"], m["ims_id"], value], DB_CONN)
        count += 1

    logger.info("Inserted " + str(count) + " rows")

