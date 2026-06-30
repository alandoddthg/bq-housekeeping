import os
import pandas as pd
from google.cloud import bigquery
from datetime import datetime, timezone, timedelta
import openpyxl

# Set SSL/gRPC roots for Netskope inspection (THG standard)
os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = "/Users/alan.dodd82/.python-ca-bundle.pem"
os.environ["REQUESTS_CA_BUNDLE"] = "/Users/alan.dodd82/.python-ca-bundle.pem"
os.environ["SSL_CERT_FILE"] = "/Users/alan.dodd82/.python-ca-bundle.pem"

PROJECTS = [
    "the-hut-group", "thg-prod-cloud-dw", "agile-bonbon-662", "thg-prod-aether", 
    "vibrant-map-107910", "thg-data-personify", "thg-prod-cloud-dw-thg-plc", 
    "thg-central-marketing", "thg-machine-learning-fraud", "thcdn-on-the-edge", 
    "thg-dev-vertexai-poc", "thg-beauty", "thg-dev-aether", "thg-ingenuity", 
    "thg-prod-data-engineering", "thg-prod-ecommplatform", "thg-prod-billing-exp", 
    "thg-ml-assets", "thg-ml-live", "thg-ml-staging", "thg-ml-dev", "thg-cx-data", 
    "thg-finops-prod", "thg-fraud-data", "thg-service-project-1", "horizon-on-the-edge", 
    "thg-sandbox-data-engineering", "thg-dev-cloud-dw", "thg-ics-reporting-prod", 
    "thg-content", "thg-dev-data-engineering-test", "thg-dev-data-sandbox", 
    "lookfantastic-ecommerce", "thg-seoclarity", "thg-influencer", "thg-unityhz-fe-li", 
    "myprotein-ecommerce", "thg-web-platform", "thg-dev-cloud-dw-thg-plc", 
    "cultbeauty-ecommerce", "thg-search-poc", "thg-media-commerce", "thg-beautydata-liveramp", 
    "tilla-2-grind", "thg-finops-nonprod", "tilla-5-mypro", "tilla-6-lfgrp", 
    "thg-finance", "big-query-test-1292", "thg-dev-ics-reporting"
]

REGIONS = ["europe-west2", "eu"]
client = bigquery.Client()

def get_last_access_details(project_id, region, access_type):
    """Retrieves the last 5 access events (Reads or Writes) for each dataset."""
    region_suffix = f"region-{region}"
    if access_type == 'READ':
        query = f"""
        WITH raw_reads AS (
          SELECT t.dataset_id, j.user_email, j.creation_time,
          ROW_NUMBER() OVER(PARTITION BY t.dataset_id ORDER BY j.creation_time DESC) as rn
          FROM `{project_id}.{region_suffix}.INFORMATION_SCHEMA.JOBS_BY_PROJECT` j,
          UNNEST(referenced_tables) t
          WHERE j.creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 180 DAY)
          AND t.project_id = '{project_id}'
        )
        SELECT dataset_id, MAX(creation_time) as last_access_time,
        ARRAY_AGG(STRUCT(user_email, creation_time) ORDER BY creation_time DESC LIMIT 5) as top_5
        FROM raw_reads WHERE rn <= 5 GROUP BY dataset_id
        """
    else: # WRITE
        query = f"""
        WITH raw_writes AS (
          SELECT destination_table.dataset_id, user_email, creation_time,
          ROW_NUMBER() OVER(PARTITION BY destination_table.dataset_id ORDER BY creation_time DESC) as rn
          FROM `{project_id}.{region_suffix}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
          WHERE destination_table.dataset_id IS NOT NULL
          AND destination_table.project_id = '{project_id}'
          AND creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 180 DAY)
        )
        SELECT dataset_id, MAX(creation_time) as last_access_time,
        ARRAY_AGG(STRUCT(user_email, creation_time) ORDER BY creation_time DESC LIMIT 5) as top_5
        FROM raw_writes WHERE rn <= 5 GROUP BY dataset_id
        """
    try:
        results = client.query(query).to_dataframe()
        access_map = {}
        for _, row in results.iterrows():
            details = []
            for item in row['top_5']:
                dt_str = item['creation_time'].strftime('%Y-%m-%d %H:%M')
                details.append(f"{dt_str} ({item['user_email']})")
            access_map[row['dataset_id']] = {'details': "\n".join(details), 'last_time': row['last_access_time']}
        return access_map
    except: return {}

