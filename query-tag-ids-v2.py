# Paste into Ignition Gateway Script Console and Execute.
# This checks all DB schemas for a tags table, then inspects
# ts.telemetry to find every tag_id already written for the Red_PDU assets.

DB = "TimeScaleCloud"

ASSET_IDS = (9972, 9974, 9975, 9976, 9977, 9978, 9979, 9980)
asset_list = ",".join(str(a) for a in ASSET_IDS)

# ── 1. Check ALL schemas for any table with 'tag' or 'asset' in the name ─────
print("=== Searching all schemas for tag/asset tables ===")
schema_sql = """
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_name ILIKE '%tag%'
   OR table_name ILIKE '%asset%'
   OR table_name ILIKE '%metric%'
   OR table_name ILIKE '%point%'
   OR table_name ILIKE '%channel%'
ORDER BY table_schema, table_name
"""
schema_ds = system.db.runQuery(schema_sql, DB)
if schema_ds.rowCount == 0:
    print("  (none found)")
else:
    for i in range(schema_ds.rowCount):
        print("  " + str(schema_ds.getValueAt(i, "table_schema")) + "." + str(schema_ds.getValueAt(i, "table_name")))
print("")

# ── 2. How many distinct tag_ids exist in telemetry per asset? ────────────────
print("=== Distinct tag_ids in ts.telemetry per asset ===")
count_sql = """
SELECT asset_id, COUNT(DISTINCT tag_id) AS tag_count
FROM ts.telemetry
WHERE asset_id IN (%s)
GROUP BY asset_id
ORDER BY asset_id
""" % asset_list
count_ds = system.db.runQuery(count_sql, DB)
for i in range(count_ds.rowCount):
    print("  asset_id=" + str(count_ds.getValueAt(i, "asset_id")) + "  tag_ids=" + str(count_ds.getValueAt(i, "tag_count")))
print("")

# ── 3. Dump all distinct tag_ids per asset (full list) ───────────────────────
print("=== All distinct tag_ids in ts.telemetry for Red_PDU assets ===")
all_sql = """
SELECT DISTINCT asset_id, tag_id
FROM ts.telemetry
WHERE asset_id IN (%s)
ORDER BY asset_id, tag_id
""" % asset_list
all_ds = system.db.runQuery(all_sql, DB)
for i in range(all_ds.rowCount):
    print(str(all_ds.getValueAt(i, "asset_id")) + " | " + str(all_ds.getValueAt(i, "tag_id")))
print("")
print("Total rows: " + str(all_ds.rowCount))
