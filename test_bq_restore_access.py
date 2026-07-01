import unittest
from unittest.mock import patch, mock_open
import bq_restore_access as bq_restore


class TestBQRestoreAccess(unittest.TestCase):

    @patch('bq_restore_access.run_command')
    @patch('os.path.exists')
    @patch('os.remove')
    def test_restore_dataset_gcs_empty_stdout_still_succeeds(self, mock_remove, mock_exists, mock_run_cmd):
        # gsutil cp writes its success message to stderr, so stdout is "" on a successful
        # download - restore_dataset must not treat that as a failed download.
        mock_exists.return_value = True
        mock_run_cmd.side_effect = ["", "Success"]

        info = {"project": "p1", "dataset": "d1", "backup_path": "gs://bucket/backups/p1_d1_backup.json"}
        result = bq_restore.restore_dataset("p1:d1", info)

        self.assertTrue(result)
        update_calls = [c for c in mock_run_cmd.mock_calls if "bq update --source" in str(c)]
        self.assertTrue(len(update_calls) > 0)

    @patch('bq_restore_access.run_command')
    def test_restore_dataset_real_download_failure_aborts(self, mock_run_cmd):
        mock_run_cmd.return_value = None

        info = {"project": "p1", "dataset": "d1", "backup_path": "gs://bucket/backups/p1_d1_backup.json"}
        result = bq_restore.restore_dataset("p1:d1", info)

        self.assertFalse(result)
        update_calls = [c for c in mock_run_cmd.mock_calls if "bq update --source" in str(c)]
        self.assertEqual(len(update_calls), 0)


if __name__ == '__main__':
    unittest.main()
