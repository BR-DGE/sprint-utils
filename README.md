# Sprint Planner #

## What is it? ##

This is a very quick and dirty way to extract holiday, L1, and L2 information from various subsystems and display it. It also shows UK bank holidays falling within a sprint (although I'm open to extending this if needs be as the library has holidays for other countries). It then uses this holiday data alongside some multipliers to calculate a rough guide to story point capacity per sprint.

## Why would I want to use this? ##

I'm using it for planning purposes - knowing who will be on holiday in future sprints and who will be unavailable because they're on support duty allows better sprint planning. Knowing about public holidays that could affect my team in advance allows me to adjust the availability in the plan early to account for it. It also means that the data is in a single place, and I'm not trying to manually pull things out of multiple systems by hand every time I'm doing sprint planning. I also didn't have any account on PagerDuty, so I was relying on my engineers to tell me in advance whether they were doing support.

## How do I run it? ##

This is a Python script (I'm using v3.13.2), so my recommendation would be to use [Astral](https://docs.astral.sh/uv/getting-started/installation/) to install the required packages:

```
uv venv --python 3.13.2
uv pip install -r requirements.txt
```

You can, of course, use any venv mechanism you like (or no venv at all) as you see fit.

The code also makes use of Kenny's Jira utils repo as a submodule (which will go into a subdirectory called `jirautils`), so that needs to be initialised:

```
git submodule init
```

As changes are made to that module, you can use the following command to update it:

```
git submodule update
```

Once that's in place, you activate the venv and run the script:

```
source .venv/bin/activate
python3 sprintplanner.py Clocktower -c
deactivate
```

There is a bash script called `sprintplanner` that can be modified to suit whichever location you've installed this in. The example file supposes that you've put the `sprint-utils` directory containing this code into your `Documents` folder.

If you call the script with `-h` you'll get the help output explaining what the various output options are:

```
usage: sprintplanner.py [-h] [-capacity] [-absences] [-l1] [-l2] [-interest] [-full] [-purge] team_name

Sprint planner tool

positional arguments:
  team_name      Team name

options:
  -h, --help     show this help message and exit
  -capacity, -c  Show capacity summary table
  -absences, -a  Show upcoming absences grouped by person
  -l1            Show upcoming L1 assignments
  -l2            Show upcoming L2 assignments
  -interest, -i  Show upcoming holidays for people of interest and the manager
  -full, -f      Show full output
  -purge, -p     Delete all cached API data before running
  -slack, -s     Send data to Slack
  -xmas, -x      Show Christmas rota CSV output
  -bankhols, -b  Show next 12 months bank holidays
  -warning, -w   Show warning if a person is absent during L1 or L2 shift
  -debug, -d     Dump employee tree, holidays, and pagerduty shifts for debugging
  -calendar, -k  Show calendar of team and POI availability
```

## Configuration ##

Configuration lives in `config.py`, but sensitive values (API keys) are now read from environment variables instead of being hardcoded.

### Environment Variables ###

Environment variables are required for API keys. The project now uses [python-dotenv](https://pypi.org/project/python-dotenv/) to automatically load a `.env` file in the project root if present (it does NOT override already-set variables). If a variable is missing after loading, the program raises an error early.

Set the following variables before running the script (either export them directly, or create a `.env` file using `.env.example`):

```
export BAMBOO_HR_API_KEY=your_bamboo_hr_key
export PAGERDUTY_API_KEY=your_pagerduty_key
export JIRA_API_KEY=your_email@company.com:your_atlassian_api_token
export SLACK_API_KEY=your_slack_token
```

If any are missing the program will raise an error at startup.

Obtain keys/tokens from:
- BambooHR: https://documentation.bamboohr.com/docs/getting-started#section-authentication
- PagerDuty: Request an API key from support / admin
- Atlassian (Jira): https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/
- Slack user/bot token (depending on usage) from a Slack app or legacy token process.

### Other Config Values ###

Within `config.py` you can still adjust non-secret settings:

```
# application configuration
social_dates = ["2025-12-11", "2026-03-18", "2026-06-17", "2026-09-16"]
xmas_rota_dates = ["2025-12-19", "2026-01-05"]
xmas_rota_exclusions = ["Craig Banach", "Donal Stewart"]
number_of_sprints = 8
number_of_sprints_back = 0
api_cache_timeout = 900  # seconds
```

`social_dates` is an array of dates for company socials events where attendance is expected, and will result in each team member's availability for that day being 0.

`number_of_sprints` is number of sprints to show in the output.

`number_of_sprints_back` is an experimental value that might be useful to look at a historical number of sprints, but bear in mind that this is limited in terms of what historical data is available for consumption and 'Done' epics don't show up.

`api_cache_timeout` is the number of seconds for which the cached api results will remain valid. This can be set to any value, but generally the data is unlikely to change rapidly so 15 minutes is probably ample. There's an option to clear out the cache directory entirely (the `-p` flag above) which can be used to clean up this data and to prevent you storing lots of data.

Each team is defined as follows:

```
clocktower = Team(
    name="Clocktower",
    jira_key="CLOCK",
    points_per_epic=9,
    manager="Allan Jones",
    team_members=[
        {"name": "Marc Howarth"},
        {"name": "Aidan Crooks"},
        {"name": "Craig Findlay"},
        {"name": "Andres Olmo"},
        {"name": "Aleksandr Radevic"},
        {"name": "Mike Porter", "leave_date": "2025-11-28"},
        {"name": "Semilore Talabi", "start_date": "2025-12-01", "start_pct": 0.5},
    ],
    people_of_interest=["Allan Jones", "David Richardson", "Connor Bates", "Priya Nimani"],
    point_capacity=0.85,
    load_factor=0.8,
    engineering_split=0.3,
    absences_canvas="F09PL2N8938",
    capacity_canvas="F09P9N467HR",
    support_canvas="F09SUFU1Z0V"
)
```
`name` is only used for display in the output.

`manager` identifies the user who is the team's manager

`team_members` is now a list of dicts, each containing:

- `name`: Display name of the team member
- `pagerduty_name`: Name as stored in PagerDuty (for L1/L2 assignment) for use where this differs from the name in Bamboo (optional)
- `start_date`: Date the member joins the team (optional)
- `start_pct`: Starting percentage FTE (default 1)
- `leave_date`: Date the member leaves the team (optional)

Ramp-up logic is handled via `start_date` and `start_pct` for each member. Leavers are handled via `leave_date`.

`people_of_interest` holds the list of people whose holidays are of interest, but aren't part of the team either in Bamboo or who belong in another team. Examples are managers, testers and product owners. These are used to generate POI holiday output, for example.

`point_capacity`, `load_factor`, and `engineering_split` are all utilised in the story point calculations. At present, the first two are simply multiplied together, but it is anticipated that in future versions of this script we may wish to allow for individual team members to have their own capacities and the existing spreadsheet version uses two variables. The engineering split is simply the split in percentage terms between product and engineering work.

Note that in each case, the names are those in Bamboo and are *not* the friendly/shortform names that people generally use.