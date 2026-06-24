const { OPCUAClient, MessageSecurityMode, SecurityPolicy, AttributeIds, TimestampsToReturn } = require("node-opcua");
const { Pool } = require("pg");

const OPC_ENDPOINT = "opc.tcp://opc-ua-simulator:4840/UA/DataCenter";
const SAMPLE_INTERVAL_MS = 10000; // 10 seconds — matches Default Historical tag group

const db = new Pool({
  host: "s268bx6qml.pw7e410c6u.tsdb.cloud.timescale.com",
  port: 37438,
  database: "tsdb",
  user: "tsdbadmin",
  password: "56sense78",
  ssl: { rejectUnauthorized: false },
});

// tag mappings: opc node id → { tag_id, asset_id, producer_id, ims_id, value_type, convert }
// convert: optional function applied to the raw OPC value before inserting
const toF = (c) => c * 9 / 5 + 32;

const TAG_MAP = [
  // ── PDU_01 → PDU.MainMeter-001 (producer 195, asset 343) ──────────────────
  { nodeId: "ns=1;s=PDU.PDU_01.Voltage_L1_L2",  tag_id: 10575, asset_id: 343, producer_id: 195, ims_id: "IMS-01", value_type: "double" },
  { nodeId: "ns=1;s=PDU.PDU_01.Voltage_L2_L3",  tag_id: 10576, asset_id: 343, producer_id: 195, ims_id: "IMS-01", value_type: "double" },
  { nodeId: "ns=1;s=PDU.PDU_01.Voltage_L1_L3",  tag_id: 10577, asset_id: 343, producer_id: 195, ims_id: "IMS-01", value_type: "double" },
  { nodeId: "ns=1;s=PDU.PDU_01.Current_L1_A",   tag_id: 10579, asset_id: 343, producer_id: 195, ims_id: "IMS-01", value_type: "double" },
  { nodeId: "ns=1;s=PDU.PDU_01.Current_L2_A",   tag_id: 10580, asset_id: 343, producer_id: 195, ims_id: "IMS-01", value_type: "double" },
  { nodeId: "ns=1;s=PDU.PDU_01.Current_L3_A",   tag_id: 10581, asset_id: 343, producer_id: 195, ims_id: "IMS-01", value_type: "double" },
  { nodeId: "ns=1;s=PDU.PDU_01.TotalPower_kW",  tag_id: 10582, asset_id: 343, producer_id: 195, ims_id: "IMS-01", value_type: "double" },
  { nodeId: "ns=1;s=PDU.PDU_01.PowerFactor",    tag_id: 10585, asset_id: 343, producer_id: 195, ims_id: "IMS-01", value_type: "double" },
  { nodeId: "ns=1;s=PDU.PDU_01.Frequency_Hz",   tag_id: 10578, asset_id: 343, producer_id: 195, ims_id: "IMS-01", value_type: "double" },

  // ── UPS_01 → UPS (producer 194, asset 341) ────────────────────────────────
  { nodeId: "ns=1;s=UPS.UPS_01.InputVoltage_V",    tag_id: 10192, asset_id: 341, producer_id: 194, ims_id: "IMS-01", value_type: "double" },
  { nodeId: "ns=1;s=UPS.UPS_01.OutputVoltage_V",   tag_id: 10198, asset_id: 341, producer_id: 194, ims_id: "IMS-01", value_type: "double" },
  { nodeId: "ns=1;s=UPS.UPS_01.BatteryCharge_Pct", tag_id: 10207, asset_id: 341, producer_id: 194, ims_id: "IMS-01", value_type: "double" },
  { nodeId: "ns=1;s=UPS.UPS_01.LoadPercent",       tag_id: 10203, asset_id: 341, producer_id: 194, ims_id: "IMS-01", value_type: "double" },
  { nodeId: "ns=1;s=UPS.UPS_01.Temperature_C",     tag_id: 10486, asset_id: 341, producer_id: 194, ims_id: "IMS-01", value_type: "double" },
  { nodeId: "ns=1;s=UPS.UPS_01.InputFrequency_Hz", tag_id: 10442, asset_id: 341, producer_id: 194, ims_id: "IMS-01", value_type: "double" },

  // ── HVAC_01 → HVAC (producer 197, asset 345) ──────────────────────────────
  // DB stores air temps in degF — convert from our C values
  { nodeId: "ns=1;s=HVAC.HVAC_01.ReturnAirTemp_C",   tag_id: 10646, asset_id: 345, producer_id: 197, ims_id: "IMS-01", value_type: "double", convert: toF },
  { nodeId: "ns=1;s=HVAC.HVAC_01.SupplyAirTemp_C",   tag_id: 10644, asset_id: 345, producer_id: 197, ims_id: "IMS-01", value_type: "double", convert: toF },
  { nodeId: "ns=1;s=HVAC.HVAC_01.CoolingCapacity_kW",tag_id: 10658, asset_id: 345, producer_id: 197, ims_id: "IMS-01", value_type: "double" },
  { nodeId: "ns=1;s=HVAC.HVAC_01.FanSpeed_RPM",      tag_id: 10652, asset_id: 345, producer_id: 197, ims_id: "IMS-01", value_type: "double",
    // DB expects %, our value is RPM. Convert: 1500 RPM ≈ 60% (max ~2500 RPM)
    convert: (rpm) => Math.min(100, (rpm / 2500) * 100) },
];

