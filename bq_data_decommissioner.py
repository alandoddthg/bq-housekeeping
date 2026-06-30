import pandas as pd
import json
import subprocess
import os
import datetime
import time
import argparse

# --- CONFIGURATION ---
EXCEL_FILE = "20260624_Data_Estate_Cleanup_Audit xlsx.xlsx"
SHEET_NAME = "BQ-added-Data"
BACKUP_DIR = "backups"
LOG_FILE = "decommission.log"
STATE_FILE = "state.json"
# Critical service accounts to keep (Optional)
# Org Admin access is inherited via Org-level IAM and does not need listing here
SAFE_PRINCIPALS = []

def log(message):
    timestamp = datetime.datetime.now().isoformat()
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(f"[{timestamp}] {message}")

def run_command(cmd, dry_run=False):
    if dry_run:
        log(f"[DRY-RUN] Would execute: {cmd}")
        return "DRY_RUN_SUCCESS"
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        log(f"ERROR running command: {cmd}\n{e.stderr}")
        return None

def backup_dataset(project, dataset, dry_run=False, bucket=None):
    filename = f"{project}_{dataset}_backup.json"
    
    if bucket:
        path = f"gs://{bucket}/{BACKUP_DIR}/{filename}"
    else:
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)
        path = os.path.join(BACKUP_DIR, filename)

    log(f"Backing up access for {project}:{dataset}...")
    cmd = f"bq show --format=prettyjson {project}:{dataset}"
    output = run_command(cmd, dry_run=False) # Always read for backup even in dry-run
    
    if dry_run:
        log(f"[DRY-RUN] Would save backup to {path}")
        return path
        
    if output:
        if bucket:
            # Write to temp file then upload to GCS
            temp_file = f"temp_{filename}"
            with open(temp_file, "w") as f:
                f.write(output)
            upload_cmd = f"gsutil cp {temp_file} {path}"
            if run_command(upload_cmd):
                os.remove(temp_file)
                return path
        else:
            with open(path, "w") as f:
                f.write(output)
            return path
    return None

def apply_scream_test(project, dataset, backup_path, dry_run=False):
    log(f"Applying Scream Test to {project}:{dataset}...")
    
    # 1. Label the dataset for visibility
    label_cmd = f"bq update --set_label cleanup-status:scream-test {project}:{dataset}"
    if not run_command(label_cmd, dry_run):
        log(f"WARNING: Failed to label {project}:{dataset} - continuing with access restriction")

    if dry_run:
        log(f"[DRY-RUN] Would update access for {project}:{dataset} to strip non-OWNER principals")
        return True

    # 2. Get current policy from backup (it was just saved)
    local_policy_file = f"temp_policy_{project}_{dataset}.json"
    if backup_path.startswith("gs://"):
        download_cmd = f"gsutil cp {backup_path} {local_policy_file}"
        if not run_command(download_cmd):
            return False
    else:
        local_policy_file = backup_path

    try:
        with open(local_policy_file, "r") as f:
            policy = json.load(f)
            
        access = policy.get("access", [])
        # Keep only entries with role OWNER or specific safe principals
        new_access = [
            entry for entry in access 
            if entry.get("role") == "OWNER" or 
            any(p in str(entry) for p in SAFE_PRINCIPALS)
        ]
        
        # Prepare update payload (bq update --source expects only the access part if we want to be safe, 
        # or we can modify the whole JSON and re-apply)
        policy["access"] = new_access
        
        update_file = f"update_{project}_{dataset}.json"
        with open(update_file, "w") as f:
            json.dump(policy, f)
            
        update_cmd = f"bq update --source {update_file} {project}:{dataset}"
        success = run_command(update_cmd) is not None
        
        os.remove(update_file)
        if local_policy_file.startswith("temp_policy_"):
            os.remove(local_policy_file)
            
        return success
    except Exception as e:
        log(f"Failed to process policy for {project}:{dataset}: {e}")
        return False

def delete_dataset(project, dataset, dry_run=False):
    log(f"PERMANENTLY DELETING {project}:{dataset}...")
    cmd = f"bq rm -r -f {project}:{dataset}"
    if run_command(cmd, dry_run):
        log(f"Deleted {project}:{dataset}")
        return True
    return False

def sync_workspace(bucket):
    log(f"Synchronizing workspace to gs://{bucket}/workspace/...")
    files_to_sync = [STATE_FILE, LOG_FILE, "PROCESS.md"]
    for f in files_to_sync:
        if os.path.exists(f):
            run_command(f"gsutil cp {f} gs://{bucket}/workspace/{f}")

