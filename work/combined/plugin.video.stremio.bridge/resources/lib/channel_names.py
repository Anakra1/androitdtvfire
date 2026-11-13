"""Conservative channel spelling aliases; countries and timeshifts stay distinct."""
import re
import unicodedata


def compact(name):
    value = unicodedata.normalize('NFKC', str(name)).casefold().replace('&', 'and')
    value = re.sub(r'\b(?:fhd|uhd|hd|sd|4k|hevc)\b', '', value)
    # EPG feeds often append HD directly to the display name.
    value = re.sub(r'(?:fhd|uhd|hd|sd)$', '', value.strip())
    return re.sub(r'[^\w+]', '', value)


def uk_guide_name(name):
    value = compact(name)
    aliases = {
        'cartoonnet': 'cartoonnetwork', 'cartoonnetwrk': 'cartoonnetwork',
        'foodnetwrk': 'foodnetwork', 'discoverychannel': 'discovery',
        'dischistory': 'discoveryhistory', 'discturbo': 'discoveryturbo',
        'discscience': 'discoveryscience', 'discoverysci': 'discoveryscience',
        'discoveryid': 'id', 'bbconelondon': 'bbconelon',
        'bbconewales': 'bbconewal', 'bbconewmid': 'bbconewm',
        'bbctwowales': 'bbctwowal', 'bbctwonorthernireland': 'bbctwoni',
        'skyscfihor': 'skyscifiandhorror',
        'skyscfihorror': 'skyscifiandhorror',
    }
    for short, full in [('action', 'action'), ('cricket', 'cricket'), ('f1', 'f1'),
                        ('golf', 'golf'), ('mix', 'mix'), ('news', 'news'),
                        ('pl', 'premierleague'), ('racing', 'racing'),
                        ('tennis', 'tennis'), ('fball', 'football'), ('mainev', 'mainevent')]:
        aliases['skysp' + short] = 'skysports' + full
        aliases['skysport' + full] = 'skysports' + full
    for genre in ('action', 'adventure', 'drama', 'family', 'greats', 'premiere', 'thriller'):
        aliases['skycinema' + genre] = 'sky' + genre
    # Apply aliases before +1 without ever removing the timeshift.
    suffix = '+1' if value.endswith('+1') else ''
    base = value[:-2] if suffix else value
    return aliases.get(base, base) + suffix
