import json,os,sys,time,unittest
from unittest.mock import patch
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer,Qt
from gui import Window,Plot,demo_message,memory,percent,number,STYLE
app=QApplication.instance() or QApplication([])
app.setStyle("Fusion");app.setStyleSheet(STYLE)

class GuiTests(unittest.TestCase):
    def setUp(self):
        self.window=Window(demo=True);self.window.demo_timer.stop();self.window.show();app.processEvents()
    def tearDown(self):
        self.window.close();app.processEvents()
    def test_diagnostics_preserves_scroll_during_live_updates(self):
        w=self.window;w.resize(1024,768);w.navigate(3)
        frame=demo_message(time.time(),0)
        frame['snapshot']['counter_status']='Diagnostic note. '*200
        w.receive(frame);app.processEvents()
        bar=w.diagnostics.verticalScrollBar();self.assertGreater(bar.maximum(),0)
        bar.setValue(bar.maximum()//2);position=bar.value()
        for index in range(3):
            frame['sample_ms']=index+10
            w.receive(frame);app.processEvents()
            self.assertEqual(bar.value(),position)
        self.assertIn('12',w.diagnostics.toPlainText())

    def test_unknown_and_zero_stay_distinct(self):
        self.assertEqual(memory(None),'n/a');self.assertEqual(memory(0),'0 B')
        self.assertIsNone(percent(100,None));self.assertEqual(percent(0,100),0)
        self.assertEqual(number(None,'%'),'n/a');self.assertEqual(number(0,'%'),'0%')
        message=demo_message(time.time(),0);message['snapshot']['device']['util_gpu']=None
        message['snapshot']['vram_total']=None;message['snapshot']['memory_note']='Client sum / PCI estimate'
        self.window.receive(message)
        self.assertEqual(self.window.cards['gpu'].value.text(),'n/a')
        self.assertEqual(self.window.memory_plot.values[-1][1],message['snapshot']['vram_used'])
        self.assertEqual(self.window.memory_plot.unit,'bytes')
        self.assertIn('visible-client sum',self.window.cards['vram'].note.text())
    def test_memory_fallback_and_single_chart_preserve_absolute_usage(self):
        message=demo_message(time.time(),0);message['snapshot']['vram_total']=None
        self.window.receive(message);self.window.focus_metric(1)
        self.assertEqual(self.window.single_plot.unit,'bytes')
        self.assertIsNone(self.window.single_plot.maximum)
        self.assertEqual(self.window.single_plot.values[-1][1],message['snapshot']['vram_used'])
        self.assertIn('GB',self.window.single_plot.format_value(message['snapshot']['vram_used']))
        message['snapshot']['vram_used']=0;self.window.receive(message)
        self.assertEqual(self.window.single_plot.values[-1][1],0)
        message['snapshot']['vram_used']=None;self.window.receive(message)
        self.assertIsNone(self.window.single_plot.values[-1][1])
        self.assertEqual(self.window.single_plot.format_value(None),'n/a')
        message['snapshot']['vram_total']=16<<30;message['snapshot']['vram_used']=8<<30
        self.window.receive(message)
        self.assertEqual(self.window.single_plot.unit,'%')
        self.assertEqual(self.window.single_plot.values[-1][1],50)
    def test_navigation_and_metric_focus(self):
        self.window.focus_metric(2);self.assertEqual(self.window.pages.currentIndex(),1)
        self.assertEqual(self.window.single_plot.title,'Temperature')
        self.assertEqual(len(self.window.single_plot.values),120)
        self.window.metric_choice.setCurrentIndex(0);self.assertEqual(self.window.performance_stack.currentIndex(),0)
    def test_process_sort_filter_and_details(self):
        self.window.navigate(2);self.window.table.sortItems(3,Qt.SortOrder.DescendingOrder)
        self.window.table.selectRow(0);self.window.process_selected()
        self.assertIn('llama-server',self.window.details.toPlainText())
        self.window.search.setText('llama')
        self.assertEqual(sum(not self.window.table.isRowHidden(i) for i in range(3)),1)
        # A reused PID with a different start time cannot inherit the selected details.
        message=demo_message(time.time(),1);message['snapshot']['processes'][0]['started_at']=2
        self.window.receive(message);self.window.process_selected()
        self.assertNotIn('"started_at": 1',self.window.details.toPlainText())
    def test_pause_and_time_window(self):
        count=len(self.window.main_plot.values);self.window.pause_button.click();self.window.demo_tick()
        self.assertTrue(self.window.paused);self.assertEqual(len(self.window.main_plot.values),count)
        self.window.pause_button.click();self.assertFalse(self.window.paused)
        self.assertTrue(all(len(p.values)<=300 for p in self.window.plots))
    def test_live_worker(self):
        # QProcess drives an actual bundled collector, not demo data.
        self.window.close()
        worker=str(Path(__file__).parent/'dist/gputaskman-collector/gputaskman-collector')
        live=Window(worker=worker,standard_access=True);live.show()
        deadline=time.monotonic()+8
        while time.monotonic()<deadline and not live.last_received:
            app.processEvents();time.sleep(.02)
        self.assertTrue(live.last_frame.get('protocol')==2)
        self.assertTrue(live.last is not None or 'system' in live.last_frame)
        self.assertNotIn('DEMO',live.subtitle.text())
        self.assertTrue(live.last_received)
        live.close();app.processEvents()
        self.assertIsNone(live.proc)
    def test_cancelled_authentication_falls_back_without_elevating_window(self):
        self.window.demo=False;self.window.elevated=True
        with patch('gui.QTimer.singleShot') as schedule:
            self.window.worker_finished(126,None)
            self.assertFalse(self.window.elevated)
            self.assertIn('not granted',self.window.notice.text())
            self.assertEqual(schedule.call_args[0][0],0)
        self.window.demo=True
    def test_resume_creates_a_history_gap(self):
        self.window.pause_button.click();self.window.pause_button.click()
        self.window.receive(demo_message(time.time(),42))
        self.assertIsNone(self.window.main_plot.values[-2][1])
        self.assertIsNotNone(self.window.main_plot.values[-1][1])
    def test_small_window_and_render(self):
        self.window.resize(980,700);app.processEvents()
        self.assertTrue(self.window.grab().save('/tmp/gputaskman-qt-small.png'))
        for index in [1,2,3]:
            self.window.navigate(index);app.processEvents()
            self.assertTrue(self.window.grab().save(f'/tmp/gputaskman-qt-page-{index}.png'))



class MultiGpuGuiTests(unittest.TestCase):
    def setUp(self):
        from gui import demo_fleet_message
        self.frame=demo_fleet_message(time.time(),20,4)
        self.window=Window(demo=True);self.window.demo_timer.stop();self.window.receive(self.frame);self.window.navigate(4)
    def tearDown(self):self.window.close();app.processEvents()
    def test_switching_preserves_history_without_restarting_or_authenticating(self):
        old=self.window.gpu.currentData();count=len(self.window.main_plot.values)
        other=self.frame['gpus'][1]['id']
        with patch.object(self.window,'restart') as restart:
            self.window.gpu.setCurrentIndex(self.window.gpu.findData(other))
            self.assertEqual(self.window.last['gpu_id'],other)
            self.assertEqual(self.window.main_plot.values[-1][1],self.frame['snapshots'][1]['device']['util_gpu'])
            self.window.gpu.setCurrentIndex(self.window.gpu.findData(old))
            self.assertEqual(len(self.window.main_plot.values),count)
            restart.assert_not_called()
    def test_four_eight_sixteen_identical_names_are_distinct(self):
        from gui import demo_fleet_message
        for count in [4,8,16]:
            self.window.receive(demo_fleet_message(time.time(),30,count))
            active=[r for r in self.window.device_inventory.values() if r.get('present',True)]
            self.assertEqual(len(active),count)
            self.assertEqual(len({r['id'] for r in active}),count)
            labels=[self.window.gpu.itemText(i) for i in range(self.window.gpu.count())]
            self.assertEqual(len(set(labels)),len(labels))
            self.assertEqual(self.window.pages.currentIndex(),4)
    def test_reordering_indices_keeps_selection_and_history(self):
        key=self.frame['gpus'][2]['id'];self.window.open_gpu(key)
        count=len(self.window.main_plot.values)
        frame=json.loads(json.dumps(self.frame));frame['gpus'].reverse()
        for i,r in enumerate(frame['gpus']):r['index']=i
        self.window.receive(frame)
        self.assertEqual(self.window.gpu.currentData(),key)
        self.assertEqual(self.window.last['gpu_id'],key)
        self.assertEqual(len(self.window.main_plot.values),count+1)
    def test_one_device_offline_does_not_mix_other_readings(self):
        key=self.frame['gpus'][1]['id'];self.window.open_gpu(key)
        frame=json.loads(json.dumps(self.frame));frame['gpus'][1]['present']=False
        frame['snapshots']=[r for r in frame['snapshots'] if r['gpu_id']!=key]
        frame['errors']=[{'gpu_id':key,'error':'GPU lost'}]
        self.window.receive(frame)
        self.assertEqual(self.window.gpu.currentData(),key)
        self.assertEqual(self.window.cards['gpu'].value.text(),'n/a')
        self.assertIsNone(self.window.main_plot.values[-1][1])
        self.window.open_gpu(frame['snapshots'][0]['gpu_id'])
        self.assertNotEqual(self.window.cards['gpu'].value.text(),'n/a')
    def test_serial_and_uuid_are_visible_in_diagnostics(self):
        self.window.navigate(3)
        text=self.window.diagnostics.toPlainText()
        self.assertIn('GPU UUID',text);self.assertIn('PCI bus address',text)
        self.assertIn(self.frame['gpus'][0]['uuid'],text)

class RefreshGuiTests(unittest.TestCase):
    def test_rate_changes_send_control_without_restart_and_preserve_pause(self):
        window=Window(demo=True);window.demo_timer.stop()
        fake=unittest.mock.Mock()
        from gui import QProcess
        fake.state.return_value=QProcess.ProcessState.Running
        window.proc=fake
        history=list(window.main_plot.values)
        with patch.object(window,'restart') as restart:
            window.rate.setCurrentIndex(3)
            self.assertIn(unittest.mock.call(b'interval 5\n'),fake.write.call_args_list)
            window.paused=True;window.rate.setCurrentIndex(0)
            self.assertEqual(fake.write.call_args_list[-2:], [unittest.mock.call(b'interval 0.5\n'),unittest.mock.call(b'pause\n')])
            self.assertEqual(list(window.main_plot.values),history)
            restart.assert_not_called()
        window.proc=None;window.close();app.processEvents()

if __name__=='__main__':unittest.main()

class RuntimeGaugeTests(unittest.TestCase):
    def test_server_metrics_preserve_zero_and_unknown(self):
        w=Window(demo=True);w.demo_timer.stop()
        try:
            frame=demo_message(time.time(),1)
            frame['snapshot']['processes'][0]['llm']={'server':{'requests_running':0,'requests_waiting':None,'kv_cache_usage':0.25}}
            w.receive(frame);w.navigate(2)
            for i in range(w.table.rowCount()):
                if w.table.item(i,1).text()=='llama-server':w.table.selectRow(i);break
            w.process_selected();text=w.details.toPlainText()
            self.assertIn('Running requests: 0',text);self.assertIn('Waiting requests: n/a',text)
            self.assertIn('KV-cache pool usage: 25%',text);self.assertIn('not per GPU',text)
        finally:w.close()
