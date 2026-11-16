# NORMA

NORMA checks building drawings against **Government of Georgia Resolution №41** (28 January 2016, the Building Safety Rules). Upload a project's PDF, DWG and DXF files, from every discipline, and it reports what breaks the rules, what is missing and what needs checking, and points at each problem on the drawing. Each discipline is checked on its own, so the fire protection section gets its own review and its own results. It measures DWG and DXF files automatically, floor by floor. An AI assistant, Claude or Gemini, answers questions about the regulation and the project. The interface is in Georgian and English.

![Home](docs/screenshots/home.png)

![Report](docs/screenshots/report.png)

## How it works

1. **Add files.** Drop files or a whole folder. Each file gets a discipline (architecture, structure, fire protection, water and sewage, heating and ventilation, electrical, low voltage, other), guessed from its name and folder, which you can change.
2. **Read.** Every file becomes sheets in one viewer, grouped by discipline and file. PDFs are read with PyMuPDF. DWG files are converted to DXF with LibreDWG, then drawn with ezdxf; each file runs in its own process, several at a time, so a bad file costs that file and not the project. A sheet is what the designer framed in a layout's viewport, or else a part of model space with clear gaps around it.
3. **Measure.** No AI is involved, so the same file always gives the same numbers. See [Measuring](#measuring).
4. **Building data.** With an AI connected, a quick pass with the fast model reads the facts most rules depend on: class, occupancy, storeys above and below ground, the height of the top occupied floor above fire-vehicle access, and sprinklers. What it cannot find is asked in a short form, with choice buttons, number fields with units and, where CAD measured something, a suggested value. Tick **Also ask about details** before the check to be asked about floor area, building length and width, occupant load, construction type, dwelling units and enclosed parking too. Blank answers are skipped, **Skip** goes on without any, and the report shows each fact as found on the drawings or given by you.
5. **Check, one section at a time.** With an API key, the AI reviews each discipline's sheets in a request of its own, against only the rules those drawings can show, using that discipline's skill (see [Sections and skills](#sections-and-skills)). Every section is given the building data and they run side by side. If the building data could not be read, architecture goes first and the building it finds is given to the others. Each gives one result per rule: non-compliant, missing, to verify, compliant or not applicable. It gets the measurements too, and cites text on the sheet, so a finding points at the exact place. Results merge per rule: a failure found in any section stands, otherwise the clearest answer wins, so an alarm drawn on the low-voltage sheets is not "missing" from the fire sheets.
   - **Claude** (`claude-opus-5-5`, an Anthropic key starting `sk-ant-`) is used when its key is set. Drawings are sent inline, up to 20 MB per section; if Claude declines a request, the API passes it to a fallback model. `NORMA_CLAUDE_MODEL` names another model.
   - **Gemini on Vertex AI** is used next, in your own Google Cloud project (see [Vertex AI](#vertex-ai)): checks go to `gemini-4-argon` at medium thinking, then `gemini-4-carbon` and `gemini-3.8-flash`; chat goes to `gemini-4-hydrogen`, then `gemini-4-argon`. Drawings are sent inline, up to 14 MB per section.
   - **Gemini with an API key** is used otherwise (`gemini-3.6-flash` first; when a model is overloaded, stuck or not open to the key, NORMA moves to `gemini-3.8-flash`, `gemini-3.5-flash` and `gemini-3.5-flash-lite`, and keeps to the one that answered). A section over Gemini's 50 MB limit is sent as lighter images.
6. **Report.** The engine builds the report. Clause numbers, requirements and quotes come from the rulebook, not from the model. A measured result replaces the AI's unless the AI found something worse. A clause that none of the added drawings can show is **not in this check**: it is listed apart, collapsed, and does not affect the verdict, so checking only the fire protection drawings gives a fire protection report. Any other rule with no result is listed as "to verify", and says why: the AI could not review that section, or no answer came back. Silence never counts as a pass. If one section's review fails, the others still stand.
7. **Review.** Every result reads in Georgian or English, values included. Filter by section (architecture, structure, fire protection, water and sewage, heating and ventilation, electrical, low voltage) and by category: use and height, means of egress, fire protection systems, fire access and site, fire resistance, accessibility, and interior environment. A section shows every clause its drawings can show. Selecting a finding opens its sheet, zooms in and highlights the place. **By Floor** shows the measurements as a table, and selecting a value shows that place.

Without an API key, DWG and DXF files are still measured and get a report of what the measurements settle, with the other rules left to verify. PDFs need the key. The sample project shows a full report, and the assistant answers from the rulebook and the report, saying that the answer is not from AI. If the AI fails during a check, the measured report still appears, with a notice.

## Measuring

`engine/measure.py` finds things from their shapes, not from layer names, because every office names layers differently.

| What | How | Rules |
| --- | --- | --- |
| Stairs | Parallel lines of one length, evenly spaced at tread distance. Flight width, tread, and the riser from labels like `20R x 16` | 1009.4, 1009.7.2, 1021.2 |
| Levels | Marks like `+32.000` | 202 |
| Doors | Quarter arcs with a leaf. Width is the leaf, so clear width is an estimate | 1008.1.1 |
| Stair separation | A map of the walls, walking out from each stair to its room. Given both ways: between outer walls and between interiors | 403.5.1 |
| Corridor, dead end | The open space most doors open onto. Its width comes from the middle line; the dead end is the corridor beyond the route between the stairs | 1018.2, 1018.4 |
| Sprinklers, cabinets, landing valves | Blocks named or layered as such | Shown in the table only |

Stairs and levels are read directly. The wall map gives estimates, so it never fails a rule alone: a duct or a column can look like a narrow corridor. The widest reading across a floor's disciplines counts, because extra lines can only narrow the map. On a real 27-storey plan it gave stair separation of 9.1 m and 8.5 m, the same as measuring by hand. It does not read rotated viewports, and a sheet with no door arcs gets no corridor.

## Sections and skills

Files get a discipline when they are added. Files marked "other" (explanatory notes, site plans, mixed sets) are read with architecture, and also answer the rules that no other added discipline can. A single PDF from before projects had disciplines is reviewed in one request against every rule.

Each rule in `engine/rulebook.py` lists the disciplines whose drawings show it (`on`): sprinklers are checked on fire drawings, standpipes on fire and water drawings, the fire alarm on fire and low-voltage drawings, stair pressurization on fire and HVAC drawings.

`engine/skills/<discipline>/SKILL.md` holds one review skill per discipline, in the Agent Skills format: what the sheets usually hold and their Georgian names, what to work out first, where each clause is shown, and when to answer missing rather than verify. The engine puts the skill into that section's instructions for Claude or Gemini. The files also work as skills on their own, for example in Claude Code or claude.ai.

## The regulation

- `engine/rulebook.py` holds 83 checks that can be made from drawings, across chapters 2–12 and the fire access sections 915–916. It is a selection, not the whole regulation.
- `engine/data/regulation/` holds the public 2016 text and all 21 amending resolutions from [matsne.gov.ge](https://matsne.gov.ge/ka/document/view/3176389), up to №426 of 4 September 2026. Matsne's consolidated text is paid, so the current wording was worked out from the amendments.
- `test_rulebook.py` fails if a quote in the rulebook is not word for word in the document it names.
- When the regulation changes, add the amendment there and review the rules it touches.

The resolution applies to class III, IV and V buildings. NORMA is an aid for designers: results need checking by a specialist, and the permitting authority makes the decision.

## Privacy

With an API key, the project's sheets are sent to Anthropic (Claude) or Google (Gemini) during a check, and in chat when a report is open. Without a key, nothing leaves the computer. Everything else stays in `~/.norma`, including reports and the API keys. Uploaded files are deleted once they are read; their sheets stay in the report.

Claude gets the drawings inline in each request, so nothing is stored in Anthropic's file storage. Anthropic does not train its models on API data by default.

Under [Google's terms](https://ai.google.dev/gemini-api/terms), content sent with a free key may be used to improve Google's products and may be read by human reviewers, and Google says not to submit confidential information. With a key from a project with billing enabled, prompts and files are not used to improve products. Use a paid key for client drawings.

## Setup

```bash
npm install
python3 -m venv engine/.venv
engine/.venv/bin/python -m pip install -r engine/requirements.txt
brew install libredwg   # to open DWG files; DXF and PDF work without it
```

## Run

```bash
npm run tauri dev
```

The app starts the Python engine on a free local port and stops it on quit. Add an API key in **Settings** for the AI review and chat: a Claude key from the [Anthropic Console](https://platform.claude.com/), or a Gemini key from [Google AI Studio](https://aistudio.google.com/apikey). NORMA tells them apart by the `sk-ant-` prefix and keeps both; with both, Claude does the checks. `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` in the environment work too. Set `NORMA_CLAUDE_MODEL` or `NORMA_MODEL` to pin a Claude or Gemini model.

To work on the UI in a browser:

```bash
cd engine && .venv/bin/python server.py --port 8100
npm run dev   # http://localhost:1440, /api is proxied to port 8100
```

## Project structure

| Path | What it does |
| --- | --- |
| `src/components/` | Home, Progress, ReportView, Viewer (drawing, pins and sheet list), Measurements, Assistant, Settings |
| `src/lib/` | `api.ts` talks to the engine; `project.ts` collects files and guesses disciplines; `i18n.ts` holds the Georgian and English text |
| `src-tauri/` | Desktop shell: starts and stops the engine |
| `engine/server.py` | Local API: upload, checks, page images, reports, chat |
| `engine/sections.py` | Checks a project one discipline at a time: which sheets and rules go together, the prompt and schema, merging the answers |
| `engine/skills/` | One review skill per discipline (`SKILL.md`), used in that section's instructions |
| `engine/claude_ai.py` | The Claude calls: a section's review, chat and its regulation search tool |
| `engine/ai.py` | The Gemini calls: a section's review, chat and its regulation search tool, offline answers |
| `engine/report.py` | Turns a review into the report, with its sections |
| `engine/rulebook.py` | The checks, with clause, requirement and quote |
| `engine/regulation.py` | Search over the regulation and amendments |
| `engine/project.py` | Reads a project's files into one drawing set |
| `engine/cad.py` | DWG and DXF: conversion, sheets, flat geometry, PDF pages. Also the worker for one file |
| `engine/measure.py` | Measurements from CAD geometry, the floor table, and the rules they settle |
| `engine/pdf_tools.py` | Page images and positioned text |
| `engine/build_sample.py` | Builds the sample project in `engine/demo/` (needs `pymupdf-fonts`) |

## Vertex AI

To run Gemini in your own Google Cloud project instead of with an API key:

1. In the Google Cloud console, turn on billing and the Vertex AI API for the project.
2. Sign in on this computer: `gcloud auth application-default login`, then `gcloud auth application-default set-quota-project PROJECT_ID`.
3. In NORMA's **Settings**, under Google Cloud Vertex AI, enter the project ID and the region (`global` unless you need another) and choose **Connect**. NORMA sends one test request first and says what is wrong if it fails: no sign-in, no permission (the account needs the Vertex AI User role), or no model in that region.

`NORMA_VERTEX_PROJECT` and `NORMA_VERTEX_LOCATION` in the environment work too. A Claude key, if one is set, still comes first.

Measured on a three-page section: Gemini 4 Argon at high thinking was silent for 400 s and took ten minutes, at medium it began in 7 s and finished in three, with the same findings. So checks use medium thinking. A project takes the architecture review plus the slowest other section, a few minutes for a small one.

## Tests

```bash
cd engine
.venv/bin/python -m unittest test_rulebook test_engine test_cad test_sections test_claude
```

`test_engine.py` and `test_claude.py` run the real Gemini and Anthropic SDKs against local stand-ins for Google's and Anthropic's servers. `test_sections.py` checks which sheets and rules go together and how answers merge. `test_cad.py` measures a floor plan it draws itself, so the right answers are known.

## Creators

- **Temo Dzneladze**
- **Elizbar Kheladze**
