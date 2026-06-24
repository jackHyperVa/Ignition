const { OPCUAServer, DataType, Variant } = require("node-opcua");

const DEVICES = {
  PDU: [
    { name: "PDU_01", currentBase: [42, 38, 44] },
    { name: "PDU_02", currentBase: [39, 41, 37] },
    { name: "PDU_03", currentBase: [45, 43, 46] },
    { name: "PDU_04", currentBase: [40, 42, 38] },
  ],
  UPS: [
    { name: "UPS_01", loadBase: 68, inputVoltBase: 480 },
    { name: "UPS_02", loadBase: 72, inputVoltBase: 480 },
  ],
  HVAC: [
    { name: "HVAC_01", supplyBase: 16, returnBase: 29, humidityBase: 44 },
    { name: "HVAC_02", supplyBase: 17, returnBase: 28, humidityBase: 47 },
  ],
};

// Sine wave with unique phase per tag so they don't all move in sync
const phases = {};
function getPhase(key) {
  if (!phases[key]) phases[key] = Math.random() * Math.PI * 2;
  return phases[key];
}

function sine(baseline, amplitude, periodMs, key) {
  return baseline + amplitude * Math.sin((Date.now() / periodMs) * 2 * Math.PI + getPhase(key));
}

function addDouble(namespace, parent, name, getter) {
  const parentId = parent.nodeId.value;
  namespace.addVariable({
    componentOf: parent,
    browseName: name,
    nodeId: `s=${parentId}.${name}`,
    dataType: DataType.Double,
    minimumSamplingInterval: 1000,
    value: {
      get: () => new Variant({ dataType: DataType.Double, value: +getter().toFixed(2) }),
    },
  });
}

function buildPDU(namespace, folder, device) {
  const node = namespace.addFolder(folder, { browseName: device.name, nodeId: `s=PDU.${device.name}` });
  const [c1, c2, c3] = device.currentBase;
  const key = device.name;

  // 480V 3-phase line-to-line, ±2V drift
  addDouble(namespace, node, "Voltage_L1_L2", () => sine(480, 2, 30000, `${key}.VL1`));
  addDouble(namespace, node, "Voltage_L2_L3", () => sine(480, 2, 30000, `${key}.VL2`));
  addDouble(namespace, node, "Voltage_L1_L3", () => sine(480, 2, 30000, `${key}.VL3`));

  addDouble(namespace, node, "Current_L1_A", () => sine(c1, 3, 20000, `${key}.A1`));
  addDouble(namespace, node, "Current_L2_A", () => sine(c2, 3, 20000, `${key}.A2`));
  addDouble(namespace, node, "Current_L3_A", () => sine(c3, 3, 20000, `${key}.A3`));

  // P = sqrt(3) * V * I_avg * PF (PF ~0.92)
  addDouble(namespace, node, "TotalPower_kW", () => {
    const iAvg = (sine(c1, 3, 20000, `${key}.A1`) + sine(c2, 3, 20000, `${key}.A2`) + sine(c3, 3, 20000, `${key}.A3`)) / 3;
    return (Math.sqrt(3) * 480 * iAvg * 0.92) / 1000;
  });

  addDouble(namespace, node, "PowerFactor", () => sine(0.92, 0.02, 60000, `${key}.PF`));
  addDouble(namespace, node, "Frequency_Hz", () => sine(60, 0.05, 15000, `${key}.Hz`));
  addDouble(namespace, node, "Temperature_C", () => sine(30, 1.5, 45000, `${key}.Tmp`));
}

function buildUPS(namespace, folder, device) {
  const node = namespace.addFolder(folder, { browseName: device.name, nodeId: `s=UPS.${device.name}` });
  const key = device.name;

  addDouble(namespace, node, "InputVoltage_V",   () => sine(device.inputVoltBase, 3, 30000, `${key}.Vin`));
  addDouble(namespace, node, "OutputVoltage_V",  () => sine(device.inputVoltBase, 1, 30000, `${key}.Vout`));
  addDouble(namespace, node, "BatteryCharge_Pct",() => sine(100, 0.3, 120000, `${key}.Bat`));
  addDouble(namespace, node, "LoadPercent",      () => sine(device.loadBase, 4, 25000, `${key}.Load`));
  addDouble(namespace, node, "Temperature_C",    () => sine(28, 1, 50000, `${key}.Tmp`));
  addDouble(namespace, node, "InputFrequency_Hz",() => sine(60, 0.05, 15000, `${key}.Hz`));
}

