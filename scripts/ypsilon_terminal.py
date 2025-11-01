#!/usr/bin/env python3
# YPSILON-14 SHIP/OUTPOST TERMINAL (Retro CLI for Mothership 1e)
# Scenario support: The Haunting of Ypsilon-14
# Author: ChatGPT (GPT-5 Thinking)

import json
import os
import readline
import shlex
import textwrap
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional

BANNER = r"""
███████╗██╗   ██╗██████╗ ██╗██╗      ██████╗ ███╗   ██╗
██╔════╝██║   ██║██╔══██╗██║██║     ██╔═══██╗████╗  ██║
█████╗  ██║   ██║██████╔╝██║██║     ██║   ██║██╔██╗ ██║
██╔══╝  ╚██╗ ██╔╝██╔══██╗██║██║     ██║   ██║██║╚██╗██║
███████╗ ╚████╔╝ ██║  ██║██║███████╗╚██████╔╝██║ ╚████║
╚══════╝  ╚═══╝  ╚═╝  ╚═╝╚═╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝
        OUTPOST OPS CONSOLE • SEBACO MINING LTD.
                 NODE: YPSILON-14 • v1.0
"""

PROMPT = "YPSI-14> "
ADMIN_PROMPT = "YPSI-14[ADMIN]> "
ADMIN_PASSPHRASE = "warden"

# --- OpenAI configuration ----------------------------------------------------

try:  # Allow local secrets without exporting env vars
    import ypsilon_terminal_secret as _ypsilon_secret  # type: ignore
except ImportError:  # pragma: no cover - optional convenience module
    _ypsilon_secret = None


def _secret_attr(name: str):
    return getattr(_ypsilon_secret, name, None) if _ypsilon_secret else None


def _coalesce(*values, default=None):
    for value in values:
        if value not in (None, ""):
            return value
    return default


OPENAI_API_KEY = _coalesce(os.getenv("OPENAI_API_KEY"), _secret_attr("OPENAI_API_KEY"), default="")
OPENAI_ORG = _coalesce(os.getenv("OPENAI_ORG"), _secret_attr("OPENAI_ORG"))
OPENAI_MODEL = _coalesce(
    os.getenv("YPSI_OPENAI_MODEL"),
    os.getenv("OPENAI_MODEL"),
    _secret_attr("OPENAI_MODEL"),
    default="gpt-4o-mini",
)
OPENAI_BASE_URL = _coalesce(
    os.getenv("YPSI_OPENAI_BASE_URL"),
    os.getenv("OPENAI_BASE_URL"),
    _secret_attr("OPENAI_BASE_URL"),
    default="https://api.openai.com/v1",
)
OPENAI_VERBOSITY = _coalesce(
    os.getenv("YPSI_OPENAI_VERBOSITY"),
    _secret_attr("OPENAI_VERBOSITY"),
    default="medium",
)

def ai_enabled() -> bool:
    return bool(OPENAI_API_KEY)

def ai_headers() -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    if OPENAI_ORG:
        headers["OpenAI-Organization"] = OPENAI_ORG
    return headers

def ai_summarize_state() -> str:
    s = STATE.ship
    telemetry = (
        f"Ship {s.name}: O2 {s.o2_minutes}m, Hull {s.hull_pct}%, Power {s.power_pct}% "
        f"Radiation {s.radiation}/10, Pressure {'OK' if s.pressure_ok else 'LOSS'}, Lockdown {s.lockdown}."
    )
    crew_bits = []
    for p in STATE.pcs.values():
        crew_bits.append(
            f"{p.name} ({p.cls}) HP {p.hp}/{p.hp_max}, Wounds {p.wounds}, Stress {p.stress}"
        )
    crew = " | ".join(crew_bits) if crew_bits else "No registered crew."
    return telemetry + " Crew: " + crew

def ai_call(prompt: str, *, include_state: bool = False, temperature: float = 0.8) -> Optional[str]:
    if not ai_enabled():
        return None
    body_prompt = prompt
    if include_state:
        body_prompt = f"{prompt}\n\nCurrent telemetry: {ai_summarize_state()}"
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are the narrative subsystem of the Ypsilon-14 outpost terminal. "
                    "Describe events with an ominous, sci-fi-horror tone. Keep descriptions at "
                    f"{OPENAI_VERBOSITY} verbosity, roughly 2-3 sentences unless instructed otherwise."
                ),
            },
            {"role": "user", "content": body_prompt},
        ],
        "temperature": temperature,
    }
    url = f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=ai_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            parsed = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8")
        except Exception:
            detail = str(exc)
        err(f"OpenAI request failed: {detail}")
        return None
    except Exception as exc:  # pragma: no cover - defensive against network issues
        err(f"OpenAI error: {exc}")
        return None
    choices = parsed.get("choices")
    if not choices:
        return None
    message = choices[0].get("message", {})
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    return None

