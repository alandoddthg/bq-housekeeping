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
- **Observation:** Monitor for failed jobs, broken dashboards, or user tickets.
- **Validation:** (Optional) Use `INFORMATION_SCHEMA.JOBS_BY_PROJECT` to confirm zero read attempts during this period.

### Phase D: Final Deletion (Automated)
After the monitoring period (default 7 days), use the `--phase-d` flag to permanently delete the datasets. The script will only delete datasets that have exceeded the retention threshold.

**Run a deletion dry-run:**
```bash
python3 bq_data_decommissioner.py --phase-d --dry-run
```

**Execute final deletion:**
```bash
python3 bq_data_decommissioner.py --phase-d
```

**Customise retention period (e.g., 14 days):**
```bash
python3 bq_data_decommissioner.py --phase-d --retention-days 14
```

---

## 3. Operational Commands

### Listing Available Tranches
View the exact tranche names from your updated audit file:
```bash
python3 bq_data_decommissioner.py --list-tranches
```

### Performing a Dry Run (Highly Recommended)
Verify exactly which datasets will be affected without making any changes:
```bash
# Supports sub-tranches (e.g., 1.1, 2.1)
python3 bq_data_decommissioner.py --tranche 1.1 --dry-run
```

### Initiating the Scream Test
Execute the actual access restriction and cloud backup:
```bash
python3 bq_data_decommissioner.py --tranche 1.1
```

### Emergency Rollback (Automated)
If access needs to be restored, use the `bq_restore_access.py` tool. It automatically handles downloading backups from GCS and reapplying them.

**Restore a specific dataset:**
```bash
python3 bq_restore_access.py --dataset project:dataset
```

**Restore an entire tranche:**
```bash
python3 bq_restore_access.py --tranche 1.1
```

**Restore everything in the current state file:**
```bash
python3 bq_restore_access.py --all
```

**Verify before restoring:**
```bash
python3 bq_restore_access.py --tranche 1.1 --dry-run
```

---

## 4. Safety Nets & Best Practices
- **Org-Level Access:** As an Org Admin, you retain access even when dataset-level permissions are stripped. You can always manage or rollback resources.
- **Sub-Tranche Support:** The script supports decimal tranche identifiers (e.g., `1.1`) to match your refined audit groupings.
- **Time Travel:** BigQuery retains data for 7 days after deletion. This is your final safety net.
- **IaC Alignment:** For FAST-managed projects, ensure the final deletion is mirrored in the relevant Terraform/YAML configuration to prevent resources from being recreated.
- **Automated Validation:** The decommissioning logic is verified by `test_bq_decommissioner.py`. Always run the test suite after making modifications to the execution logic.
