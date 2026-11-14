import copy,json,sys,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from identity import normalize_pci,pci_key,identify_adapters,nvidia_records
from fleet import Fleet
from gputaskman.collector import Snapshot
from gputaskman.dxgi import Adapter
from gputaskman.nvml import NvDevice


def adapter(index=0,uuid=None):
    pci=f'0000:{index+1:02x}:00.0'
    return Adapter(luid=pci_key(pci),name='NVIDIA Identical Model',vendor_id=0x10de,dedicated_vram=16<<30,shared_system=0,software=False)

def records(count):
    return [{'pci_bus_id':f'0000:{i+1:02x}:00.0','uuid':f'GPU-{i:08x}-0000-0000-0000-000000000000','serial':None,'nvml_index':i} for i in range(count)]

class IdentityTests(unittest.TestCase):
    def test_normalize_keeps_pci_domains(self):
        self.assertEqual(normalize_pci(b'00000000:41:00.0'),'0000:41:00.0')
        self.assertNotEqual(pci_key('0000:41:00.0'),pci_key('0001:41:00.0'))
        self.assertIsNone(normalize_pci('not a pci address'))
    def test_identical_models_4_8_16_distinct(self):
        for count in [4,8,16]:
            identities=identify_adapters([adapter(i) for i in range(count)],records(count),[])
            self.assertEqual(len({x['id'] for x in identities}),count)
            self.assertTrue(all(x['uuid'] and x['pci_bus_id'] for x in identities))
    def test_reordered_nvml_indices_do_not_change_identity(self):
        adapters=[adapter(i) for i in range(4)]
        before=identify_adapters(adapters,records(4),[])
        shuffled=list(reversed(records(4)))
        for i,item in enumerate(shuffled):item['nvml_index']=i
        after=identify_adapters(adapters,shuffled,[])
        self.assertEqual([x['id'] for x in before],[x['id'] for x in after])
        self.assertEqual(after[0]['nvml_index'],3)
    def test_uuid_unavailable_or_duplicate_falls_back_to_pci(self):
        r=records(2);r[0]['uuid']=None
        identity=identify_adapters([adapter(0)],r,[])[0]
        self.assertEqual(identity['id'],'pci:0000:01:00.0')
        r=records(2);r[1]['uuid']=r[0]['uuid']
        identities=identify_adapters([adapter(0),adapter(1)],r,[])
        self.assertEqual(len({x['id'] for x in identities}),2)
        self.assertTrue(all(x['id'].startswith('pci:') for x in identities))
    def test_serial_not_supported_does_not_hide_card(self):
        class API:
            nvmlInit=staticmethod(lambda:None);nvmlShutdown=staticmethod(lambda:None)
            nvmlDeviceGetCount=staticmethod(lambda:4)
            nvmlDeviceGetHandleByIndex=staticmethod(lambda i:i)
            nvmlDeviceGetPciInfo=staticmethod(lambda i:SimpleNamespace(busId=f'00000000:{i+1:02x}:00.0'.encode()))
            nvmlDeviceGetUUID=staticmethod(lambda i:f'GPU-{i:08x}-0000-0000-0000-000000000000'.encode())
            @staticmethod
            def nvmlDeviceGetSerial(i):raise RuntimeError('Not supported')
        result=nvidia_records(API)
        self.assertEqual(len(result),4);self.assertTrue(all(r['serial'] is None for r in result))
    def test_no_name_based_identity_guess(self):
        item=identify_adapters([adapter(0)],[],[])[0]
        self.assertEqual(item['identity_source'],'session only')
        self.assertIsNone(item['uuid']);self.assertIsNone(item['pci_bus_id'])

class FakeCollector:
    def __init__(self,index,adapters,**kwargs):
        self.adapter=adapters[index];self.scan_budget=kwargs['scan_budget'];self.closed=False
    def sample(self):
        return Snapshot(taken=time.time(),adapter=self.adapter,adapters=[],
            nv=NvDevice(index=0,name='NVIDIA Identical Model',util_gpu=37),driver='',cuda='',
            vram_total=16<<30,vram_used=self.adapter.luid,shared_used=None,procs=[],backend='nvml')
    def close(self):self.closed=True