def main():
    parser = argparse.ArgumentParser(description="BigQuery Data Decommissioner")
    parser.add_argument("--tranche", help="Specific tranche to process (e.g., '1', '2' or full name)")
    parser.add_argument("--list-tranches", action="store_true", help="List all available tranches in the audit file")
    parser.add_argument("--dry-run", action="store_true", help="Simulate actions without making changes")
    parser.add_argument("--backup-bucket", default="bq-admin-backup", help="GCS bucket name for storing backups (default: 'bq-admin-backup')")
    parser.add_argument("--phase-d", action="store_true", help="Execute Phase D: Final Deletion for datasets that passed monitoring")
    parser.add_argument("--retention-days", type=int, default=7, help="Monitoring period in days before Phase D deletion (default: 7)")
    args = parser.parse_args()

    if args.dry_run:
        log("!!! DRY RUN MODE ENABLED - No changes will be made !!!")

    # PHASE D: Deletion
    if args.phase_d:
        if not os.path.exists(STATE_FILE):
            print("Error: No state.json found. Nothing to delete.")
            return
            
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            
        log(f"Initiating Phase D (Deletion) with {args.retention_days} day retention...")
        deleted_keys = []
        for key, info in state.items():
            if info.get("status") != "scream_test":
                continue
                
            initiated_at = datetime.datetime.fromisoformat(info['scream_initiated_at'])
            elapsed = datetime.datetime.now() - initiated_at
            
            if elapsed.days >= args.retention_days:
                if delete_dataset(info['project'], info['dataset'], args.dry_run):
                    if not args.dry_run:
                        deleted_keys.append(key)
            else:
                log(f"Skipping {key} - only {elapsed.days} days elapsed (threshold: {args.retention_days})")
                
        if deleted_keys:
            for key in deleted_keys:
                state[key]["status"] = "deleted"
                state[key]["deleted_at"] = datetime.datetime.now().isoformat()
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)
            sync_workspace(args.backup_bucket)
        return

    # List Tranches or Process Tranche
    if not os.path.exists(EXCEL_FILE):
        print(f"Error: Audit file {EXCEL_FILE} not found.")
        return

    df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)
    
    if args.list_tranches:
        print("Available Tranches:")
        for t in df['Tranche'].unique():
            print(f" - {t}")
        return

    if not args.tranche:
        print("Error: No tranche specified. Use --tranche <name/number> or --list-tranches.")
        return

    # Flexible tranche matching
    selected_tranche = args.tranche
    available_tranches = df['Tranche'].unique().tolist()
    
    if selected_tranche not in available_tranches:
        # Try numeric/decimal shorthand
        is_num = all(c.isdigit() or c == '.' for c in selected_tranche)
        if is_num:
            prefix = f"Tranche {selected_tranche}:"
            matches = [t for t in available_tranches if str(t).startswith(prefix)]
            if matches:
                selected_tranche = matches[0]
            else:
                print(f"Error: Could not find Tranche starting with '{prefix}'")
                return
        else:
            print(f"Error: Tranche '{selected_tranche}' not found in audit file.")
            return

    # Filter for selected Tranche and CONFIRMED status
    targets = df[(df['Tranche'] == selected_tranche) & (df['Defensible Deletion Status'].str.contains("CONFIRMED", na=False))]
    
    if targets.empty:
        print(f"No confirmed targets found for {selected_tranche}.")
        return

    log(f"Processing {len(targets)} targets for {selected_tranche}.")
    
    state = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            try:
                state = json.load(f)
            except json.JSONDecodeError:
                state = {}

    for _, row in targets.iterrows():
        project = row['Project']
        dataset = row['Dataset']
        key = f"{project}:{dataset}"
        
        if key in state and state[key].get("status") in ["deleted", "scream_test"]:
            log(f"Skipping {key} - already processed (Status: {state[key].get('status')})")
            continue
            
        log(f"Processing {key} (Size: {row['Size (GB)']} GB, Cost: ${row['Monthly Cost ($)']})")
        
        # 1. Backup
        backup_path = backup_dataset(project, dataset, dry_run=args.dry_run, bucket=args.backup_bucket)
        if not backup_path:
            log(f"Failed to backup {key}. Skipping.")
            continue
            
        # 2. Scream Test
        if apply_scream_test(project, dataset, backup_path, dry_run=args.dry_run):
            log(f"Scream test applied successfully for {key}")
            if not args.dry_run:
                state[key] = {
                    "project": project,
                    "dataset": dataset,
                    "tranche": selected_tranche,
                    "backup_path": backup_path,
                    "scream_initiated_at": datetime.datetime.now().isoformat(),
                    "status": "scream_test"
                }
        else:
            log(f"ERROR: Failed to apply scream test for {key} - dataset access NOT modified")

    if not args.dry_run:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
        log(f"Phase 1 complete for {selected_tranche}. Scream tests initiated.")
        sync_workspace(args.backup_bucket)
    else:
        log(f"[DRY-RUN] Phase 1 simulation complete for {selected_tranche}.")

if __name__ == "__main__":
    main()
