"""Read-only visual QA fixture; never connects to the user's Kodi profile."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json,threading

assets=Path(__file__).resolve().parent/'overlay/resources/setup'
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        data=None
        if self.path=='/api/sources':data={'sources':[{'key':'public','label':'Pluto TV UK','enabled':True,'group':'internet','guide_country':'GB','provider':'Pluto TV UK','url':'https://public.example/pluto.m3u','health':{'checked':1,'catalogue':'ready','stream':'sample_responded'}}]}
        elif self.path=='/api/programmes':data={'settings':{'feeds':[]},'countries':{'GB':'United Kingdom'},'status':{}}
        elif self.path=='/api/pvr':data={'config':{'selected':[],'favourites_first':True},'groups':['Favourites','UK TV','Internet TV','Sports'],'sources':[],'status':{'state':'ready','channels':614,'guide_channels':478},'channels':[{'id':'cbr.'+'a'*24,'name':'BBC One','number':1,'groups':['UK TV'],'visible':True,'favourite':True}]}
        elif self.path=='/api/diagnostics':data={'version':'0.11.0','runtime':{'automatic_install':True,'components':{'plugin.video.stremio.bridge':{'version':'0.11.0','enabled':True,'repository_linked':True}}},'channels':{'visible':614},'tv':{'guide_channels':478},'player':{'explanation':'The torrent engine starts when playback needs it.'},'repair':{'state':'ready'},'sources':[{'label':'Pluto TV UK','enabled':True,'health':{'catalogue':'ready','stream':'sample_responded'}}],'errors':[]}
        if data is not None:raw=json.dumps(data).encode();mime='application/json'
        else:
            names={'/':'index.html','/setup.js':'setup.js','/style.css':'style.css'}
            if self.path not in names:self.send_error(404);return
            path=assets/names[self.path];raw=path.read_bytes();mime={'.html':'text/html','.js':'text/javascript','.css':'text/css'}[path.suffix]
            if self.path=='/':raw=raw.replace(b'<h1>Source setup</h1>',b'<h1>Source setup preview</h1>')
        self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
server=ThreadingHTTPServer(('127.0.0.1',8769),Handler)
timer=threading.Timer(180,server.shutdown);timer.daemon=True;timer.start()
print('Read-only preview ready on localhost:8769',flush=True)
try:server.serve_forever()
finally:server.server_close()