function buildHVAC(namespace, folder, device) {
  const node = namespace.addFolder(folder, { browseName: device.name, nodeId: `s=HVAC.${device.name}` });
  const key = device.name;

  addDouble(namespace, node, "SupplyAirTemp_C",  () => sine(device.supplyBase, 0.8, 40000, `${key}.Sup`));
  addDouble(namespace, node, "ReturnAirTemp_C",  () => sine(device.returnBase, 1.2, 35000, `${key}.Ret`));
  addDouble(namespace, node, "Humidity_Pct",     () => sine(device.humidityBase, 2, 60000, `${key}.Hum`));
  addDouble(namespace, node, "FanSpeed_RPM",     () => sine(1500, 80, 20000, `${key}.Fan`));
  addDouble(namespace, node, "CoolingCapacity_kW",() => sine(42, 2.5, 30000, `${key}.Cool`));

  namespace.addVariable({
    componentOf: node,
    browseName: "CompressorStatus",
    nodeId: `s=HVAC.${device.name}.CompressorStatus`,
    dataType: DataType.Boolean,
    minimumSamplingInterval: 1000,
    value: { get: () => new Variant({ dataType: DataType.Boolean, value: true }) },
  });
}

// ============================================================
// Red_PDU — Janitza UMG800 (Branch Meter + CB01-CB06) & UMG801 (Breaker)
// ============================================================
const SERVER_START_MS = Date.now();


// Adds: base + _Avg + _Min + _Max (demand-interval statistics)
function addMMA(ns, parent, name, base, amp, period, key) {
  addDouble(ns, parent, name,
    () => sine(base, amp, period, key));
  addDouble(ns, parent, name + "_Avg",
    () => sine(base, amp * 0.05, period * 12, key + "_A"));
  addDouble(ns, parent, name + "_Min",
    () => base - amp * (1.02 + 0.06 * Math.sin(Date.now() / 870000 + getPhase(key + "_N"))));
  addDouble(ns, parent, name + "_Max",
    () => base + amp * (1.02 + 0.06 * Math.sin(Date.now() / 870000 + getPhase(key + "_X"))));
}

const CB_DEVICES = [
  { name: "CB01", iBase: [24.0, 23.0, 25.0], eBase: [11600, 3870, 3710, 4030] },
  { name: "CB02", iBase: [18.0, 17.0, 19.0], eBase: [8700,  2900, 2740, 3060] },
  { name: "CB03", iBase: [20.0, 21.0, 19.0], eBase: [9700,  3230, 3390, 3070] },
  { name: "CB04", iBase: [22.0, 23.0, 21.0], eBase: [10600, 3550, 3710, 3390] },
  { name: "CB05", iBase: [12.0, 11.0, 13.0], eBase: [5800,  1940, 1780, 2100] },
  { name: "CB06", iBase: [16.0, 15.0, 17.0], eBase: [7700,  2580, 2420, 2740] },
];

function buildBranchMeter(namespace, redPduFolder) {
  const node = namespace.addFolder(redPduFolder, { browseName: "Branch_Meter", nodeId: "s=Red_PDU.Branch_Meter" });
  const k = "BM";

  addDouble(namespace, node, "Voltage_Frequency_RMS", () => sine(60, 0.03, 15000, `${k}.Hz`));

  // L-L voltages (480V 3-phase bus)
  addMMA(namespace, node, "Voltage_Voltage_LL_RMS_L12", 480, 1.2, 60000, `${k}.VLL12`);
  addMMA(namespace, node, "Voltage_Voltage_LL_RMS_L23", 480, 1.2, 65000, `${k}.VLL23`);
  addMMA(namespace, node, "Voltage_Voltage_LL_RMS_L31", 480, 1.2, 70000, `${k}.VLL31`);
  addDouble(namespace, node, "Voltage_AvgPhases_Voltage_LL_RMS_L12",
    () => sine(480, 0.6, 90000, `${k}.VLLAv`));

  // L-N voltages (277V = 480/√3)
  addMMA(namespace, node, "Voltage_Voltage_LN_RMS_L1", 277.1, 0.7, 60000, `${k}.VLN1`);
  addMMA(namespace, node, "Voltage_Voltage_LN_RMS_L2", 277.1, 0.7, 65000, `${k}.VLN2`);
  addMMA(namespace, node, "Voltage_Voltage_LN_RMS_L3", 277.1, 0.7, 70000, `${k}.VLN3`);
  addDouble(namespace, node, "Voltage_AvgPhases_Voltage_LN_RMS_L1",
    () => sine(277.1, 0.3, 90000, `${k}.VLNAv`));

  // Power quality — voltage THD (%) and unbalance (%)
  // Note: OPC browseName uses underscore instead of space (space invalid in Ignition tag names)
  addDouble(namespace, node, "Power_Quality_Voltage_THD_L1", () => sine(2.5, 0.4, 300000, `${k}.THD1`));
  addDouble(namespace, node, "Power_Quality_Voltage_THD_L2", () => sine(2.4, 0.35, 300000, `${k}.THD2`));
  addDouble(namespace, node, "Power_Quality_Voltage_THD_L3", () => sine(2.6, 0.45, 300000, `${k}.THD3`));
  addDouble(namespace, node, "Voltage_Voltage_Unbalance",    () => sine(0.5, 0.12, 120000, `${k}.VUnb`));
}

