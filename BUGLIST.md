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

Does the data need to be re-embedded when the model changes.  IF so make this automatic after warning the user before hand that it will take time.  Get them to confirm their acceptance whenever a re-embed is required.  

-------

## DVA-SCHEDULER

What is dva-scheduler and why is not NOT running?  When does it run and when should the container status of it not running matter?  If not required remove it from all code, docker and documentation. I belive it was originally to initiate scheduled backups.  See backup section below prior to implementing changes or making a decision.

## BACKUP

Does the data management back up process actually back up everything except from github?  If not it needs to.  Also make the back up location path something user set.  Update admin_tasks.ps1, makes sure it works entirely prior to contiuing with any scheduling as valid.

## User Seed Submission via GUI

User add seed to scraper via gui has gone missing.

Add the following seeds iwth normal duplication, trust and ranking logic etc:

<https://soldieron.org.au/>
<https://www.veteransemployment.gov.au/veterans-finding-job/your-job-search>
<https://apod.com.au/>
<https://veteranssa.sa.gov.au/>
<https://www.army.gov.au/community/members-veterans/veterans>
<https://www.servicesaustralia.gov.au/support-for-veterans?context=64107>
<https://www.veterans.nsw.gov.au/education/how-to-research-a-veteran/>
<https://www.rslaustralia.org/veteran-support>
<https://www.veterans.nsw.gov.au/support/information-services/>
<https://www.victorianveteranscouncil.org.au/ex-service-and-veterans-service-organisations>
<https://www.veteransemployment.gov.au/>
<https://www.veteransemployment.gov.au/veterans-finding-job/your-job-search>
<https://www.navy.gov.au/navy-people/veteran-support>
<https://www.healthdirect.gov.au/partners/department-of-veterans-affairs>
<https://mindconnectionsshs.com.au/top-veteran-health-services-australia/>
<https://www.defence.gov.au/adf-members-families/wellbeing/support-services/veterans-ex-serving-members>
<https://www.legacy.com.au/>
<https://www.veterans.nsw.gov.au/>
<https://pva.org.au/>

**Where hardware aware model routing is enabled, this may be invalid changes....**

VALIDATE REQUIREMENT AFTER MODEL ROUTING CHANGES:

Dynamic update of System Load (%) bar information without breaking response visibility or refreshing entire app.

RESOLVED (March 2026):

* Added dva-api container (FastAPI on port 8502) for System Status polling
* UI sidebar displays styled metrics (GPU, VRAM, Temp, Net)
* Stats update automatically on page interaction
* No refresh button during generation to prevent cancellation
* Removed auto-refresh (caused full page reloads in Streamlit)

VRAM critical warning should be shown once per minute while condition is true.  When hover over with mouse, explain concisley the problem and solution (e.g. model bigger than vram - choose another model using.

Reduce the padding between sections System Status and Model Routing.

Make the entries under Knowledge Base be able to be clicked on as hyperlinks to websites except for Support where an internal page will be displayed explaining what Support seeds contain.  For all else, as follows:

CLIK             = <https://clik.dva.gov.au/>
DVA_GOV          = <https://www.dva.gov.au/>
LEGISLATION      = BOTH :  <https://www.rma.gov.au/> AND <https://www.legislation.gov.au/> to be opened in different tabs in browser when clicked.
REDDIT          = <https://www.reddit.com/r/DVAAustralia/>
SUPPORT         = create internal webpage to be displayed in app.  for now make it a landing page with the seeds listed.