async function readAndInsert(session) {
  const nodeIds = TAG_MAP.map((t) => ({ nodeId: t.nodeId, attributeId: AttributeIds.Value }));
  const results = await session.read(nodeIds, TimestampsToReturn.Both);

  const now = new Date();
  const rows = [];

  TAG_MAP.forEach((mapping, i) => {
    const dv = results[i];
    if (!dv || dv.statusCode.value !== 0 || dv.value == null) return;

    let raw = dv.value.value;
    if (typeof raw !== "number" && typeof raw !== "boolean") return;

    const value = mapping.convert ? mapping.convert(raw) : raw;
    const ts = dv.sourceTimestamp || now;

    const col = mapping.value_type === "bool" ? "value_bool"
              : mapping.value_type === "int"  ? "value_int"
              : "value_double";

    rows.push({ ts, tag_id: mapping.tag_id, asset_id: mapping.asset_id,
                producer_id: mapping.producer_id, ims_id: mapping.ims_id,
                col, value });
  });

  if (rows.length === 0) return;

  const client = await db.connect();
  try {
    await client.query("BEGIN");
    for (const r of rows) {
      await client.query(
        `INSERT INTO ts.telemetry (ts, tag_id, asset_id, producer_id, ims_id, ${r.col})
         VALUES ($1, $2, $3, $4, $5, $6)
         ON CONFLICT DO NOTHING`,
        [r.ts, r.tag_id, r.asset_id, r.producer_id, r.ims_id, r.value]
      );
    }
    await client.query("COMMIT");
    console.log(`[${new Date().toISOString()}] Inserted ${rows.length} rows`);
  } catch (err) {
    await client.query("ROLLBACK");
    console.error("DB error:", err.message);
  } finally {
    client.release();
  }
}

async function main() {
  const client = OPCUAClient.create({
    endpointMustExist: false,
    securityMode: MessageSecurityMode.None,
    securityPolicy: SecurityPolicy.None,
    connectionStrategy: { maxRetry: Infinity, initialDelay: 2000, maxDelay: 30000 },
  });

  client.on("connection_reestablished", () => console.log("OPC-UA reconnected"));
  client.on("connection_lost",          () => console.log("OPC-UA connection lost — retrying..."));

  await client.connect(OPC_ENDPOINT);
  console.log("Connected to OPC-UA simulator:", OPC_ENDPOINT);

  const session = await client.createSession();
  console.log(`Polling ${TAG_MAP.length} tags every ${SAMPLE_INTERVAL_MS / 1000}s → ts.telemetry`);

  const poll = async () => {
    try { await readAndInsert(session); }
    catch (e) { console.error("Poll error:", e.message); }
    setTimeout(poll, SAMPLE_INTERVAL_MS);
  };
  poll();
}

main().catch((err) => { console.error(err); process.exit(1); });