function buildCB(namespace, redPduFolder, device) {
  const node = namespace.addFolder(redPduFolder, {
    browseName: device.name,
    nodeId: `s=Red_PDU.${device.name}`,
  });
  const k = `Red_PDU.${device.name}`;
  const [iA, iB, iC] = device.iBase;
  const [eSum, eA, eB, eC] = device.eBase;

  const VLN       = 277.13;   // 480 / √3
  const PF_BASE   = 0.97;
  const PF_AMP    = 0.008;
  const I_AMP     = 1.5;      // A amplitude for phase current drift
  const I_PERIOD  = 22000;
  const P_PERIOD  = 25000;
  const Q_PERIOD  = 28000;
  const RATED_A   = 32;       // rated current for load-% calculation
  const CT_RATIO  = 1000;
  const FUND_F    = 0.963;    // fraction of power at fundamental (THD ~5%)
  const Q_FACTOR  = Math.tan(Math.acos(PF_BASE));

  // Nominal per-phase power (kW)
  const pBa = (VLN * iA * PF_BASE) / 1000;
  const pBb = (VLN * iB * PF_BASE) / 1000;
  const pBc = (VLN * iC * PF_BASE) / 1000;
  const pBs = pBa + pBb + pBc;

  // Closures used for complex current (called per read — tiny time drift is acceptable)
  const getIA  = () => sine(iA, I_AMP, I_PERIOD, `${k}.IA`);
  const getIB  = () => sine(iB, I_AMP, I_PERIOD + 1500, `${k}.IB`);
  const getIC  = () => sine(iC, I_AMP, I_PERIOD + 3000, `${k}.IC`);
  const getIN  = () => sine(2.0, 0.3, 30000, `${k}.IN`);
  const getPFA = () => sine(PF_BASE + 0.003, PF_AMP, 120000, `${k}.PFA`);
  const getPFB = () => sine(PF_BASE,         PF_AMP, 125000, `${k}.PFB`);
  const getPFC = () => sine(PF_BASE - 0.003, PF_AMP, 130000, `${k}.PFC`);

  const elapsed = () => (Date.now() - SERVER_START_MS) / 3600000; // hours

  // ---- Energy (kWh) — monotonically increasing from server start ----
  addDouble(namespace, node, "Energy_PhaseA_Active_Energy",           () => eA + elapsed() * pBa);
  addDouble(namespace, node, "Energy_PhaseA_Active_Energy_Consumed",  () => eA + elapsed() * pBa);
  addDouble(namespace, node, "Energy_PhaseA_Active_Energy_Supplied",  () => 0.001);
  addDouble(namespace, node, "Energy_PhaseB_Active_Energy",           () => eB + elapsed() * pBb);
  addDouble(namespace, node, "Energy_PhaseB_Active_Energy_Consumed",  () => eB + elapsed() * pBb);
  addDouble(namespace, node, "Energy_PhaseB_Active_Energy_Supplied",  () => 0.001);
  addDouble(namespace, node, "Energy_PhaseC_Active_Energy",           () => eC + elapsed() * pBc);
  addDouble(namespace, node, "Energy_PhaseC_Active_Energy_Consumed",  () => eC + elapsed() * pBc);
  addDouble(namespace, node, "Energy_PhaseC_Active_Energy_Supplied",  () => 0.001);
  addDouble(namespace, node, "Energy_Sum_Active_Energy",              () => eSum + elapsed() * pBs);
  addDouble(namespace, node, "Energy_Sum_Active_Energy_Consumed",     () => eSum + elapsed() * pBs);
  addDouble(namespace, node, "Energy_Sum_Active_Energy_Supplied",     () => 0.003);

  // ---- Energy (kVAh) ----
  addDouble(namespace, node, "Energy_PhaseA_Apparent_Energy", () => (eA  + elapsed() * pBa) / PF_BASE);
  addDouble(namespace, node, "Energy_PhaseB_Apparent_Energy", () => (eB  + elapsed() * pBb) / PF_BASE);
  addDouble(namespace, node, "Energy_PhaseC_Apparent_Energy", () => (eC  + elapsed() * pBc) / PF_BASE);
  addDouble(namespace, node, "Energy_Sum_Apparent_Energy",    () => (eSum + elapsed() * pBs) / PF_BASE);

  // ---- Energy (kVARh) — inductive load dominates ----
  addDouble(namespace, node, "Energy_PhaseA_Reactive_Energy",                    () => (eA  + elapsed() * pBa) * Q_FACTOR);
  addDouble(namespace, node, "Energy_PhaseA_Reactive_Energy_Consumed_Inductive", () => (eA  + elapsed() * pBa) * Q_FACTOR);
  addDouble(namespace, node, "Energy_PhaseA_Reactive_Energy_Consumed_Capacitive",() => 0.001);
  addDouble(namespace, node, "Energy_PhaseB_Reactive_Energy",                    () => (eB  + elapsed() * pBb) * Q_FACTOR);
  addDouble(namespace, node, "Energy_PhaseB_Reactive_Energy_Consumed_Inductive", () => (eB  + elapsed() * pBb) * Q_FACTOR);
  addDouble(namespace, node, "Energy_PhaseB_Reactive_Energy_Consumed_Capacitive",() => 0.001);
  addDouble(namespace, node, "Energy_PhaseC_Reactive_Energy",                    () => (eC  + elapsed() * pBc) * Q_FACTOR);
  addDouble(namespace, node, "Energy_PhaseC_Reactive_Energy_Consumed_Inductive", () => (eC  + elapsed() * pBc) * Q_FACTOR);
  addDouble(namespace, node, "Energy_PhaseC_Reactive_Energy_Consumed_Capacitive",() => 0.001);
  addDouble(namespace, node, "Energy_Sum_Reactive_Energy",                       () => (eSum + elapsed() * pBs) * Q_FACTOR);
  addDouble(namespace, node, "Energy_Sum_Reactive_Energy_Consumed_Inductive",    () => (eSum + elapsed() * pBs) * Q_FACTOR);
  addDouble(namespace, node, "Energy_Sum_Reactive_Energy_Consumed_Capacitive",   () => 0.003);

  // ---- Active Power (kW): base + _Avg/_Min/_Max + Fundamental variants ----
  addMMA(namespace, node, "Power_PhaseA_Active_Power",             pBa,       pBa * 0.08,       P_PERIOD,       `${k}.PA`);
  addMMA(namespace, node, "Power_PhaseA_Active_Power_Fundamental", pBa*FUND_F,pBa*FUND_F*0.08, P_PERIOD,       `${k}.PAF`);
  addMMA(namespace, node, "Power_PhaseB_Active_Power",             pBb,       pBb * 0.08,       P_PERIOD+2000,  `${k}.PB`);
  addMMA(namespace, node, "Power_PhaseB_Active_Power_Fundamental", pBb*FUND_F,pBb*FUND_F*0.08, P_PERIOD+2000,  `${k}.PBF`);
  addMMA(namespace, node, "Power_PhaseC_Active_Power",             pBc,       pBc * 0.08,       P_PERIOD+4000,  `${k}.PC`);
  addMMA(namespace, node, "Power_PhaseC_Active_Power_Fundamental", pBc*FUND_F,pBc*FUND_F*0.08, P_PERIOD+4000,  `${k}.PCF`);
  addMMA(namespace, node, "Power_Sum_Active_Power",                pBs,       pBs * 0.08,       P_PERIOD,       `${k}.PS`);
  addMMA(namespace, node, "Power_Sum_Active_Power_Fundamental",    pBs*FUND_F,pBs*FUND_F*0.08, P_PERIOD,       `${k}.PSF`);

  // ---- Reactive Power (kVAR) ----
  const qBa = pBa * Q_FACTOR, qBb = pBb * Q_FACTOR, qBc = pBc * Q_FACTOR, qBs = pBs * Q_FACTOR;
  addMMA(namespace, node, "Power_PhaseA_Reactive_Power",             qBa,       qBa * 0.1,       Q_PERIOD,      `${k}.QA`);
  addMMA(namespace, node, "Power_PhaseA_Reactive_Power_Fundamental", qBa*FUND_F,qBa*FUND_F*0.1, Q_PERIOD,      `${k}.QAF`);
  addMMA(namespace, node, "Power_PhaseB_Reactive_Power",             qBb,       qBb * 0.1,       Q_PERIOD+2000, `${k}.QB`);
  addMMA(namespace, node, "Power_PhaseB_Reactive_Power_Fundamental", qBb*FUND_F,qBb*FUND_F*0.1, Q_PERIOD+2000, `${k}.QBF`);
  addMMA(namespace, node, "Power_PhaseC_Reactive_Power",             qBc,       qBc * 0.1,       Q_PERIOD+4000, `${k}.QC`);
  addMMA(namespace, node, "Power_PhaseC_Reactive_Power_Fundamental", qBc*FUND_F,qBc*FUND_F*0.1, Q_PERIOD+4000, `${k}.QCF`);
  addMMA(namespace, node, "Power_Sum_Reactive_Power",                qBs,       qBs * 0.1,       Q_PERIOD,      `${k}.QS`);
  addMMA(namespace, node, "Power_Sum_Reactive_Power_Fundamental",    qBs*FUND_F,qBs*FUND_F*0.1, Q_PERIOD,      `${k}.QSF`);

  // ---- Apparent Power (kVA) ----
  const sBa = pBa/PF_BASE, sBb = pBb/PF_BASE, sBc = pBc/PF_BASE, sBs = pBs/PF_BASE;
  addMMA(namespace, node, "Power_PhaseA_Apparent_Power", sBa, sBa*0.07, P_PERIOD,      `${k}.SA`);
  addMMA(namespace, node, "Power_PhaseB_Apparent_Power", sBb, sBb*0.07, P_PERIOD+2000, `${k}.SB`);
  addMMA(namespace, node, "Power_PhaseC_Apparent_Power", sBc, sBc*0.07, P_PERIOD+4000, `${k}.SC`);
  addMMA(namespace, node, "Power_Sum_Apparent_Power",    sBs, sBs*0.07, P_PERIOD,      `${k}.SS`);

  // ---- Distortion Power (kVA) D = sqrt(S²-P²-Q²) ----
  const dB = (p) => Math.sqrt(Math.max(0, (p/PF_BASE)**2 - p**2 - (p*Q_FACTOR)**2));
  const dBa = dB(pBa), dBb = dB(pBb), dBc = dB(pBc);
  const dBs = dBa + dBb + dBc;
  addMMA(namespace, node, "Power_PhaseA_Distortion_Power", dBa, dBa*0.12+0.001, P_PERIOD,      `${k}.DA`);
  addMMA(namespace, node, "Power_PhaseB_Distortion_Power", dBb, dBb*0.12+0.001, P_PERIOD+2000, `${k}.DB`);
  addMMA(namespace, node, "Power_PhaseC_Distortion_Power", dBc, dBc*0.12+0.001, P_PERIOD+4000, `${k}.DC`);
  // Sum: only Avg/Min/Max in IDS (no instantaneous base)
  addDouble(namespace, node, "Power_Sum_Distortion_Power_Avg", () => sine(dBs, dBs*0.05+0.001, P_PERIOD*5, `${k}.DSa`));
  addDouble(namespace, node, "Power_Sum_Distortion_Power_Min", () => dBs * 0.90);
  addDouble(namespace, node, "Power_Sum_Distortion_Power_Max", () => dBs * 1.10);

  // ---- Power Factor (dimensionless) ----
  const pfBa = PF_BASE+0.003, pfBb = PF_BASE, pfBc = PF_BASE-0.003;
  addMMA(namespace, node, "Power_PhaseA_Power_Factor",             pfBa,       PF_AMP,      120000, `${k}.PFA`);
  addMMA(namespace, node, "Power_PhaseA_Power_Factor_Fundamental", pfBa*1.005, PF_AMP,      120000, `${k}.PFAF`);
  addMMA(namespace, node, "Power_PhaseB_Power_Factor",             pfBb,       PF_AMP,      125000, `${k}.PFB`);
  addMMA(namespace, node, "Power_PhaseB_Power_Factor_Fundamental", pfBb*1.005, PF_AMP,      125000, `${k}.PFBF`);
  addMMA(namespace, node, "Power_PhaseC_Power_Factor",             pfBc,       PF_AMP,      130000, `${k}.PFC`);
  addMMA(namespace, node, "Power_PhaseC_Power_Factor_Fundamental", pfBc*1.005, PF_AMP,      130000, `${k}.PFCF`);
  addMMA(namespace, node, "Power_Sum_Power_Factor",                PF_BASE,    PF_AMP*0.7,  125000, `${k}.PFS`);
  addMMA(namespace, node, "Power_Sum_Power_Factor_Fundamental",    PF_BASE*1.005,PF_AMP*0.7,125000, `${k}.PFSF`);

  // ---- Current RMS (A) ----
  addMMA(namespace, node, "Current_PhaseA_Current_RMS", iA,  I_AMP, I_PERIOD,       `${k}.IA`);
  addMMA(namespace, node, "Current_PhaseB_Current_RMS", iB,  I_AMP, I_PERIOD+1500,  `${k}.IB`);
  addMMA(namespace, node, "Current_PhaseC_Current_RMS", iC,  I_AMP, I_PERIOD+3000,  `${k}.IC`);
  addMMA(namespace, node, "Current_PhaseN_Current_RMS", 2.0, 0.3,   30000,          `${k}.IN`);
  // AvgPhases: only demand stats (no instantaneous base in IDS)
  const iAvg = (iA + iB + iC) / 3;
  addDouble(namespace, node, "Current_AvgPhases_Current_RMS_Avg", () => sine(iAvg, I_AMP*0.05, I_PERIOD*10, `${k}.IAa`));
  addDouble(namespace, node, "Current_AvgPhases_Current_RMS_Min", () => iAvg - I_AMP * 1.02);
  addDouble(namespace, node, "Current_AvgPhases_Current_RMS_Max", () => iAvg + I_AMP * 1.02);

  // ---- Current Load % (rated = 32A) ----
  const lpA = (iA/RATED_A)*100, lpB = (iB/RATED_A)*100, lpC = (iC/RATED_A)*100;
  const lpN = (2.0/RATED_A)*100, lpAvg = (lpA+lpB+lpC)/3;
  const lpAmp = (I_AMP/RATED_A)*100;
  addDouble(namespace, node, "Current_PhaseA_Current_Load_Pct",     () => sine(lpA, lpAmp, I_PERIOD,      `${k}.LPA`));
  addDouble(namespace, node, "Current_PhaseA_Current_Load_Pct_Avg", () => sine(lpA, lpAmp*0.05, I_PERIOD*10, `${k}.LPAa`));
  addDouble(namespace, node, "Current_PhaseA_Current_Load_Pct_Min", () => lpA - lpAmp * 1.02);
  addDouble(namespace, node, "Current_PhaseA_Current_Load_Pct_Max", () => lpA + lpAmp * 1.02);
  addDouble(namespace, node, "Current_PhaseB_Current_Load_Pct",     () => sine(lpB, lpAmp, I_PERIOD+1500,  `${k}.LPB`));
  addDouble(namespace, node, "Current_PhaseB_Current_Load_Pct_Avg", () => sine(lpB, lpAmp*0.05, I_PERIOD*10, `${k}.LPBa`));
  addDouble(namespace, node, "Current_PhaseB_Current_Load_Pct_Min", () => lpB - lpAmp * 1.02);
  addDouble(namespace, node, "Current_PhaseB_Current_Load_Pct_Max", () => lpB + lpAmp * 1.02);
  addDouble(namespace, node, "Current_PhaseC_Current_Load_Pct",     () => sine(lpC, lpAmp, I_PERIOD+3000,  `${k}.LPC`));
  addDouble(namespace, node, "Current_PhaseC_Current_Load_Pct_Avg", () => sine(lpC, lpAmp*0.05, I_PERIOD*10, `${k}.LPCa`));
  addDouble(namespace, node, "Current_PhaseC_Current_Load_Pct_Min", () => lpC - lpAmp * 1.02);
  addDouble(namespace, node, "Current_PhaseC_Current_Load_Pct_Max", () => lpC + lpAmp * 1.02);
  addDouble(namespace, node, "Current_PhaseN_Current_Load_Pct",     () => sine(lpN, (0.3/RATED_A)*100, 30000, `${k}.LPN`));
  addDouble(namespace, node, "Current_PhaseN_Current_Load_Pct_Avg", () => sine(lpN, 0.03, 300000, `${k}.LPNa`));
  addDouble(namespace, node, "Current_PhaseN_Current_Load_Pct_Min", () => lpN - (0.3/RATED_A)*100 * 1.02);
  addDouble(namespace, node, "Current_PhaseN_Current_Load_Pct_Max", () => lpN + (0.3/RATED_A)*100 * 1.02);
  addDouble(namespace, node, "Current_AvgPhases_Current_Load_Pct_Avg", () => sine(lpAvg, lpAmp*0.05, I_PERIOD*10, `${k}.LPAva`));
  addDouble(namespace, node, "Current_AvgPhases_Current_Load_Pct_Min", () => lpAvg - lpAmp * 1.02);
  addDouble(namespace, node, "Current_AvgPhases_Current_Load_Pct_Max", () => lpAvg + lpAmp * 1.02);

  // ---- Current THD (%) — slowly varying, typical SMPS ~5% ----
  const THD = [{ph:"A",b:5.0},{ph:"B",b:4.8},{ph:"C",b:5.2},{ph:"N",b:8.0}];
  THD.forEach(({ph, b}) => {
    const amp = ph === "N" ? 1.2 : 0.8;
    const per = ph === "N" ? 300000 : 305000;
    const key2 = `${k}.THD${ph}`;
    addDouble(namespace, node, `Current_Phase${ph}_Current_THD`,     () => sine(b, amp, per, key2));
    addDouble(namespace, node, `Current_Phase${ph}_Current_THD_Avg`, () => sine(b, amp*0.05, per*6, key2+"a"));
    addDouble(namespace, node, `Current_Phase${ph}_Current_THD_Min`, () => b - amp * 1.02);
    addDouble(namespace, node, `Current_Phase${ph}_Current_THD_Max`, () => b + amp * 1.02);
  });
  const thdAvgB = (5.0+4.8+5.2)/3;
  addDouble(namespace, node, "Current_AvgPhases_Current_THD_Avg", () => sine(thdAvgB, 0.04, 1800000, `${k}.THDAva`));
  addDouble(namespace, node, "Current_AvgPhases_Current_THD_Min", () => thdAvgB - 0.8 * 1.02);
  addDouble(namespace, node, "Current_AvgPhases_Current_THD_Max", () => thdAvgB + 0.8 * 1.02);

  // ---- Current TDD (%) ----
  const TDD = [{ph:"A",b:3.5},{ph:"B",b:3.3},{ph:"C",b:3.7},{ph:"N",b:5.0}];
  TDD.forEach(({ph, b}) => {
    const amp = ph === "N" ? 0.7 : 0.5;
    const per = 300000 + (ph === "B" ? 5000 : ph === "C" ? -5000 : 0);
    const key2 = `${k}.TDD${ph}`;
    addDouble(namespace, node, `Current_Phase${ph}_Current_TDD`,     () => sine(b, amp, per, key2));
    addDouble(namespace, node, `Current_Phase${ph}_Current_TDD_Avg`, () => sine(b, amp*0.05, per*6, key2+"a"));
    addDouble(namespace, node, `Current_Phase${ph}_Current_TDD_Min`, () => b - amp * 1.02);
    addDouble(namespace, node, `Current_Phase${ph}_Current_TDD_Max`, () => b + amp * 1.02);
  });
  const tddAvgB = (3.5+3.3+3.7)/3;
  addDouble(namespace, node, "Current_AvgPhases_Current_TDD_Avg", () => sine(tddAvgB, 0.025, 1800000, `${k}.TDDAva`));
  addDouble(namespace, node, "Current_AvgPhases_Current_TDD_Min", () => tddAvgB - 0.5 * 1.02);
  addDouble(namespace, node, "Current_AvgPhases_Current_TDD_Max", () => tddAvgB + 0.5 * 1.02);

  // ---- Current Harmonic_k — 3rd harmonic ≈ 5% of fundamental ----
  // OPC browseName uses _k instead of [k] (brackets invalid in Ignition tag names)
  addDouble(namespace, node, "Current_PhaseA_Current_Harmonic_k",
    () => iA * 0.05 * (1 + 0.1 * Math.sin(Date.now() / 120000 + getPhase(`${k}.H3A`))));
  addDouble(namespace, node, "Current_PhaseB_Current_Harmonic_k",
    () => iB * 0.05 * (1 + 0.1 * Math.sin(Date.now() / 120000 + getPhase(`${k}.H3B`))));
  addDouble(namespace, node, "Current_PhaseC_Current_Harmonic_k",
    () => iC * 0.05 * (1 + 0.1 * Math.sin(Date.now() / 120000 + getPhase(`${k}.H3C`))));
  addDouble(namespace, node, "Current_PhaseN_Current_Harmonic_k",
    () => 2.0 * 0.08 * (1 + 0.1 * Math.sin(Date.now() / 120000 + getPhase(`${k}.H3N`))));

  // ---- Crest Factor (~1.52 for SMPS loads) ----
  addDouble(namespace, node, "Current_PhaseA_Current_Crest_Factor", () => sine(1.52, 0.04, 120000, `${k}.CrA`));
  addDouble(namespace, node, "Current_PhaseB_Current_Crest_Factor", () => sine(1.51, 0.04, 125000, `${k}.CrB`));
  addDouble(namespace, node, "Current_PhaseC_Current_Crest_Factor", () => sine(1.53, 0.04, 130000, `${k}.CrC`));
  addDouble(namespace, node, "Current_PhaseN_Current_Crest_Factor", () => sine(1.65, 0.06, 120000, `${k}.CrN`));

  // ---- Complex Current (A) — real & imaginary components ----
  addDouble(namespace, node, "Current_PhaseA_Current_Complex_Real", () => getIA() * getPFA());
  addDouble(namespace, node, "Current_PhaseA_Current_Complex_Imag", () => getIA() * Math.sin(Math.acos(Math.min(getPFA(), 0.9999))));
  addDouble(namespace, node, "Current_PhaseB_Current_Complex_Real", () => getIB() * getPFB());
  addDouble(namespace, node, "Current_PhaseB_Current_Complex_Imag", () => getIB() * Math.sin(Math.acos(Math.min(getPFB(), 0.9999))));
  addDouble(namespace, node, "Current_PhaseC_Current_Complex_Real", () => getIC() * getPFC());
  addDouble(namespace, node, "Current_PhaseC_Current_Complex_Imag", () => getIC() * Math.sin(Math.acos(Math.min(getPFC(), 0.9999))));
  addDouble(namespace, node, "Current_PhaseN_Current_Complex_Real", () => getIN() * 0.980);
  addDouble(namespace, node, "Current_PhaseN_Current_Complex_Imag", () => getIN() * 0.200);

  // ---- Current Unbalance (%) ----
  addDouble(namespace, node, "Current_System_Current_Unbalance", () => {
    const avg = (iA + iB + iC) / 3;
    const maxDev = Math.max(Math.abs(iA - avg), Math.abs(iB - avg), Math.abs(iC - avg));
    return (maxDev / avg) * 100 + sine(0, 0.3, 60000, `${k}.IUnb`);
  });

  // ---- Configuration — static values ----
  // _k suffix replaces [k] (brackets invalid in Ignition tag names)
  addDouble(namespace, node, "Configuration_Branch_Branch_Label",           () => 0);
  addDouble(namespace, node, "Configuration_N_CT_Transformer_Ratio_k",     () => CT_RATIO);
  addDouble(namespace, node, "Configuration_PhaseA_CT_Transformer_Ratio_k", () => CT_RATIO);
  addDouble(namespace, node, "Configuration_PhaseB_CT_Transformer_Ratio_k", () => CT_RATIO);
  addDouble(namespace, node, "Configuration_PhaseC_CT_Transformer_Ratio_k", () => CT_RATIO);
}