wrap = lambda s: textwrap.fill(s, width=78)

# --- Data Models --------------------------------------------------------------

@dataclass
class Player:
    name: str
    cls: str = "crew"
    hp_max: int = 20
    hp: int = 20
    wounds: int = 1
    stress: int = 2
    fear_save: int = 30
    body_save: int = 30
    notes: str = ""
    conditions: List[str] = field(default_factory=list)

@dataclass
class Ship:
    name: str = "YPSILON-14"
    o2_minutes: int = 480  # 8 hours
    hull_pct: int = 100
    radiation: int = 0      # 0=nominal, rises to 10=lethal
    power_pct: int = 100
    pressure_ok: bool = True
    lockdown: bool = False
    doors: Dict[str, bool] = field(default_factory=lambda: {
        "airlock": True,      # True=Locked
        "cargo": False,
        "hab": False,
        "lab": True,
        "admin": True,
    })

@dataclass
class World:
    admin: bool = False
    ship: Ship = field(default_factory=Ship)
    pcs: Dict[str, Player] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    omens: List[str] = field(default_factory=lambda: [
        "Unscheduled power flicker in HAB-2.",
        "Automated paging loop repeats a miner’s name… no response.",
        "Wet footprints leading from the Lab vents to the Cargo lift.",
        "Geiger counters tick sporadically near Processing Bay 3.",
    ])
    scenario_flags: Dict[str, bool] = field(default_factory=lambda: {
        "lab_access": False,
        "unknown_growth_seen": False,
        "panic_increase": False,
    })

STATE = World()

def log(msg: str):
    STATE.logs.append(msg)
    print(f"[LOG] {msg}")

# --- Utilities ----------------------------------------------------------------

def ok(msg="OK"):
    print(f"✔ {msg}")

def err(msg="Error"):
    print(f"✖ {msg}")

def require_admin():
    if not STATE.admin:
        err("Admin required. Use: admin on")
        return False
    return True

def door_name(key: str) -> Optional[str]:
    key = key.lower()
    for k in STATE.ship.doors.keys():
        if k.startswith(key):
            return k
    return None

def player_match(q: str) -> Optional[Player]:
    q = q.lower()
    for p in STATE.pcs.values():
        if p.name.lower().startswith(q):
            return p
    return None

# --- Command Handlers ---------------------------------------------------------

def cmd_help(args):
    print(wrap(
        "Retro terminal commands. Players can use status, doors, sensors, "
        "map, ping, logs, and sos. The Warden can toggle admin and set "
        "values, inject omens/alerts, and script scene beats."
    ))
    print("""
PLAYER COMMANDS
  help                         Show this help
  status [who]                 Show ship or player status
  doors                        List door locks
  lock <door> | unlock <door>  Request door lock/unlock (denied if lockdown/Admin)
  sensors                      Show O₂, hull, power, rad levels
  map                          Show simple zone listing
  ping <zone>                  Ping motion/sensor sweep (fictional hook)
  logs [n]                     Last n logs (default 10)
  sos [message]                Broadcast a distress call stub
  narrate <prompt>             Ask the AI narrator for atmospheric output (OpenAI required)

WARDEN / ADMIN
  admin on|off                 Enter/exit admin (passphrase required)
  set ship <field> <value>     Set ship stat (o2_minutes, hull_pct, power_pct, radiation, lockdown true/false)
  set door <name> <locked>     Lock/unlock door exactly
  add pc <name> [class]        Add a player record
  set pc <name> <field> <val>  Set pc field (hp, hp_max, wounds, stress, fear_save, body_save, notes, +condition, -condition)
  omen [text]                  Push or list omens (no args = list; with text = add+announce)
  alert <text>                 Print a red-alert style log (also good for jump-scare beats)
  script <beat>                Run a prepared Ypsilon-14 beat (see: script list)
  savepanic <+n|-n>            Mass modify Stress on all PCs and log it
  reset                        Reset ship to nominal baseline
""")
    if ai_enabled():
        print(
            f"\nAI NARRATOR\n  narrate <prompt>             Active (OpenAI API). Verbosity: {OPENAI_VERBOSITY}, Model: {OPENAI_MODEL}"
        )
    else:
        print(
            "\nAI NARRATOR\n  Set OPENAI_API_KEY (or add scripts/ypsilon_terminal_secret.py with OPENAI_API_KEY) "
            "and optional YPSI_OPENAI_MODEL/YPSI_OPENAI_BASE_URL to enable narrate/AI embellishments.\n"
        )

