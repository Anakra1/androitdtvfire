"""Exercise failure paths against actual packaged modules, without provider traffic."""
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch
import tempfile,sys,json,time,os,threading,socket
from urllib.error import HTTPError,URLError
ROOT=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(dir=ROOT/'outputs',prefix='verified-live-reliability-')as tmp:
    tmp=Path(tmp)
    with ZipFile(ROOT/'cbr0120.zip')as z:z.extractall(tmp/'code')
    sys.path.insert(0,str(tmp/'code/plugin.video.stremio.bridge'))
    from resources.lib.core import Store
    from resources.lib.live_player import LiveAutoplay
    from resources.lib.playback_memory import PlaybackMemory,channel_key,stream_key,queue_retry,poll_retry,retry_context
    from resources.lib import pvr,tv_health,maintenance
    from resources.lib.tv_repair import RepairTask
    store=Store(str(tmp/'profile'))
    channel=dict(provider='p',provider_id='test',resource_type='tv',meta=dict(id='one',name='Test TV',type='tv'))
    a=dict(url='https://a.example/one.m3u8?token=old',name='HD')
    b=dict(url='https://b.example/one.m3u8?token=old',name='HD')
    memory=PlaybackMemory(store);autoplay=LiveAutoplay(store)
    assert memory.rank(channel,[('a',a),('b',b)])[0][1]==a
    memory.prepare(channel,b,b['url'])
    assert not memory.confirm('https://unrelated.example/video')
    assert memory.confirm(b['url'])
    saved=Path(memory.path).read_text();assert 'https://'not in saved and 'token'not in saved
    fresh=dict(b,url='https://b.example/one.m3u8?token=new')
    calls=[]
    path=autoplay.begin(channel['meta'],channel,[a,fresh],probe=lambda s:calls.append(s['url'])or True)
    assert path.startswith(fresh['url']) and calls==[fresh['url']]
    # A confirmed link failing a fresh probe falls through to another fresh candidate.
    calls=[]
    path=autoplay.begin(channel['meta'],channel,[a,fresh],probe=lambda s:calls.append(s['url'])or(s is a))
    assert path.startswith(a['url']) and len(calls)==2
    # Only a matching fresh PVR context may confirm; unrelated playback cannot.
    ctx=retry_context(store,'cbr.'+'a'*24,'Test TV',42)
    memory.prepare(channel,a,a['url'],ctx)
    assert not memory.confirm('pvr://something','Other channel')
    assert memory.confirm('pvr://something','Test TV')
    memory.prepare(channel,a,a['url'],ctx);attempt=memory.failed();queue_retry(store,attempt)
    class Idle:
        def isPlaying(self):return False
    rpc_calls=[]
    def rpc(method,params):
        rpc_calls.append((method,params))
        if method=='PVR.GetChannels':return {'channels':[{'label':'Test TV','channelnumber':42,'channelid':9}]}
        return 'OK'
    poll_retry(store,Idle(),rpc)
    assert rpc_calls[-1]==('Player.Open',{'item':{'channelid':9}})
    retry=retry_context(store,ctx['id'],'Test TV',42)
    assert retry['failed']==[attempt['token']]
    path=autoplay.begin(channel['meta'],channel,[a,fresh],probe=lambda s:True,context=retry)
    assert path.startswith(fresh['url'])
    # User playback and duplicate names prevent native retries.
    memory.prepare(channel,a,a['url'],ctx);queue_retry(store,memory.failed())
    class Playing:
        def isPlaying(self):return True
    calls_before=len(rpc_calls);poll_retry(store,Playing(),rpc);assert len(rpc_calls)==calls_before
    retry_context(store,ctx['id'],'Test TV',42);memory.prepare(channel,a,a['url'],ctx);queue_retry(store,memory.failed())
    def duplicate(method,params):
        assert method=='PVR.GetChannels'
        return {'channels':[{'label':'Test TV','channelnumber':42,'channelid':9},{'label':'Test TV','channelnumber':42,'channelid':10}]}
    poll_retry(store,Idle(),duplicate)
    assert not store.read(os.path.join(store.root,'pvr-retry.json'))
    print('Confirmed fresh-link preference, token-free long-term cache, unrelated-playback guard and bounded native retry ownership passed')
    assert tv_health.classify(HTTPError('https://private.example/token',403,'No',None,None))==('http_error','403')
    assert tv_health.classify(URLError(socket.gaierror(11001,'DNS failed')))[0]=='dns_failed'
    assert 'No channel matching' in tv_health.text_report(store,'Missing ITV')
    report=tv_health.component_report({'components':{'plugin.video.stremio.bridge':{'version':'0.11.3','enabled':True}}},{'plugin.video.stremio.bridge':'0.12.0','script.crb.wizard':'0.4.0'})
    assert 'Update needed'in report and 'Missing'in report
    # Cancel before network work writes nothing and never changes visibility.
    stop=threading.Event();stop.set();before=pvr.channels(store)
    with patch.object(tv_health,'check_channel',side_effect=AssertionError('Network check after cancel')):
        assert tv_health.test_channels(store,stop)['cancelled']
    assert before==pvr.channels(store)
    print('Channel error classification, missing-channel explanation, component mismatch and cancellation preservation passed')
    # Failed source refresh must retain both last-good exports and channel metadata.
    source=dict(key='source',label='Failed source',provider='p',default=True)
    fixture=dict(channel,live_country='GB');row=pvr.merge_channels([fixture])[0]
    store.write(os.path.join(store.root,'pvr-channels.json'),[row])
    folder=Path(store.root)/'pvr';folder.mkdir();(folder/'channels.m3u').write_text('LAST GOOD M3U');(folder/'guide.xml').write_text('LAST GOOD GUIDE')
    old_channels=store.read(os.path.join(store.root,'pvr-channels.json'))
    with patch.object(pvr,'sources',return_value=[source]),patch.object(pvr,'collect_source',side_effect=ValueError('Provider down')):
        pvr.PVRUpdater(store).build()
    assert (folder/'channels.m3u').read_text()=='LAST GOOD M3U' and (folder/'guide.xml').read_text()=='LAST GOOD GUIDE'
    assert store.read(os.path.join(store.root,'pvr-channels.json'))==old_channels
    # If the second output replacement fails, the first must be rolled back too.
    one,two=folder/'pair-one',folder/'pair-two';one.write_bytes(b'old-one');two.write_bytes(b'old-two')
    replace=os.replace;raised=[]
    def fail_second(src,dest):
        if str(dest)==str(two)and not raised:raised.append(True);raise OSError('simulated disk error')
        return replace(src,dest)
    with patch.object(pvr.os,'replace',side_effect=fail_second):
        try:pvr.commit_exports({str(one):b'new-one',str(two):b'new-two'})
        except OSError:pass
        else:raise AssertionError('Simulated export failure accepted')
    assert one.read_bytes()==b'old-one' and two.read_bytes()==b'old-two'
    assert not list(folder.glob('.cbr-*'))
    task=RepairTask(str(tmp/'code/plugin.video.stremio.bridge'),store.root,str(tmp/'iptv'))
    task.guide_progress(1,3,'Example guide');assert '2/3'in task.message
    task.channel_progress(0,2,'Example source');assert '1/2'in task.message
    assert 'elapsed'in task.elapsed_message()
    task.cancel();assert 'Stopping'in task.elapsed_message()
    try:task.run()
    except InterruptedError:pass
    else:raise AssertionError('Cancelled repair ran')
    assert store.read(task.report_path)['state']=='cancelled' and store.read(task.flag)=={}
    print('Last-good TV preservation, per-guide/source progress, elapsed time, cancellation and heartbeat cleanup passed')
