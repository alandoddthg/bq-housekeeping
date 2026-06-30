import os
import pandas as pd
from google.cloud import bigquery
from datetime import datetime, timezone, timedelta

# Set SSL/gRPC roots for Netskope inspection (THG standard)
os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = "/Users/alan.dodd82/.python-ca-bundle.pem"
os.environ["REQUESTS_CA_BUNDLE"] = "/Users/alan.dodd82/.python-ca-bundle.pem"
os.environ["SSL_CERT_FILE"] = "/Users/alan.dodd82/.python-ca-bundle.pem"

PROJECTS = [
    "the-hut-group",
    "thg-prod-cloud-dw",
    "agile-bonbon-662",
    "thg-prod-aether",
    "vibrant-map-107910",
    "thg-data-personify",
    "thg-central-marketing"
]

REGIONS = ["europe-west2", "eu"] # Use short names for region- syntax

client = bigquery.Client()

def get_last_access_details(project_id, region, access_type):
    """
    Retrieves the last 5 access events (Reads or Writes) for each dataset.
    """
    region_suffix = f"region-{region}"
    
    if access_type == 'READ':
        query = f"""
        WITH raw_reads AS (
          SELECT 
            t.dataset_id,
            j.user_email,
            j.creation_time,
            ROW_NUMBER() OVER(PARTITION BY t.dataset_id ORDER BY j.creation_time DESC) as rn
          FROM `{project_id}.{region_suffix}.INFORMATION_SCHEMA.JOBS_BY_PROJECT` j,
          UNNEST(referenced_tables) t
          WHERE j.creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 180 DAY)
          AND t.project_id = '{project_id}'
        )
        SELECT 
          dataset_id,
          ARRAY_AGG(STRUCT(user_email, creation_time) ORDER BY creation_time DESC LIMIT 5) as top_5
        FROM raw_reads
        WHERE rn <= 5
        GROUP BY dataset_id
        """
    else: # WRITE
        query = f"""
        WITH raw_writes AS (
          SELECT 
            destination_table.dataset_id,
            user_email,
            creation_time,
            ROW_NUMBER() OVER(PARTITION BY destination_table.dataset_id ORDER BY creation_time DESC) as rn
          FROM `{project_id}.{region_suffix}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
          WHERE destination_table.dataset_id IS NOT NULL
          AND destination_table.project_id = '{project_id}'
          AND creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 180 DAY)
        )
        SELECT 
          dataset_id,
          ARRAY_AGG(STRUCT(user_email, creation_time) ORDER BY creation_time DESC LIMIT 5) as top_5
        FROM raw_writes
        WHERE rn <= 5
        GROUP BY dataset_id
        """
    
    try:
        results = client.query(query).to_dataframe()
        access_map = {}
        for _, row in results.iterrows():
            details = []
            for item in row['top_5']:
                dt_str = item['creation_time'].strftime('%Y-%m-%d %H:%M')
                details.append(f"{dt_str} ({item['user_email']})")
            access_map[row['dataset_id']] = "\n".join(details)
        return access_map
    except Exception as e:
        print(f"    Warning: Could not get {access_type} info for {project_id} {region}: {e}")
        return {}

def get_dataset_metadata(project_id, region):
    region_suffix = f"region-{region}"
    query = f"""
    SELECT 
      s.schema_name as dataset_id,
      COALESCE(
        (SELECT option_value FROM `{project_id}.{region_suffix}.INFORMATION_SCHEMA.SCHEMATA_OPTIONS` so 
         WHERE so.schema_name = s.schema_name AND so.option_name = 'description'),
        'No Description'
      ) as description,
      CAST(SUM(st.total_logical_bytes) / 1024 / 1024 / 1024 AS FLOAT64) as size_gb,
      MAX(st.storage_last_modified_time) as last_storage_modified
    FROM `{project_id}.{region_suffix}.INFORMATION_SCHEMA.SCHEMATA` s
    LEFT JOIN `{project_id}.{region_suffix}.INFORMATION_SCHEMA.TABLE_STORAGE` st
      ON s.schema_name = st.table_schema
    GROUP BY 1, 2
    """
    try:
        return client.query(query).to_dataframe()
    except Exception as e:
        print(f"    Error: Could not get metadata for {project_id} {region}: {e}")
        return pd.DataFrame()

all_data = []

for pid in PROJECTS:
    print(f"Processing project: {pid}...")
    for reg in REGIONS:
        print(f"  Region: {reg}...")
        
        # 1. Get Metadata
        df_meta = get_dataset_metadata(pid, reg)
        if df_meta.empty:
            continue
            
        # 2. Get Access Details
        reads = get_last_access_details(pid, reg, 'READ')
        writes = get_last_access_details(pid, reg, 'WRITE')
        
        # 3. Combine
        for _, row in df_meta.iterrows():
            ds_id = row['dataset_id']
            last_r = reads.get(ds_id, "No Read Access (180d)")
            last_w = writes.get(ds_id, "No Write Access (180d)")
            
            # Determine Status / Cleanup Priority
            status = "ACTIVE"
            priority = "Low"
            action = "Keep"
            
            is_stale = (last_r == "No Read Access (180d)" and last_w == "No Write Access (180d)")
            is_test = any(x in ds_id.lower() for x in ['test', 'temp', 'tmp', 'demo', 'poc', 'beta'])
            
            if is_stale:
                status = "STALE"
                priority = "High"
                action = "DELETE (No access 180d)"
            elif is_test:
                status = "TEST DATA"
                priority = "Medium"
                action = "Verify & Cleanup (Test/Temp naming)"
            
            if row['size_gb'] > 100:
                priority = "Critical" if is_stale or is_test else priority
            
            all_data.append({
                'Project': pid,
                'Region': reg,
                'Dataset': ds_id,
                'Description': row['description'].strip('"'),
                'Size (GB)': round(row['size_gb'], 2),
                'Last Storage Update': row['last_storage_modified'],
                'Last 5 Reads (Who/When)': last_r,
                'Last 5 Writes (Who/When)': last_w,
                'Status': status,
                'Cleanup Priority': priority,
                'Recommended Action': action
            })

if all_data:
    final_df = pd.DataFrame(all_data)
    # Sort: Priority High/Critical first, then Size
    priority_order = {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}
    final_df['p_sort'] = final_df['Cleanup Priority'].map(priority_order)
    final_df = final_df.sort_values(by=['p_sort', 'Size (GB)'], ascending=[True, False]).drop(columns=['p_sort'])
    
    output_file = "BigQuery_Access_and_Staleness_Audit_2026.xlsx"
    final_df.to_excel(output_file, index=False)
    print(f"\nAudit complete. Found {len(all_data)} datasets.")
    print(f"Report saved to: {output_file}")
else:
    print("\nNo data found.")
