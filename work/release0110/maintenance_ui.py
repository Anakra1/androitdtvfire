"""Functions inserted into the Kodi video entry point by the release builder."""
def maintenance_menu():
    item('Check and repair CBR', 'maintenance_repair', artwork='settings')
    item('View CBR status and diagnostics', 'maintenance_report', artwork='settings')
    item('Test sources (catalogues and sample streams)', 'maintenance_test', artwork='settings')
    item('Back up CBR settings', 'maintenance_backup', artwork='settings')
    item('Restore CBR settings backup', 'maintenance_restore', artwork='settings')
    item('Organise channels and favourites on phone / PC', 'web_setup', artwork='live')
    item('Uninstall CBR safely', 'maintenance_uninstall', artwork='settings')
    finish()


def maintenance_action(action):
    from resources.lib import maintenance as care
    if action == 'maintenance_report':
        data = care.diagnose(STORE, ADDON.getAddonInfo('path'))
        DIALOG.textviewer('CBR status and diagnostics', json.dumps(data, indent=2))
    elif action == 'maintenance_repair':
        ensure_defaults(STORE, ADDON.getAddonInfo('path'))
        repo = 'repository.crb.android' if xbmc.getCondVisibility('System.Platform.Android') else 'repository.crb.windows'
        try:
            rpc('Addons.SetAddonEnabled', {'addonid':repo,'enabled':True})
        except Exception:
            DIALOG.ok(BRAND, 'The CBR repository is missing. Install it from your CBR source before enabling automatic updates. Your existing sources are kept.')
        care.request_repair(STORE)
        xbmc.executebuiltin('UpdateAddonRepos')
        DIALOG.ok('CBR repair requested', 'CBR will refresh public defaults, programme feeds and its TV guide while idle. Disabled sources and personal manifests are kept.\n\nFor automatic installation, select CBR Information → Versions → the CBR repository version once, and keep Kodi automatic updates enabled. Use View CBR status for details.')
    elif action == 'maintenance_test':
        import threading
        progress = xbmcgui.DialogProgress(); progress.create('Check CBR sources', 'Checking catalogues and small stream samples. No torrent downloads are started.')
        result = {}
        def work():
            try: result['data'] = care.test_sources(STORE)
            except Exception: result['error'] = True
        worker = threading.Thread(target=work, daemon=True); worker.start()
        monitor = xbmc.Monitor()
        while worker.is_alive() and not monitor.abortRequested():
            if progress.iscanceled():break
            worker.join(0.2)
        progress.close()
        if result.get('data'):
            labels = {e['key']:e['label'] for e in STORE.providers()}
            DIALOG.textviewer('Source test results', '\n\n'.join('{}: catalogue {} · stream {}'.format(labels.get(k,'Source'),care.status_text(v['catalogue']),care.status_text(v['stream'])) for k,v in result['data'].items())+'\n\nA responding sample is not a full playback or audio-language verification.')
        elif result.get('error'):
            DIALOG.ok(BRAND, 'Source tests could not finish. Your sources were kept.')
    elif action == 'maintenance_backup':
        personal = DIALOG.yesno('Include personal settings?', 'Include manifest URLs and saved channels for transfer to another device? Keep the resulting file private. Choose No for channel layout only.', yeslabel='Include personal settings', nolabel='Layout only')
        folder = DIALOG.browse(3, 'Save CBR backup folder', 'files')
        if folder:
            address = folder.rstrip('/\\') + '/cbr-settings-backup.json'
            data = care.export_backup(STORE, personal)
            with xbmcvfs.File(address, 'w') as target:target.write(json.dumps(data, indent=2))
            DIALOG.ok(BRAND, 'Backup saved. On another device use Restore CBR settings backup, or upload it through the paired PC setup page.')
    elif action == 'maintenance_restore':
        address = DIALOG.browse(1, 'Choose CBR settings backup', 'files', '.json')
        if address:
            with xbmcvfs.File(address) as source:raw = source.read(care.LIMIT + 1)
            if len(raw.encode('utf8')) > care.LIMIT:raise ValueError('Backup exceeds 4 MB.')
            data = json.loads(raw); files = care.validate_backup(data)
            if DIALOG.yesno('Restore CBR settings?', 'Replace these CBR settings: '+', '.join(files)+'. A copy of the current settings will be kept. Personal provider links may require renewal at the new location.'):
                care.restore_backup(STORE, data)
                DIALOG.ok(BRAND, 'Settings restored. CBR will rebuild its guide while idle. Restart Kodi to refresh all menus and TV listings.')
    elif action == 'maintenance_uninstall':
        try:rpc('Addons.ExecuteAddon', {'addonid':'script.crb.wizard','params':{'mode':'uninstall'}})
        except Exception:DIALOG.ok(BRAND, 'Install the latest CBR Setup Wizard, then choose Uninstall CBR there.')
    maintenance_menu()
