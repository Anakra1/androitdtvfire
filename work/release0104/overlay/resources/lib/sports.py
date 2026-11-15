"""Sport-first listings; resolve each provider's own IDs only when selected."""
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

from .core import fetch_resource, resource_url, aggregate
from .live import LiveCatalogueCache, entry_catalogs, catalogue_group
from .programmes import normalized, country_for

SPORTS = (
    ('all', 'All sports'), ('football', 'Football'), ('motor_sports', 'Motor sports / Formula 1'),
    ('cricket', 'Cricket'), ('rugby', 'Rugby'), ('tennis', 'Tennis'), ('golf', 'Golf'),
    ('basketball', 'Basketball'), ('american_football', 'American football'), ('hockey', 'Ice hockey'),
    ('baseball', 'Baseball'), ('fight', 'Boxing / UFC / wrestling'), ('billiards', 'Snooker / pool'),
    ('afl', 'Australian football'), ('darts', 'Darts'), ('other', 'Other sports'))
PATTERNS = {
    'football': r'\b(soccer|football|premier league|la liga|laliga|serie a|bundesliga|ligue 1|uefa)\b',
    'motor_sports': r'\b(motor|motorsport|racing|formula|f1|nascar|motogp|indycar)\b',
    'cricket': r'\b(cricket|ashes|ipl)\b', 'rugby': r'\b(rugby|six nations)\b',
    'tennis': r'\b(tennis|atp|wta|wimbledon)\b', 'golf': r'\b(golf|pga)\b',
    'basketball': r'\b(basketball|nba|wnba)\b', 'american_football': r'\b(american football|nfl|ncaaf|nfl network)\b',
    'hockey': r'\b(hockey|nhl)\b', 'baseball': r'\b(baseball|mlb)\b',
    'fight': r'\b(boxing|fight|ufc|mma|wrestling|wwe)\b',
    'billiards': r'\b(billiards|snooker|pool)\b', 'afl': r'\b(afl|australian football)\b', 'darts': r'\bdarts\b'}
CHANNEL = re.compile(r'\b(sky sport[s]?|tnt sport[s]?|bt sport[s]?|eurosport|espn|bein sport[s]?|supersport|premier sport[s]?|dazn|sport tv|sportsnet|fox sport[s]?|tsn|nfl network|nba tv|mlb network|nhl network|tennis channel|golf channel|racing tv|pluto.+sport[s]?)\b', re.I)

def classifications(meta, declared=''):
    name=normalized(meta.get('name',''))
    text=normalized(meta.get('name','')+' '+' '.join(str(x)for x in meta.get('genres',[])))
    found={key for key,pattern in PATTERNS.items() if re.search(pattern,text)}
    if 'american_football' in found or 'afl' in found:found.discard('football')
    if declared and declared!='all':found.add(declared)
    is_channel=bool(CHANNEL.search(text)) or meta.get('type') in ('tv','channel','channels','live')
    if is_channel and CHANNEL.search(name) and not any(re.search(pattern,name)for pattern in PATTERNS.values()):
        found=set()  # Mixed-sport networks stay in the separate channel folder.
    is_sports=bool(found or CHANNEL.search(text) or re.search(r'\bsports?\b',text) or declared)
    return found,is_channel,is_sports

def choose(entry, sport):
    cats=[c for c in entry_catalogs(entry) if c['type'] in ('tv','channel','channels','live','sport','sports','event','events')]
    if not cats:return None
    if entry.get('kind')=='daddylive':
        cat=next((c for c in cats if c['id']=='daddy_uk'),cats[0]);return cat,{},''
    if entry.get('kind')=='m3u':
        if entry.get('include_tvg_ids') and all(x.startswith(('BBC','CBBC','CBeebies'))for x in entry['include_tvg_ids']):return None
        cat=next((c for c in cats if c['id']=='m3u_uk'),cats[0]);return cat,{},''
    sports=[c for c in cats if catalogue_group(entry,c)=='sports']
    if sports:
        specific=next((c for c in sports if c['id'].lower().endswith('_'+sport)),None) if sport!='all'else None
        cat=specific or next((c for c in sports if c['id'].lower().endswith(('_live','_all'))),sports[0])
        extras={}
        for extra in cat.get('extra',[]):
            if extra.get('isRequired'):
                if extra['name']=='search' and sport!='all':extras['search']=dict(SPORTS)[sport]
                else:return None
        return cat,extras,sport if specific else 'all'
    cat=next((c for c in cats if 'sport'in (c['id']+' '+c.get('name','')).lower()),None)
    if cat is None:return None
    if any(e.get('isRequired')for e in cat.get('extra',[])):return None
    return cat,{},''

