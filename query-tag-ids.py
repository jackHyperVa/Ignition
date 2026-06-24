# Run in Ignition Gateway Script Console:
#   Gateway → Status → Diagnostics → Script Console
# Paste this entire script and click Execute.
# It will print all tag_id / asset_id / producer_id values for the
# Red_PDU assets so they can be used to expand the TAG_MAP.

DB = "TimeScaleCloud"

# ── Step 1: discover tables in the ts schema ────────────────────────────────
table_sql = """
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'ts'
ORDER BY table_name
"""
tables = system.db.runQuery(table_sql, DB)
print("=== Tables in ts schema ===")
for row in tables:
    print("  " + str(row["table_name"]))
print("")

# ── Step 2: look for a tags/metrics lookup table ─────────────────────────────
# Try common names. We'll inspect columns to identify the right one.
candidate_tables = []
for row in tables:
    name = str(row["table_name"]).lower()
    if any(k in name for k in ("tag", "metric", "point", "signal", "channel")):
        candidate_tables.append(str(row["table_name"]))

print("=== Candidate lookup tables: " + str(candidate_tables))
print("")

for tbl in candidate_tables:
    col_sql = """
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'ts' AND table_name = '%s'
    ORDER BY ordinal_position
    """ % tbl
    cols = system.db.runQuery(col_sql, DB)
    col_names = [str(r["column_name"]) for r in cols]
    print("ts." + tbl + " columns: " + str(col_names))

print("")

# ── Step 3: if a tags table exists, query it for Red_PDU asset IDs ───────────
# Asset IDs from the existing TAG_MAP:
#   Branch Meter=9972, Breaker=9974, CB01=9975, CB02=9976,
#   CB03=9977, CB04=9978, CB05=9979, CB06=9980
TARGET_ASSET_IDS = (9972, 9974, 9975, 9976, 9977, 9978, 9979, 9980)
asset_id_list = ",".join(str(a) for a in TARGET_ASSET_IDS)

# Try 'tags' table first, then 'metrics'
for tbl in ["tags", "metrics", "tag", "metric"]:
    try:
        q = "SELECT * FROM ts.%s WHERE asset_id IN (%s) ORDER BY asset_id, tag_id LIMIT 5" % (tbl, asset_id_list)
        result = system.db.runQuery(q, DB)
        if result.rowCount > 0:
            print("=== Found data in ts." + tbl + " ===")
            # Print column names
            ds = result
            cols = [ds.getColumnName(i) for i in range(ds.columnCount)]
            print("Columns: " + str(cols))
            for i in range(min(5, ds.rowCount)):
                row_vals = [str(ds.getValueAt(i, c)) for c in cols]
                print("  " + str(dict(zip(cols, row_vals))))
            print("  ... (showing first 5 rows)")
            break
    except Exception as e:
        pass  # table doesn't exist, try next

# ── Step 4: full dump for the TAG_MAP build ──────────────────────────────────
# Once we confirm the table name above, this query gets everything we need.
# Adjust the table name if needed based on Step 3 output.
TAG_TABLE = "tags"  # <-- update if Step 3 found a different table name

try:
    full_sql = """
    SELECT tag_id, asset_id, tag_name
    FROM ts.%s
    WHERE asset_id IN (%s)
    ORDER BY asset_id, tag_id
    """ % (TAG_TABLE, asset_id_list)
    full = system.db.runQuery(full_sql, DB)
    ds = full

    if ds.rowCount == 0:
        print("No rows returned from ts." + TAG_TABLE + " for those asset IDs.")
        print("Either the table name is different (check Step 3) or the tags aren't registered yet.")
    else:
        print("=== Full tag list (" + str(ds.rowCount) + " rows) ===")
        cols = [ds.getColumnName(i) for i in range(ds.columnCount)]
        for i in range(ds.rowCount):
            row_vals = {c: ds.getValueAt(i, c) for c in cols}
            print(str(row_vals["asset_id"]) + " | " + str(row_vals["tag_id"]) + " | " + str(row_vals["tag_name"]))

except Exception as e:
    print("ERROR querying ts." + TAG_TABLE + ": " + str(e))
    print("Update TAG_TABLE on line above based on the table name found in Step 3.")
