# CBR Android / Fire TV 0.10.4

CBR → Live TV → Live Sports now opens Football and other sport categories. Provider event listings are grouped by sport. A separate Sports channels folder contains networks whose programming varies. Matching channel names merge only for a known matching country; playback resolves original provider IDs and interleaves alternatives from enabled sources. Events from different providers and unknown-country channels remain distinct. Browsing uses cached metadata, not stored playback URLs. Favourites and recent entries retain their source variants.

When The Crew is installed and enabled, Football and the other supported sport pages include links to The Crew's corresponding sport menus. The Crew handles playback inside Kodi with its maintained players. These are sport-specific handoffs; Crew's internal streams are not copied into CBR's automatic fallback list. CBR does not install another Crew copy or execute downloaded Crew XML/Python in its own process.

DaddyLive's catalogue adapter is included but disabled by default and excluded from PVR. Its current player links failed actual playback tests and its player pages request browser verification. It is not advertised as working playback support. Experimental proxy code is excluded from the release. Existing working sports sources remain available.

Install **fulla023.zip** from the existing CBR Kodi source, then run **Program add-ons → CBR Setup Wizard → Full install / repair**, and restart Kodi. This installs video add-on 0.10.4 with wizard 0.2.3. The existing 0.1.2 skin and ARM engine/client components are retained. Existing private manifest URLs and disabled-source choices are preserved. The BBC feeds, UK TV group, hidden failed channels and movie home posters from 0.10.3 remain included. Windows release archives and rollback packages are unchanged.

The combined Football menus and playback of Sky Sports Main Event and Tenerife vs Ceuta were tested in Windows Kodi. The football feed tested was a Spanish broadcast; English commentary is not guaranteed. The Crew handoff is covered by routing tests against its official menu actions; native Crew playback and this release's playback on a physical Fire TV remain device-side tests. Crew is not installed on the Windows test PC.

Build and verification use G:\Codex. Private profiles and signed URLs stay in ignored outputs folders and must never be packaged or published.