def listing(store, sport, refresh=False):
    if sport not in dict(SPORTS):raise ValueError('Unknown sport')
    cache=LiveCatalogueCache(store)
    jobs=[(e,choice)for e in store.providers()if e.get('enabled',True)for choice in [choose(e,sport)]if choice]
    for entry,(selected,_,_)in list(jobs):
        for cat in entry_catalogs(entry):
            if cat['id']!=selected['id'] and catalogue_group(entry,cat)=='sports' and cat['id'].lower().endswith('_live'):
                jobs.append((entry,(cat,{},'all')))
    def load(job):
        entry,(cat,extras,declared)=job
        try:
            data=None
            if entry.get('kind')=='m3u' and not refresh:
                from .pvr import digest
                key=digest([entry['manifest']['id'],cat['type'],cat['id'],extras])
                path=os.path.join(store.root,'pvr-source-'+key+'.json')
                if os.path.exists(path)and time.time()-os.path.getmtime(path)<1800:
                    data={'metas':[v['meta']for v in store.read(path,[])if v['provider']==entry['key']]}
            if data is None:
                url=resource_url(entry['url'],'catalog',cat['type'],cat['id'],extras)
                data=cache.get(url,lambda unused:fetch_resource(entry,'catalog',cat['type'],cat['id'],extras),refresh=refresh)
            rows=[]
            for raw in data.get('metas',[])[:3000]:
                if not isinstance(raw,dict)or not raw.get('id')or not raw.get('name'):continue
                meta={k:v for k,v in raw.items()if k not in ('streams','videos')}
                meta.setdefault('type',cat['type'])
                categories,channel,sports=classifications(meta,declared)
                if not sports or sport!='all'and sport not in categories and not(channel and not categories):continue
                prefix=re.match(r'^(AU|CA|US|UK|GB)\s*:',meta['name'],re.I)
                country=prefix[1].upper() if prefix else country_for(meta,provider=entry)
                if country=='UK':country='GB'
                if not country and CHANNEL.search(meta['name']) and re.search(r'\b(sky sports|tnt sports?)\b',meta['name'],re.I) and not re.search(r'\b(?:nz|de|italy|germany|it)\b',meta['name'],re.I):country='GB'
                if not country and cat['id']=='m3u_uk':country='GB'
                rows.append(dict(provider=entry['key'],provider_id=entry['manifest']['id'],provider_label=entry['label'],
                                 resource_type=cat['type'],live_group='sports',live_country=country,
                                 meta=meta,channel=channel))
            return rows,None
        except Exception:return [],entry['label']
    with ThreadPoolExecutor(max_workers=4)as pool:results=list(pool.map(load,jobs))
    groups={};seen=set()
    for rows,_ in results:
        for variant in rows:
            identity=(variant['provider'],variant['resource_type'],variant['meta']['id'])
            if identity in seen:continue
            seen.add(identity)
            name=normalized(variant['meta']['name'],True)
            name=re.sub(r'\b(?:2160p|1080p|720p|480p)\b','',name)
            name=re.sub(r'^(?:au|ca|us|uk|gb)\s+','',name)
            name=re.sub(r'\btnt sports\b','tnt sport',name);name=re.sub(r'\s+',' ',name).strip()
            # Unknown-country channels remain separate to avoid mixing languages.
            key=('channel',variant['live_country'],name) if variant['channel']and variant['live_country']else identity
            group=groups.setdefault(key,dict(meta=dict(variant['meta']),provider=variant['provider'],resource_type=variant['resource_type'],
                live_group='sports',live_country=variant['live_country'],sports_variants=[],is_channel=variant['channel']))
            group['sports_variants'].append({k:v for k,v in variant.items()if k!='channel'})
    rows=list(groups.values())
    provider_order={entry['key']:index for index,entry in enumerate(store.providers())}
    for row in rows:
        row['sports_variants'].sort(key=lambda v:provider_order.get(v['provider'],999))
        primary=row['sports_variants'][0]
        row.update(meta=dict(primary['meta']),provider=primary['provider'],resource_type=primary['resource_type'])
        row['meta']['name']=re.sub(r'^(?:(?:\((?:FHD|HD|SD|UHD|4K)\)|4K|2160p|1080p)\s*:?\s*)+','',row['meta']['name'],flags=re.I)
        labels=list(dict.fromkeys(v['provider_label']for v in row['sports_variants']))
        prefix='Sports channel. Programming varies; check the schedule.' if row['is_channel']else 'Event from the provider catalogue. Streams may become available near the start time.'
        row['meta']['description']=prefix+'\nSources: '+', '.join(labels)+'\n\n'+row['meta'].get('description','')
    rows.sort(key=lambda r:(r['is_channel'],r['is_channel']and r['live_country']!='GB',r['meta']['name'].casefold(),r['live_country']))
    return rows,[error for _,error in results if error]

def streams(store, saved):
    enabled=[e for e in store.providers()if e.get('enabled',True)]
    def load(variant):
        entry=next((e for e in enabled if e['key']==variant['provider']),None)
        if entry is None:return []
        data=aggregate([entry],'stream',variant['resource_type'],variant['meta']['id'])
        result=[]
        for _,response,error in data:
            if error:continue
            for stream in response.get('streams',[]):
                if isinstance(stream,dict):result.append(dict(stream,name=entry['label']+' / '+stream.get('name','Live')))
        return result
    with ThreadPoolExecutor(max_workers=4)as pool:
        batches=list(pool.map(load,saved.get('sports_variants',[])[:8]))
    return [batch[index]for index in range(max((len(b)for b in batches),default=0))for batch in batches if index<len(batch)]
