from teammember import TeamMember


class Team:
    """Represents a team with configuration for sprint planning.
    
    Attributes:
        name: Team name
        jira_key: JIRA project key for the team
        points_per_epic: Story points per epic
        manager: Manager name
        team_members: List of TeamMember objects
        people_of_interest: List of POI names (for tracking absences)
        point_capacity: Point capacity per person per day
        load_factor: Load factor for capacity calculations
        engineering_split: Proportion of capacity for engineering work
        absences_canvas: Slack canvas ID for absences
        capacity_canvas: Slack canvas ID for capacity
        support_canvas: Slack canvas ID for support assignments
    """
    
    def __init__(
        self,
        name,
        jira_key,
        points_per_epic,
        manager,
        team_members,
        people_of_interest,
        point_capacity,
        load_factor,
        engineering_split,
        absences_canvas=None,
        capacity_canvas=None,
        support_canvas=None
    ):
        self.name = name
        self.jira_key = jira_key
        self.points_per_epic = points_per_epic
        self.manager = manager
        # Accept a list of dicts and instantiate TeamMember objects
        self.team_members = [TeamMember.from_dict(m) if not isinstance(m, TeamMember) else m for m in team_members]
        self.people_of_interest = people_of_interest
        self.point_capacity = point_capacity
        self.load_factor = load_factor
        self.engineering_split = engineering_split
        self.absences_canvas = absences_canvas
        self.capacity_canvas = capacity_canvas
        self.support_canvas = support_canvas


    def __repr__(self):
        """String representation of Team."""
        return f"<Team {self.name} (support_canvas={self.support_canvas})>"
