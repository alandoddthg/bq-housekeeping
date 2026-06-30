# BigQuery Housekeeping & Decommissioning

This repository contains tools and processes for auditing, managing, and decommissioning stale BigQuery datasets across the THG enterprise estate.

## Overview
The suite provides a structured approach to "Defensible Deletion," ensuring that data is only removed after a rigorous verification period (the "Scream Test") while maintaining full auditability and rollback capability.

## Key Components
*   **Audit Scripts**: `bq_stale_audit.py`, `bq_deep_history_audit.py`, and `bq_comprehensive_tranche_audit.py` for identifying targets.
*   **Execution Engine**: `bq_data_decommissioner.py` for performing backups and initiating Scream Tests.
*   **Recovery Tool**: `bq_restore_access.py` for automated emergency restoration of dataset access.
*   **Test Suite**: `test_bq_decommissioner.py` for validating script logic.

## Getting Started

### Prerequisites
*   Python 3.8+
*   `gcloud` and `bq` CLI tools authenticated.
*   Python dependencies:
    ```bash
    pip install pandas google-cloud-bigquery openpyxl xlsxwriter
    ```

### Usage
1.  **Auditing**: Run the audit scripts to generate targets in Excel format.
2.  **Scream Test**: Initiate access restriction for a specific tranche:
    ```bash
    python3 bq_data_decommissioner.py --tranche 1.1
    ```
3.  **Restoration**: Rollback access if needed:
    ```bash
    python3 bq_restore_access.py --dataset project:dataset
    ```
4.  **Final Deletion**: Execute Phase D after the monitoring period (default 7 days):
    ```bash
    python3 bq_data_decommissioner.py --phase-d
    ```

## Documentation
Detailed process flows and operational commands are documented in [PROCESS.md](PROCESS.md).
Presentation materials for stakeholders are available in `BigQuery_Housekeeping_Process.pptx`.
