from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).parent
SKIN = ROOT / 'skin.crimsonbloodrequiem'
HOME = SKIN / 'xml' / 'Home.xml'

old = ET.parse(SKIN / 'addon.xml').getroot()
skin_extension = old.find("extension[@point='xbmc.gui.skin']")
requires = ET.Element('requires')
ET.SubElement(requires, 'import', addon='xbmc.gui', version='5.17.0')
ET.SubElement(requires, 'import', addon='plugin.video.stremio.bridge', version='0.5.3')
root = ET.Element('addon', id='skin.crimsonbloodrequiem', version='0.1.0',
                  name='Crimson Blood Requiem', **{'provider-name': 'CRB Project'})
root.append(requires)
root.append(skin_extension)
metadata = ET.SubElement(root, 'extension', point='xbmc.addon.metadata')
ET.SubElement(metadata, 'platform').text = 'all'
ET.SubElement(metadata, 'license').text = 'GPL-2.0-or-later; CC BY-SA 4.0 where applicable'
assets = ET.SubElement(metadata, 'assets')
ET.SubElement(assets, 'icon').text = 'resources/icon.png'
ET.SubElement(assets, 'fanart').text = 'resources/fanart.jpg'
ET.SubElement(metadata, 'summary', lang='en_GB').text = 'A crimson space-command skin for Kodi, built for CRB.'
ET.SubElement(metadata, 'description', lang='en_GB').text = (
    'Crimson Blood Requiem brings a dark space-fleet backdrop, deep red accents, '
    'and direct home-screen access to CRB movies, TV series, Live TV and search. '
    'Based on Kodi Estuary and designed to keep Kodi library, settings and other add-ons available.'
)
ET.SubElement(metadata, 'disclaimer', lang='en_GB').text = (
    'An independent community skin. Kodi and Estuary are trademarks and software of their respective owners.'
)
ET.indent(root, space='  ')
ET.ElementTree(root).write(SKIN / 'addon.xml', encoding='utf-8', xml_declaration=True)

palette = {
    'primary_background': 'FF280711',
    'secondary_background': 'AA591126',
    'dialog_tint': 'FF17090D',
    'background': 'FF050509',
    'bg_image': 'FFFFFFFF',
    'bg_overlay': '42FFFFFF',
    'black': 'FF000000',
    'white': 'FFF4E9EC',
    'grey': 'FFAA9AA0',
    'blue': 'FFE34862',
    'red': 'FFE34862',
    'button_focus': 'FF83152A',
    'button_alt_focus': 'C86A1025',
    'text_shadow': 'CC000000',
    'border_alpha': '75FFFFFF',
    'disabled': '60FFFFFF',
    'selected': 'FFFF536D',
    'invalid': 'FFFF253E',
}
colors = ET.Element('colors')
for key, value in palette.items():
    ET.SubElement(colors, 'color', name=key).text = value
ET.indent(colors, space='  ')
for color_file in (SKIN / 'colors').glob('*.xml'):
    ET.ElementTree(colors).write(color_file, encoding='utf-8', xml_declaration=True)

home = HOME.read_text(encoding='utf-8-sig')
home = home.replace('<imagepath background="true" colordiffuse="bg_overlay">$VAR[HomeFanartVar]</imagepath>',
                    '<imagepath background="true" colordiffuse="bg_overlay">backgrounds/crb-space.jpg</imagepath>')
entries = [
    ('CRB Movies', 'CRB movie catalogues and collections',
     'ActivateWindow(Videos,plugin://plugin.video.stremio.bridge/,return)', 'movies'),
    ('CRB TV Series', 'Browse series, seasons and episodes',
     'ActivateWindow(Videos,plugin://plugin.video.stremio.bridge/?action=catalogues&amp;media_type=series,return)', 'series'),
    ('CRB Live TV', 'TV channels, internet TV and live sports',
     'ActivateWindow(Videos,plugin://plugin.video.stremio.bridge/?action=live,return)', 'live'),
    ('Search Movies', 'Find a movie across connected catalogues',
     'ActivateWindow(Videos,plugin://plugin.video.stremio.bridge/?action=search&amp;media_type=movie,return)', 'search'),
    ('Search TV Series', 'Find a series across connected catalogues',
     'ActivateWindow(Videos,plugin://plugin.video.stremio.bridge/?action=search&amp;media_type=series,return)', 'search'),
    ('Search Live TV', 'Find live channels and sports',
     'ActivateWindow(Videos,plugin://plugin.video.stremio.bridge/?action=search&amp;live_only=true,return)', 'search'),
    ('CRB Setup Wizard', 'Change the CRB interface or restore Kodi',
     'RunAddon(script.crb.wizard)', 'wizard'),
]
items = []
for index, (label, summary, action, icon) in enumerate(entries):
    items.append('''\t\t\t\t\t<item>
\t\t\t\t\t\t<label>{}</label>
\t\t\t\t\t\t<label2>{}</label2>
\t\t\t\t\t\t<onclick>{}</onclick>
\t\t\t\t\t\t<property name="menu_id">$NUMBER[9000]</property>
\t\t\t\t\t\t<thumb>crb-{}.png</thumb>
\t\t\t\t\t\t<property name="id">crb_{}</property>
\t\t\t\t\t</item>'''.format(label, summary, action, icon, index))
insert = '\n'.join(items) + '\n'
needle = '\t\t\t\t\t<content>\n\t\t\t\t\t\t<item>\n\t\t\t\t\t\t\t<label>$LOCALIZE[342]</label>'
if needle in home:
    home = home.replace(needle, '\t\t\t\t\t<content>\n' + insert + '\t\t\t\t\t\t<item>\n\t\t\t\t\t\t\t<label>$LOCALIZE[342]</label>', 1)
elif '<label>CRB Movies</label>' not in home:
    raise RuntimeError('Could not locate the Estuary home menu insertion point.')
HOME.write_text(home, encoding='utf-8')

license_path = SKIN / 'LICENSE.txt'
license_text = license_path.read_text(encoding='utf-8-sig')
if 'Crimson Blood Requiem modifications' not in license_text:
    with license_path.open('a', encoding='utf-8') as license_file:
        license_file.write('\n\nCrimson Blood Requiem modifications\n')
        license_file.write('The CRB-specific artwork and modifications are licensed GPL-2.0-or-later.\n')
        license_file.write('Estuary code remains GPL-2.0; Estuary artwork remains CC BY-SA 4.0.\n')
        license_file.write('Estuary by phil65 and Kodi contributors; source: https://github.com/xbmc/skin.estuary/\n')

print('Prepared the CRB Estuary-based skin, palette, backdrop and seven home entries.')
