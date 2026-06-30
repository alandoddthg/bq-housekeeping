import json
import subprocess
import os
import datetime
import argparse
import sys

# --- CONFIGURATION ---
STATE_FILE = "state.json"
LOG_FILE = "decommission.log"

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

def restore_dataset(key, info, dry_run=False):
    project = info['project']
    dataset = info['dataset']
    backup_path = info['backup_path']
    
    log(f"Restoring access for {project}:{dataset} from {backup_path}...")
    
    local_backup = f"temp_restore_{project}_{dataset}.json"
    
    # 1. Download if GCS
    if backup_path.startswith("gs://"):
        download_cmd = f"gsutil cp {backup_path} {local_backup}"
        if not run_command(download_cmd, dry_run):
            return False
    else:
        local_backup = backup_path

    # 2. Apply Backup
    restore_cmd = f"bq update --source {local_backup} {project}:{dataset}"
    success = run_command(restore_cmd, dry_run) is not None
    
    if success:
        log(f"Successfully restored {project}:{dataset}")
    
    # Cleanup temp
    if local_backup.startswith("temp_restore_") and os.path.exists(local_backup):
        os.remove(local_backup)
        
    return success

def main():
    parser = argparse.ArgumentParser(description="BigQuery Access Restoration Tool")
    parser.add_argument("--dataset", help="Restore a specific dataset (project:dataset)")
    parser.add_argument("--tranche", help="Restore all datasets in a specific tranche")
    parser.add_argument("--all", action="store_true", help="Restore ALL datasets currently in scream test")
    parser.add_argument("--dry-run", action="store_true", help="Simulate restoration without making changes")
    args = parser.parse_args()

    if not os.path.exists(STATE_FILE):
        print(f"Error: {STATE_FILE} not found. Nothing to restore.")
        return

    with open(STATE_FILE, "r") as f:
        state = json.load(f)

    targets = {}
    
    if args.dataset:
        if args.dataset in state:
            targets[args.dataset] = state[args.dataset]
        else:
            print(f"Error: Dataset {args.dataset} not found in state file.")
            return
    elif args.tranche:
        # Flexible tranche matching
        prefix = f"Tranche {args.tranche}:" if args.tranche[0].isdigit() else args.tranche
        for key, info in state.items():
            if info['tranche'] == args.tranche or info['tranche'].startswith(prefix):
                targets[key] = info
        if not targets:
            print(f"No datasets found for tranche {args.tranche} in state file.")
            return
    elif args.all:
        targets = {k: v for k, v in state.items() if v.get("status") == "scream_test"}
    else:
        print("Error: Specify --dataset, --tranche, or --all.")
        return

    log(f"Initiating restoration for {len(targets)} datasets...")

    restored_keys = []
    failed_keys = []
    for key, info in targets.items():
        if info.get("status") == "restored":
            log(f"Skipping {key} - already marked as restored.")
            continue

        if restore_dataset(key, info, args.dry_run):
            if not args.dry_run:
                restored_keys.append(key)
        else:
            failed_keys.append(key)
            log(f"ERROR: Failed to restore {key}")

    # Update state file
    if restored_keys:
        for key in restored_keys:
            state[key]["status"] = "restored"
            state[key]["restored_at"] = datetime.datetime.now().isoformat()

        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
        log("State file updated.")

        # Sync state back to GCS so it stays consistent with local
        backup_bucket = next(
            (v.get("backup_path", "").split("/")[2] for v in state.values() if v.get("backup_path", "").startswith("gs://")),
            None
        )
        if backup_bucket:
            run_command(f"gsutil cp {STATE_FILE} gs://{backup_bucket}/workspace/{STATE_FILE}")

    if failed_keys:
        log(f"RESTORATION INCOMPLETE: {len(failed_keys)} dataset(s) failed to restore: {', '.join(failed_keys)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
