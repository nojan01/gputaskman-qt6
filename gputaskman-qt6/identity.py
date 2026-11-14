"""MIT: PCI-verified physical GPU identities; never match hardware by model name."""
from pathlib import Path
import re


def normalize_pci(value):
    if isinstance(value,bytes):value=value.decode(errors='replace')
    match=re.fullmatch(r'([0-9a-fA-F]{4,8}):([0-9a-fA-F]{2}):([0-9a-fA-F]{2})\.([0-7])',str(value).strip())
    if not match:return None
    domain,bus,device,function=(int(v,16) for v in match.groups())
    if device>31:return None
    return f'{domain:04x}:{bus:02x}:{device:02x}.{function:x}'


def pci_key(value):
    pci=normalize_pci(value)
    return int(re.sub('[^0-9a-f]','',pci),16) if pci else None


def text(value):
    if isinstance(value,bytes):value=value.decode(errors='replace')
    return str(value).strip() if value is not None else None


def nvidia_records(api=None):
    """Identity-only NVML query; unsupported serial/UUID do not hide the device."""
    if api is None:
        try:import pynvml as api
        except ImportError:return []
    try:api.nvmlInit()
    except Exception:return []
    records=[]
    try:
        count=api.nvmlDeviceGetCount()
        for index in range(count):
            try:
                handle=api.nvmlDeviceGetHandleByIndex(index)
                pci=normalize_pci(api.nvmlDeviceGetPciInfo(handle).busId)
                if not pci:continue
                record={'pci_bus_id':pci,'nvml_index':index,'uuid':None,'serial':None}
                for field,method in [('uuid','nvmlDeviceGetUUID'),('serial','nvmlDeviceGetSerial')]:
                    try:record[field]=text(getattr(api,method)(handle))
                    except Exception:pass
                records.append(record)
            except Exception:continue
    except Exception:pass
    finally:
        try:api.nvmlShutdown()
        except Exception:pass
    return records


def sysfs_records(root='/sys/bus/pci/devices'):
    records=[]
    try:paths=list(Path(root).iterdir())
    except OSError:return records
    for path in paths:
        pci=normalize_pci(path.name)
        if pci:
            try:vendor=int((path/'vendor').read_text().strip(),16)
            except (OSError,ValueError):continue
            records.append({'pci_bus_id':pci,'vendor_id':vendor})
    return records


def identify_adapters(adapters,nvidia=None,sysfs=None):
    nvidia=nvidia_records() if nvidia is None else nvidia
    sysfs=sysfs_records() if sysfs is None else sysfs
    uuid_counts={}
    for r in nvidia:
        if r.get('uuid'):uuid_counts[r['uuid']]=uuid_counts.get(r['uuid'],0)+1
    result=[]
    for index,adapter in enumerate(adapters):
        matches=[r for r in nvidia if pci_key(r.get('pci_bus_id'))==adapter.luid] if adapter.vendor_id==0x10de else []
        record=matches[0] if len(matches)==1 else {}
        pci=record.get('pci_bus_id')
        if not pci and adapter.vendor_id!=0x10de:
            candidates=[r for r in sysfs if r['vendor_id']==adapter.vendor_id and pci_key(r['pci_bus_id'])==adapter.luid]
            if len(candidates)==1:pci=candidates[0]['pci_bus_id']
        uuid=record.get('uuid');unique_uuid=bool(uuid and uuid_counts.get(uuid)==1)
        key='uuid:'+uuid if unique_uuid else 'pci:'+pci if pci else f'session:{adapter.vendor_id:x}:{adapter.luid:x}'
        result.append({'id':key,'index':index,'name':adapter.name,'vendor':adapter.vendor,
                       'pci_bus_id':pci,'uuid':uuid,'serial':record.get('serial'),
                       'nvml_index':record.get('nvml_index'),'present':True,
                       'identity_source':'NVIDIA UUID + PCI' if unique_uuid else 'PCI' if pci else 'session only',
                       'identity_warning':('UUID is not unique; using verified PCI address.' if uuid and not unique_uuid else
                                           'Stable hardware identity unavailable; session identifier only.' if not pci else None)})
    if len({r['id'] for r in result})!=len(result):
        raise RuntimeError('Ambiguous adapter identities; refusing to merge GPU data.')
    return result


def bind_nvml_telemetry(collector,identity,api=None):
    """Limit expensive device telemetry to its verified PCI handle.

    Linux process-counter discovery remains unchanged: its cross-GPU namespace
    matching must not be weakened by dropping other devices from that context.
    """
    nvml=getattr(collector,'nvml',None)
    pci=identity.get('pci_bus_id')
    if nvml is None or not hasattr(nvml,'handles') or not pci:return
    if api is None:
        try:import pynvml as api
        except ImportError:return
    matched=[]
    for index,handle in nvml.handles:
        try:
            if normalize_pci(api.nvmlDeviceGetPciInfo(handle).busId)==pci:matched.append((index,handle))
        except Exception:continue
    nvml.handles=matched if len(matched)==1 else []
