"""Replace the retired public Pluto manifest with a refreshing UK M3U source."""
import hashlib
import os
import time

from . import pvr, programmes

URL = 'https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_gb.m3u'
EPG = 'https://raw.githubusercontent.com/matthuisman/i.mjh.nz/master/PlutoTV/gb.xml.gz'
FREEVIEW_EPG = 'https://raw.githubusercontent.com/dp247/Freeview-EPG/master/epg.xml'
OLD = 'https://dev.nebulawp.org/stremio/pluto-tv-addon/manifest.json'


def ensure(store, force=False):
    marker = os.path.join(store.root,'pluto-uk-defaults-0110.json')
    if not force and store.read(marker):return
    entries=store.providers()
    old=next((e for e in entries if e.get('url')==OLD),None)
    key=hashlib.sha256(URL.encode()).hexdigest()[:24]
    current=next((e for e in entries if e.get('url')==URL),None)
    if current is None:
        identity='org.cbr.m3u.'+hashlib.sha256(('raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_gb.m3u').encode()).hexdigest()[:16]
        manifest=dict(id=identity,name='Pluto TV UK',version='1.0.0',types=['tv'],
            resources=['catalog','meta','stream'],idPrefixes=['m3u.'],catalogs=[
                dict(type='tv',id='m3u_uk',name='UK channels',extra=[dict(name='search')])])
        current=dict(key=key,url=URL,label='Pluto TV UK',manifest=manifest,
            enabled=old.get('enabled',True) if old else True,kind='m3u',scope_types=['tv'],
            live_group='internet',guide_country='GB')
        entries.append(current)
    if old:
        old['enabled']=False
        old['pvr_enabled']=False
    # Custom Pluto manifests and the explicit disabled state are preserved.
    store.save_providers(entries)
    guide=programmes.settings(store)
    for url,label in [(EPG,'Pluto TV UK guide'),(FREEVIEW_EPG,'Freeview UK programme guide')]:
        if not any(f['url']==url for f in guide['feeds']):
            guide['feeds'].append(dict(key=programmes.feed_key(url),label=label,url=url,country='GB',enabled=True))
    programmes.save_settings(store,guide)
    for e in entries:
        if e.get('label')=='BBC UK (Free-TV)' and e.get('kind')=='m3u':
            mapping=e.setdefault('epg_ids',{})
            if mapping.get('BBCOne.uk') in (None,'BBC.One.Yorks.HD.uk'):
                mapping['BBCOne.uk']='BBCOneYorkshire.uk'
            if mapping.get('BBCTwo.uk') in (None,'BBCTwo.uk'):
                mapping['BBCTwo.uk']='BBCTwoHD.uk'
    store.save_providers(entries)
    value=pvr.config(store)
    if value.get('selected') is not None and current.get('enabled',True):
        value['selected']=list(dict.fromkeys(value['selected']+[s['key'] for s in pvr.sources(store)if s['provider']==key]))
        pvr.save_config(store,value)
    programmes.request_refresh(store)
    if value.get('enabled'):pvr.refresh(store)
    store.write(marker,{'time':time.time()})
