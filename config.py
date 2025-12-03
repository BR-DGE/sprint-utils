from team import Team
from teammember import TeamMember
from dotenv import load_dotenv
import os


# Load variables from .env (if present). Does not override existing environment.
load_dotenv(override=False)

# Helper to require environment variables
def _require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val

# API keys now sourced from environment variables (see .env.example / README)
bamboo_hr_api_key = _require_env("BAMBOO_HR_API_KEY")
pagerduty_api_key = _require_env("PAGERDUTY_API_KEY")
jira_api_key = _require_env("JIRA_API_KEY")  # Expected format email:token for basic auth use
slack_api_key = _require_env("SLACK_API_KEY")

# application configuration
social_dates = ["2025-12-11", "2026-03-18", "2026-06-17", "2026-09-16"]
xmas_rota_dates = ["2025-12-19", "2026-01-05"]
xmas_rota_exclusions = ["Craig Banach", "Donal Stewart"]
number_of_sprints = 8
number_of_sprints_back = 0
api_cache_timeout = 900  # seconds

# date and sprint configuration
date_format = '%Y-%m-%d'
first_sprint_date = '2025-03-03'
first_sprint_number = 73
level_one_support_id = 'PGNTR7I'
level_two_support_id = 'PJJERK8'

# team definitions
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

waterloo = Team(
	name="Waterloo",
    jira_key="WAT",
    points_per_epic=9,
	manager="Allan Jones",
    team_members=[
        {"name": "Kate Tindall", "start_date": "2025-11-24"},
        {"name": "Christopher Logue", "pagerduty_name": "Chris Logue", "start_date": "2025-11-24"},
        {"name": "Donal Stewart", "leave_date": "2025-12-19"},
        {"name": "Yelyzaveta Hordynets", "pagerduty_name": "Liz Hordynets"},
        {"name": "Andrew Coburn"},
        {"name": "Andrew Trail"},
        {"name": "Wesley Acheson", "start_date": "2025-12-08"},

    ],
    people_of_interest=["Allan Jones", "Will Gough", "Connor Bates", "Andy Paton"],
    point_capacity=0.8,
    load_factor=0.8,
    engineering_split=0.3,
    absences_canvas="F09QS9RGQCT",
    capacity_canvas="F09QYMVDBHQ",
    support_canvas="F09SRKC9059"
)

glenfinnan = Team(
	name="Glenfinnan",
    jira_key="GLEN",
    points_per_epic=6,
	manager="Kenny Scott",
    team_members=[
        {"name": "John Pooley"},
        {"name": "Charlie Shale"},
        {"name": "David Lynn"},
        {"name": "Kevin Donnelly"},
        {"name": "Wesley Acheson", "leave_date": "2025-12-07"},
        {"name": "Kevin Kossipos"},
        {"name": "Andrew Allan"},
    ],
    people_of_interest=["Kenny Scott, Alan Sambells", "Andy Paton", "Matt Smith"],
    point_capacity=0.8,
    load_factor=0.8,
    engineering_split=0.3,
    absences_canvas="F09UP3P0C2F",
    capacity_canvas="F09UE2CAFGX",
    support_canvas="F0A09QR5G7J"
)

skye = Team(
	name="Skye",
    jira_key="SKYE",
    points_per_epic=9,
	manager="Simon Reid",
    team_members=[
        {"name": "Aaron Savage"},
        {"name": "James Coburn"},
        {"name": "Mikolaj Olejnik"},
        {"name": "Paul Wilson"},
        {"name": "Simon Gross"},
        {"name": "Urszula Drzazga"},
    ],
    people_of_interest=["David Agbowu", "Priya Nimani"],
    point_capacity=0.8,
    load_factor=0.9,
    engineering_split=0.3,
    absences_canvas="#skye-canvas",
    capacity_canvas="Skye Sprint Canvas",
    support_canvas=None
)

sunniberg = Team(
	name="Sunniberg",
    jira_key="SUN",
    points_per_epic=9,
	manager="Stuart Veloso Grant",
    team_members=[
        {"name": "Alex Lazellari"},
        {"name": "William Mcintosh"},
        {"name": "Christopher Feetham"},
        {"name": "Ekaterina Kladova"},
        {"name": "Mack Millar"},
        {"name": "Gary Clark"},
        {"name": "Marcin Juszczyk"},
        {"name": "Craig Banach", "start_date": "2025-11-24"},
    ],
    people_of_interest=["Stuart Veloso Grant", "Alan Sambells"],
    point_capacity=0.8,
    load_factor=0.9,
    engineering_split=0.3,
    absences_canvas="F09UUDRKSLV",
    capacity_canvas="F09UUDSBWKX",
    support_canvas=None
)


platform = Team(
	name="Platform",
    jira_key="PL",
    points_per_epic=9,
	manager="Stuart Radley",
    team_members=[
        {"name": "Allan Kilpatrick"},
        {"name": "Matt Cluness"},
        {"name": "Michael Keightley"},
        {"name": "Roderick Sneddon"},
        {"name": "Ignas Kancleris"},
    ],
    people_of_interest=[],
    point_capacity=0.8,
    load_factor=0.9,
    engineering_split=0.3,
    absences_canvas="#platform-canvas",
    capacity_canvas="Platform Sprint Canvas",
    support_canvas=None
)

teams = [clocktower, waterloo, skye, glenfinnan, sunniberg, platform]
