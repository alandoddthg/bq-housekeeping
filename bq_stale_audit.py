import os
import pandas as pd
from google.cloud import bigquery
from datetime import datetime, timezone

# Set SSL/gRPC roots for Netskope inspection
os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = "/Users/alan.dodd82/.python-ca-bundle.pem"
os.environ["REQUESTS_CA_BUNDLE"] = "/Users/alan.dodd82/.python-ca-bundle.pem"
os.environ["SSL_CERT_FILE"] = "/Users/alan.dodd82/.python-ca-bundle.pem"

client = bigquery.Client(project="thg-finops-prod")

# Target projects across both orgs
projects = [
    "the-hut-group",          # thehutgroup.com
    "thg-prod-cloud-dw",      # thgingenuity.com
    "agile-bonbon-662",       # thehutgroup.com
    "thg-prod-aether",        # thgingenuity.com
    "vibrant-map-107910",     # thehutgroup.com
    "thg-data-personify",     # thgingenuity.com
    "thg-central-marketing"   # thgingenuity.com
]

stale_findings = []

for pid in projects:
    print(f"Auditing BQ access history for project: {pid}...")
    
    # Check both common regions
    for region in ["region-europe-west2", "region-eu"]:
        print(f"  Checking region: {region}...")
        
        # Query for table sizes and creation times
        query_tables = f"""
        SELECT 
          t.table_schema as dataset,
          t.table_name,
          CAST(s.total_logical_bytes / 1024 / 1024 / 1024 AS FLOAT64) as size_gb,
          t.creation_time
        FROM `{pid}.{region}`.INFORMATION_SCHEMA.TABLES t
        JOIN `{pid}.{region}`.INFORMATION_SCHEMA.TABLE_STORAGE s
          ON t.table_schema = s.table_schema AND t.table_name = s.table_name
        WHERE s.total_logical_bytes > 0
        ORDER BY size_gb DESC
        LIMIT 100
        """
        
        # Query for last access (jobs referencing the table)
        query_usage = f"""
        SELECT 
          t.dataset_id as dataset,
          t.table_id as table_name,
          MAX(j.creation_time) as last_accessed
        FROM `{pid}.{region}`.INFORMATION_SCHEMA.JOBS_BY_PROJECT j,
        UNNEST(referenced_tables) t
        WHERE j.creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 180 DAY)
        GROUP BY 1, 2
        """
        
        try:
            # Load tables
            df_tables = client.query(query_tables).to_dataframe()
            if df_tables.empty:
                continue
                
            # Load usage
            try:
                df_usage = client.query(query_usage).to_dataframe()
            except Exception as e:
                print(f"    --> Could not query jobs in {region}: {e}")
                df_usage = pd.DataFrame(columns=['dataset', 'table_name', 'last_accessed'])

            # Merge
            merged = pd.merge(df_tables, df_usage, on=['dataset', 'table_name'], how='left')
            
            for _, row in merged.iterrows():
                last_access = str(row['last_accessed']) if not pd.isna(row['last_accessed']) else "NEVER (>180 days)"
                created = str(row['creation_time'])
                
                # Convert created to offset-naive for comparison if needed
                creation_dt = row['creation_time']
                if hasattr(creation_dt, 'to_pydatetime'):
                    creation_dt = creation_dt.to_pydatetime()
                if creation_dt.tzinfo is not None:
                    creation_dt = creation_dt.astimezone(timezone.utc).replace(tzinfo=None)
                
                now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
                days_since_creation = (now_naive - creation_dt).days

                # Stale logic: If last_accessed is null AND creation_time > 180 days ago
                if last_access == "NEVER (>180 days)" and days_since_creation > 180:
                    stale_findings.append({
                        'Organisation': 'thgingenuity.com' if pid.startswith('thg-') else 'thehutgroup.com',
                        'Project ID': pid,
                        'Region': region,
                        'Dataset': row['dataset'],
                        'Table': row['table_name'],
                        'Size (GB)': round(row['size_gb'], 2),
                        'Created': created,
                        'Last Accessed': last_access,
                        'Status': 'ZOMBIE DATA',
                        'Action': 'DELETE: No query history found for 180 days.',
                        'Monthly Waste ($)': round(row['size_gb'] * 0.02, 2)
                    })
        except Exception as e:
            if "403" in str(e):
                print(f"    --> Access Denied for {pid} in {region}")
            else:
                print(f"    --> Error in {region}: {e}")

if stale_findings:
    final_df = pd.DataFrame(stale_findings).sort_values(by='Monthly Waste ($)', ascending=False)
    final_df.to_excel("BigQuery_Last_Access_Deep_Audit.xlsx", index=False)
    print(f"\nDone. Identified {len(stale_findings)} truly stale tables with access verification.")
else:
    print("\nNo stale tables identified.")
