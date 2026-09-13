# RAASTA AI — Lahore Transport Dataset (FINAL v3)

## Scope
Lahore only. Three bus systems, merged into one set of CSVs (distinguished
by the `bus_type` column: `Metro`, `Speedo`, `Electro`).

- **Metro** — Lahore Metrobus, the main BRT corridor (Shahdara ↔ Gajju Matta).
- **Speedo** — Officially PMA's "Feeder Route" network (34 routes, Phase I+II,
  currently operating). Publicly branded "Speedo". Feeds passengers into the
  Metrobus corridor.
- **Electro** — Punjab's new electric bus service, operated by the Punjab
  Transport Company (PTC). Main line (Railway Station ↔ Green Town) plus 2
  newer Phase-II routes.

## File overview
| File | Rows | Purpose |
|---|---|---|
| `routes.csv` | 38 | One row per route, across all 3 systems |
| `stops.csv` | 214 | Deduplicated master list of every stop |
| `route_stops.csv` | 316 | Stop sequence per route (join table) |
| `transfers.csv` | 58 | Stops served by 2+ routes (interchange points) |
| `fares.csv` | 3 | Fare structure per bus_type |
| `operating_hours.csv` | 3 | First/last bus, frequency, days |
| `service_info.csv` | 3 | Operator, launch date, helpline, notes |

## Data quality / verification
Every row carries a `verification_status`:
- **VERIFIED** — stop names and sequence confirmed against an official
  government source (PMA planning PDF, PMA website, or an official Punjab
  Govt press release).
- **PARTIAL** — only the route's start/end points are confirmed; the
  intermediate stop sequence has not been published yet.

**36 of 38 routes are fully VERIFIED.** Only 2 routes are PARTIAL — both are
brand-new Electro Phase-II routes (Raiwind↔Thokar Niaz Baig, Thokar Niaz
Baig↔Harbanspura) launched recently enough that Punjab hasn't published
their stop-by-stop list yet. This is a real, current limitation — not
something to guess around.

## Known intentional gaps (do not fill with guesses)
1. **`latitude`/`longitude` are blank in `stops.csv`.** These need to be
   filled by a geocoding script (`maps/geocoding.py`, query pattern:
   `"<stop_name>, Lahore, Pakistan"`), not manually estimated.
2. **The 2 Electro Phase-II routes** listed above — real endpoints, no
   verified intermediate stops yet.
3. **Fares for Speedo are a system-wide range (Rs 20–80, distance-based)**,
   not an exact per-route figure — that's how the source publishes it.
4. **Only Speedo Phase I+II (routes 1–34) are included** — PMA's long-term
   plan includes Phase III–VIII (routes 35–122), but these are not yet
   operational, so they're correctly excluded.

## Revision history
- **v1**: Initial build. Incorrectly listed "Metro feeder routes" as a
  separate system from Speedo (they are the same buses).
- **v2**: Fixed the Metro/Speedo duplication. Added full official stop
  sequences for all 34 Speedo routes (previously 8 had only endpoints).
- **v3 (this version)**: Corrected Electro's operator to the real entity,
  Punjab Transport Company (PTC) — previously a generic guess. Upgraded
  Electro's main-line stop list to a fuller, more authoritative official
  government press release. Added `verification_status` and `source`
  columns across all files for auditability.

## A note on a second dataset we compared against
A teammate generated an alternate version of this dataset with ChatGPT.
We compared both side by side before finalizing this one. That version had
better per-route source citations (individual PMA page links) and correctly
identified PTC as Electro's operator — both ideas are incorporated here.
However, it also included intermediate stops (e.g. "T-Stop", "Korray Stop",
"Package") that do not appear in the official PMA document it cited as its
own source, and it only covered 15 of the 34 currently-operating Speedo
routes. This dataset supersedes it.
