"""Local Command UI state. Stores catalogue identity and progress, never resolved streams."""
import datetime
import hashlib
import json
import os
import sqlite3
import time
import math,re
from contextlib import contextmanager

META_FIELDS=('id','type','name','description','overview','poster','thumbnail','background','logo','releaseInfo','imdbRating','runtime','genres','season','episode','seriesName')
VIDEO_FIELDS=('id','title','name','season','episode','released','overview','thumbnail')

def clean_meta(meta):
    result={k:meta[k] for k in META_FIELDS if k in meta}
    if isinstance(meta.get('videos'),list):
        result['videos']=[{k:v[k] for k in VIDEO_FIELDS if k in v} for v in meta['videos'] if isinstance(v,dict) and v.get('id')]
    return result

def identity(kind,media_id):return kind+':'+str(media_id)
def fingerprint(path):return hashlib.sha256(path.split('|')[0].encode('utf-8')).hexdigest()

def next_episode(meta,current_id,now=None):
    now=now or datetime.datetime.now(datetime.timezone.utc)
    def number(v):
        try:return int(v.get('season') or 0),int(v.get('episode') or 0)
        except (ValueError,TypeError):return (0,0)
    def released(v):
        stamp=v.get('released')
        if not stamp:return True
        try:
            dt=datetime.datetime.fromisoformat(stamp.replace('Z','+00:00'))
            if dt.tzinfo is None:dt=dt.replace(tzinfo=datetime.timezone.utc)
            return dt<=now
        except (ValueError,TypeError):return False
    videos=[v for v in meta.get('videos',[]) if v.get('id') and number(v)[1]>0]
    current=next((v for v in videos if v['id']==current_id),None)
    if current is None:return None
    following=[v for v in videos if number(v)>number(current) and (number(current)[0]==0 or number(v)[0]>0) and released(v)]
    return min(following,key=number) if following else None

def episode_meta(meta,video):
    result=dict(meta,seriesName=meta.get('seriesName') or meta.get('name',''),
                name=video.get('title') or video.get('name') or 'Episode',season=video.get('season'),episode=video.get('episode'))
    if video.get('thumbnail'):result['thumbnail']=video['thumbnail']
    return clean_meta(result)

def upcoming(meta,now=None):
    now=now or datetime.datetime.now(datetime.timezone.utc)
    values=[meta.get(k) for k in ('startTime','start','start_time','released','releaseInfo')]
    values.extend(re.findall(r'\d{4}-\d{2}-\d{2}[T ][0-9:.]+(?:Z|[+-]\d\d:\d\d)?',meta.get('description','')))
    for value in values:
        if not value:continue
        try:
            if isinstance(value,(float,int)):
                dt=datetime.datetime.fromtimestamp(value/1000 if value>1e11 else value,datetime.timezone.utc)
            else:
                dt=datetime.datetime.fromisoformat(str(value).replace('Z','+00:00'))
                if dt.tzinfo is None:dt=dt.replace(tzinfo=datetime.timezone.utc)
            return dt>now
        except (ValueError,TypeError,OverflowError,OSError):continue
    text=str(meta.get('releaseInfo',''))+' '+meta.get('description','')
    match=re.search(r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4}).*?(\d{1,2}):(\d{2})\s*UTC',text,re.I)
    if match:
        day,month,year,hour,minute=match.groups()
        months={v:i+1 for i,v in enumerate(('jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'))}
        try:return datetime.datetime(int(year),months[month.lower()],int(day),int(hour),int(minute),tzinfo=datetime.timezone.utc)>now
        except ValueError:return False
    return False

class CommandState:
    def __init__(self,root):
        os.makedirs(root,exist_ok=True)
        self.path=os.path.join(root,'command.sqlite3')
        with self.connect() as c:
            c.executescript('CREATE TABLE IF NOT EXISTS progress (identity TEXT PRIMARY KEY, kind TEXT, media_id TEXT, meta TEXT, position REAL, duration REAL, completed INTEGER, updated REAL); CREATE TABLE IF NOT EXISTS saved (collection TEXT, identity TEXT, payload TEXT, updated REAL, PRIMARY KEY(collection,identity));')

    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.path,timeout=10);c.row_factory=sqlite3.Row
        try:
            yield c;c.commit()
        except Exception:
            c.rollback();raise
        finally:c.close()

    def record(self,kind,media_id,meta,position,duration,ended=False):
        if kind not in ('movie','series') or not media_id:return
        try:position=float(position);duration=float(duration)
        except (ValueError,TypeError):return
        if not math.isfinite(position) or not math.isfinite(duration) or not duration or position>duration+30:return
        position=max(0,position);duration=max(0,duration)
        if not duration:return
        complete=position/duration>=.9
        with self.connect() as c:
            c.execute('INSERT OR REPLACE INTO progress VALUES (?,?,?,?,?,?,?,?)',(identity(kind,media_id),kind,media_id,json.dumps(clean_meta(meta)),min(position,duration),duration,int(complete),time.time()))

    def get(self,kind,media_id):
        with self.connect() as c:r=c.execute('SELECT * FROM progress WHERE identity=?',(identity(kind,media_id),)).fetchone()
        return self.unpack(r) if r else None

    @staticmethod
    def unpack(row):
        value=dict(row);value['meta']=json.loads(value['meta']);return value

    def continuing(self):
        with self.connect() as c:rows=c.execute('SELECT * FROM progress ORDER BY updated DESC').fetchall()
        out=[];seen=set()
        for row in rows:
            r=self.unpack(row);group=identity(r['kind'],r['meta'].get('id') if r['kind']=='series' else r['media_id'])
            if group in seen:continue
            seen.add(group)
            if r['completed']:
                video=next_episode(r['meta'],r['media_id']) if r['kind']=='series' else None
                if video:
                    r.update(media_id=video['id'],meta=episode_meta(r['meta'],video),position=0,next_ready=True)
                    out.append(r)
            elif r['position']>=30 and r['duration']-r['position']>10:out.append(r)
        return out[:30]

    def remove_progress(self,kind,media_id):
        with self.connect() as c:c.execute('DELETE FROM progress WHERE identity=?',(identity(kind,media_id),))

    def saved(self,collection):
        with self.connect() as c:rows=c.execute('SELECT identity,payload FROM saved WHERE collection=? ORDER BY updated DESC',(collection,)).fetchall()
        return [dict(identity=r['identity'],payload=json.loads(r['payload'])) for r in rows]

    def contains(self,collection,key):
        with self.connect() as c:return c.execute('SELECT 1 FROM saved WHERE collection=? AND identity=?',(collection,key)).fetchone() is not None

    def toggle(self,collection,key,payload):
        with self.connect() as c:
            if c.execute('SELECT 1 FROM saved WHERE collection=? AND identity=?',(collection,key)).fetchone():
                c.execute('DELETE FROM saved WHERE collection=? AND identity=?',(collection,key));return False
            c.execute('INSERT INTO saved VALUES (?,?,?,?)',(collection,key,json.dumps(payload),time.time()));return True
