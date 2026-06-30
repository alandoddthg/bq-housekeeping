import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import os
import pandas as pd
import bq_data_decommissioner as bq_dec

class TestBQDecommissioner(unittest.TestCase):

    @patch('bq_data_decommissioner.subprocess.run')
    def test_run_command_success(self, mock_run):
        mock_run.return_value.stdout = "Success"
        result = bq_dec.run_command("ls")
        self.assertEqual(result, "Success")

    @patch('bq_data_decommissioner.subprocess.run')
    def test_run_command_dry_run(self, mock_run):
        result = bq_dec.run_command("ls", dry_run=True)
        self.assertEqual(result, "DRY_RUN_SUCCESS")
        mock_run.assert_not_called()

    @patch('bq_data_decommissioner.run_command')
    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_backup_dataset_local(self, mock_file, mock_makedirs, mock_exists, mock_run_cmd):
        mock_exists.return_value = False
        mock_run_cmd.return_value = '{"access": []}'
        
        path = bq_dec.backup_dataset("project", "dataset")
        
        self.assertEqual(path, os.path.join("backups", "project_dataset_backup.json"))
        mock_makedirs.assert_called_with("backups")
        mock_file.assert_called_with(path, "w")

    @patch('bq_data_decommissioner.run_command')
    @patch('builtins.open', new_callable=mock_open, read_data='{"access": [{"role": "OWNER", "userByEmail": "admin@thg.com"}, {"role": "READER", "userByEmail": "user@thg.com"}]}')
    @patch('os.remove')
    def test_apply_scream_test_logic(self, mock_remove, mock_file, mock_run_cmd):
        # We need to mock the write calls within apply_scream_test as well
        # The mock_open will handle both read and write calls to open()
        
        mock_run_cmd.return_value = "Success"
        
        success = bq_dec.apply_scream_test("project", "dataset", "backups/project_dataset_backup.json")
        
        self.assertTrue(success)
        # Check if the update file was written with only OWNER access
        # Find the call where update_project_dataset.json was opened for writing
        write_call = [call for call in mock_file.mock_calls if 'update_project_dataset.json' in str(call) and "'w'" in str(call)]
        self.assertTrue(len(write_call) > 0)
        
        # Verify bq update was called
        update_cmd_call = [call for call in mock_run_cmd.mock_calls if "bq update --source update_project_dataset.json" in str(call)]
        self.assertTrue(len(update_cmd_call) > 0)

    @patch('bq_data_decommissioner.pd.read_excel')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='{}')
    @patch('bq_data_decommissioner.backup_dataset')
    @patch('bq_data_decommissioner.apply_scream_test')
    @patch('bq_data_decommissioner.sync_workspace')
    def test_main_tranche_processing(self, mock_sync, mock_scream, mock_backup, mock_file, mock_exists, mock_pd):
        mock_exists.side_effect = lambda x: x in [bq_dec.EXCEL_FILE, bq_dec.STATE_FILE]
        
        # Mocking DataFrame
        df = pd.DataFrame({
            'Project': ['p1'],
            'Dataset': ['d1'],
            'Tranche': ['Tranche 1: Abandoned'],
            'Defensible Deletion Status': ['CONFIRMED'],
            'Size (GB)': [10],
            'Monthly Cost ($)': [0.2]
        })
        mock_pd.return_value = df
        mock_backup.return_value = "path/to/backup"
        mock_scream.return_value = True
        
        with patch('argparse.ArgumentParser.parse_args', return_value=MagicMock(tranche='1', dry_run=False, phase_d=False, list_tranches=False, backup_bucket='bucket')):
            bq_dec.main()
            
        mock_backup.assert_called_once()
        mock_scream.assert_called_once()
        mock_sync.assert_called_once()

if __name__ == '__main__':
    unittest.main()
