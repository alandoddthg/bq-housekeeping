# BigQuery Data Decommissioning & Scream Test Process

This document outlines the automated process for safely decommissioning BigQuery datasets within the THG estate. It utilises the `bq_data_decommissioner.py` tool to automate backups, access restriction (Scream Test), and tracking.

---

## 1. Prerequisites
- **CLI Tools:** `gcloud` and `bq` must be authenticated and operational.
- **Permissions:** Organisation Admin access (required to modify access policies across projects).
- **Audit File:** `20260624_Data_Estate_Cleanup_Audit xlsx.xlsx` must be present in the `bq-housekeeping` directory.
- **Backup Bucket:** A GCS bucket named `bq-admin-backup` must exist (default location for all metadata backups).

## 2. The Scream Test Strategy
A "Scream Test" is a safe method to verify data staleness by temporarily revoking access before physical deletion. If a downstream process or user "screams" (reports a failure), access can be restored instantly.

### Phase A: Identification (Audit)
Targets are identified in the Audit Excel file under the `BQ-added-Data` sheet. 
- **Tranche Selection:** Targets are grouped by Tranche (e.g., Tranche 1, Tranche 1.1, etc.).
- **Confirmation Gate:** **Only** rows marked as **`CONFIRMED`** (e.g., `CONFIRMED: NO MODS > 1YR`) in the `Defensible Deletion Status` column (Column P) will be processed. All other statuses (e.g., `REVIEW`) are ignored.

### Phase B: Initiation (Scream Test)
The script performs the following for each target:
1. **Backup:** Captures the current access policy and uploads it to `gs://bq-admin-backup/backups/[project]_[dataset]_backup.json`.
2. **Labelling:** Adds a label `cleanup-status:scream-test` to the dataset for in-console visibility.
3. **Restriction:** Updates the dataset access to remove all users/groups EXCEPT:
   - Organisation Admins (retained via Org-level IAM).
   - `OWNER` role holders (preserved to maintain resource ownership integrity).
4. **Logging:** Records the initiation timestamp and backup location in `state.json`.

### Phase C: Monitoring (7-14 Days)
The datasets remain in this restricted state for a minimum of 7 days (matching BigQuery's Time Travel window).

### Phase D: Final Deletion (Automated)
After the monitoring period (default 7 days), use the `--phase-d` flag to permanently delete the datasets.

---

## 3. EMERGENCY RECOVERY PROCESS
If a user or automated system "screams" (reports access denied), follow these steps to restore access immediately.

### Step 1: Identify the Target
Locate the project and dataset name from the user report.

### Step 2: Run the Restoration Tool
The `bq_restore_access.py` tool is designed for rapid recovery. It automatically identifies the backup location in GCS and reapplies the original policy.

**To restore a specific dataset:**
```bash
python3 bq_restore_access.py --dataset project_id:dataset_id
```

**To restore an entire tranche (if a systemic issue is found):**
```bash
python3 bq_restore_access.py --tranche 1.1
```

**To restore everything (emergency "undo" for all active tests):**
```bash
python3 bq_restore_access.py --all
```

### Step 3: Manual Verification (If script fails)
If the script cannot run, you can manually re-apply the policy using the `bq` CLI:
1. Locate the backup JSON: `gsutil ls gs://bq-admin-backup/backups/`
2. Download the backup: `gsutil cp gs://bq-admin-backup/backups/[project]_[dataset]_backup.json .`
3. Apply the policy: `bq update --source [project]_[dataset]_backup.json [project]:[dataset]`

---

## 4. Operational Commands

### Listing Available Tranches
```bash
python3 bq_data_decommissioner.py --list-tranches
```

### Performing a Dry Run
```bash
python3 bq_data_decommissioner.py --tranche 1.1 --dry-run
```

---

## 5. Safety Nets & Best Practices
- **Org-Level Access:** As an Org Admin, you retain access even when dataset-level permissions are stripped. You can always manage or rollback resources.
- **Time Travel:** BigQuery retains data for 7 days after deletion. This is your final safety net for accidental deletions.
- **Automated Validation:** The decommissioning logic is verified by `test_bq_decommissioner.py`. Always run the test suite after making modifications to the execution logic.
