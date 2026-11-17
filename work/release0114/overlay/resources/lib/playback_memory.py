"""Rank fresh links by confirmed Kodi playback; never save expiring URLs."""
import hashlib,json,os,time
from urllib.parse import urlsplit

def channel_key(channel):
    return hashlib.sha256(json.dumps([channel.get('provider'),channel.get('resource_type'),channel.get('meta',{}).get('id')]).encode()).hexdigest()[:32]

def stream_key(stream):
    parts=urlsplit(stream.get('url',''))
    return hashlib.sha256(json.dumps([parts.netloc,parts.path,stream.get('name','')]).encode()).hexdigest()[:32]

def path_key(path):
    return hashlib.sha256(path.split('|',1)[0].encode()).hexdigest()

class PlaybackMemory:
    def __init__(self,store):self.store=store;self.path=os.path.join(store.root,'confirmed-playback.json');self.pending=os.path.join(store.root,'playback-attempt.json')
    def read(self,path,default):
        try:return self.store.read(path,default)
        except (ValueError,OSError):return default
    def rank(self,channel,candidates):
        record=self.read(self.path,{}).get(channel_key(channel),{})
        good=record.get('stream')if 0<=time.time()-record.get('confirmed',0)<21600 else None
        return sorted(candidates,key=lambda pair:stream_key(pair[1])!=good)
    def variants(self,items):
        records=self.read(self.path,{})
        return sorted(items,key=lambda item:-records.get(channel_key(item),{}).get('confirmed',0) if 0<=time.time()-records.get(channel_key(item),{}).get('confirmed',0)<21600 else 0)
    def preferred(self,channel,stream):
        record=self.read(self.path,{}).get(channel_key(channel),{})
        return record.get('stream')==stream_key(stream) and 0<=time.time()-record.get('confirmed',0)<21600
    def prepare(self,channel,stream,path,context=None):
        value=dict(created=time.time(),channel=channel_key(channel),stream=stream_key(stream),path=path_key(path),
                   token=channel_key(channel)+stream_key(stream),context=context or {},name=channel.get('meta',{}).get('name','Live TV'))
        self.store.write(self.pending,value)
    def confirm(self,path,channel_name=''):
        value=self.read(self.pending,{})
        if not value or not 0<=time.time()-value.get('created',0)<120:return False
        matches=value['path']==path_key(path) or (path.startswith('pvr://') and value.get('context',{}).get('pvr') and channel_name==value['context'].get('name'))
        if not matches:return False
        records=self.read(self.path,{})
        records[value['channel']]=dict(stream=value['stream'],confirmed=time.time())
        records=dict(sorted(records.items(),key=lambda pair:pair[1].get('confirmed',0),reverse=True)[:1000])
        self.store.write(self.path,records);self.store.write(self.pending,{})
        return True
    def failed(self):
        value=self.read(self.pending,{})
        self.store.write(self.pending,{})
        if not value or not 0<=time.time()-value.get('created',0)<120:return None
        records=self.read(self.path,{})
        if records.get(value['channel'],{}).get('stream')==value['stream']:
            records.pop(value['channel'],None);self.store.write(self.path,records)
        return value
    def clear(self):self.store.write(self.pending,{})


def retry_context(store,identity,name,number):
    path=os.path.join(store.root,'pvr-retry.json');plan=store.read(path,{})
    auto=plan.get('channel')==identity and plan.get('queued') and 0<=time.time()-plan.get('created',0)<120
    if auto:
        plan['queued']=False;store.write(path,plan)
    else:
        plan=dict(channel=identity,created=time.time(),attempts=0,failed=[],queued=False);store.write(path,plan)
    return dict(pvr=True,id=identity,name=name,number=number,failed=plan.get('failed',[]))


def queue_retry(store,attempt):
    context=(attempt or {}).get('context',{})
    if not context.get('pvr'):return
    path=os.path.join(store.root,'pvr-retry.json');plan=store.read(path,{})
    if plan.get('channel')!=context['id'] or time.time()-plan.get('created',0)>120 or plan.get('attempts',0)>=3:return
    plan.update(name=context['name'],number=context['number'],requested=time.time())
    plan['failed']=list(dict.fromkeys(plan.get('failed',[])+[attempt['token']]))
    store.write(path,plan)


def poll_retry(store,player,rpc):
    path=os.path.join(store.root,'pvr-retry.json');plan=store.read(path,{})
    if not plan.get('requested') or plan.get('queued'):return
    if plan.get('attempts',0)>=3:store.write(path,{});return
    if time.time()-plan['requested']>15 or player.isPlaying():
        store.write(path,{});return
    try:
        channels=rpc('PVR.GetChannels',dict(channelgroupid='alltv',properties=['channel','channelnumber']))['channels']
        matches=[c for c in channels if c.get('label',c.get('channel'))==plan['name'] and c.get('channelnumber')==plan['number']]
        if len(matches)!=1:store.write(path,{});return
        plan.update(queued=True,requested=0,attempts=plan.get('attempts',0)+1);store.write(path,plan)
        rpc('Player.Open',{'item':{'channelid':matches[0]['channelid']}})
    except Exception:store.write(path,{})