def cmd_status(args):
    if not args:
        s = STATE.ship
        print(f"[SHIP] {s.name} | O₂:{s.o2_minutes}m  Hull:{s.hull_pct}%  Power:{s.power_pct}%  Rad:{s.radiation}/10  "
              f"Pressure:{'OK' if s.pressure_ok else 'LOSS'}  Lockdown:{s.lockdown}")
        return
    who = player_match(args[0])
    if not who:
        err("No such player.")
        return
    p = who
    print(f"[PC] {p.name} ({p.cls}) HP:{p.hp}/{p.hp_max} Wounds:{p.wounds} Stress:{p.stress} "
          f"Fear:{p.fear_save} Body:{p.body_save}")
    if p.conditions:
        print("  Conditions:", ", ".join(p.conditions))
    if p.notes:
        print("  Notes:", p.notes)

def cmd_doors(args):
    for k,v in STATE.ship.doors.items():
        print(f" - {k.upper():7} :: {'LOCKED' if v else 'OPEN'}")
    if STATE.ship.lockdown:
        print("! Station-wide LOCKDOWN is engaged.")

def cmd_lock(args):
    if not args:
        err("lock <door>")
        return
    n = door_name(args[0])
    if not n:
        err("Unknown door.")
        return
    if STATE.ship.lockdown and not STATE.admin:
        err("Lockdown in effect. Only Admin may override.")
        return
    STATE.ship.doors[n] = True
    log(f"Door {n} -> LOCKED")

def cmd_unlock(args):
    if not args:
        err("unlock <door>")
        return
    n = door_name(args[0])
    if not n:
        err("Unknown door.")
        return
    if STATE.ship.lockdown and not STATE.admin:
        err("Lockdown in effect. Only Admin may override.")
        return
    STATE.ship.doors[n] = False
    log(f"Door {n} -> OPEN")

