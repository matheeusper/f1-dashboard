# Painel F1 25: telemetry dashboard and race engineer with voice

[Português](README.md) · **English**

A car-cluster style dashboard for **F1 25**, built for a vertical second monitor, a tablet or your phone. It comes with a **race engineer who talks to you over the radio, in English or Portuguese**:

- analyses every corner, learns your habits and tracks your progress;
- runs your pit strategy;
- answers your steering wheel buttons.

<p align="center">
  <img src="docs/painel.jpg" alt="Dashboard on the vertical monitor" width="32%">
  <img src="docs/analise.jpg" alt="Corner analysis with telemetry comparison" width="32%">
  <img src="docs/celular.jpg" alt="Compact layout on a phone in landscape" width="32%">
</p>

> Fan project, not affiliated with EA, Codemasters or Formula 1. It only uses the official UDP telemetry the game sends: it doesn't touch the game and doesn't use mods. The screenshots above show the Portuguese interface.

## What it does

- **Dashboard:**
  - RPM and shift lights, gear, speed, pedals, steering and G-force;
  - DRS or active aero;
  - lap times, sectors and delta to your best lap;
  - ERS and fuel;
  - tyre temperature, pressure and wear, brakes, damage and power unit.
- **Engineer with a natural voice:** only talks on the straights, calls you by name, has a team radio sound and changes tone with the situation.
- **Corner-by-corner analysis:**
  - tells you where you lost time and why, for example *"In turn 3 you braked at 131 metres, the record brakes at 90"*;
  - reminds you before that corner on the next lap;
  - has a telemetry chart comparing your lap with your record.
- **Memory:** record and ideal lap per track, habits that keep repeating, a summary of each session and the **Progress** page with charts.
- **Race:** replaces the in-game engineer. Uses the drivers' names and calls box box, the pit limiter, rival stops, undercut and overcut, safety car, penalties, weather and the drop zone in qualifying.
- **Pit strategist:** learns what a stop costs at each track and predicts where you'll rejoin.
- **Timing tower (key P):** the whole grid with gaps, intervals, tyre compound and age, stops, last and best lap.
- **Steering wheel buttons:** ask about tyres, gaps, fuel, strategy and setup without taking your hands off the wheel.
- **Time Trial:** single-corner practice mode, daily goals and achievements.
- **Setup:** detects understeer and oversteer and suggests changes. When you change the setup in the garage, the analysis restarts by itself.
- **Layouts:** portrait monitor, landscape monitor or tablet, and phone (compact, large text).
- **Two languages:** English and Portuguese, for the menu, the dashboard and the engineer's voice.

## Installation (Windows)

### Easiest way: download the executable

Nothing to install: it's a single file.

