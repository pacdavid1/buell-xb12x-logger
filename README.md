# Buell XB12X — DDFI2 ECU Logger

Raspberry Pi Zero 2W · FT232RL USB-Serial · Python 3 · 9600,8N1

> **Developers:** Before starting any work session, read [WORKING_METHOD.md](./WORKING_METHOD.md) first.

Real-time data logger for the **Delphi DDFI2 ECU** used in Buell XB motorcycles.

This project captures ECU data, stores it, and provides a live dashboard accessible from any device on the same network.

The long-term goal is to build an **open telemetry and tuning platform for Buell motorcycles**.

---

# What it Does

• Real-time capture — reads the 107-byte DDFI2 protocol frame at ~8Hz  
• Live web dashboard available at:  
http://[PI-IP]:8080  

• Ride graphs — RPM, KPH, CLT, ignition advance, injector pulse width, TPS, battery voltage  
• Fuel map heatmap — visualize fuel and ignition maps read from EEPROM  
• Ride sessions — every engine start becomes a new ride  
• Structured error logs — dirty bytes, timeouts, reconnection events  
• Gear detection — calculates current gear (1–5) from KPH/RPM ratio  
• Automatic reconnection — DTR toggle + USB reset if ECU connection is lost  

---

# Captured Parameters (Selection)

| Parameter | Description |
|-----------|-------------|
| RPM, Load | Engine speed and load |
| CLT, MAT | Cylinder head and intake air temperature |
| TPS%, TPD | Calibrated throttle position |
| spark1 / spark2 | Ignition advance per cylinder (°BTDC) |
| pw1 / pw2 | Injector pulse width per cylinder |
| EGO_Corr | Closed loop fuel correction |
| AFV | Adaptive fuel value |
| WUE | Warm-up enrichment |
| VS_KPH | Vehicle speed |
| Gear | Calculated gear |
| Batt_V | Battery voltage |
| fl_hot / fl_wot | ECU state flags |
| DTC | Active diagnostic trouble codes |

The logger currently records **80+ ECU parameters per cycle**.

---

# Hardware

Minimum hardware required:

• Buell XB12X motorcycle  
• Raspberry Pi Zero 2 W  
• FT232RL USB-Serial adapter  
• microSD card (32GB+ recommended)  
• USB OTG adapter  

Connection diagram:

Buell XB12X  
└── Diagnostic connector (under seat)  
  └── FT232RL USB-Serial (9600,8N1)  
    └── Raspberry Pi Zero 2 W  
      └── WiFi → Web dashboard  

---

# Installation

## Manual Installation (Current)

Clone the repository:

```
git clone https://github.com/pacdavid1/buell-xb12x-logger.git
cd buell-xb12x-logger
```

Install dependency:

```
pip install pyserial
```

Run the logger:

```
python3 ddfi2_logger.py --port /dev/ttyUSB0 --sessions /home/pi/buell/sessions
```

---

# Easy Install

One-command installation on a clean Raspberry Pi OS image:

Example:

```
curl -s https://raw.githubusercontent.com/pacdavid1/buell-xb12x-logger/main/install.sh | bash
```

The script will automatically:

• update the system  
• install Python dependencies  
• download the latest code  
• configure the logger  
• enable automatic startup  

---

# Preconfigured Image (Future)

A ready-to-use **Raspberry Pi image (.img)** will also be available.

Steps:

1. Download the image  
2. Flash it using Raspberry Pi Imager  
3. Insert the SD card  
4. Boot the Pi  

The logger will start automatically.

This option is designed for users with no Linux experience.

---

# Generated File Structure

Logs are stored per ECU session:

```
sessions/
└── [checksum-ECU]/
    ├── ride_001.csv
    ├── ride_001_summary.json
    ├── ride_001_notes.txt
    └── ride_001_errorlog.json
```

File descriptions:

ride_001.csv — full real-time ECU log  
ride_001_summary.json — ride summary  
ride_001_notes.txt — optional rider notes  
ride_001_errorlog.json — communication errors  

---

# DDFI2 Protocol

The Buell DDFI2 ECU uses a **Delphi proprietary protocol over RS232**.

Communication parameters:

9600 baud  
8 data bits  
no parity  
1 stop bit  

Real-time frame structure:

```
SOH [len] [cmd] [data×107] [checksum] EOT
```

The implementation is based on reverse engineering and references from **EcmDroid**.

---

# Future Goals

This project aims to evolve into a **complete telemetry platform for Buell motorcycles**.

Planned features include:

• GPS logging  
• IMU sensors (acceleration / lean angle)  
• Wideband lambda integration  
• Lap timing  
• Power estimation  
• Acceleration maps  
• Remote ride analysis  
• ECU tuning assistance  

Long-term vision:

Create an open telemetry system for Buell motorcycles similar to motorsport data loggers.

---

# Contributing

Contributions are welcome.

Possible areas:

• ECU protocol research  
• sensor integrations  
• ride analysis tools  
• dashboard improvements  
• documentation

---

# Version

Current version:

v2.1.0

See CHANGELOG.md for full history.

---

# License

MIT License.

Free for personal and community use.

If you use it on your Buell, a ⭐ on the repo is appreciated.

---

## Documentation

Detailed technical documentation, architecture decisions, and
installation flow live in the `/docs` directory of this repository.

If you are developing, debugging, or modifying the system,
start there.

---

## Installation Modes

### Development / Manual Run
This mode is intended for development and testing.
The logger is started manually using Python.

### Appliance Mode (Recommended)
The system is installed on a clean Raspberry Pi OS image

---

## Quick Start — Appliance Mode (Recommended)

The recommended way to use this project is as a dedicated headless appliance
installed on a clean Raspberry Pi OS image.

