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

REGIONS = ["europe-west2", "eu"]

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
          MAX(creation_time) as last_access_time,
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
          MAX(creation_time) as last_access_time,
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
            access_map[row['dataset_id']] = {
                'details': "\n".join(details),
                'last_time': row['last_access_time']
            }
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
            read_info = reads.get(ds_id, {'details': "No Read Access (180d)", 'last_time': None})
            write_info = writes.get(ds_id, {'details': "No Write Access (180d)", 'last_time': None})
            
            last_r_details = read_info['details']
            last_w_details = write_info['details']
            last_r_time = read_info['last_time']
            last_w_time = write_info['last_time']
            
            # Determine Tranche
            is_stale = (last_r_time is None and last_w_time is None)
            is_test = any(x in ds_id.lower() for x in ['test', 'temp', 'tmp', 'demo', 'poc', 'beta'])
            size_gb = row['size_gb']
            
            tranche = "Active"
            priority = "Low"
            
            if is_stale:
                if is_test:
                    tranche = "Tranche 1: Stale Test/Temp"
                    priority = "Critical"
                elif size_gb > 100:
                    tranche = "Tranche 2: High Saving Stale (>100GB)"
                    priority = "Critical"
                else:
                    tranche = "Tranche 3: Stale Production"
                    priority = "High"
            elif is_test:
                tranche = "Tranche 4: Active Test/Temp (Review Needed)"
                priority = "Medium"
            elif size_gb > 500:
                tranche = "Active (Large: Monitor)"
                priority = "Low"
            
            all_data.append({
                'Project': pid,
                'Region': reg,
                'Dataset': ds_id,
                'Description': row['description'].strip('"'),
                'Size (GB)': round(size_gb, 2) if not pd.isna(size_gb) else 0.0,
                'Monthly Cost ($)': round(size_gb * 0.02, 2) if not pd.isna(size_gb) else 0.0,
                'Tranche': tranche,
                'Cleanup Priority': priority,
                'Last Read Time': last_r_time.replace(tzinfo=None) if last_r_time else None,
                'Last Write Time': last_w_time.replace(tzinfo=None) if last_w_time else None,
                'Last 5 Reads (Who/When)': last_r_details,
                'Last 5 Writes (Who/When)': last_w_details,
                'Last Storage Update': row['last_storage_modified'].replace(tzinfo=None) if row['last_storage_modified'] else None
            })

if all_data:
    final_df = pd.DataFrame(all_data)
    
    # Ensure all datetime columns are timezone-unaware just in case
    for col in ['Last Read Time', 'Last Write Time', 'Last Storage Update']:
        if col in final_df.columns:
            final_df[col] = pd.to_datetime(final_df[col]).dt.tz_localize(None)
    
    # Custom Sort order for Tranches
    tranche_order = {
        "Tranche 1: Stale Test/Temp": 0,
        "Tranche 2: High Saving Stale (>100GB)": 1,
        "Tranche 3: Stale Production": 2,
        "Tranche 4: Active Test/Temp (Review Needed)": 3,
        "Active (Large: Monitor)": 4,
        "Active": 5
    }
    final_df['t_sort'] = final_df['Tranche'].map(tranche_order)
    final_df = final_df.sort_values(by=['t_sort', 'Size (GB)'], ascending=[True, False]).drop(columns=['t_sort'])
    
    # Create README data
    readme_data = [
        {'Category': 'Tranche 1', 'Definition': 'Stale Test/Temp', 'Detail': 'Datasets with "test/temp/tmp" in the name AND no access in 180 days. Immediate deletion candidates.'},
        {'Category': 'Tranche 2', 'Definition': 'High Saving Stale', 'Detail': 'Production datasets > 100GB with no access in 180 days. Primary target for cost reduction.'},
        {'Category': 'Tranche 3', 'Definition': 'Stale Production', 'Detail': 'Small production datasets with no access in 180 days.'},
        {'Category': 'Tranche 4', 'Definition': 'Active Test/Temp', 'Detail': 'Datasets with "test/temp/tmp" in name but HAVE access history. Review for housekeeping.'},
        {'Category': 'Column: Description', 'Definition': 'Dataset Metadata', 'Detail': 'Pulled from BigQuery SCHEMATA_OPTIONS. Helps identify ownership/purpose.'},
        {'Category': 'Column: Last 5 Access', 'Definition': 'Audit Trail', 'Detail': 'Shows the most recent 5 jobs (Read or Write) including the user email and time.'},
        {'Category': 'Column: Monthly Cost', 'Definition': 'Financial Impact', 'Detail': 'Estimated based on $0.02 per GB per month (standard logical storage).'}
    ]
    df_readme = pd.DataFrame(readme_data)

    output_file = "BigQuery_Comprehensive_Cleanup_Audit_2026.xlsx"
    with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
        df_readme.to_excel(writer, sheet_name='README', index=False)
        final_df.to_excel(writer, sheet_name='Audit Results', index=False)
        
        # Formatting
        workbook = writer.book
        worksheet_audit = writer.sheets['Audit Results']
        worksheet_readme = writer.sheets['README']
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
        
        for col_num, value in enumerate(df_readme.columns.values):
            worksheet_readme.write(0, col_num, value, header_format)
            worksheet_readme.set_column(col_num, col_num, 30)

        for col_num, value in enumerate(final_df.columns.values):
            worksheet_audit.write(0, col_num, value, header_format)
            worksheet_audit.set_column(col_num, col_num, 20)
            
    print(f"\nAudit complete. Found {len(all_data)} datasets.")
    print(f"Report saved to: {output_file}")
else:
    print("\nNo data found.")
