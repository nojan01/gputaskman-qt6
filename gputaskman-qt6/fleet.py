"""MIT: isolate per-GPU collectors and preserve identity across index reordering."""
import time
from identity import identify_adapters,bind_nvml_telemetry

class Fleet:
    def __init__(self,discover,factory,identity=identify_adapters,budget=.15):
        self.discover=discover;self.factory=factory;self.identity=identity;self.budget=budget
        self.known={};self.collectors={};self.errors={}
    def sync(self):
        adapters=self.discover()
        identities=self.identity(adapters)
        active={r['id'] for r in identities}
        for key,record in self.known.items():
            record['present']=key in active
            if key not in active:
                collector=self.collectors.pop(key,None)
                if collector:
                    try:collector.close()
                    except Exception:pass
                self.errors[key]='Device is no longer detected. Its history is retained.'
        budget=None if self.budget is None else self.budget/max(1,len(identities))
        for record in identities:
            key=record['id']
            previous=self.known.get(key)
            if previous and previous.get('pci_bus_id')!=record.get('pci_bus_id'):
                collector=self.collectors.pop(key,None)
                if collector:
                    try:collector.close()
                    except Exception:pass
            self.known[key]=record
            if key not in self.collectors:
                try:
                    self.collectors[key]=self.factory(record['index'],adapters=adapters,scan_budget=budget,host=False)
                    if record.get('vendor')=='NVIDIA':bind_nvml_telemetry(self.collectors[key],record)
                    self.errors.pop(key,None)
                except Exception as error:self.errors[key]=f'{type(error).__name__}: {error}'
            else:self.collectors[key].scan_budget=budget
        return list(self.known.values())
    def sample(self,system=None,system_error=None):
        from gputaskman.report import to_json_dict
        snapshots=[];errors=[]
        for key,identity in self.known.items():
            collector=self.collectors.get(key)
            if not identity.get('present') or collector is None:
                errors.append({'gpu_id':key,'error':self.errors.get(key,'Device unavailable')});continue
            try:
                snap=collector.sample()
                for row in snap.procs:
                    hp=system.proc(row.pid,row.detail.create_time) if system and not row.host else None
                    row.ram=hp.rss if hp else None;row.cpu=hp.cpu_pct if hp else None
                data=to_json_dict(snap,system,system_error)
                for row,item in zip(snap.procs,data['processes']):
                    item['ram_bytes'],item['cpu_pct']=row.ram,row.cpu
                data['gpu_id']=key;data['gpu_identity']=dict(identity)
                if identity.get('vendor')=='NVIDIA' and data.get('device') is None:
                    reason='NVIDIA device telemetry unavailable; process counters may still be readable.'
                    data['counter_status']=' '.join(filter(None,[data.get('counter_status'),reason]))
                    errors.append({'gpu_id':key,'error':reason})
                if getattr(getattr(collector,'nvml',None),'needs_reset',False):
                    try:collector.close()
                    except Exception:pass
                    self.collectors.pop(key,None)
                snapshots.append(data)
            except Exception as error:
                reason=f'{type(error).__name__}: {error}'
                errors.append({'gpu_id':key,'error':reason});self.errors[key]=reason
                self.collectors.pop(key,None)
                try:collector.close()
                except Exception:pass
        return snapshots,errors
    def close(self):
        for collector in self.collectors.values():
            try:collector.close()
            except Exception:pass
        self.collectors.clear()