1. On the **[Releases](https://github.com/matheeusper/f1-dashboard/releases/latest)** page, download **`PainelF1.exe`** and put it in a folder of your own, for example `Documents\PainelF1`.
2. **Set up the game** (only once): see the table in step 3 below.
3. Double-click **`PainelF1.exe`** and choose from the menu:
   - **Start dashboard**: receives the game telemetry and opens the dashboard;
   - **Demo: simulated race** and **Demo: Time Trial**: see everything working without the game;
   - **Dashboard on phone or tablet**: shares the dashboard on your local network and shows the address to type on the device.

The menu follows your Windows language. To switch, click **🌐 English / Português** at the bottom of the menu, or use **⚙ SETTINGS → LANGUAGE** on the dashboard.

After you choose a mode, the menu goes to the taskbar. From there it shows the status and has buttons to bring the dashboard to the front, open the Progress page or change mode. **Closing that window shuts the dashboard down.**

The first time, Windows may show *"Windows protected your PC"*, because the program isn't digitally signed. Click **More info → Run anyway**.

Your data lives in the `dados` folder, created next to the `.exe`. To update, just replace `PainelF1.exe` and keep that folder.

### Running from source (with uv)

1. **Install [uv](https://docs.astral.sh/uv/)**: paste this into PowerShell and close the window when it's done.
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
   No need to install Python: uv downloads the right version by itself.
2. **Get the project:** **Code → Download ZIP** on this page (and extract it), or:
   ```powershell
   git clone https://github.com/matheeusper/f1-dashboard.git
   ```
3. **Set up the game** (only once). In F1 25, go to **Settings → Telemetry**:

   | Option | Value |
   |---|---|
   | UDP Telemetry | On |
   | UDP Broadcast Mode | Off |
   | UDP IP Address | 127.0.0.1 |
   | UDP Port | 20777 |
   | UDP Send Rate | 60 Hz |
   | UDP Format | 2025 or 2026 (both work) |

4. **Double-click `Painel F1 25.bat`.** It opens the same menu as the executable. The first time, uv sets up the environment, which takes about a minute.
5. Choose **Start dashboard**: it opens by itself, full screen on the vertical monitor. If it doesn't open on the right monitor, drag the window there and press **F11**.
6. Start the game and go out on track: the dashboard lights up by itself.

**Linux or macOS:** run `uv run server.py --menu` (or `uv run server.py --abrir`) in the project folder.

### Try it without the game

In the menu, choose **Demo: simulated race** (rivals, pit stops, safety car and driving mistakes) or **Demo: Time Trial** (practice mode and goals). The demo saves to a separate history, so it doesn't mix with your laps.

## Race engineer

The engineer talks to you and shows the messages in the **ENGINEER RADIO** strip. He only talks on the straights, never under braking or mid-corner. Urgent warnings, like damage, penalties or the safety car, wait 2 seconds at most.

**Voice and personality:** press **C**, or click **⚙ SETTINGS** on the radio, to choose:
- **Language:** English or Português. The whole dashboard and the engineer switch together.
- **Your name on the radio:** he calls you by your first name (*"Yes, Max! New personal best!"*). By default he uses the name of the driver you picked in the game, including a custom driver in Career or My Team. Online, or with that option turned off, he uses the name you typed.
- **The voice:** in English, Ryan or Sonia (British), Andrew (American) or William (Australian), all Microsoft neural voices that sound human. In Portuguese, Antonio, Francisca or Thalita. Or the Windows voice, which works offline.
- **Speed and volume.** The **▶ TEST VOICE** button does a radio check.
- **Team radio sound:** beeps when the transmission opens and closes, a filtered voice and adjustable static.

He changes tone with the situation (excited on a record, quick on an urgent warning, calm with tips) and varies his phrases so he doesn't sound like a recording. The natural voices need the internet. Offline, the dashboard switches to the Windows voice by itself.

### Corner by corner

On the first clean lap, the engineer maps the track's corners and numbers them in order: Turn 1, 2, 3… On every lap after that, he compares each corner with your reference and tells you where you lost time and why:
- braked too early;
- braked late and overshot;
- slower through the corner;
- got on the power late;
- locked a wheel;
- wheelspin on exit.

On the next lap, he warns you **before** the corner: *"Turn 3, brake at 90 metres."*

- **Brake points in metres:** measured like the 100/50 m boards, from the point where the steering starts to turn on your reference lap.
- **Live minisectors:** as you leave each corner, the dashboard flashes the gain or loss in that section (**TURN 4 +0.061**).
- **Telemetry comparison (key A):**
  - track map coloured by corner;
  - speed, throttle and brake of your lap over the reference;
  - the brake points;
  - time gained or lost through the corner.

### Memory and progress

Everything is saved in `dados/historico.sqlite3`:
- **Record per track:** the telemetry of your best lap becomes the reference for the next sessions.
- **Ideal lap:** the sum of your best sections.
- **Habits:** mistakes that keep repeating in the same corner. He brings them up at the start of the session and before the corner.
- **Session summary:** compares with the previous session and tells you where you improved and what to work on.
- **Progress page** (key **E**, or `http://127.0.0.1:8025/evolucao`): chart per session, corner-by-corner table with trends and habits, and achievements.

### Race and qualifying (instead of the in-game engineer)

- **Start and position:** formation lap, lights out, *"You got Leclerc! P4"*, *"You're leading!"*
- **Your stop:**
  - *"Box, box"* on the strategy lap, with a prediction of where you'll rejoin;
  - **"Limiter! Limiter!"**;
  - stop time and cold tyres.
- **Strategist:**
  - learns what a stop costs at each track;
  - predicts your position if you stop now (**PIT NOW → P7** on the radio);
  - calls *"Safety car deployed! A stop only costs about 12 seconds now"*;
  - warns about the undercut and overcut;
  - compares your tyres with your rivals'.
- **Rivals:** *"Norris has pitted, onto hards"*, pace (*"you'll catch them in 4 laps"*), DRS behind, retirements, other drivers' fastest laps.
- **Rules and car:**
  - fuel, with lift and coast at the right corners;
  - hot or cold tyres and brakes;
  - tyre wear;
  - pit window, rain and the two-compound rule;
  - track limits, penalties, damage, punctures, safety car and flags.
- **Qualifying:** time remaining, the **drop zone** (*"P17, in the drop zone. The cut-off is Lindqvist, 2 tenths needed"*), *"car on a flying lap behind"* and traffic ahead.

**To turn off the in-game engineer:** lower the race engineer volume in F1 25's **Audio** settings. The MFD on your wheel keeps working as normal.

### Steering wheel buttons

F1 25 has **"UDP Action 1" to "UDP Action 12"** buttons. Map them in **Settings → Controls** (usually at the end of the list) and the engineer answers right away:

| Button | You ask | He answers, for example |
|---|---|---|
| UDP Action 1 | Tyres | "Mediums with 7 laps on them. Wear at 18 percent, the worst is the front left. At this rate they hit 70 percent in about 12 laps." |
| UDP Action 2 | Gaps | "P4. Norris, P3, is 1.2 seconds ahead, you're taking 2 tenths a lap." |
| UDP Action 3 | Fuel and battery | "Fuel plus 0.4 laps, standard mix. Battery at 64 percent." |
| UDP Action 4 | Where am I losing time | "Last lap you lost the most in turn 3, 4 tenths: braked at 131 metres, the record brakes at 90." |
| UDP Action 5 | Weather and pit | "Track at 34 degrees. 65 percent chance of rain in 10 minutes. Pit window between laps 6 and 8." |
| UDP Action 6 | Repeat | Repeats the last message. |
| UDP Action 7 | Quiet | Toggles "essentials only" mode. |
| UDP Action 8 | Pit strategy | "A stop here costs about 21 seconds. If you stop now, you rejoin P5, behind Norris." |
| UDP Action 9 | Goals and practice | Progress on each Time Trial goal. |
| UDP Action 10 | Car setup | "Understeer mid-corner in turn 2. Suggestion: more front wing from 28 to 29." |

On the dashboard, keys **1 to 9** and **0** (which counts as 10) ask the same questions.

### Practice mode with goals (Time Trial only)

- **Daily goals:**
  - a lap time to beat;
  - *"5 laps in a row without a lock-up"*;
  - consistency;
  - your habit.

  A completed goal becomes an **achievement** on the Progress page.
- **Practise a corner:** select the corner in the analysis (**A**) and press **T**. Every lap he tells you how far you were from your best section, where you braked against the target and your spread over the last 5 laps.

### Setup analysis

The engineer measures the car's balance on entry, mid-corner and exit of every corner, from the slip angle of the front tyres against the rears. He also looks at wheelspin and tyre temperatures. He only points out what repeats over 3 laps or more, and suggests changes using your current setup values:

| What he sees | What he suggests |
|---|---|
| Understeer on entry | Brake bias further back, off-throttle diff more open |
| Oversteer on entry | Brake bias further forward, off-throttle diff more locked |
| Understeer mid-corner | More front wing |
| Oversteer mid-corner | More rear wing |
| Problems on exit | On-throttle diff more open, smoother on the throttle |
| One axle much hotter | Slightly lower pressure on that axle |

It's a starting point: change one thing at a time. When you change the setup in the garage (wings, suspension, pressures…), the engineer notices, drops the laps from the old setup and restarts the 3-lap count. Changes made on the MFD while driving, like brake bias and differential, don't restart the analysis.

## Shortcuts

| Key | What it does |
|---|---|
| **A** | Last lap analysis: map, telemetry comparison, goals and setup. Use **← →** or click to change corner. |
| **P** | Timing tower: the whole grid (or tap the position) |
| **E** | Progress page |
| **C** | Radio settings: language, name, voice, speed, volume and radio sound |
| **V** | Voice: all → important only → off |
| **1 to 9, 0** | Questions for the engineer (same as the wheel buttons) |
| **T** | Time Trial: practise the selected corner |
| **Esc** | Closes the analysis or the settings |

## Phone and tablet

1. In the menu, choose **Dashboard on phone or tablet**. The window shows the address to type on the device, for example `http://192.168.0.10:8025`.
2. The phone needs to be on the same network as the PC.
3. The first time, allow Painel F1 25 through the Windows firewall: also tick **Public networks** if your network is set as public.

- **Layouts:** the dashboard picks the layout from the screen. On a phone it's compact, with everything large, in landscape or portrait.
- **Full screen:** tap the top bar.
- **Force a layout:** add `?modo=celular` (phone) or `?modo=monitor` to the end of the address.
- **Voice:** set **VOICE: OFF** on the phone so the engineer doesn't talk on two devices.

## Command line

`uv run server.py [options]`

| Option | What it does |
|---|---|
| `--menu` | Opens the menu window (what `PainelF1.exe` does with no options) |
| `--abrir` | Opens the dashboard in Chrome or Edge, full screen on the vertical monitor if there is one |
| `--demo` | Simulated telemetry, no game needed |
| `--time-trial` | With `--demo`: simulates a Time Trial |
| `--formato 2026` | With `--demo`: uses the 2026 UDP format |
| `--lan` | Accepts connections from other devices on the network (phone, tablet, console) |
| `--porta-udp N` | Telemetry port (default 20777) |
| `--porta-web N` | Page port (default 8025) |
| `--historico FILE` | Uses a different history file |

## Common problems

- **"Waiting for F1 25" with the game open:** check the IP 127.0.0.1, port 20777 and that UDP telemetry is on. You need to be on track: in the menus, the game doesn't send data.
- **"UDP port 20777 is already in use":** another telemetry app (SimHub, Crew Chief…) is using the port. Close the other app, or use `--porta-udp 20778` and set 20778 in the game.
- **Game on PS5/Xbox or another PC:** use `--lan` and put this PC's IP in the game (check it with `ipconfig`).
- **The engineer doesn't talk:** check the radio isn't on "VOICE: OFF" (key V). If you see "Click here to turn on the engineer's voice", click once on the dashboard.
- **Start the history from scratch:** delete the `dados` folder with the dashboard closed.

**Known limitations:**
- The game doesn't report corner names. The numbering is the engineer's own, in track order, and stays the same between sessions.
- Online, comparing with rivals depends on them having public telemetry.
- Achievements from the Time Trial goals are saved in the language that was active when you earned them.

## For developers

Python standard library only, plus [`edge-tts`](https://pypi.org/project/edge-tts/) for the voice. Plain HTML, CSS and JS frontend, no build step. The code and comments are in Portuguese.

| File | What it does |
|---|---|
| `server.py` | Server: receives the UDP telemetry and sends the state to the page over SSE |
| `f1_packets.py` | Decodes F1 25 packets (2025 and 2026 formats) |
| `engenheiro.py` | The engineer: per-lap analysis, rules, messages, habits, summary |
| `analise.py` | Detects corners and compares laps corner by corner |
| `corrida.py` | Race and qualifying calls (position, pit, rivals, events) |
| `estrategia.py` | Pit strategist |
| `treino.py` | Time Trial practice mode and goals |
| `acerto.py` | Car setup analysis |
| `historico.py` | SQLite history and the Progress page data |
| `voz.py` | Neural voice (edge-tts) and settings |
| `idioma.py`, `textos_en.py` | Language and the English translation of the engineer, menu and server |
| `simulador.py` | Generates fake telemetry in the game's format, for testing |
| `menu.py` | Menu window: start dashboard, demo, Time Trial, phone |
| `caminhos.py` | Where files live, running from source or as an executable |
| `web/` | Dashboard and Progress page (`web/i18n.js` translates the pages) |

```bash
uv run server.py --demo --abrir           # dashboard with a simulated race
uv run simulador.py --porta 20777         # simulator only, sending to an already running server
uv run tools/checar_traducao.py           # checks every text has an English translation
```

**Translations:** texts are written in Portuguese inside `tx("...")` (or `N_("...")` for module-level lists) in Python and `T('...')` in the pages. The English versions live in `textos_en.py` and `web/i18n.js`, keyed by the Portuguese text. `tools/checar_traducao.py` lists anything missing.

**Executable:** `build.ps1` builds `dist\PainelF1.exe`, a single file with no console and an icon, using PyInstaller (`powershell -ExecutionPolicy Bypass -File build.ps1`). The same build runs on GitHub Actions (`.github/workflows/executavel.yml`): for every published release, the `.exe` is built on Windows and attached to the release. The icon is generated by `tools/gerar_icone.py` (`icone.ico` and `web/icone.png`).

The F1 25 UDP specification is on the official EA forums (*Data Output from F1 25*).

## License

[MIT](LICENSE). Use, modify and share freely.
