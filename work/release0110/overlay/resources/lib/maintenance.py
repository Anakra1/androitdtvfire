"""Local diagnostics, bounded source samples and portable settings backups."""
import copy
import hashlib
import json
import os
import re
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit, urljoin
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from .core import normalize_url, validate_manifest, load_manifest, fetch_resource
from .live import entry_catalogs, catalogue_group

FILES = ('providers.json', 'programme-settings.json', 'pvr-settings.json',
         'live-favourites.json', 'live-recent.json')
LIMIT = 4 * 1024 * 1024
STATUS = {'ready':'Catalogue available', 'manifest_ready':'Provider connected',
          'unavailable':'Provider could not be reached', 'disabled':'Disabled',
          'not_tested':'Not checked', 'sample_responded':'Sample responded; full playback unverified',
          'sample_failed':'Sample could not be read', 'no_links':'No stream links returned',
          'renew_manifest':'Needs a renewed manifest', 'configuration_required':'Needs a configured manifest'}


def status_text(value):
    return STATUS.get(value, value.replace('_',' '))


def read(store, name, default=None):
    try:
        return store.read(os.path.join(store.root, name), default)
    except (ValueError, OSError):
        return default


def redact(value):
    if isinstance(value,dict):return {k:redact(v) for k,v in value.items()}
    if isinstance(value,list):return [redact(v) for v in value]
    if isinstance(value,str):
        value=re.sub(r'(?:https?|stremio)://\S+', '[address removed]', value)
        return re.sub(r'(?<![\w])[A-Za-z0-9_-]{32,}(?![\w])','[identifier removed]',value)
    return value


def diagnose(store, addon_path):
    from . import pvr
    root = ET.parse(os.path.join(addon_path, 'addon.xml')).getroot()
    sources = store.providers()
    tests = read(store, 'source-health.json', {})
    runtime = read(store, 'maintenance-runtime.json', {})
    return redact(dict(platform=root.findtext("extension[@point='xbmc.addon.metadata']/platform"), version=root.get('version'), checked=time.time(), runtime=runtime,
        startup=read(store, 'startup-update-check.json', {}),
        tv={k:v for k,v in read(store, 'pvr-status.json', {}).items() if k in
            ('state','channels','guide_channels','programmes','updated','exported')},
        guide={key:{k:v for k,v in value.items() if k in ('state','channels','programmes','updated','attempted')}
               for key,value in read(store, 'programme-status.json', {}).items() if isinstance(value,dict)},
        player=dict(engine_started=bool(read(store, 'engine-endpoint.json', {}).get('endpoint')),
                    windows_engine_present=os.path.isfile(os.path.join(addon_path,'resources','bin','windows-x64','TorrServer.exe')),
                    explanation='The torrent engine starts when playback needs it.'),
        sources=[dict(key=e['key'], label=e['label'], enabled=e.get('enabled', True),
                      health=tests.get(e['key'], {'catalogue':'not_tested', 'stream':'not_tested'}))
                 for e in sources],
        errors=read(store, 'recent-errors.json', [])[:20],
        repair=read(store, 'maintenance-result.json', {}),
        channels=dict(total=len(pvr.channels(store)),
                      visible=sum(bool(c.get('visible', True)) for c in pvr.channels(store)))))


def runtime_snapshot(rpc, database_dir, platform):
    """Read Kodi's own origin/update policy; never modify its database."""
    repo = 'repository.crb.android' if platform == 'android' else 'repository.crb.windows'
    result = dict(repository=repo, components={}, origin_status='unknown')
    components = ('plugin.video.stremio.bridge','skin.crimsonbloodrequiem','script.crb.wizard', repo)
    if platform == 'android': components += ('script.module.cbr.engine',)
    for identity in components:
        try:
            result['components'][identity] = rpc('Addons.GetAddonDetails',
                {'addonid':identity,'properties':['enabled','version']})['addon']
        except Exception:
            result['components'][identity] = {'enabled':False,'version':'missing'}
    try:
        result['automatic_install'] = rpc('Settings.GetSettingValue', {'setting':'general.addonupdates'})['value'] == 0
        candidates = [p for p in Path(database_dir).glob('Addons*.db') if re.fullmatch(r'Addons\d+\.db',p.name)]
        path = max(candidates, key=lambda p:int(re.search(r'\d+',p.name)[0]))
        with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=1) as db:
            origins = dict(db.execute('SELECT addonID,origin FROM installed'))
            rules = {row[0] for row in db.execute('SELECT addonID FROM update_rules')}
        for identity, details in result['components'].items():
            details['repository_linked'] = origins.get(identity) == repo
            details['auto_update_allowed'] = identity not in rules
        result['origin_status'] = 'known'
    except Exception:
        pass
    result['checked'] = time.time()
    return result


