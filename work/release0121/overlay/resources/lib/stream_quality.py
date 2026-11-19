"""Classify provider-declared VOD quality without probing or guessing from URLs."""
import re
from collections import Counter

OPTIONS=(('hd','4K + 1080p'),('4k','4K only'),('1080p','1080p only'),('720p','720p only'),('1440p','1440p / 2K only'),('sd','SD (480p / 576p)'),('cam','CAM / TS / TC only'),('other','Other / unknown quality'),('all','Show all qualities'))
LABELS=dict(OPTIONS)
CAM=re.compile(r'(?<![a-z0-9])(?:hd[ ._-]?(?:cam|ts|tc)|cam(?:rip)?|telesync|telecine|tsrip|tc(?:rip)?|ts)(?![a-z0-9])',re.I)

def classify(stream):
    hints=stream.get('behaviorHints')
    values=[stream.get(k) for k in ('name','title','description','quality','resolution')]
    filenames=[stream.get('filename')]
    if isinstance(hints,dict):filenames.append(hints.get('filename'))
    values.extend(re.sub(r'(?i)\.ts$','',v) for v in filenames if isinstance(v,str))
    text=' '.join(str(v) for v in values if isinstance(v,(str,int))).replace('_',' ')
    if CAM.search(text):return 'cam'
    for quality,pattern in [('4k',r'\b(?:2160[pi]?|4k|uhd|3840\s*[x×]\s*2160)\b'),('1440p',r'\b(?:1440[pi]?|2k|2560\s*[x×]\s*1440)\b'),('1080p',r'\b(?:1080[pi]?|1920\s*[x×]\s*1080|fhd|full[ ._-]?hd)\b'),('720p',r'\b(?:720[pi]?|1280\s*[x×]\s*720)\b'),('sd',r'\b(?:480[pi]?|576[pi]?|sd)\b')]:
        if re.search(pattern,text,re.I):return quality
    return 'other'

def mode(value):
    return next((key for key,label in OPTIONS if value in (key,label)),'hd')

def select(streams,selection):
    selection=mode(selection);accepted={'4k','1080p'} if selection=='hd' else {selection}
    counts=Counter(classify(stream) for _,stream in streams)
    visible=[(source,stream) for source,stream in streams if selection=='all' or classify(stream) in accepted]
    return visible,dict(counts)

def summary(selection,shown,counts):
    total=sum(counts.values());hidden=total-shown;selection=mode(selection)
    line='{} of {} links shown'.format(shown,total)
    if hidden:
        line+=' · {} hidden'.format(hidden)
        if selection!='cam' and counts.get('cam'):line+=' ({} CAM/TS/TC)'.format(counts['cam'])
    return line

def details(selection,shown,counts):
    names={'4k':'4K','1080p':'1080p','720p':'720p','1440p':'1440p / 2K','sd':'SD','cam':'CAM / TS / TC','other':'Other / unknown'}
    lines=['Filter: '+LABELS[mode(selection)],summary(selection,shown,counts),'']
    lines += ['{}: {}'.format(names[key],counts.get(key,0)) for key in names]
    lines += ['', 'Quality is taken from provider labels and filenames; it is not a playback or picture-quality test.',
              'CAM / TS / TC sources are kept separate even when labelled 1080p or 4K.',
              'Change the filter or choose Show all qualities to see hidden links. Unknown quality is never assumed to be HD.']
    return '\n'.join(lines)
