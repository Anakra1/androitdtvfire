"""Verify packaged Pluto resolution without live credentials or network."""
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch
import copy,sys,tempfile
from urllib.parse import urlsplit,parse_qs
ROOT=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(dir=ROOT/'outputs',prefix='verified-live-pluto-unit-')as folder:
    with ZipFile(ROOT/'cbr0120.zip')as z:z.extractall(folder)
    sys.path.insert(0,str(Path(folder)/'plugin.video.stremio.bridge'))
    from resources.lib import pluto,m3u
    identity='5ad8d54be738977e2c310940';calls=[]
    data=dict(sessionToken='private-test-session',servers={'stitcher':'https://example.prd.pluto.tv/'},
              stitcherParams='sid=fresh&serverSideAds=true&country=GB',
              EPG=[dict(id=identity,stitched={'path':'/stitch/hls/channel/'+identity+'/master.m3u8'})])
    def fetch(url):calls.append(parse_qs(urlsplit(url).query));return copy.deepcopy(data)
    first=pluto.streams(identity,fetch)[0];second=pluto.streams(identity,fetch)[0]
    assert calls[0]['clientID']!=calls[1]['clientID']
    assert all(q['serverSideAds']==['true'] and q['channelSlug']==[identity]for q in calls)
    assert all('country'not in q and 'X-Forwarded-For'not in q for q in calls)
    assert 'X-Forwarded-For'not in first['behaviorHints']['proxyHeaders']['request']
    target=urlsplit(first['url']);q=parse_qs(target.query)
    assert target.path=='/v2/stitch/hls/channel/'+identity+'/master.m3u8'
    assert q['jwt']==['private-test-session']and q['serverSideAds']==['true']
    for bad in [dict(data,EPG=[]),dict(data,sessionToken=''),dict(data,servers={'stitcher':'https://pluto.tv.attacker.example/'}),dict(data,servers={'stitcher':'http://example.pluto.tv/'}),dict(data,EPG=[dict(id=identity,stitched={'path':'/other'})])]:
        try:pluto.streams(identity,lambda url:bad)
        except ValueError as e:assert 'private-test-session'not in str(e)
        else:raise AssertionError('Invalid session accepted')
    for bad in ('../channel','',None):
        try:pluto.streams(bad,lambda url:1/0)
        except ValueError:pass
        else:raise AssertionError('Invalid identity accepted')
    def fail(url):raise RuntimeError('private-test-session https://private.example/token')
    try:pluto.streams(identity,fail)
    except ValueError as e:assert 'private-test-session'not in str(e)and 'private.example'not in str(e)
    entry={'url':'https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_gb.m3u'}
    row=dict(id='m3u.'+'a'*24,tvg_id=identity,name='Pluto TV Kids',country='GB',streams=[{'url':'https://old.example/shared.m3u8'}])
    with patch.object(m3u,'load',return_value=[row]),patch.object(pluto,'streams',return_value=[first])as resolve:
        assert m3u.resource(entry,'catalog','tv','m3u_uk')['metas'][0]['id']==row['id']
        resolve.assert_not_called()
        assert m3u.resource(entry,'stream','tv',row['id'])=={'streams':[first]}
        resolve.assert_called_once_with(identity)
        assert m3u.resource({'url':'https://other.example/list.m3u'},'stream','tv',row['id'])=={'streams':row['streams']}
        assert resolve.call_count==1
    print('Pluto sessions: unique client per selection, ads enabled, native region, allowed host/channel checks, redacted errors, unchanged channel IDs and unaffected other M3U sources passed.')