def get_deep_storage_metadata(project_id, region):
    region_suffix = f"region-{region}"
    query = f"""
    SELECT s.schema_name as dataset_id,
      COALESCE((SELECT option_value FROM `{project_id}.{region_suffix}.INFORMATION_SCHEMA.SCHEMATA_OPTIONS` so 
         WHERE so.schema_name = s.schema_name AND so.option_name = 'description'), 'No Description') as description,
      CAST(SUM(st.total_logical_bytes) / 1024 / 1024 / 1024 AS FLOAT64) as size_gb,
      MAX(st.storage_last_modified_time) as last_storage_modified
    FROM `{project_id}.{region_suffix}.INFORMATION_SCHEMA.SCHEMATA` s
    LEFT JOIN `{project_id}.{region_suffix}.INFORMATION_SCHEMA.TABLE_STORAGE` st
      ON s.schema_name = st.table_schema
    GROUP BY 1, 2
    """
    try:
        return client.query(query).to_dataframe()
    except Exception as e: return str(e)

all_data = []
now = datetime.now(timezone.utc)

for pid in PROJECTS:
    print(f"Deep Auditing with Details: {pid}...")
    for reg in REGIONS:
        df_meta = get_deep_storage_metadata(pid, reg)
        if isinstance(df_meta, str): continue
            
        reads = get_last_access_details(pid, reg, 'READ')
        writes = get_last_access_details(pid, reg, 'WRITE')
        
        for _, row in df_meta.iterrows():
            ds_id = row['dataset_id']
            size_gb = row['size_gb'] if not pd.isna(row['size_gb']) else 0.0
            last_store = row['last_storage_modified']
            
            read_info = reads.get(ds_id, {'details': "No Read Access (180d)", 'last_time': None})
            write_info = writes.get(ds_id, {'details': "No Write Access (180d)", 'last_time': None})
            
            last_r = read_info['last_time']
            last_w = write_info['last_time']
            
            # Determine "Deep Staleness"
            days_since_touched = None
            if last_store:
                last_store_utc = last_store.replace(tzinfo=timezone.utc)
                days_since_touched = (now - last_store_utc).days
            
            # Determine "Days Since Last Activity" (most recent of R, W, or Store)
            activity_dates = [d for d in [last_r, last_w, last_store] if d is not None]
            days_since_activity = None
            if activity_dates:
                last_act = max(activity_dates)
                if last_act.tzinfo is None: last_act = last_act.replace(tzinfo=timezone.utc)
                days_since_activity = (now - last_act).days
            
            is_test = any(x in ds_id.lower() for x in ['test', 'temp', 'tmp', 'demo', 'poc', 'beta'])
            
            tranche = "Active"
            priority = "Low"
            
            if days_since_touched is None or days_since_touched > 365:
                if is_test: tranche, priority = "Tranche 1: Abandoned Test/Temp (>1yr)", "Critical"
                elif size_gb > 100: tranche, priority = "Tranche 2: Abandoned Large Prod (>1yr)", "Critical"
                else: tranche, priority = "Tranche 3: Abandoned Small Prod (>1yr)", "High"
            elif days_since_activity is not None and days_since_activity > 180:
                tranche, priority = "Tranche 4: Stale (No Access 180d, No Write >6mo)", "Medium"
            elif is_test:
                tranche, priority = "Tranche 5: Active Test (Housekeeping)", "Low"

            all_data.append({
                'Project': pid, 'Region': reg, 'Dataset': ds_id,
                'Description': row['description'].strip('"'),
                'Size (GB)': round(size_gb, 2),
                'Monthly Cost ($)': round(size_gb * 0.02, 2),
                'Tranche': tranche,
                'Cleanup Priority': priority,
                'Days Since Last Activity': days_since_activity,
                'Days Since Last Modified': days_since_touched,
                'Last Read Time': last_r.replace(tzinfo=None) if last_r else None,
                'Last Write Time': last_w.replace(tzinfo=None) if last_w else None,
                'Last 5 Reads (Who/When)': read_info['details'],
                'Last 5 Writes (Who/When)': write_info['details'],
                'Last Storage Update': last_store.replace(tzinfo=None) if last_store else "Never/Historical",
                'Defensible Deletion Status': "CONFIRMED: NO MODS > 1YR" if (days_since_touched and days_since_touched > 365) else "REVIEW"
            })

final_df = pd.DataFrame(all_data)

# Sort by Staleness and Size
tranche_order = {
    "Tranche 1: Abandoned Test/Temp (>1yr)": 0,
    "Tranche 2: Abandoned Large Prod (>1yr)": 1,
    "Tranche 3: Abandoned Small Prod (>1yr)": 2,
    "Tranche 4: Stale (No Access 180d, No Write >6mo)": 3,
    "Tranche 5: Active Test (Housekeeping)": 4,
    "Active": 5
}
final_df['t_sort'] = final_df['Tranche'].map(tranche_order).fillna(99)
final_df = final_df.sort_values(by=['t_sort', 'Size (GB)'], ascending=[True, False]).drop(columns=['t_sort'])

output_file = '20260624_Data_Estate_Cleanup_Audit xlsx.xlsx'
with pd.ExcelWriter(output_file, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
    final_df.to_excel(writer, sheet_name='BQ-added-Data', index=False)

print(f"\nAudit complete. Restored access details for {len(final_df)} datasets.")
