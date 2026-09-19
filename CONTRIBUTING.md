# Contributing

Thanks for looking at this project. It started as a tuning tool for one Buell XB12X and is
meant to grow into something the wider Buell/DDFI2 community can use and extend.

## Before you start

This targets an **IDS DDFI2 ECU** (Buell XB/1125 series). If you're working with a
different ECU family, the serial protocol (`ecu/protocol.py`) and EEPROM map layout
(`ecu_defs/*.xml`) will need their own definitions — see [ecu_defs/README.md](ecu_defs/README.md).

## Dev setup

You need either a Raspberry Pi wired to a live ECU, or just session data to work against
offline (most map/analysis work doesn't need live hardware):

```bash
git clone https://github.com/pacdavid1/buell-xb12x-logger.git
cd buell-xb12x-logger
python3 -m pip install -r requirements.txt
```

**On the Pi**, with an ECU connected:
```bash
python3 main.py --port /dev/ttyECU --sessions-dir ./sessions --buell-dir .
```

**Offline / no Pi**, against saved session data: the [tools/xpr_viewer.html](tools/xpr_viewer.html)
tool decodes an `.xpr`/`.bin` EEPROM dump and views maps + configuration entirely in the
browser — no server needed. Useful for map-decoding work without touching a live bike.

## Coding conventions

- **All code, comments, and identifiers in English** — every source file in this repo
  starts with a `DEV NOTE` line saying so. UI-facing strings follow the same rule; Spanish
  is only used in some `# DEV NOTE`-style internal notes that predate this convention.
- **No comments explaining *what* code does** — names should make that obvious. A comment
  is worth adding only when it explains a non-obvious *why*: a hardware quirk, a protocol
  constraint, a bug workaround.
- **Match the existing style in whatever file you're editing** before introducing a new
  pattern. `main.py` and most `web/handlers/*.py` files show the conventions in practice.
- **Small, focused files** over one large one. `web/handlers/` is already split by concern
  (eeprom, gps, tuner, sessions, ...) — new endpoints belong in the matching mixin, or a
  new one if nothing fits.

## Hardware-specific claims

Don't guess at electrical, protocol, or ECU behavior — verify against the OEM manuals or
real hardware evidence (`i2cget`, a logic analyzer capture, a decoded EEPROM dump) before
stating it as fact, and say so in the commit/PR description. This project has a history of
diagnosing sensor issues down to the raw register/byte level rather than guessing — that's
the bar.

## Submitting changes

1. Open an issue first for anything non-trivial (new sensor integration, protocol changes,
   ECU support beyond DDFI2) so the approach can be discussed before you invest time in it.
2. Keep PRs focused — one logical change per PR is much easier to review than a bundle.
3. Update [CHANGELOG.md](CHANGELOG.md): add a new entry at the top (see the instructions in
   that file's own header comment) describing what changed and why.
4. If your change touches ECU communication, EEPROM encode/decode, or anything that could
   write to a live ECU, call that out explicitly in the PR — those changes get scrutinized
   harder for good reason (a bad EEPROM write can brick a tune).

## Questions

Open a GitHub issue. If it's specific to your own bike's tune or a one-off diagnostic
question rather than a bug/feature in this codebase, a discussion (if enabled) or issue
tagged accordingly is still the right place — it helps the next person hitting the same
question.