def cmd_sensors(args):
    s = STATE.ship
    bars = lambda pct: "[" + "#" * (pct//10) + "-" * (10 - pct//10) + "]"
    print(f"O₂ Remaining: {s.o2_minutes} minutes")
    print(f"Power: {s.power_pct}% {bars(s.power_pct)}")
    print(f"Hull Integrity: {s.hull_pct}% {bars(s.hull_pct)}")
    rad_note = "Nominal" if s.radiation == 0 else ("Elevated" if s.radiation <= 3 else ("Danger" if s.radiation <=7 else "LETHAL"))
    print(f"Radiation: {s.radiation}/10 :: {rad_note}")
    if s.radiation >= 5:
        print("! WARNING: Sustained exposure requires BODY saves; Admin may reduce with 'set ship radiation <n>'.")

def cmd_map(args):
    print("""
SECTORS/ROOMS
 - AIRLOCK  - CARGO BAY  - HAB  - LAB  - ADMIN
SECRET PATHS?
 - Vents (LAB→CARGO), Maintenance Shafts (HAB↔LAB)
NOTES
 - LAB requires keycard (unless ADMIN overrides)
 - Airlock safety interlocks prevent OPEN if pressure not OK
""".strip())

def cmd_ping(args):
    zone = args[0].upper() if args else "HAB"
    print(f"Pinging {zone}…")
    # Light fiction hook
    if zone.startswith("LAB") and not STATE.scenario_flags["unknown_growth_seen"]:
        print("…movement detected inside ventilation. Moisture anomaly.")
    else:
        print("…no movement detected.")

def cmd_logs(args):
    n = int(args[0]) if args else 10
    for line in STATE.logs[-n:]:
        print("•", line)

def cmd_sos(args):
    msg = " ".join(args) if args else "Requesting emergency assistance. Personnel missing."
    log(f"SOS BROADCAST: {msg}")
    print("Transmitting… carrier noise and static answer. No immediate reply.")

# --- Admin --------------------------------------------------------------------

def cmd_admin(args):
    if not args:
        print(f"Admin: {'ON' if STATE.admin else 'OFF'}")
        return
    if args[0] == "on":
        pw = input("Passphrase: ").strip()
        if pw == ADMIN_PASSPHRASE:
            STATE.admin = True
            ok("Admin enabled.")
        else:
            err("Bad passphrase.")
    elif args[0] == "off":
        STATE.admin = False
        ok("Admin disabled.")
    else:
        err("admin on|off")

def cmd_set(args):
    if not require_admin(): return
    if len(args) < 3:
        err("set ship <field> <value> | set door <name> <true/false> | set pc <name> <field> <value>")
        return
    target = args[0].lower()
    if target == "ship":
        field = args[1].lower()
        val = args[2]
        ship = STATE.ship
        if field in {"o2_minutes","hull_pct","power_pct","radiation"}:
            try:
                ival = int(val)
            except:
                err("Value must be int.")
                return
            setattr(ship, field, ival)
            log(f"Ship.{field} -> {ival}")
        elif field == "lockdown":
            setattr(ship, field, val.lower() in ("true","1","yes","on"))
            log(f"Ship.lockdown -> {getattr(ship, field)}")
        elif field == "pressure_ok":
            setattr(ship, field, val.lower() in ("true","1","yes","on"))
            log(f"Ship.pressure_ok -> {getattr(ship, field)}")
        else:
            err("Unknown ship field.")
    elif target == "door":
        name = door_name(args[1])
        if not name:
            err("Unknown door.")
            return
        locked = args[2].lower() in ("true","1","yes","on","locked")
        STATE.ship.doors[name] = locked
        log(f"Door {name} -> {'LOCKED' if locked else 'OPEN'}")
    elif target == "pc":
        pc = player_match(args[1])
        if not pc:
            err("No such player.")
            return
        field = args[2].lower()
        val = " ".join(args[3:]) if len(args) > 3 else ""
        if field in {"hp","hp_max","wounds","stress","fear_save","body_save"}:
            try:
                setattr(pc, field, int(val))
                log(f"{pc.name}.{field} -> {val}")
            except:
                err("Value must be int.")
                return
        elif field == "notes":
            pc.notes = val
            log(f"{pc.name}.notes set.")
        elif field == "+condition":
            if val and val not in pc.conditions:
                pc.conditions.append(val)
                log(f"{pc.name} +condition {val}")
        elif field == "-condition":
            if val in pc.conditions:
                pc.conditions.remove(val)
                log(f"{pc.name} -condition {val}")
        else:
            err("Unknown pc field.")
    else:
        err("Target must be ship|door|pc")

def cmd_add(args):
    if not require_admin(): return
    if len(args) < 2 or args[0].lower() != "pc":
        err("add pc <name> [class]")
        return
    name = args[1]
    cls = args[2] if len(args) > 2 else "crew"
    if name.lower() in (p.name.lower() for p in STATE.pcs.values()):
        err("PC already exists.")
        return
    pc = Player(name=name, cls=cls)
    STATE.pcs[name] = pc
    log(f"PC added: {name} ({cls})")

def cmd_omen(args):
    if not STATE.admin and args:
        err("Admin required to inject new omen.")
        return
    if not args:
        print("Active Omens:")
        for i, o in enumerate(STATE.omens, 1):
            print(f" {i}. {o}")
        return
    text = " ".join(args)
    STATE.omens.append(text)
    log(f"OMEN: {text}")
    print("PA invoked: station hushed; someone whispers, 'Did you hear that?'")
    response = ai_call(
        f"Announce the following omen to the crew: {text}. Make it feel like a diegetic system broadcast with subtle dread.",
        include_state=True,
    )
    if response:
        print(response)

def cmd_alert(args):
    if not require_admin(): return
    if not args:
        err("alert <text>")
        return
    text = " ".join(args)
    banner = "!!! ALERT: " + text
    log(banner)
    print(banner)
    response = ai_call(
        f"Provide a medium-verbosity console narration expanding on this alert: {text}.",
        include_state=True,
        temperature=0.6,
    )
    if response:
        print(response)

def cmd_savepanic(args):
    if not require_admin(): return
    if not args or not (args[0].startswith("+") or args[0].startswith("-")):
        err("savepanic <+n|-n>")
        return
    try:
        delta = int(args[0])
    except:
        err("Bad number.")
        return
    for p in STATE.pcs.values():
        p.stress = max(0, p.stress + delta)
    log(f"Group stress modified by {delta}.")

# Scenario scripting for Ypsilon-14 beats
def cmd_script(args):
    if not require_admin(): return
    if not args or args[0] in {"list","help"}:
        print("""Beats:
  airlock_denied      -> Pressure fault blocks opening (builds tension)
  lab_warning         -> Terminal warns: 'ELEVATED BIOHAZARD' (hints at lab)
  raise_radiation     -> Increments radiation by 1 and warns
  lockdown            -> Engage station-wide lockdown
  cargo_lock          -> Specifically locks cargo bay (invisible thing outside…)
  lab_keycard_grant   -> Grant players Lab access (scenario progress)
  panic_spike         -> +1 Stress to all PCs
""")
        return
    beat = args[0]
    s = STATE.ship
    narrative_prompt = None
    if beat == "airlock_denied":
        s.pressure_ok = False
        s.doors["airlock"] = True
        log("AIRLOCK OPEN REQUEST DENIED: External pressure mismatch.")
        narrative_prompt = (
            "Describe how the airlock rejects the crew, stressing the pressure imbalance and the hush that follows."
        )
    elif beat == "lab_warning":
        log("LAB ENV ALERT: Unknown organic mass detected near vents. Access restricted.")
        narrative_prompt = "Narrate the lab warning as sensors pick up the organic mass, keeping the tone tense and investigative."
    elif beat == "raise_radiation":
        s.radiation = min(10, s.radiation + 1)
        log(f"RADIATION SPIKE: Level {s.radiation}/10. Avoid Processing Bay 3.")
        narrative_prompt = "Explain the radiation spike with medium verbosity, highlighting erratic gauges and prickling unease."
    elif beat == "lockdown":
        s.lockdown = True
        log("SECURITY: Station-wide LOCKDOWN engaged.")
        narrative_prompt = "Describe the lockdown clamping down, focusing on the metallic seals and heavy silence."
    elif beat == "cargo_lock":
        s.doors["cargo"] = True
        log("CARGO BAY sealed due to motion anomaly on exterior cameras.")
        narrative_prompt = "Detail how the cargo bay seals after detecting unseen exterior motion, hinting that something waits outside."
    elif beat == "lab_keycard_grant":
        STATE.scenario_flags["lab_access"] = True
        s.doors["lab"] = False
        log("SECURITY OVERRIDE: Temporary LAB access granted.")
        narrative_prompt = "Describe the system grudgingly granting lab access, mixing tactical relief with dread."
    elif beat == "panic_spike":
        for p in STATE.pcs.values():
            p.stress += 1
        STATE.scenario_flags["panic_increase"] = True
        log("Crew-wide anxiety event recorded. (Stress +1)")
        narrative_prompt = "Narrate the crew's stress spike, focusing on shaking hands, clipped comms, and glitching monitors."
    else:
        err("Unknown beat. Try: script list")
        return
    if narrative_prompt:
        response = ai_call(narrative_prompt, include_state=True)
        if response:
            print(response)

def cmd_narrate(args):
    if not args:
        err("narrate <prompt>")
        return
    prompt = " ".join(args)
    response = ai_call(prompt, include_state=True)
    if response:
        print(response)
    else:
        err("Narrative subsystem offline. Set OPENAI_API_KEY to enable.")

def cmd_reset(args):
    if not require_admin(): return
    STATE.ship = Ship()
    STATE.logs.clear()
    ok("Ship reset to nominal.")

# --- Parser/Loop --------------------------------------------------------------

COMMANDS = {
    "help": cmd_help,
    "status": cmd_status,
    "doors": cmd_doors,
    "lock": cmd_lock,
    "unlock": cmd_unlock,
    "sensors": cmd_sensors,
    "map": cmd_map,
    "ping": cmd_ping,
    "logs": cmd_logs,
    "sos": cmd_sos,
    "narrate": cmd_narrate,
    # admin
    "admin": cmd_admin,
    "set": cmd_set,
    "add": cmd_add,
    "omen": cmd_omen,
    "alert": cmd_alert,
    "savepanic": cmd_savepanic,
    "script": cmd_script,
    "reset": cmd_reset,
}

def repl():
    print(BANNER)
    print(wrap("Type 'help' for commands. This console is diegetic—use it as in-game "
               "fiction. Players use normal commands; the Warden can enter 'admin on' "
               "and drive beats (radiation spikes, lockdowns, etc.) to pace 'The Haunting "
               "of Ypsilon-14'."))
    while True:
        try:
            prompt = ADMIN_PROMPT if STATE.admin else PROMPT
            raw = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break
        if not raw.strip():
            continue
        try:
            parts = shlex.split(raw)
        except ValueError:
            err("Parse error.")
            continue
        cmd, *args = parts
        cmd = cmd.lower()
        if cmd in {"quit","exit"}:
            print("Closing console.")
            break
        fn = COMMANDS.get(cmd)
        if not fn:
            err("Unknown command. Try 'help'.")
            continue
        fn(args)

if __name__ == "__main__":
    # Seed a couple of example PCs for quick start
    STATE.pcs["Rook"] = Player(name="Rook", cls="teamster", notes="Knows vents.")
    STATE.pcs["Voss"] = Player(name="Voss", cls="marine", hp_max=22, hp=22, wounds=2)
    log("Console boot complete. Systems nominal.")
    repl()