def video_sample(url, headers=None):
    """Read a small playlist/segment sample, not a playback or language claim."""
    headers = dict(headers or {})
    headers.setdefault('User-Agent','Kodi-CBR/0.11')
    def get(address, limit):
        if urlsplit(address).scheme not in ('http','https'):
            raise ValueError('Unsupported response')
        with urlopen(Request(address, headers=headers), timeout=8) as response:
            return response.read(limit), response.headers.get('Content-Type','')
    raw, kind = get(url, 65536)
    if raw.lstrip().startswith(b'#EXTM3U'):
        # Follow at most two HLS levels; never download an entire programme.
        for unused in range(2):
            lines = raw.decode('utf8','replace').splitlines()
            candidate = next((s.strip() for s in lines if s.strip() and not s.startswith('#')),None)
            if not candidate: return False
            url = urljoin(url,candidate)
            raw, kind = get(url, 65536 if '#EXT-X-STREAM-INF' in '\n'.join(lines) else 1024)
            if not raw.lstrip().startswith(b'#EXTM3U'):
                return bool(raw) and ('video' in kind or 'octet-stream' in kind or raw[:1]==b'G')
        return False
    return bool(raw) and kind.startswith('video/')


def probe_source(entry, fetch=None, sample=video_sample):
    result = dict(checked=time.time(), catalogue='not_tested', stream='not_tested', native_playback=False)
    if not entry.get('enabled',True):
        result['catalogue']='disabled'; return result
    try:
        manifest = load_manifest(entry['url']) if fetch is None else fetch(entry['url'])
        if manifest.get('behaviorHints',{}).get('configurationRequired'):
            result.update(catalogue='configuration_required',stream='renew_manifest');return result
        validate_manifest(manifest)
        current = dict(entry, manifest=manifest)
        candidates = [c for c in entry_catalogs(current) if not any(x.get('isRequired') for x in c.get('extra',[]))]
        if not candidates:
            result['catalogue']='manifest_ready'; return result
        cat = candidates[0]
        data = fetch_resource(current,'catalog',cat['type'],cat['id'])
        metas = data.get('metas',[])
        result.update(catalogue='ready', listings=len(metas))
        if not metas or catalogue_group(current,cat) is None:
            return result
        meta = next((m for m in metas if isinstance(m,dict) and m.get('id')),None)
        if not meta: return result
        result['sample_channel']=str(meta.get('name',''))[:100]
        streams = fetch_resource(current,'stream',cat['type'],meta['id']).get('streams',[])
        result['stream']='no_links'
        for stream in streams[:3]:
            text = ' '.join(str(stream.get(k,'')) for k in ('name','title','description')).lower()
            if any(s in text for s in ('please reinstall','update manifest','reinstall addon','reconfigure')):
                result['stream']='renew_manifest';continue
            url = stream.get('url','')
            if urlsplit(url).scheme not in ('http','https'):continue
            try:
                headers=stream.get('behaviorHints',{}).get('proxyHeaders',{}).get('request',{})
                if sample(url,headers): result['stream']='sample_responded';break
                if result['stream']!='renew_manifest':result['stream']='sample_failed'
            except Exception:
                if result['stream']!='renew_manifest':result['stream']='sample_failed'
        return result
    except Exception:
        # URLs, provider exception messages and headers can contain secrets.
        result['catalogue']='unavailable';return result


def test_sources(store):
    entries=store.providers()
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(probe_source,entries))
    previous=read(store,'source-health.json',{})
    data={e['key']:result for e,result in zip(entries,results)}
    for key,result in data.items():
        for field in ('last_playback','playback_channel'):
            if field in previous.get(key,{}):result[field]=previous[key][field]
    store.write(os.path.join(store.root,'source-health.json'),data)
    return data


def record_playback(store, channel):
    key=channel.get('provider')
    if not any(e['key']==key for e in store.providers()):return
    data=read(store,'source-health.json',{})
    state=data.setdefault(key,{'catalogue':'not_tested','stream':'not_tested'})
    state.update(last_playback=time.time(),playback_channel=redact(channel.get('meta',{}).get('name','Channel')))
    store.write(os.path.join(store.root,'source-health.json'),data)


def request_repair(store):
    store.write(os.path.join(store.root,'maintenance-request.json'),{'time':time.time()})


def export_backup(store, include_personal=False):
    files={}
    for name in FILES:
        if name=='providers.json' and not include_personal:continue
        value=read(store,name)
        if value is not None:files[name]=value
    # Feed URLs and bookmarks can also embed private settings; omit them by
    # default rather than pretending that removing only provider URLs suffices.
    if not include_personal:
        files.pop('programme-settings.json',None)
        files.pop('live-favourites.json',None)
        files.pop('live-recent.json',None)
        if 'pvr-settings.json' in files:
            files['pvr-settings.json'] = {k:v for k,v in files['pvr-settings.json'].items() if k in ('overrides','favourites_first')}
    result=dict(format='cbr-settings',schema=1,created=time.time(),
                includes_personal=bool(include_personal),files=files)
    if len(json.dumps(result).encode())>LIMIT:raise ValueError('Settings backup exceeds 4 MB.')
    return result


