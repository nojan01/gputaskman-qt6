# SPDX-License-Identifier: MIT
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QFileDialog,QMessageBox
from gui import Window,demo_fleet_message
app=QApplication.instance() or QApplication([])

class RecordingTests(unittest.TestCase):
    def test_roundtrip_and_transport(self):
        w=Window(demo=True);w.demo_timer.stop()
        try:
            with tempfile.TemporaryDirectory() as folder:
                path=str(Path(folder)/'session.jsonl')
                with patch.object(QFileDialog,'getSaveFileName',return_value=(path,'')):w.toggle_recording()
                start=time.time()
                for index in range(3):w.receive(demo_fleet_message(start+index,index,4))
                w.stop_recording()
                lines=Path(path).read_text().splitlines()
                self.assertEqual(len(lines),4)
                with patch.object(QFileDialog,'getOpenFileName',return_value=(path,'')):w.open_recording()
                w.replay_timer.stop()
                self.assertEqual(len(w.device_inventory),4)
                self.assertEqual(w.last_frame['taken'],start)
                w.pause(True);w.replay_step();self.assertEqual(w.replay_index,1)
                w.pause(False);w.replay_timer.stop();self.assertEqual(w.last_frame['taken'],start+1)
                w.replay_step();self.assertIn('finished',w.live.text())
                w.rewind_recording();w.replay_timer.stop();self.assertEqual(w.replay_index,1)
                w.return_live();w.demo_timer.stop();self.assertIsNone(w.replay_frames)
                self.assertTrue(w.record_button.isEnabled())
        finally:w.close()
    def test_reject_invalid_file_without_stopping_live(self):
        w=Window(demo=True);w.demo_timer.stop()
        try:
            with tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'invalid.jsonl';path.write_text('{}\n')
                with patch.object(QFileDialog,'getOpenFileName',return_value=(str(path),'')),patch.object(QMessageBox,'warning') as warning:
                    w.open_recording();warning.assert_called_once()
                self.assertIsNone(w.replay_frames)
        finally:w.close()

    def test_duration_expires_while_paused_and_keeps_live_session(self):
        w=Window(demo=True);w.demo_timer.stop()
        try:
            with tempfile.TemporaryDirectory() as folder:
                path=str(Path(folder)/'timed.jsonl');w.record_duration.setValue(1)
                with patch.object(QFileDialog,'getSaveFileName',return_value=(path,'')),patch('gui.time.monotonic',return_value=100):w.toggle_recording()
                self.assertEqual(w.record_deadline,160)
                self.assertFalse(w.record_duration.isEnabled())
                w.receive(demo_fleet_message(time.time(),1,4));w.pause(True)
                with patch('gui.time.monotonic',return_value=159):w.check_recording_duration()
                self.assertIsNotNone(w.record_file)
                with patch('gui.time.monotonic',return_value=160):w.check_recording_duration()
                self.assertIsNone(w.record_file);self.assertTrue(w.record_duration.isEnabled())
                self.assertIn('duration reached',w.record_status.text())
                self.assertEqual(len(Path(path).read_text().splitlines()),2)
                self.assertEqual(len(w.device_inventory),4)
        finally:w.close()
    def test_unlimited_and_manual_stop_cancel_deadline(self):
        w=Window(demo=True);w.demo_timer.stop()
        try:
            with tempfile.TemporaryDirectory() as folder:
                with patch.object(QFileDialog,'getSaveFileName',return_value=(str(Path(folder)/'unlimited.jsonl'),'')):w.toggle_recording()
                self.assertIsNone(w.record_deadline);self.assertFalse(w.record_timer.isActive())
                w.toggle_recording();self.assertIsNone(w.record_file)
        finally:w.close()
