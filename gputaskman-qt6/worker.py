"""Read-only multi-GPU collector process. MIT; original gputaskman backend."""
import argparse,json,os,signal,sys,threading,time,math
from fleet import Fleet
from importlib.metadata import version
COLLECTOR_VERSION = version("gputaskman")

class RefreshControl:
    """Validated interval changes over the existing stdin channel, no process restart."""
    def __init__(self,interval):self.interval=interval
    def apply(self,command):
        parts=command.split()
        if len(parts)!=2 or parts[0]!='interval':return False
        try:value=float(parts[1])
        except ValueError:return False
        if not math.isfinite(value) or not .25<=value<=60:return False
        self.interval=value;return True

def run():
    from gputaskman.collector import Collector,enumerate_adapters,ordered_adapters
    from gputaskman.host import HostSampler,to_dict as system_dict
    parser=argparse.ArgumentParser()
    parser.add_argument('--version',action='version',version='gputaskman collector '+COLLECTOR_VERSION)
    parser.add_argument('--gpu',type=int,default=0,help='legacy preferred index; all physical GPUs are sampled')
    parser.add_argument('--interval',type=float,default=1)
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    if args.gpu<0 or not .25<=args.interval<=60:parser.error('Invalid GPU index or refresh interval.')
    stop=threading.Event();paused=threading.Event();wake=threading.Event();refresh=RefreshControl(args.interval)
    def control():
        for line in sys.stdin:
            command=line.strip()
            if command=='quit':break
            if refresh.apply(command):wake.set()
            if command=='pause':paused.set();wake.set()
            if command=='resume':paused.clear();wake.set()
        stop.set();wake.set()
    if not args.once:threading.Thread(target=control,daemon=True).start()
    signal.signal(signal.SIGTERM,lambda *_:(stop.set(),wake.set()));signal.signal(signal.SIGINT,lambda *_:(stop.set(),wake.set()))
    fleet=Fleet(lambda:ordered_adapters(enumerate_adapters()),Collector,budget=None if args.once else Collector.SCAN_BUDGET)
    try:
        sampler=HostSampler();sampler.sample();stop.wait(.5);next_discovery=0
        while not stop.is_set():
            wake.clear();started=time.monotonic()
            if not paused.is_set():
                discovery_error=None
                if started>=next_discovery:
                    try:fleet.sync()
                    except Exception as error:discovery_error=str(error)
                    next_discovery=started+5
                system,system_error=None,None
                try:system=sampler.sample()
                except Exception as error:system_error=str(error)
                snapshots,errors=fleet.sample(system,system_error)
                message={'protocol':2,'collector_version':COLLECTOR_VERSION,'gpus':list(fleet.known.values()),'snapshots':snapshots,'errors':errors,
                         'elevated':os.geteuid()==0,'taken':time.time(),'sample_ms':round((time.monotonic()-started)*1000,1),'interval_seconds':refresh.interval}
                if system:message['system']=system_dict(system)
                if discovery_error:message['discovery_error']=discovery_error
                if snapshots:message['snapshot']=next((s for s in snapshots if s['gpu_identity']['index']==args.gpu),snapshots[0])  # legacy clients
                elif not fleet.known:message['error']=discovery_error or 'No supported physical GPU is detected.'
                print(json.dumps(message,default=str),flush=True)
                if args.once:return
            wake.wait(max(.05,refresh.interval-(time.monotonic()-started)))
    except BrokenPipeError:return
    except Exception as error:
        try:print(json.dumps({'error':f'{type(error).__name__}: {error}'}),flush=True)
        except BrokenPipeError:pass
    finally:fleet.close()

if __name__=='__main__':run()
