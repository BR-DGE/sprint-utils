import csv
import io
from datetime import datetime, timedelta
from config import social_dates
import holidays as hols

date_format = '%Y-%m-%d'


class SprintPresentation:
    """Renders sprint planning data in various formats for display and export."""
    
    @staticmethod
    def render_l1_l2_absence_warnings(data):
        """Generate warnings for team members scheduled for on-call during absences.
        
        Args:
            data: Sprint data dictionary containing L1/L2 assignments and holidays
            
        Returns:
            String with warnings or "No L1/L2 absence warnings."
        """
        warnings = []
        for sprint in data['sprints']:
            l1 = sprint.get('l1', {})
            l2 = sprint.get('l2', {})
            holidays = sprint.get('holidays', [])
            absences_map = {}
            for row in holidays:
                name = row[0]
                absences = SprintPresentation.safe_eval_absences(row[2]) if len(row) > 2 else []
                for a in absences:
                    start = a[0] if isinstance(a[0], str) else a[0].strftime('%Y-%m-%d')
                    end = a[1] if isinstance(a[1], str) else a[1].strftime('%Y-%m-%d')
                    start_dt = datetime.strptime(start, '%Y-%m-%d').date()
                    end_dt = datetime.strptime(end, '%Y-%m-%d').date()
                    for n in range((end_dt - start_dt).days + 1):
                        absences_map.setdefault(name, set()).add(start_dt + timedelta(days=n))
            for name, l1_dates in l1.items():
                for d in l1_dates:
                    d_dt = datetime.strptime(d, '%Y-%m-%d').date() if isinstance(d, str) else d
                    if name in absences_map and d_dt in absences_map[name]:
                        warnings.append(f"WARNING: {name} is absent on {d_dt} but scheduled for L1 shift.")
            for name, l2_dates in l2.items():
                for d in l2_dates:
                    d_dt = datetime.strptime(d, '%Y-%m-%d').date() if isinstance(d, str) else d
                    if name in absences_map and d_dt in absences_map[name]:
                        warnings.append(f"WARNING: {name} is absent on {d_dt} but scheduled for L2 shift.")
        return '\n'.join(warnings) if warnings else "No L1/L2 absence warnings."
    
    
    @staticmethod
    def render_xmas_rota_csv(date_list, user_absence_map):
        """Render Christmas rota as CSV format.
        
        Args:
            date_list: List of dates to include in the rota
            user_absence_map: Dictionary mapping names to sets of absence dates
            
        Returns:
            CSV formatted string
        """
        header = ["Name"] + [d.strftime("%A %Y-%m-%d") for d in date_list]
        rows = []
        for display_name, absence_dates in user_absence_map.items():
            row = [display_name]
            for d in date_list:
                row.append("1" if d in absence_dates else "")
            rows.append(row)
        rows.sort(key=lambda x: x[0])
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)
        return output.getvalue()
    
    
    @staticmethod
    def filter_future_dates(dates):
        """Filter list of dates to only include future dates.
        
        Args:
            dates: List of date strings
            
        Returns:
            Filtered list of dates >= today
        """
        today = datetime.now().strftime(date_format)
        return [d for d in dates if d >= today]


    @staticmethod
    def filter_future_holiday_ranges(ranges):
        """Filter list of date ranges to only include those ending in the future.
        
        Args:
            ranges: List of (start, end) date tuples
            
        Returns:
            Filtered list of ranges where end >= today
        """
        today = datetime.now().strftime(date_format)
        return [(start, end) for start, end in ranges if end >= today]


    @staticmethod
    def aggregate_assignments(data, key):
        """Aggregate L1/L2 assignments across all sprints.
        
        Args:
            data: Sprint data dictionary
            key: 'l1' or 'l2' to specify which assignments to aggregate
            
        Returns:
            Dictionary mapping names to sets of assignment dates
        """
        assignments = {}
        for sprint in data['sprints']:
            for name, dates in sprint[key].items():
                if name not in assignments:
                    assignments[name] = set()
                for d in SprintPresentation.filter_future_dates(dates):
                    assignments[name].add(d)
        return assignments


    @staticmethod
    def sort_and_render_table(rows, headers=None, label=None, sort_by=0):
        """Sort and render a table with optional headers and label.
        
        Args:
            rows: List of row data
            headers: Optional list of column headers
            label: Optional label to display above table
            sort_by: Column index to sort by (0 = first column)
            
        Returns:
            Formatted table string
        """
        if sort_by:
            rows.sort(key=lambda row: row[sort_by])
        output = ""
        if not rows:
            if label:
                output += f"  None ({label})\n"
            else:
                output += "  None\n"
            return output
        if label:
            output += f"{label}\n"
        output += SprintPresentation.build_aligned_table(rows, headers=headers)
        return output


    @staticmethod
    def safe_eval_absences(absences):
        """Safely parse absence data which may be in various formats.
        
        Handles string representations, lists of tuples, or pre-formatted data.
        
        Args:
            absences: Absence data in various formats
            
        Returns:
            List of absence tuples or empty list
        """
        # If absences is a string, try to eval, else return as is
        if isinstance(absences, str):
            try:
                return eval(absences)
            except Exception:
                return []
        if isinstance(absences, (list, tuple)):
            # If it's a list of tuples, return as is
            if absences and isinstance(absences[0], (tuple, list)):
                return absences
            # If it's a list of date ranges as strings, wrap in a list
            if absences and isinstance(absences[0], str):
                return absences
        # If it's already a formatted string, return empty list
        return []


    @staticmethod
    def filter_future_absence_ranges(absence_ranges):
        """Filter absence ranges to only include those ending in the future.
        
        Args:
            absence_ranges: List of (start, end) date tuples
            
        Returns:
            Filtered list of ranges where end >= today
        """
        today = datetime.now().strftime(date_format)
        return [(start, end) for start, end in absence_ranges if str(end) >= today]


    @staticmethod
    def format_date_ranges(dates):
        """Format a list of dates into compact range strings.
        
        Consecutive dates are collapsed into ranges (e.g., "2025-01-01 - 2025-01-03").
        
        Args:
            dates: Sorted list of date strings or datetime.date objects
            
        Returns:
            Comma-separated string of dates and date ranges
        """
        # Accepts a sorted list of date strings or datetime.date objects
        if not dates:
            return ""
        # Convert to date objects if needed
        if isinstance(dates[0], str):
            dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in dates]
        dates.sort()
        ranges = []
        start = end = dates[0]
        for d in dates[1:]:
            if (d - end).days == 1:
                end = d
            else:
                if start == end:
                    ranges.append(start.strftime('%Y-%m-%d'))
                else:
                    ranges.append(f"{start.strftime('%Y-%m-%d')} - {end.strftime('%Y-%m-%d')}")
                start = end = d
        # Add last range
        if start == end:
            ranges.append(start.strftime('%Y-%m-%d'))
        else:
            ranges.append(f"{start.strftime('%Y-%m-%d')} - {end.strftime('%Y-%m-%d')}")
        return ", ".join(ranges)


    @staticmethod
    def format_absence_ranges(absences):
        """Format absence tuples into readable date range strings.
        
        Args:
            absences: List of tuples (start, end, ...) with date data
            
        Returns:
            Comma-separated string of formatted date ranges
        """
        # absences: list of tuples (start, end, ...), but may contain strings
        formatted = []
        for a in absences:
            # Handle if a[0] or a[1] is a string
            if isinstance(a[0], str):
                start_str = a[0]
            else:
                start_str = a[0].strftime('%Y-%m-%d')
            if isinstance(a[1], str):
                end_str = a[1]
            else:
                end_str = a[1].strftime('%Y-%m-%d')
            if start_str == end_str:
                formatted.append(start_str)
            else:
                formatted.append(f"{start_str} - {end_str}")
        return ", ".join(formatted)


    @staticmethod
    def build_holiday_rows(sprints, key):
        """Build rows for holiday display from sprint data.
        
        Args:
            sprints: List of sprint dictionaries
            key: 'holidays' or 'poi_manager_holidays'
            
        Returns:
            List of [name, formatted_date_range] rows
        """
        rows = []
        today = datetime.now().date()
        for sprint in sprints:
            for row in sprint.get(key, []):
                name = row[0]
                absences = SprintPresentation.safe_eval_absences(row[2])
                for a in absences:
                    # Format each absence as a single row, skip if already ended
                    end_date = a[1] if not isinstance(a[1], str) else datetime.strptime(a[1], "%Y-%m-%d").date()
                    if end_date < today:
                        continue
                    start_str = a[0] if isinstance(a[0], str) else a[0].strftime('%Y-%m-%d')
                    end_str = a[1] if isinstance(a[1], str) else a[1].strftime('%Y-%m-%d')
                    if start_str == end_str:
                        formatted = start_str
                    else:
                        formatted = f"{start_str} - {end_str}"
                    rows.append([name, formatted])
        return rows


    @staticmethod
    def list_gb_public_holidays(division, start, end):
        """List UK public holidays for a specific division.
        
        Args:
            division: UK division code ('ENG', 'SCT', 'WLS', 'NIR')
            start: Start datetime
            end: End datetime
            
        Returns:
            Tuple of (public_holidays dict, formatted output string)
        """
        public_holidays = {}
        output = ""
        for date, name in sorted(hols.GB(subdiv=division, years=[start.year,start.year + 1]).items()):
            if date >= start.date() and date <= end.date():
                public_holidays[date] = name
        if not public_holidays:
            output += f"None ({division})\n"
        else:
            for key, value in public_holidays.items():
                output += f"{key}: {value} ({division})\n"
        return public_holidays, output


    @staticmethod
    def list_ie_public_holidays(start, end):
        """List Irish public holidays.
        
        Args:
            start: Start datetime
            end: End datetime
            
        Returns:
            Tuple of (public_holidays dict, formatted output string)
        """
        public_holidays = {}
        output = ""
        for date, name in sorted(hols.IE(years=[start.year,start.year + 1]).items()):
            if date >= start.date() and date <= end.date():
                public_holidays[date] = name
        if not public_holidays:
            output += "None (IE)\n"
        else:
            for key, value in public_holidays.items():
                output += f"{key}: {value} (IE)\n"
        return public_holidays, output


    @staticmethod
    def build_aligned_table(rows, headers=None):
        """Build a text table with aligned columns.
        
        Args:
            rows: List of row data
            headers: Optional list of column headers
            
        Returns:
            Formatted table string with aligned columns
        """
        if not rows:
            return ""
        output = ""
        if headers:
            col_widths = [max(len(str(h)), max(len(str(item)) for item in col)) for h, col in zip(headers, zip(*rows))]
        else:
            col_widths = [max(len(str(item)) for item in col) for col in zip(*rows)]
        if headers:
            header_row = "  ".join(f"{h:<{w}}" for h, w in zip(headers, col_widths))
            output += header_row + "\n"
            output += "  ".join("-" * w for w in col_widths) + "\n"
        for row in rows:
            output += "  ".join(f"{str(item):<{w}}" for item, w in zip(row, col_widths)) + "\n"
        return output


    @staticmethod
    def render_team_availability(data):
        """Render team availability table with capacity calculations.
        
        Args:
            data: Team availability data with rows, totals, and point calculations
            
        Returns:
            Formatted availability summary string
        """
        output = "\nTeam Availability:\n"
        # Format holidays, L1, L2 columns with ranges
        formatted_rows = []
        for row in data["rows"]:
            name, days, holidays, l1, l2 = row
            holidays_str = SprintPresentation.format_date_ranges(sorted(holidays)) if isinstance(holidays, (list, set)) and holidays else str(holidays)
            l1_str = SprintPresentation.format_date_ranges(sorted(l1)) if isinstance(l1, (list, set)) and l1 else str(l1)
            l2_str = SprintPresentation.format_date_ranges(sorted(l2)) if isinstance(l2, (list, set)) and l2 else str(l2)
            formatted_rows.append([name, days, holidays_str, l1_str, l2_str])
        output += SprintPresentation.sort_and_render_table(formatted_rows, headers=["Name", "Days", "Holidays", "L1", "L2"])
        output += f"Total available days: {data['total_team_days']}\n\n"
        output += f"Scheduled Epics:  {data['sprint_epic_total']:.1f} ({data['sprint_epic_total'] * data['team'].points_per_epic:.1f} points)\n"
        output += f"Estimated point capacity: {data['points']:.1f}\n"
        output += f"  ENG:  {data['eng_points']:.1f}\n"
        output += f"  PROD: {data['prod_points']:.1f}\n"
        if data['sprint_epic_total'] * data['team'].points_per_epic > data['points']:
            output += f"  WARNING: Scheduled epics exceed available point capacity\n"
        for name, date_str in data['starters_this_sprint']:
            output += f"NOTE: {name} joins the team on {date_str}.\n"
        for name, date_str in data['leavers_this_sprint']:
            output += f"NOTE: {name} is leaving the team on {date_str}.\n"
        if data['ramping_this_sprint']:
            output += "Ramping up this sprint:\n"
            for name, pct in data['ramping_this_sprint']:
                output += f"  {name} (ramp multiplier: {pct}%)\n"
        return output


    @staticmethod
    def render_sprint_data(data):
        """Render comprehensive sprint data including holidays, on-call, and availability.
        
        Args:
            data: Complete sprint data dictionary
            
        Returns:
            Formatted full sprint report string
        """
        output = f"Team: {data['team'].name} | Manager: {data['team'].manager} | Team ({len(data['core_display_names'])}): {data['core_display_names']}\n"
        for sprint in data['sprints']:
            output += f"\nSprint {sprint['sprint_number']}: {sprint['start']} to {sprint['end']}\n"
            if sprint['social']:
                output += f"This sprint includes a company social on {sprint['social']} (availability reduced by 1 day for all team members)\n"
            output += "Holidays:\n"
            holiday_rows = []
            for row in sprint.get('holidays', []):
                name = row[0]
                absences = SprintPresentation.safe_eval_absences(row[2])
                for a in absences:
                    start_str = a[0] if isinstance(a[0], str) else a[0].strftime('%Y-%m-%d')
                    end_str = a[1] if isinstance(a[1], str) else a[1].strftime('%Y-%m-%d')
                    formatted = start_str if start_str == end_str else f"{start_str} - {end_str}"
                    holiday_rows.append((name, formatted))
            holiday_rows = [list(t) for t in sorted(set(holiday_rows))]
            output += SprintPresentation.sort_and_render_table(holiday_rows, headers=["Name", "Holiday"])
            output += "\nManager/POI Holidays:\n"
            poi_rows = []
            for row in sprint.get('poi_manager_holidays', []):
                name = row[0]
                absences = SprintPresentation.safe_eval_absences(row[2])
                for a in absences:
                    start_str = a[0] if isinstance(a[0], str) else a[0].strftime('%Y-%m-%d')
                    end_str = a[1] if isinstance(a[1], str) else a[1].strftime('%Y-%m-%d')
                    formatted = start_str if start_str == end_str else f"{start_str} - {end_str}"
                    poi_rows.append((name, formatted))
            poi_rows = [list(t) for t in sorted(set(poi_rows))]
            output += SprintPresentation.sort_and_render_table(poi_rows, headers=["Name", "Holiday"])
            output += '\nBank Holidays:\n'
            for division in ['SCT', 'ENG', 'NIR', 'WLS']:
                bh, bh_output = SprintPresentation.list_gb_public_holidays(division, datetime.strptime(sprint['start'], date_format), datetime.strptime(sprint['end'], date_format))
                if bh:
                    formatted_bh = SprintPresentation.format_date_ranges(sorted(bh.keys()))
                    output += f"{division} Bank Holidays: {formatted_bh}\n"
                else:
                    output += bh_output
            ie_bh, ie_output = SprintPresentation.list_ie_public_holidays(datetime.strptime(sprint['start'], date_format), datetime.strptime(sprint['end'], date_format))
            if ie_bh:
                formatted_ie_bh = SprintPresentation.format_date_ranges(sorted(ie_bh.keys()))
                output += f"IE Bank Holidays: {formatted_ie_bh}\n"
            else:
                output += ie_output
            output += "\nOn Call:\n"
            output += "L1:\n"
            l1 = sprint['l1']
            l1_rows = []
            for name, dates in l1.items():
                formatted_dates = SprintPresentation.format_date_ranges(sorted(dates))
                l1_rows.append([str(name), len(dates), formatted_dates])
            output += SprintPresentation.sort_and_render_table(l1_rows, headers=["Name", "Days", "Dates"])
            output += "L2:\n"
            l2 = sprint['l2']
            l2_rows = []
            for name, dates in l2.items():
                formatted_dates = SprintPresentation.format_date_ranges(sorted(dates))
                l2_rows.append([str(name), len(dates), formatted_dates])
            output += SprintPresentation.sort_and_render_table(l2_rows, headers=["Name", "Days", "Dates"])
            output += SprintPresentation.render_team_availability(sprint['team_availability'])
        return output


    @staticmethod
    def render_capacity_table(data):
        """Render capacity planning table with scheduled epics vs capacity.
        
        Args:
            data: Sprint data with capacity calculations
            
        Returns:
            Formatted capacity table string
        """
        rows = []
        for sprint in data['sprints']:
            sprint_number = sprint['sprint_number']
            sprint_start = sprint['start']
            scheduled_epics = sprint['team_availability']['sprint_epic_total']
            points_per_epic = data['team'].points_per_epic
            scheduled_points = scheduled_epics * points_per_epic
            point_capacity = sprint['team_availability']['points']
            total_working_days = sprint['team_availability']['total_team_days']
            active_names = set(row[0].replace(" *", "") for row in sprint['team_availability']['rows'] if row[1] != "0")
            def norm(s):
                return str(s).strip().lower()
            active_pd_names = set(norm(m.pagerduty_name) for m in data['team'].team_members if m.name in active_names)
            total_holidays = sprint['team_availability']['total_team_holidays']
            total_l1_days = sum(len(days) for name, days in sprint['l1'].items() if norm(name) in active_pd_names)
            diff_pct = 100.0 * (scheduled_points - point_capacity) / point_capacity if point_capacity > 0 else 0.0
            sprint_start_dt = datetime.strptime(sprint_start, '%Y-%m-%d').date()
            sprint_end_dt = sprint_start_dt + timedelta(days=13)
            has_social = any(social_date for social_date in social_dates if sprint_start_dt <= datetime.strptime(social_date, '%Y-%m-%d').date() <= sprint_end_dt)
            warning = ''
            if scheduled_points > point_capacity:
                warning += '+'
            if has_social:
                warning += 's'
            starters = sprint['team_availability'].get('starters_this_sprint', [])
            leavers = sprint['team_availability'].get('leavers_this_sprint', [])
            if starters:
                warning += 'n'
            if leavers:
                warning += 'l'
            rows.append([
                sprint_number,
                sprint_start,
                scheduled_epics,
                f"{scheduled_points:.1f}",
                total_working_days,
                total_holidays,
                total_l1_days,
                f"{point_capacity:.1f}",
                f"{diff_pct:+.1f}%",
                warning
            ])
        headers = ["Sprint", "Start Date", "Epics", "Points", "Working Days", "Holidays", "L1", "Capacity", "% Diff", ""]
        return SprintPresentation.sort_and_render_table(rows, headers=headers)


    @staticmethod
    def render_simplified_capacity_table(data):
        """Render a simplified capacity plan table.
        
        Columns: Sprint | Start Date | Capacity | Holidays | L1
        
        Args:
            data: Sprint data with capacity information
            
        Returns:
            Formatted simplified capacity table string
        """
        rows = []
        for sprint in data['sprints']:
            sprint_number = sprint['sprint_number']
            sprint_start = sprint['start']
            point_capacity = sprint['team_availability']['points']
            total_holidays = sprint['team_availability']['total_team_holidays']
            # L1: sum of days for active members
            def norm(s):
                return str(s).strip().lower()
            active_names = set(row[0].replace(" *", "") for row in sprint['team_availability']['rows'] if row[1] != "0")
            active_pd_names = set(norm(m.pagerduty_name) for m in data['team'].team_members if m.name in active_names)
            total_l1_days = sum(len(days) for name, days in sprint['l1'].items() if norm(name) in active_pd_names)
            rows.append([
                sprint_number,
                sprint_start,
                f"{point_capacity:.1f}",
                total_holidays,
                total_l1_days
            ])
        headers = ["Sprint", "Start Date", "Capacity", "Holidays", "L1"]
        return SprintPresentation.sort_and_render_table(rows, headers=headers)
    

    @staticmethod
    def render_absences_and_oncall(data, team):
        """Render absences, POI absences, and bank holidays with warnings.
        
        Args:
            data: Sprint data dictionary
            team: Team object
            
        Returns:
            Formatted absence and bank holiday report with L1/L2 warnings
        """
        output = ""
        # Absences table
        output += "Absences\n\n" + SprintPresentation.render_holidays(team, data) + "\n"
        # Add L1/L2 absence warnings
        warnings = SprintPresentation.render_l1_l2_absence_warnings(data) + "\n"
        if warnings and warnings.strip() != "No L1/L2 absence warnings.":
            output += warnings + "\n"
        # POI Absences table
        output += "POI Absences\n\n" + SprintPresentation.render_manager_and_poi_holidays(team, data) + "\n"
        # Bank Holidays table
        output += "Bank Holidays\n\n" + SprintPresentation.render_next_12_months_bank_holidays() + "\n"
        return output
    

    @staticmethod
    def render_support(data, team):
        """Render L1/L2 support assignments with absence conflict warnings.
        
        Args:
            data: Sprint data dictionary
            team: Team object
            
        Returns:
            Formatted L1/L2 assignments with warnings
        """
        output = ""
        # L1 assignments table
        output += "L1 Assignments\n\n" + SprintPresentation.render_l1_assignments(data) + "\n"
        # L2 assignments table
        output += "L2 Assignments\n\n" + SprintPresentation.render_l2_assignments(data) + "\n"
        # Add L1/L2 absence warnings
        warnings = SprintPresentation.render_l1_l2_absence_warnings(data) + "\n"
        if warnings and warnings.strip() != "No L1/L2 absence warnings.":
            output += warnings + "\n"
        return output


    @staticmethod
    def render_holidays(team, data, key='holidays'):
        """Render holiday/absence table.
        
        Args:
            team: Team object
            data: Sprint data dictionary
            key: 'holidays' or 'poi_manager_holidays'
            
        Returns:
            Formatted holiday table string
        """
        rows = []
        for sprint in data['sprints']:
            for row in sprint.get(key, []):
                name = row[0]
                absences = SprintPresentation.safe_eval_absences(row[2])
                for a in absences:
                    start_str = a[0] if isinstance(a[0], str) else a[0].strftime('%Y-%m-%d')
                    end_str = a[1] if isinstance(a[1], str) else a[1].strftime('%Y-%m-%d')
                    formatted = start_str if start_str == end_str else f"{start_str} - {end_str}"
                    rows.append([name, formatted])
        # Deduplicate and sort
        rows = [list(t) for t in sorted(set(tuple(row) for row in rows))]
        table = SprintPresentation.sort_and_render_table(rows, ["Name", "Holiday"])
        return table


    @staticmethod
    def render_l1_assignments(data):
        """Render L1 on-call assignments aggregated across all sprints.
        
        Args:
            data: Sprint data dictionary
            
        Returns:
            Formatted L1 assignment table string
        """
        l1_assignments = SprintPresentation.aggregate_assignments(data, 'l1')
        rows = []
        for name, dates in l1_assignments.items():
            if dates:
                formatted_dates = SprintPresentation.format_date_ranges(sorted(dates))
                rows.append([str(name), len(dates), formatted_dates])
        return SprintPresentation.sort_and_render_table(rows, headers=["Name", "Days", "Dates"])


    @staticmethod
    def render_l2_assignments(data):
        """Render L2 on-call assignments aggregated across all sprints.
        
        Args:
            data: Sprint data dictionary
            
        Returns:
            Formatted L2 assignment table string
        """
        l2_assignments = SprintPresentation.aggregate_assignments(data, 'l2')
        rows = []
        for name in sorted(l2_assignments):
            for d in sorted(l2_assignments[name]):
                rows.append([name, d])
        return SprintPresentation.sort_and_render_table(rows, headers=["Name", "Date"], sort_by=1)


    @staticmethod
    def render_manager_and_poi_holidays(team, data):
        """Render holidays for manager and people of interest.
        
        Args:
            team: Team object
            data: Sprint data dictionary
            
        Returns:
            Formatted POI holiday table string
        """
        return SprintPresentation.render_holidays(team, data, key='poi_manager_holidays')

    @staticmethod
    def render_next_12_months_bank_holidays():
        """
        Render bank holidays for the next 12 months grouped by date.

        Columns:
          Date | Name | Regions

        If the same named holiday occurs on a date across multiple regions, the regions
        are combined into a comma-separated list. If different names occur on the same
        date (unlikely but guarded), each distinct name gets its own row.
        """
        start = datetime.now()
        end = start + timedelta(days=365)
        # Collect per date: name -> set(regions)
        by_date = {}
        gb_divisions = ['ENG', 'SCT', 'WLS', 'NIR']
        for division in gb_divisions:
            hols_dict, _ = SprintPresentation.list_gb_public_holidays(division, start, end)
            for date_obj, name in hols_dict.items():
                date_str = date_obj.strftime('%Y-%m-%d')
                if date_str not in by_date:
                    by_date[date_str] = {}
                if name not in by_date[date_str]:
                    by_date[date_str][name] = set()
                by_date[date_str][name].add(division)
        ie_hols_dict, _ = SprintPresentation.list_ie_public_holidays(start, end)
        for date_obj, name in ie_hols_dict.items():
            date_str = date_obj.strftime('%Y-%m-%d')
            if date_str not in by_date:
                by_date[date_str] = {}
            if name not in by_date[date_str]:
                by_date[date_str][name] = set()
            by_date[date_str][name].add('IE')
        rows = []
        for date_str in sorted(by_date.keys()):
            for name, regions in sorted(by_date[date_str].items()):
                region_list = ", ".join(sorted(regions))
                rows.append([date_str, name, region_list])
        if not rows:
            return "No bank holidays found in next 12 months\n"
        return SprintPresentation.build_aligned_table(rows, headers=["Date", "Name", "Regions"])


    @staticmethod
    def render_calendar(all_people, absence_map, l1_map, l2_map, start_date, end_date):
        """Render a calendar showing team and POI availability with L1/L2 assignments.
        
        Columns: Name | Day1 | Day2 | ... | DayN
        Each day column header is: DOW\ndd/mm (e.g., Mon\n27/11)
        Mark with 'L1' or 'L2' if person is on-call, 'X' if absent, blank if working normally.
        
        Args:
            all_people: List of all people to include
            absence_map: Dictionary mapping names to sets of absence dates
            l1_map: Dictionary mapping names to sets of L1 assignment dates
            l2_map: Dictionary mapping names to sets of L2 assignment dates
            start_date: Start date for calendar
            end_date: End date for calendar
            
        Returns:
            Formatted calendar table string
        """
        # Build list of weekdays in range
        date_list = []
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:  # Monday=0, Friday=4
                date_list.append(current)
            current += timedelta(days=1)
        
        # Build headers
        headers = ["Name"]
        for d in date_list:
            day_abbr = d.strftime('%a')
            day_month = d.strftime('%d/%m')
            headers.append(f"{day_abbr}\n{day_month}")
        
        # Build rows
        rows = []
        for person in sorted(all_people):
            row = [person]
            for d in date_list:
                if d in l1_map.get(person, set()):
                    row.append("L1")
                elif d in l2_map.get(person, set()):
                    row.append("L2")
                elif d in absence_map.get(person, set()):
                    row.append("X")
                else:
                    row.append("")
            rows.append(row)
        
        # Custom table builder for multi-line headers
        if not rows:
            return "No data\n"
        
        output = ""
        # Calculate column widths
        col_widths = []
        for col_idx in range(len(headers)):
            header_lines = headers[col_idx].split('\n')
            max_header_width = max(len(line) for line in header_lines)
            if col_idx < len(rows[0]):
                max_data_width = max(len(str(row[col_idx])) for row in rows)
                col_widths.append(max(max_header_width, max_data_width))
            else:
                col_widths.append(max_header_width)
        
        # Print multi-line headers
        header_lines_split = [h.split('\n') for h in headers]
        max_header_height = max(len(h) for h in header_lines_split)
        for line_idx in range(max_header_height):
            line_parts = []
            for col_idx, header_parts in enumerate(header_lines_split):
                if line_idx < len(header_parts):
                    line_parts.append(f"{header_parts[line_idx]:<{col_widths[col_idx]}}")
                else:
                    line_parts.append(" " * col_widths[col_idx])
            output += "  ".join(line_parts) + "\n"
        
        # Print separator
        output += "  ".join("-" * w for w in col_widths) + "\n"
        
        # Print data rows
        for row in rows:
            output += "  ".join(f"{str(item):<{w}}" for item, w in zip(row, col_widths)) + "\n"
        
        return output