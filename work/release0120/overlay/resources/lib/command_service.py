"""Track confirmed CBR playback without touching unrelated player sessions."""
import os,time
import xbmc,xbmcgui
from .command_state import CommandState,fingerprint

class CommandTracker:
    def __init__(self,store):
        self.store=store;self.state=CommandState(store.root);self.active=None;self.last_write=0
        self.pending=os.path.join(store.root,'command-pending.json')
        self.window=xbmcgui.Window(10000)

    def started(self,player):
        previous=self.active
        self.window.clearProperty('CBR.PlaybackStatus')
        self.window.clearProperty('CBR.PlaybackFingerprint')
        pending=self.store.read(self.pending,{})
        self.active=None
        if not pending and previous:
            try:
                if fingerprint(player.getPlayingFile())==previous['fingerprint']:
                    self.active=previous;self.window.setProperty('CBR.PlaybackFingerprint',previous['fingerprint']);return
            except Exception:pass
        if not pending:
            pending_live=self.store.read(os.path.join(self.store.root,'live-pending.json'),{})
            if pending_live and time.time()-pending_live.get('created',0)<120:
                pending=dict(kind='live',media_id='',meta={},resume=0,**{k:v for k,v in pending_live.items() if k in ('fingerprint','created')})
        if not pending or time.time()-pending.get('created',0)>180:return
        try:
            if fingerprint(player.getPlayingFile())!=pending.get('fingerprint'):return
        except Exception:return
        self.store.write(self.pending,{})
        self.active=dict(pending,position=0,duration=0)
        self.window.setProperty('CBR.PlaybackFingerprint',pending['fingerprint'])
        if pending.get('resume',0)>0:
            try:player.seekTime(float(pending['resume']))
            except Exception:pass
        self.window.clearProperty('CBR.PlaybackStatus')

    def event(self,event):
        if self.active:
            a=self.active
            self.state.record(a['kind'],a['media_id'],a['meta'],a['position'],a['duration'],event=='ended')
            self.active=None
        self.window.clearProperty('CBR.PlaybackStatus')
        self.window.clearProperty('CBR.PlaybackFingerprint')

    def poll(self,player):
        if not self.active:
            try:
                requested=float(self.window.getProperty('CBR.PlaybackRequested') or 0)
                if requested and time.time()-requested>30:self.window.clearProperty('CBR.PlaybackStatus')
            except Exception:pass
            return
        a=self.active
        try:
            if not player.isPlayingVideo() or fingerprint(player.getPlayingFile())!=a['fingerprint']:return
            position=player.getTime()
            if a.get('resume',0)>0 and position<max(0,a['resume']-5) and time.time()-a['created']<15:
                return  # Cancelling before Kodi finishes seeking must preserve the old bookmark.
            a['position']=position;a['duration']=player.getTotalTime();a['resume']=0
            self.window.setProperty('CBR.PlaybackStatus','Buffering…' if xbmc.getCondVisibility('Player.Caching') else '')
            if time.monotonic()-self.last_write>=5:
                self.state.record(a['kind'],a['media_id'],a['meta'],a['position'],a['duration'])
                self.last_write=time.monotonic()
        except Exception:pass

    def close(self):self.event('stopped')
