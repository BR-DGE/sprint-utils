from team import Team
from teammember import TeamMember
from dotenv import load_dotenv
import os
import yaml
from pathlib import Path


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

# Load teams from YAML files
def load_teams():
    """Load team configurations from YAML files in the teams directory."""
    teams = []
    teams_dir = Path(__file__).parent / "teams"
    
    if not teams_dir.exists():
        raise RuntimeError(f"Teams directory not found: {teams_dir}")
    
    # Load all .yaml files from the teams directory
    for yaml_file in sorted(teams_dir.glob("*.yaml")):
        with open(yaml_file, 'r') as f:
            team_config = yaml.safe_load(f)
        
        # Create Team object from YAML config
        team = Team(
            name=team_config['name'],
            jira_key=team_config['jira_key'],
            points_per_epic=team_config['points_per_epic'],
            manager=team_config['manager'],
            team_members=team_config.get('team_members', []),
            people_of_interest=team_config.get('people_of_interest', []),
            point_capacity=team_config['point_capacity'],
            load_factor=team_config['load_factor'],
            engineering_split=team_config['engineering_split'],
            absences_canvas=team_config.get('absences_canvas'),
            capacity_canvas=team_config.get('capacity_canvas'),
            support_canvas=team_config.get('support_canvas')
        )
        teams.append(team)
    
    return teams

teams = load_teams()
