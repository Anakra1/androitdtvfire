"""Readable, cancellable Kodi tools backed by the existing CBR stores."""
import json,os,threading,time
import xbmc,xbmcaddon,xbmcgui,xbmcvfs
from . import maintenance as care,tv_health,pvr
from .tv_repair import RepairTask

def run_job(title,work,task=None):
    result={};state=dict(percent=0,message='Preparing…');stop=threading.Event()
    def progress(done,total,label):state.update(percent=int(100*done/max(1,total)),message='{}/{}: {}'.format(done,total,label))
    def worker():
        try:result['value']=work(stop,progress)
        except InterruptedError:result['cancelled']=True
        except Exception:result['error']=True
    dialog=xbmcgui.DialogProgress();dialog.create(title,'Preparing…')
    monitor=xbmc.Monitor();started=time.monotonic();last_heartbeat=started;thread=threading.Thread(target=worker,daemon=True)
    thread.start()
    try:
        while thread.is_alive():
            if dialog.iscanceled()or monitor.abortRequested():
                stop.set()
                if task:task.cancel()
            if task:
                if time.monotonic()-last_heartbeat>2:
                    task.heartbeat();last_heartbeat=time.monotonic()
                dialog.update(task.progress,task.elapsed_message())
            else:
                elapsed=int(time.monotonic()-started)
                dialog.update(state['percent'],('Stopping after the current network request…'if stop.is_set()else state['message'])+' | {}s elapsed'.format(elapsed))
            if monitor.abortRequested():return {'cancelled':True}
            thread.join(0.2)
    finally:dialog.close()
    result['cancelled']=result.get('cancelled',False)or stop.is_set()
    return result

def repair(store,addon_path,rpc):
    dialog=xbmcgui.Dialog()
    if xbmc.Player().isPlaying():dialog.ok('Check and repair TV','Stop playback before repairing TV.');return
    task=RepairTask(addon_path,store.root,xbmcvfs.translatePath('special://profile/addon_data/pvr.iptvsimple/'))
    result=run_job('Check and repair TV',lambda stop,progress:task.run(),task)
    if result.get('cancelled'):dialog.ok('TV repair cancelled','Stopped. Previous usable channel and guide files are kept.');return
    if result.get('error'):dialog.ok('TV repair needs attention','TV repair did not finish. Previous usable files were kept. Open TV status for details.');return
    value=result['value'];message='{} channels ready; {} have genuine programme listings.\n'.format(value['channels'],value.get('guide_channels',0))
    if value.get('failed'):message+='Sources needing attention: '+', '.join(value['failed'])+'\n'
    if value.get('retained'):message+='Previous cached channels retained for: '+', '.join(value['retained'])+'\n'
    if value.get('guide_failed'):message+='Programme feeds needing attention: '+', '.join(value['guide_failed'])+'\n'
    message+='Unavailable programme information does not block live playback.'
    if not xbmc.Player().isPlaying():
        try:
            rpc('Addons.GetAddonDetails',{'addonid':'pvr.iptvsimple','properties':['enabled']})
            rpc('Addons.SetAddonEnabled',{'addonid':'pvr.iptvsimple','enabled':False})
            try:pvr.configure_instance(task.iptv_profile,'special://profile/addon_data/plugin.video.stremio.bridge/pvr/channels.m3u','special://profile/addon_data/plugin.video.stremio.bridge/pvr/guide.xml',refresh_guide=True)
            finally:rpc('Addons.SetAddonEnabled',{'addonid':'pvr.iptvsimple','enabled':True})
        except Exception:message+='\nKodi TV client needs attention. Open Kodi TV setup.'
    dialog.textviewer('TV repair results',message)

def channels(store,test=False):
    dialog=xbmcgui.Dialog()
    if test:
        result=run_job('Check channel links',lambda stop,progress:tv_health.test_channels(store,stop,progress))
        if result.get('error'):dialog.ok('Channel checks','Checks could not finish. Existing results and channels were kept.');return
        if result.get('value'):
            value=result['value'];dialog.ok('Channel checks','Checked {} of {} channels{}. Open Channel status to see individual results. Samples do not confirm full playback.'.format(value['checked'],value['total'],' (cancelled)'if result.get('cancelled')else ''))
    else:
        query=dialog.input('Channel name (leave blank for all channels)')
        dialog.textviewer('Channel status',tv_health.text_report(store,query))

def updates(store,addon_path,rpc):
    from .update_status import latest
    platform='android'if xbmc.getCondVisibility('System.Platform.Android')else 'windows'
    runtime=care.runtime_snapshot(rpc,xbmcvfs.translatePath('special://database/'),platform)
    result=run_job('Check CBR component updates',lambda stop,progress:latest(platform))
    if result.get('cancelled'):return
    if result.get('error'):
        with open(os.path.join(addon_path,'resources','defaults','release-components.json'),encoding='utf8')as source:expected=json.load(source)
        xbmcgui.Dialog().textviewer('Installed CBR components',tv_health.component_report(runtime,expected)+'\n\nThe online repository could not be checked. The latest column above is the expected version for this installed release. Versions above refer to this installed release, not a verified latest online version.');return
    store.write(os.path.join(store.root,'maintenance-runtime.json'),runtime)
    xbmc.executebuiltin('UpdateAddonRepos')
    text=tv_health.component_report(runtime,result['value'])+'\n\nSkin and Setup Wizard are optional for addon-only use. Kodi installs repository updates; its update settings and each component Auto-update switch still apply. Keep the CBR repository enabled.'
    xbmcgui.Dialog().textviewer('CBR component versions',text)
    if xbmcgui.Dialog().yesno('Open available updates?','Open Kodi’s available-updates screen to select any CBR components needing an update?'):
        xbmc.executebuiltin('ActivateWindow(AddonBrowser,addons://outdated/)')
