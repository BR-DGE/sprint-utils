import requests
from config import slack_api_key
from presentation import SprintPresentation

class Slack:
    """Slack API client for updating canvas documents with sprint data."""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://slack.com/api/"


    def update_canvas(self, canvas_id, content):
        """Update a Slack canvas with new content.
        
        Args:
            canvas_id: ID of the Slack canvas to update
            content: Text content to write to the canvas (will be formatted as code block)
            
        Returns:
            JSON response from the Slack API
        """
        url = self.base_url + "canvases.edit"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "canvas_id": canvas_id,
            "changes": [
                {
                    "operation": "replace",
                    "document_content": {
                        "type": "markdown",
                        "markdown": f"```\n{content}\n```"
                    }
                }
            ]
        }
        response = requests.post(url, json=payload, headers=headers)
        return response.json()
    
    @staticmethod
    def send_sprint_data_to_slack(data, team):
        """Send sprint data to Slack canvases.
        
        Updates capacity, absences, and support canvases if configured for the team.
        
        Args:
            data: Sprint data dictionary with capacity and availability information
            team: Team object with canvas IDs for Slack integration
        """
        from sprintplanner import build_calendar_data
        
        slack = Slack(api_key=slack_api_key)
        # capacity (includes calendar)
        if team.capacity_canvas:
            capacity_text = SprintPresentation.render_capacity_table(data)
            calendar_text = SprintPresentation.render_calendar(*build_calendar_data(team, data))
            text = capacity_text + "\n\nCalendar\n\n" + calendar_text
            slack.update_canvas(team.capacity_canvas, text)
        # absences
        if team.absences_canvas:
            text = SprintPresentation.render_absences_and_oncall(data, team)
            slack.update_canvas(team.absences_canvas, text)
        # support
        if team.support_canvas:
            text = SprintPresentation.render_support(data, team)
            slack.update_canvas(team.support_canvas, text)