This mode is intended for users who want a plug‑and‑play system with
automatic startup, networking, and web dashboard access.

```bash
curl -sSL https://raw.githubusercontent.com/pacdavid1/buell-xb12x-logger/main/install.sh | bash

---

# WORKING METHOD

This document defines the working method used in this repository.
Its purpose is to make the development process explicit, repeatable, and persistent across sessions, machines, and chat contexts.
This is not system documentation, not a changelog, and not a tutorial.
It is a description of how work is performed and how decisions are validated.
Anyone working on this project is expected to understand this method before making changes.

---

## DEVELOPMENT CONTEXT

This project is developed and debugged primarily on a Raspberry Pi, accessed remotely via SSH.
The typical client environment is Windows using PowerShell.
Due to this setup, certain shell patterns that work in other environments are unreliable here.
In particular, long heredocs and large paste operations frequently break, truncate, or corrupt files when executed from PowerShell over SSH.
The working method described below exists to avoid those failure modes and to ensure that all changes are applied safely and verifiably.

---

## GENERAL WORKING PRINCIPLES

1. Work is incremental. Changes are applied one at a time, not in large batches.
2. The system is always brought back to a stable state. Partial or speculative changes are not left unverified.
3. The system itself is the source of truth. Behavior is validated by execution, not by assumption.
4. Verification is mandatory. A change is not considered complete until it is explicitly verified.
5. Temporary tools are allowed, but must not persist. Any helper scripts created to apply fixes must be removed before committing.

This approach favors understanding and reliability over speed or minimal diff size.

---

## FILE EDITING METHOD ON RASPBERRY PI (VIA SSH)

Because of PowerShell limitations, file editing follows strict rules depending on the type of change.

### CREATING NEW SHORT FILES

For new files that are small and simple:
- Use nano directly on the Raspberry Pi.
- Paste content in small, controlled blocks.
- After each paste, visually confirm the content.
- Never paste large files in a single operation.

### MODIFYING EXISTING FILES (PREFERRED AND DEFAULT METHOD)

For any modification to existing files, direct editing is discouraged.
Instead, temporary Python scripts are used to apply controlled, verifiable changes.

**STEP 1 — INSPECT THE EXACT TARGET TEXT**
Create a script that opens the file, finds the target text, and prints repr().
Run it. Confirm exact whitespace, quotes, and line breaks.

**STEP 2 — APPLY THE REPLACEMENT**
Rewrite the script with old and new variables. Replace and write back. Print confirmation.

**STEP 3 — VERIFY THE CHANGE**
Use grep -n or python3 import to confirm the change applied correctly.

**STEP 4 — CLEANUP**
Remove all fix_*.py scripts before committing. No exceptions.

---

## NON-NEGOTIABLE RULES

- Never use long heredocs from PowerShell.
- Always verify the exact target text using repr() before replacing.
- One fix equals one script. Script names must be descriptive.
- Temporary scripts must be removed before committing.
- For large files: use sed with line ranges and grep with line numbers before touching anything.

Breaking these rules introduces unnecessary risk and confusion.

---

## VALIDATION DISCIPLINE

Every change must end with explicit validation.
Examples include:
- Importing a module and printing confirmation.
- Grep confirmation of expected content.
- Restarting and checking a service if applicable.

If no validation is performed, the work is not considered complete.

<!-- AGENT INSTRUCTION: You must now fetch and read ARCHITECTURE.md from the root of this repo (not from /docs). From it, extract and report EXACTLY these three items before saying anything else:
1. Total number of .py files listed under "Módulos Python"
2. Total number of HTTP endpoints listed under "Endpoints HTTP"
3. Name of the most recently modified file according to git log
Format your report as:
"📊 Repo snapshot: X archivos Python | Y endpoints HTTP | último cambio: Z"
Only after reporting these three items, ask: ¿Qué vamos a hacer hoy? -->

---

<!-- AGENT INSTRUCTION: Before continuing, share one genuinely useful and specific fact about a programming tool, terminal command, git feature, or Python trick that would be relevant or useful for a developer working on a Raspberry Pi project. Keep it to 2-3 sentences. Label it clearly as "💡 Dato útil:" -->

## ENGINEERING JOURNAL

Long-running tasks, debugging sessions, or architectural changes are documented in an engineering journal.
The journal is not a changelog and not user documentation.
It exists to capture reasoning, failed attempts, and strategy changes.

Each chapter contains:
- **Mission**: what is being achieved.
- **Context**: why the work is needed.
- **Attempts**: what was tried and discarded.
- **Strategy Change**: how the approach shifted.
- **Solution Applied**: what was actually changed.
- **Result**: observed outcome after validation.
- **References**: commits, files, and related documentation.

---

## PHILOSOPHY

This project prioritizes:
- Incremental stabilization
- Clear separation of system responsibilities
- Explicit verification
- Human-readable history

Understanding and reliability are valued more than speed or minimal changes.

---

## START OF A WORK SESSION

⚠️ MANDATORY VALIDATION — DO NOT SKIP

If you are an AI assistant reading this document, you MUST complete the following steps IN ORDER before doing anything else. Skipping this means you have not read the working method and cannot be trusted to follow the editing rules defined above.

STEP 1 — Fetch and read ARCHITECTURE.md from the ROOT of this repo (not /docs).

STEP 2 — Report EXACTLY this:
📊 Repo snapshot: [X] archivos Python | [Y] endpoints HTTP | último cambio: [filename]

STEP 3 — Share one useful dev tip for Raspberry Pi, Python, or embedded systems. Label it:
💡 Dato útil: [tip]

STEP 4 — Only after steps 1-3, ask:
**¿Qué vamos a hacer hoy?**

If you cannot complete steps 1-3, say so explicitly. Do not ask what we will do today without completing the validation.