def validate_backup(data):
    if not isinstance(data,dict) or data.get('format')!='cbr-settings' or data.get('schema')!=1:
        raise ValueError('Choose a CBR settings backup (schema 1).')
    if len(json.dumps(data).encode())>LIMIT:raise ValueError('Backup exceeds 4 MB.')
    files=data.get('files')
    if not isinstance(files,dict) or not files or any(n not in FILES for n in files):
        raise ValueError('Backup contains unsupported settings files.')
    if not data.get('includes_personal') and any(n!='pvr-settings.json' for n in files):
        raise ValueError('Personal settings must be explicitly identified in the backup.')
    for name,value in files.items():
        if name in ('providers.json','live-favourites.json','live-recent.json'):
            if not isinstance(value,list) or len(value)>25000:raise ValueError('Invalid source or bookmark list.')
        elif not isinstance(value,dict):raise ValueError('Invalid settings object.')
        if name=='providers.json':
            keys=set()
            for e in value:
                if not isinstance(e,dict) or not isinstance(e.get('label'),str) or len(e['label'])>100:
                    raise ValueError('Invalid provider in backup.')
                url=normalize_url(e.get('url',''));key=hashlib.sha256(url.encode()).hexdigest()[:24]
                if e.get('key')!=key or key in keys:raise ValueError('Invalid or repeated provider identity.')
                validate_manifest(e.get('manifest',{}));keys.add(key)
                if e.get('kind') not in (None,'m3u','daddylive'):raise ValueError('Invalid provider kind.')
                for cat in e['manifest'].get('catalogs',[]):
                    if not isinstance(cat,dict) or not all(isinstance(cat.get(k),str) for k in ('id','type')):
                        raise ValueError('Invalid provider catalogue.')
                    if not isinstance(cat.get('extra',[]),list) or any(not isinstance(x,dict) for x in cat.get('extra',[])):
                        raise ValueError('Invalid provider catalogue filters.')
        if name=='pvr-settings.json':
            if not isinstance(value.get('overrides',{}),dict):raise ValueError('Invalid channel overrides.')
            selected=value.get('selected')
            if selected is not None and (not isinstance(selected,list) or any(not isinstance(k,str) for k in selected)):
                raise ValueError('Invalid TV source selection.')
            for identity,row in value.get('overrides',{}).items():
                if not re.fullmatch(r'cbr\.[a-f0-9]{24}',identity) or not isinstance(row,dict):raise ValueError('Invalid channel override.')
                if not isinstance(row.get('number'),int) or not 1<=row['number']<=9999:raise ValueError('Invalid channel number.')
                if not isinstance(row.get('name'),str) or not row['name']:raise ValueError('Invalid channel name.')
                from .pvr import GROUPS
                if not isinstance(row.get('groups'),list) or not row['groups'] or any(g not in GROUPS for g in row['groups']):raise ValueError('Invalid channel groups.')
        if name=='programme-settings.json':
            from .programmes import COUNTRIES, feed_key
            if not isinstance(value.get('feeds'),list) or not isinstance(value.get('mappings',{}),dict):raise ValueError('Invalid guide settings.')
            for feed in value['feeds']:
                if not isinstance(feed,dict) or not isinstance(feed.get('url'),str):raise ValueError('Invalid guide feed.')
                address=urlsplit(feed['url'])
                if address.scheme not in ('http','https') or not address.hostname or address.username or address.password or address.fragment:raise ValueError('Invalid guide URL.')
                if feed.get('country') not in COUNTRIES or feed.get('key')!=feed_key(feed['url']):raise ValueError('Invalid guide country or identity.')
            for identity,mapping in value.get('mappings',{}).items():
                if not re.fullmatch(r'[a-f0-9]{64}',identity) or not isinstance(mapping,dict) or not all(isinstance(mapping.get(k),str) for k in ('feed','channel')):
                    raise ValueError('Invalid programme mapping.')
        if name in ('live-favourites.json','live-recent.json'):
            for row in value:
                if not isinstance(row,dict) or not isinstance(row.get('meta'),dict) or not all(isinstance(row.get(k),str)for k in ('provider','provider_id','resource_type')):
                    raise ValueError('Invalid saved channel.')
                if not isinstance(row['meta'].get('id'),str):raise ValueError('Invalid saved channel identity.')
    return copy.deepcopy(files)


def restore_backup(store,data):
    files=validate_backup(data)  # Validate every file before writing any.
    if not data.get('includes_personal') and 'pvr-settings.json' in files:
        previous = read(store, 'pvr-settings.json', {})
        files['pvr-settings.json'] = dict(previous, **files['pvr-settings.json'])
    rollback={name:read(store,name) for name in files}
    folder=os.path.join(store.root,'settings-backups');os.makedirs(folder,exist_ok=True)
    store.write(os.path.join(folder,'before-restore-{}.json'.format(time.time_ns())),
                dict(format='cbr-settings',schema=1,includes_personal=True,files={k:v for k,v in rollback.items()if v is not None}))
    written=[]
    try:
        for name,value in files.items():
            store.write(os.path.join(store.root,name),value);written.append(name)
    except Exception:
        for name in written:
            path=os.path.join(store.root,name)
            if rollback[name] is None:os.remove(path)
            else:store.write(path,rollback[name])
        raise
    request_repair(store)
    return len(files)