function buildBreaker(namespace, redPduFolder) {
  const node = namespace.addFolder(redPduFolder, { browseName: "Breaker", nodeId: "s=Red_PDU.Breaker" });
  addDouble(namespace, node, "Status_Breaker_Status",           () => 1); // 1 = closed/normal
  addDouble(namespace, node, "Status_Metering_Function_Status", () => 1); // 1 = active
  addDouble(namespace, node, "Status_Trip_Count",               () => 0);
}

async function main() {
  const server = new OPCUAServer({
    port: 4840,
    resourcePath: "/UA/DataCenter",
    hostname: "opc-ua-simulator",
    buildInfo: { productName: "DataCenter Simulator", productUri: "urn:datacenter:simulator" },
  });

  await server.initialize();

  const addressSpace = server.engine.addressSpace;
  const namespace = addressSpace.getOwnNamespace();
  const root = namespace.addFolder(addressSpace.rootFolder.objects, { browseName: "DataCenter" });

  const pduFolder  = namespace.addFolder(root, { browseName: "PDU" });
  const upsFolder  = namespace.addFolder(root, { browseName: "UPS" });
  const hvacFolder = namespace.addFolder(root, { browseName: "HVAC" });

  DEVICES.PDU.forEach(d  => buildPDU(namespace, pduFolder, d));
  DEVICES.UPS.forEach(d  => buildUPS(namespace, upsFolder, d));
  DEVICES.HVAC.forEach(d => buildHVAC(namespace, hvacFolder, d));

  const redPduFolder = namespace.addFolder(root, { browseName: "Red_PDU", nodeId: "s=Red_PDU" });
  buildBranchMeter(namespace, redPduFolder);
  CB_DEVICES.forEach(d => buildCB(namespace, redPduFolder, d));
  buildBreaker(namespace, redPduFolder);

  await server.start();

  const endpoint = server.endpoints[0].endpointDescriptions()[0].endpointUrl;
  console.log("OPC-UA simulator running at:", endpoint);
  console.log("  4x PDU  | 480V 3-phase, current, power, PF, freq, temp");
  console.log("  2x UPS  | voltage in/out, battery, load, temp, freq");
  console.log("  2x HVAC | supply/return temp, humidity, fan RPM, cooling kW");
  console.log("  Red_PDU | Branch Meter (31 tags) + CB01-CB06 (253 tags each) + Breaker (3 tags)");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
