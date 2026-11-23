"""Boxing discovery and honest availability windows; never infer playable streams."""
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from .core import fetch_resource
from .live import entry_catalogs
from .programmes import timestamp

def boxing(meta):
    text=' '.join(str(meta.get(k,'')) for k in ('name','genres','sport','category'))
    if re.search(r'\b(?:ufc|mma|wrestling|wwe)\b',text,re.I) and not re.search(r'\bboxing\b',text,re.I):return False
    return bool(re.search(r'\bboxing\b|\bbox office\b|\bppv\b',text,re.I))

def starts(meta):
    for key in ('startTime','start','start_time','released'):
        stamp=timestamp(meta.get(key))
        if stamp:return stamp
    # Sports Streams publishes its scheduled times in the description artwork text.
    text=str(meta.get('description',''))+' '+str(meta.get('releaseInfo',''))
    match=re.search(r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})[^\n\d]*?(\d{1,2}):(\d{2})\s*UTC',text,re.I)
    if match:
        day,month,year,hour,minute=match.groups()
        months={name:index+1 for index,name in enumerate(('jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'))}
        try:return datetime(int(year),months[month.lower()],int(day),int(hour),int(minute),tzinfo=timezone.utc).timestamp()
        except ValueError:pass
    return None

def status(meta,now=None):
    now=time.time() if now is None else now
    start=starts(meta)
    if start is None:return 'Start time not supplied. Check links near the broadcast.'
    local=lambda value:datetime.fromtimestamp(value).strftime('%a %d %b %H:%M')
    if now<start-3600:
        return 'Starts {}. Links expected from about {} (local time); availability is not guaranteed.'.format(local(start),local(start-3600))
    if now<start:return 'Starts {} (local time). Expected link window is open; check availability.'.format(local(start))
    return 'Scheduled start {} (local time). Check links; the provider may still be waiting or the event may have ended.'.format(local(start))

def events(store,entry):
    selected=[c for c in entry_catalogs(entry) if c['id'] in ('sports_live','sports_today','sports_fight')]
    def load(cat):
        try:return cat,fetch_resource(entry,'catalog',cat['type'],cat['id']).get('metas',[]),False
        except Exception:return cat,[],True
    seen=set();rows=[];errors=0
    with ThreadPoolExecutor(max_workers=3) as pool:
        for cat,metas,failed in pool.map(load,selected):
            errors+=int(failed)
            for meta in metas:
                if not isinstance(meta,dict) or not meta.get('id') or not meta.get('name') or not boxing(meta):continue
                kind=meta.get('type',cat['type']);key=(kind,meta['id'])
                if key in seen:continue
                seen.add(key)
                rows.append(dict(provider=entry['key'],provider_id=entry['manifest']['id'],provider_label=entry['label'],resource_type=kind,live_group='sports',meta=meta))
    rows.sort(key=lambda r:(starts(r['meta']) or float('inf'),r['meta']['name']))
    return rows,errors
