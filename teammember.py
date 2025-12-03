class TeamMember:
    """Represents a team member with their configuration.
    
    Attributes:
        name: Member name as it appears in BambooHR
        pagerduty_name: Name as it appears in PagerDuty (defaults to name)
        start_date: Date the member joined (for ramp-up calculations)
        leave_date: Date the member is leaving (if applicable)
        start_pct: Starting capacity percentage (for ramp-up)
    """
    
    def __init__(self, name, pagerduty_name=None, start_date=None, leave_date=None, start_pct=1):
        self.name = name
        self.pagerduty_name = pagerduty_name if pagerduty_name else name
        self.start_date = start_date
        self.leave_date = leave_date
        self.start_pct = start_pct

    @staticmethod
    def from_dict(member_dict):
        """Create a TeamMember from a dictionary.
        
        Args:
            member_dict: Dictionary with member configuration
            
        Returns:
            TeamMember instance
        """
        return TeamMember(
            name=member_dict["name"],
            pagerduty_name=member_dict.get("pagerduty_name", member_dict["name"]),
            start_date=member_dict.get("start_date", None),
            leave_date=member_dict.get("leave_date", None),
            start_pct=member_dict.get("start_pct", 1)
        )

    def to_dict(self):
        """Convert TeamMember to dictionary.
        
        Returns:
            Dictionary representation of the team member
        """
        return {
            "name": self.name,
            "pagerduty_name": self.pagerduty_name,
            "start_date": self.start_date,
            "leave_date": self.leave_date,
            "start_pct": self.start_pct
        }

    def __repr__(self):
        """String representation of TeamMember."""
        return f"<TeamMember {self.name}>"
