# DVA Wizard v3.0 - Bug List & Feature Requests

## v3.0 Architecture Change (March 2026)

**IMPORTANT - Architecture Change:**

The v3.0 has been rebuilt from the ground up to address the Streamlit limitations:

- **Frontend:** React SPA served by Nginx (replaces Streamlit)
- **Backend:** FastAPI (enhanced from existing api.py)
- **Real-time Status:** Polls every 2 seconds via JavaScript - no page refresh needed
- **Container Changes:**
  - `dva-web` now serves React build via Nginx on port 80
  - `dva-api` handles chat + system status endpoints
  - Access UI at http://localhost:8501
  - Access API at http://localhost:8502

---

## Migration Notes (v3.0)

- Migrated from dva-assistant-v2 to dva_wizard_v3
- New GitHub repo: https://github.com/Overlawd/dva_wizard_v3.git
- Added new seed URLs for veteran support sites

---

# FIX the following errors in scraper.py

* Expression of type "None" cannot be assigned to parameter of type "str"
    "None" is not assignable to "str" line 179 Col 74

Does upgrading python to the latest version provide any meaningful beenfits to this application?

## UI

### Drop down list

with regards to ui.py, it does not Automatically resets to "Select a question..." after the answer is displayed

### Citations and References

Provide better summaries of the references.  Some are simply one letter.  Needs to be a short sentence.

For example - see the references are listed in long and short form.  do one only.

```text
[1] Defence Home Ownership Assistance Scheme (DHOAS) - https://www.dva.gov.au/providers/assistance-for-veterans/dhoas [2] DVA Rent Assistance - https://www.dva.gov.au/personal-claims/rent-assistance [3] Summary of Australian Veteran DVA Entitlements for Housing and Financial Support (source: context knowledge base) [4] DVA Financial Hardship Support (source: context knowledge base)

[1] Loans and insurance

[2] Defence Service Homes loans

[3] Home Equity Access Scheme

[4] Our Blog

[5] Housing Entitlements for Veterans: Accessing Secure Homes and Accommodation

[6] Confused: Is DVA Incapacity Payment the same as a Class A/B/C pension?

```

### RE-EMBEDDING and MODEL CHANGE

Does the data need to be re-embedded when the model changes.  IF so make this automatic when model is changed in admin_tasks.ps1 after warning the user before hand that it will take time.  Get them to confirm their acceptance whenever a re-embed is required.  

-------

## BACKUP

Does the data management back up process actually back up everything except from github?  If not it needs to.  Also make the back up location path something user set.  Update admin_tasks.ps1, makes sure it works entirely prior to contiuing with any scheduling as valid.

## DVA-SCHEDULER

RESOLVED (v3.0):

- Scheduler is properly configured in docker-compose.yml
- Runs automatic monthly scrapes (200 pages) on the 1st of each month at 2:00 AM
- Uses Ofelia to execute `python scraper.py 200 --force` inside the scraper container
- Logs are saved automatically
- Properly documented in README.md
- Can be disabled by removing the scheduler service from docker-compose.yml

Manual trigger: `docker exec dva-scraper python scraper.py 200 --force`

## User Seed Submission via GUI

User add seed to scraper via gui has gone missing.

**Where hardware aware model routing is enabled, this may be invalid changes....**

VALIDATE REQUIREMENT AFTER MODEL ROUTING CHANGES:

Dynamic update of System Load (%) bar information without breaking response visibility or refreshing entire app.

**RESOLVED (v3.0 - React Rebuild):**

- ✅ React frontend with real-time polling (2 second intervals)
- ✅ No page refresh - JavaScript fetches /api/system-status independently
- ✅ Chat and sidebar work independently
- ✅ dva-api container provides system status on port 8502
- ✅ Color-coded load bar with warnings

VRAM critical warning should be shown once per minute while condition is true.  When hover over with mouse, explain concisley the problem and solution (e.g. model bigger than vram - choose another model using.

Reduce the padding between sections System Status and Model Routing.

Make the entries under Knowledge Base be able to be clicked on as hyperlinks to websites except for Support where an internal page will be displayed explaining what Support seeds contain.  For all else, as follows:

CLIK             = <https://clik.dva.gov.au/>
DVA_GOV          = <https://www.dva.gov.au/>
LEGISLATION      = BOTH :  <https://www.rma.gov.au/> AND <https://www.legislation.gov.au/> to be opened in different tabs in browser when clicked.
REDDIT          = <https://www.reddit.com/r/DVAAustralia/>
SUPPORT         = create internal webpage to be displayed in app.  for now make it a landing page with the seeds listed.

---

## v3.0 API Endpoints

| Endpoint | Description |
| --- | --- |
| `GET /api/system-status` | Real-time metrics (GPU, CPU, VRAM) |
| `POST /api/chat` | Send message, get answer |
| `GET /api/common-questions` | FAQ by category |
| `GET /api/knowledge-stats` | Database statistics |
| `GET /api/health` | Health check |

Test commands:
```powershell
curl http://localhost:8502/api/health
curl http://localhost:8502/api/system-status
```