class FleetTests(unittest.TestCase):
    def make_fleet(self,count=4,factory=FakeCollector):
        self.adapters=[adapter(i) for i in range(count)];self.records=records(count)
        return Fleet(lambda:self.adapters,factory,lambda adapters:identify_adapters(adapters,self.records,[]))
    def test_failure_of_one_gpu_does_not_stop_others(self):
        def factory(index,**kwargs):
            if index==2:raise RuntimeError('GPU lost')
            return FakeCollector(index,**kwargs)
        fleet=self.make_fleet(8,factory);fleet.sync();snapshots,errors=fleet.sample()
        self.assertEqual(len(snapshots),7);self.assertEqual(len(errors),1)
        self.assertEqual(len({s['gpu_id'] for s in snapshots}),7)
        self.assertTrue(all(abs(c.scan_budget-.15/8)<1e-10 for c in fleet.collectors.values()))
        fleet.close()
    def test_index_reorder_retains_collectors_and_correct_values(self):
        fleet=self.make_fleet();fleet.sync();old=dict(fleet.collectors)
        self.adapters.reverse();fleet.sync();snapshots,errors=fleet.sample()
        self.assertFalse(errors)
        for data in snapshots:
            self.assertEqual(data['vram_used'],pci_key(data['gpu_identity']['pci_bus_id']))
            self.assertIs(fleet.collectors[data['gpu_id']],old[data['gpu_id']])
        fleet.close()
    def test_removed_device_is_offline_and_returning_device_recovers(self):
        fleet=self.make_fleet();fleet.sync();old=list(fleet.known)[1];previous=fleet.collectors[old]
        removed=self.adapters.pop(1);fleet.sync();snapshots,errors=fleet.sample()
        self.assertEqual(len(snapshots),3);self.assertFalse(fleet.known[old]['present']);self.assertTrue(previous.closed)
        self.adapters.append(removed);fleet.sync();snapshots,errors=fleet.sample()
        self.assertEqual(len(snapshots),4);self.assertFalse(errors);self.assertTrue(fleet.known[old]['present'])
        fleet.close()
    def test_uuid_survives_pci_move_but_collector_rebinds(self):
        fleet=self.make_fleet(1);fleet.sync();key=next(iter(fleet.known));old=fleet.collectors[key]
        self.records[0]['pci_bus_id']='0001:41:00.0';self.adapters[0].luid=pci_key('0001:41:00.0')
        fleet.sync()
        self.assertTrue(old.closed);self.assertIn(key,fleet.collectors);self.assertIsNot(old,fleet.collectors[key]);fleet.close()



class AdditionalFleetTests(unittest.TestCase):
    def test_replacement_card_in_same_slot_is_a_new_identity(self):
        adapters=[adapter(0)];r=records(1)
        fleet=Fleet(lambda:adapters,FakeCollector,lambda a:identify_adapters(a,r,[]))
        fleet.sync();old=next(iter(fleet.known));c=fleet.collectors[old]
        r[0]['uuid']='GPU-ffffffff-0000-0000-0000-000000000000';fleet.sync()
        self.assertFalse(fleet.known[old]['present']);self.assertTrue(c.closed)
        self.assertEqual(len(fleet.known),2);self.assertNotIn(old,fleet.collectors);fleet.close()
    def test_sample_failure_is_isolated_and_retried(self):
        class Broken(FakeCollector):
            def sample(self):raise RuntimeError('GPU temporarily lost')
        adapters=[adapter(i) for i in range(4)];r=records(4)
        broken=True
        def factory(index,**kwargs):return (Broken if index==1 and broken else FakeCollector)(index,**kwargs)
        fleet=Fleet(lambda:adapters,factory,lambda a:identify_adapters(a,r,[]))
        fleet.sync();snapshots,errors=fleet.sample()
        self.assertEqual(len(snapshots),3);self.assertEqual(len(errors),1)
        broken=False;fleet.sync();snapshots,errors=fleet.sample()
        self.assertEqual(len(snapshots),4);self.assertFalse(errors);fleet.close()
    def test_telemetry_binding_uses_full_pci_not_nvml_index_or_name(self):
        from identity import bind_nvml_telemetry
        class API:
            nvmlDeviceGetPciInfo=staticmethod(lambda h:SimpleNamespace(busId=h.encode()))
        collector=SimpleNamespace(nvml=SimpleNamespace(handles=[(0,'0000:41:00.0'),(1,'0001:41:00.0')]))
        bind_nvml_telemetry(collector,{'pci_bus_id':'0001:41:00.0'},API)
        self.assertEqual(collector.nvml.handles,[(1,'0001:41:00.0')])

class RefreshWorkerTests(unittest.TestCase):
    def test_only_finite_bounded_intervals_are_accepted(self):
        from worker import RefreshControl
        control=RefreshControl(1)
        for command in ['interval 0.5','interval 5','interval 0.25','interval 60']:
            self.assertTrue(control.apply(command))
        for command in ['interval nan','interval inf','interval 0','interval -1','interval 61','interval bad','interval 1 extra','exec anything']:
            previous=control.interval;self.assertFalse(control.apply(command));self.assertEqual(control.interval,previous)

if __name__=='__main__':unittest.main()
