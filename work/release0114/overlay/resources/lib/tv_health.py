"""Channel-level source samples, guide state and component version checks."""
import os,time,re,hashlib,threading
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.error import HTTPError,URLError
import socket
from . import pvr,maintenance
from .core import fetch_resource

LABELS={'sample_responded':'Media sample received (playback unverified)', 'sample_failed':'Link did not return a usable sample',
        'no_links':'No stream links returned','renew_manifest':'Provider renewal required','dns_failed':'Stream address did not resolve',
        'timeout':'Stream connection timed out','http_error':'Stream server rejected the request','unavailable':'Source could not be reached',
        'disabled':'Source is disabled or removed','not_checked':'Not checked'}

def classify(error):
    if isinstance(error,HTTPError):return 'http_error',str(error.code)
    reason=getattr(error,'reason',error)
    if isinstance(reason,socket.gaierror):return 'dns_failed',''
    if isinstance(reason,(TimeoutError,socket.timeout)):return 'timeout',''
    return 'unavailable',''

def check_channel(store,row,stop=None):
    result=dict(id=row['id'],name=row['name'],checked=time.time(),status='no_links',detail='',guide='unavailable')
    guide=pvr.ProgrammeGuide(store)
    try:
        for variant in row.get('variants',[]):
            current=pvr.resolve_variant(store,variant)
            if current and guide.lookup(current):
                info=guide.lookup(current)
                if info and (info.get('now')or info.get('next')):result['guide']='available';break
    finally:guide.close()
    found=False
    def cancelled():return stop is not None and stop.is_set()
    for variant in row.get('variants',[])[:8]:
        if cancelled():result['status']='not_checked';return result
        current=pvr.resolve_variant(store,variant)
        if not current:continue
        found=True
        try:
            entry=store.provider(current['provider'])
            streams=fetch_resource(entry,'stream',current['resource_type'],current['meta']['id']).get('streams',[])
            for stream in streams[:3]:
                if cancelled():result['status']='not_checked';return result
                text=' '.join(str(stream.get(k,''))for k in ['name','title','description']).lower()
                if any(word in text for word in ['please reinstall','update manifest','reconfigure','reinstall addon']):
                    result['status']='renew_manifest';continue
                url=stream.get('url','')
                if not url.startswith(('http://','https://')):continue
                try:
                    headers=stream.get('behaviorHints',{}).get('proxyHeaders',{}).get('request',{})
                    if maintenance.video_sample(url,headers):
                        result['status']='sample_responded';return result
                    result['status']='sample_failed'
                except Exception as error:result['status'],result['detail']=classify(error)
        except Exception as error:result['status'],result['detail']=classify(error)
    if not found:result['status']='disabled'
    return result

def test_channels(store,stop=None,progress=None):
    stop=stop or threading.Event();rows=[r for r in pvr.channels(store)if r.get('visible',True)]
    results=maintenance.read(store,'channel-health.json',{})
    # Work is scheduled in small batches so Cancel does not queue hundreds of requests.
    completed=0
    with ThreadPoolExecutor(max_workers=3)as pool:
        for offset in range(0,len(rows),3):
            if stop.is_set():break
            tasks={pool.submit(check_channel,store,r,stop):r for r in rows[offset:offset+3]}
            for future in as_completed(tasks):
                result=future.result()
                if result['status']!='not_checked':results[result['id']]=result;completed+=1
                if progress:progress(completed,len(rows),result['name'])
            store.write(os.path.join(store.root,'channel-health.json'),results)
    return dict(checked=completed,total=len(rows),cancelled=stop.is_set())

def text_report(store,query=''):
    rows=pvr.channels(store);health=maintenance.read(store,'channel-health.json',{})
    records=maintenance.read(store,'confirmed-playback.json',{})
    from .playback_memory import channel_key
    rows=[r for r in rows if query.casefold()in r['name'].casefold()]
    lines=[]
    for row in sorted(rows,key=lambda r:r['name'].casefold()):
        result=health.get(row['id'],{});status=LABELS.get(result.get('status','not_checked'),'Not checked')
        confirmed=max((records.get(channel_key(v),{}).get('confirmed',0)for v in row.get('variants',[])),default=0)
        age='Last sample: '+time.strftime('%d %b %H:%M',time.localtime(result['checked']))if result.get('checked')else 'No recent sample'
        lines.append('{}{}\n{}{}\n{} | Programme guide: {}{}'.format(row['name'],' (hidden)'if not row.get('visible',True)else '',status,
            ' ('+result['detail']+')'if result.get('detail')else '',age,result.get('guide','not checked'),
            '\nKodi previously started playback: '+time.strftime('%d %b %H:%M',time.localtime(confirmed))if confirmed else ''))
    if not lines:return 'No channel matching that name is present in the current CBR channel list. Missing entries cannot be repaired by refreshing a stream.'
    return '\n\n'.join(lines)+'\n\nSamples do not verify continuous playback or audio language. Missing programme information does not prevent playback. Checks do not hide or remove channels.'

COMPONENTS={'plugin.video.stremio.bridge':'CBR video addon','script.crb.wizard':'Setup Wizard',
            'skin.crimsonbloodrequiem':'CBR skin','script.module.cbr.engine':'Playback Engine'}

def version(value):
    try:return tuple(int(x)for x in value.split('+',1)[0].split('.'))
    except (ValueError,AttributeError):return ()

def component_report(runtime,expected):
    lines=[]
    for identity,wanted in expected.items():
        installed=runtime.get('components',{}).get(identity,{});actual=installed.get('version','missing')
        state='Missing'if actual=='missing'else 'Update needed'if version(actual)<version(wanted)else 'Newer than repository'if version(actual)>version(wanted)else 'Current'
        if actual!='missing'and not installed.get('enabled',True):state+='; disabled'
        lines.append('{}: {} | latest {} | {}'.format(COMPONENTS.get(identity,identity),actual,wanted,state))
    repo=runtime.get('components',{}).get(runtime.get('repository'),{})
    lines.append('CBR repository: '+('enabled'if repo.get('enabled')else 'missing or disabled'))
    lines.append('Kodi automatic installation: '+('enabled'if runtime.get('automatic_install')else 'off or unavailable'))
    return '\n'.join(lines)
