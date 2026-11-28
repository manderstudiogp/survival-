# Paperland Trails: Oregon Wilds

A cozy papercraft survival game that runs in the browser.

## Play in a browser (GitHub Pages)
1. Upload these files to a GitHub repository (keep the `.github` folder).
2. Repository **Settings → Pages → Build and deployment**: Source = *Deploy from a branch*, Branch = `main`, folder `/ (root)`. Save.
3. After a minute the game is at `https://<your-name>.github.io/<repo-name>/`.

Extra addresses: add `#hollow` for Ember Hollow only (quick test map), `#gorge` for the gorge test map.

## Android app (APK)
Every push to `main` builds an APK automatically:
1. Open the repository's **Actions** tab → *Build Android APK* → the latest run.
2. Download **paperland-trails-apk** at the bottom, unzip, and copy `app-debug.apk` to your phone.
3. Open it on the phone and allow installing from this source.

## Playing together online
Open the menu (☰, top left) → **Online** → *Host a game*, then *Copy invite* and send it. Up to 4 players.
Friends open the link on their own device (browser or the Android app; both play together) and press *Join*.
Online play is peer-to-peer and needs internet. Codes start with `pn-`.

- **The host runs the world:** time of day, weather and snow, and all the animals. Everyone sees the same thing.
  Animals react to every player (bears to whoever is close, wolves to the easiest catch with food), and everyone
  hears when someone is knocked down, faints or gets back up.
- **The invite carries the host's map**, e.g. `…#hollow.pn-k3m9qa`. A player on another map is moved over.
- **Shared storage:** the camp crates and the van hold one shared load for everyone.
- **One camp each:** others see your tent and fire with your name, or "carrying camp" when it's packed.
  Others' lit fires warm you and their tents shelter you.

## Dev tools (maps, Time, Light, Weather)
Only the dev sees the map picker and the Time, Light and Weather tabs. Unlock them on a device with the
password box on the start screen (lock again with the same button). Everyone else plays the main map unless
invited to another, with the standard look; *Lighter graphics* is there for slow devices.
Change the password: `python3 tools/set_dev_password.py "new password"` (only a hash is stored in the file).

## Testing online play without two devices
`python3 tools/online-test/two_hikers.py` runs two players in one headless Chrome on Ember Hollow
(no internet needed) and checks joining, map, dev lock, movement, camps, chat, weather, animals,
crates, the van, wolves' choice of prey, a bear knockout and leaving. See the top of the file for setup.
