from datetime import datetime, timedelta
from lxml import objectify
import json
import numpy as np
import re
import requests
import sys
import argparse
from jirautils.service.Roadmap import Roadmap
from config import *
from slack import Slack
from presentation import SprintPresentation
import os
import pickle


_employee_directory_tree_cache = None
_sprint_fte_cache = None


def cache_api_response(cache_key, fetch_func, timeout_seconds):
    """Cache API responses to disk with expiry.
    
    Args:
        cache_key: Unique identifier for the cached data
        fetch_func: Function to call to fetch fresh data if cache is invalid
        timeout_seconds: Cache expiry time in seconds
        
    Returns:
        Cached or freshly fetched data
    """
    cache_dir = "./.api_cache"
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"{cache_key}.pkl")
    now = datetime.now().timestamp()
    # Try to load cache
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "rb") as f:
                cached = pickle.load(f)
            if now - cached["timestamp"] < timeout_seconds:
                return cached["data"]
        except Exception:
            pass
    # Fetch new data
    data = fetch_func()
    with open(cache_file, "wb") as f:
        pickle.dump({"timestamp": now, "data": data}, f)
    return data


def get_future_sprint_fte():
    """Fetch and cache future sprint FTE data from JIRA.
    
    Returns:
        Dictionary mapping team keys to sprint end dates and FTE counts
    """
    global _sprint_fte_cache
    if _sprint_fte_cache is not None:
        return _sprint_fte_cache
    def fetch():
        rm = Roadmap(JIRA_API_KEY=jira_api_key)
        rm.auth = rm.get_auth()
        future_epics = rm.get_future_epics()
        extracted_data = rm.extract_data_from_epics(future_epics)
        end_sprint_dates = rm.get_end_sprint_dates()
        return rm.count_fte_per_sprint(extracted_data, end_sprint_dates)
    _sprint_fte_cache = cache_api_response("future_sprint_fte", fetch, api_cache_timeout)
    return _sprint_fte_cache


def sprint_start(d):
    """Calculate the start date of the sprint containing the given date.
    
    Sprints start on odd-numbered Mondays (week 1, 3, 5, etc.).
    
    Args:
        d: Date to find the sprint start for
        
    Returns:
        datetime: The Monday that starts the sprint containing d
    """
    weekday = 0 # Monday
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0: # Target day already happened this week
        days_ahead += 7
    target_date = d + timedelta(days_ahead)
    week = int(target_date.strftime("%V"))
    if week % 2 == 0: # even numbered week
        return target_date - timedelta(14)
    return target_date - timedelta(7) # odd numbered week


def get_sprint_number(current_sprint_start):
    """Calculate the sprint number based on the start date.
    
    Args:
        current_sprint_start: Start date of the sprint
        
    Returns:
        int: The sprint number
    """
    delta = current_sprint_start - datetime.strptime(str(first_sprint_date), date_format)
    return int(first_sprint_number + (delta.days / 14))


def fetch_bamboohr_holidays(start, end, employee_id_list):
    """Fetch employee holiday/absence data from BambooHR API.
    
    Args:
        start: Start date for the query range
        end: End date for the query range
        employee_id_list: List of employee IDs to fetch absences for
        
    Returns:
        Dictionary mapping employee objects to lists of absence periods
    """
    def fetch():
        holiday_uri = 'https://api.bamboohr.com/api/gateway.php/brdge/v1/time_off/whos_out?start={0}&end={1}'
        # start and end may already be datetime.date objects
        start_str = start.strftime('%Y-%m-%d') if hasattr(start, 'strftime') else str(start)
        end_str = end.strftime('%Y-%m-%d') if hasattr(end, 'strftime') else str(end)
        holiday_request = requests.get(holiday_uri.format(start_str, end_str), auth=(bamboo_hr_api_key, 'x'))
        return holiday_request.text
    cache_key = f"bamboohr_holidays_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}"
    raw_xml = cache_api_response(cache_key, fetch, api_cache_timeout)
    calendar = objectify.fromstring(raw_xml)
    employee_days = {}
    if hasattr(calendar, 'item'):
        for item in calendar.item:
            employee_id = item.employee.attrib["id"]
            if employee_id in employee_id_list:
                if item.employee not in employee_days:
                    employee_days[item.employee] = []
                # start and end are already datetime.date objects
                # Ensure both are datetime.date for comparison
                check_start = start.date() if hasattr(start, 'date') else start
                item_start = datetime.strptime(str(item.start), date_format).date()
                if item_start > check_start:
                    check_start = item_start
                check_end = end.date() if hasattr(end, 'date') else end
                item_end = datetime.strptime(str(item.end), date_format).date()
                if item_end <= check_end:
                    check_end = item_end
                delta = np.busday_count(str(item.start), str(item.end))
                if np.is_busday(str(item.end)):
                    delta += 1
                sprint_delta = np.busday_count(check_start, check_end)
                if np.is_busday(check_end):
                    sprint_delta += 1
                employee_days[item.employee].append([item.start, item.end, int(delta), int(sprint_delta)])
    return employee_days


def fetch_employee_directory_tree():
    """Fetch and cache the employee directory from BambooHR.
    
    Returns:
        lxml.objectify tree of employee directory data
    """
    global _employee_directory_tree_cache
    if _employee_directory_tree_cache is not None:
        return _employee_directory_tree_cache
    def fetch():
        directory_uri = 'https://api.bamboohr.com/api/gateway.php/brdge/v1/employees/directory'
        directory_request = requests.get(directory_uri, auth=(bamboo_hr_api_key, 'x'))
        return objectify.fromstring(directory_request.text)
    _employee_directory_tree_cache = cache_api_response(
        "bamboohr_directory",
        fetch,
        getattr(sys.modules[__name__], "api_cache_timeout", 3600)
    )
    return _employee_directory_tree_cache


def get_employee_id_list_from_tree(tree, team):
    """Extract employee IDs and names from the directory tree.
    
    Separates core team members from POI (people of interest) and manager.
    
    Args:
        tree: Employee directory tree from BambooHR
        team: Team object with member names and POI list
        
    Returns:
        Tuple of (core_employee_ids, core_display_names, poi_employee_ids, poi_display_names)
    """
    core_employee_ids = []
    core_display_names = []
    poi_employee_ids = []
    poi_display_names = []
    member_names = [m.name for m in team.team_members]
    for employee in tree.employees.employee:
        employee_id = employee.attrib["id"]
        display_name = employee.find(".//field[@id='displayName']")
        # Exclude manager and people_of_interest from core team
        if display_name == team.manager or display_name in team.people_of_interest:
            poi_employee_ids.append(employee_id)
            poi_display_names.append(display_name)
        if display_name in member_names:
            core_employee_ids.append(employee_id)
            core_display_names.append(display_name)
    return core_employee_ids, core_display_names, poi_employee_ids, poi_display_names


def get_team_availability(sprint_start_date, sprint_end_date, l1_dict, l2_dict, holidays_dict, team):
    """Calculate team availability and capacity for a sprint.
    
    Handles starters, leavers, ramp-up, holidays, L1/L2 shifts, and social events.
    
    Args:
        sprint_start_date: Start date of the sprint
        sprint_end_date: End date of the sprint
        l1_dict: Dictionary of L1 on-call assignments
        l2_dict: Dictionary of L2 on-call assignments
        holidays_dict: Dictionary mapping names to sets of holiday dates
        team: Team object with member details and capacity settings
        
    Returns:
        Dictionary with availability rows, totals, points, and notes about starters/leavers/ramping
    """
    total_team_days = 0
    total_team_holidays = 0
    rows = []
    leavers_this_sprint = []
    starters_this_sprint = []
    ramping_this_sprint = []
    socials_in_sprint = [d for d in social_dates if sprint_start_date.strftime(date_format) <= d <= sprint_end_date.strftime(date_format)]
    social_penalty = 1 if socials_in_sprint else 0
    for member in team.team_members:
        name_str = member.name
        pd_name = getattr(member, "pagerduty_name", name_str)
        start_date = getattr(member, "start_date", None)
        base_pct = getattr(member, "start_pct", 1)
        leave_date = getattr(member, "leave_date", None)
        days_in_sprint = 10
        holidays = holidays_dict.get(name_str, set())
        l1_days = len(l1_dict.get(pd_name, []))
        l2_days = len(l2_dict.get(pd_name, []))
        actual_available = days_in_sprint - len(holidays) - l1_days - social_penalty
        available = max(0, actual_available)
        name_display = name_str
        days_display = f"{available}"
        exclude_from_counts = False
        # Handle leavers
        leave_dt = None
        if leave_date:
            leave_dt = datetime.strptime(leave_date, date_format).date()
            if leave_dt < sprint_start_date.date():
                actual_available = available = 0
                name_display = name_str
                days_display = "0"
                exclude_from_counts = True
            elif sprint_start_date.date() <= leave_dt <= sprint_end_date.date():
                days_left = (leave_dt - sprint_start_date.date()).days + 1
                actual_available = sum(
                    1 for i in range(days_left)
                    if (sprint_start_date.date() + timedelta(i)).weekday() < 5
                )
                actual_available = max(0, actual_available - len(holidays) - l1_days - social_penalty)
                available = actual_available
                name_display = name_str
                days_display = f"{available}"
                leavers_this_sprint.append((name_str, leave_date))
            else:
                actual_available = available = max(0, days_in_sprint - len(holidays) - l1_days - social_penalty)
                name_display = name_str
                days_display = f"{available}"
        # Handle starters/ramp-up
        ramping = False
        ramp_multiplier = 1.0
        if start_date and (not leave_dt or leave_dt > sprint_end_date.date()):
            start_dt = datetime.strptime(start_date, date_format).date()
            if sprint_end_date.date() < start_dt:
                actual_available = available = 0
                name_display = name_str
                days_display = "0"
                exclude_from_counts = True
            else:
                if sprint_start_date.date() < start_dt:
                    actual_available = available = 0
                    name_display = name_str
                    days_display = "0"
                    exclude_from_counts = True
                else:
                    days_since_start = (sprint_start_date.date() - start_dt).days
                    sprint_num = max(0, days_since_start // 14)
                    ramp_multiplier = min(base_pct + 0.1 * sprint_num, 1.0)
                    if sprint_start_date.date() <= start_dt <= sprint_end_date.date():
                        days_left = (sprint_end_date.date() - start_dt).days + 1
                        actual_available = sum(
                            1 for i in range(days_left)
                            if (start_dt + timedelta(i)).weekday() < 5
                        )
                        actual_available = max(0, actual_available - len(holidays) - l1_days - social_penalty)
                        starters_this_sprint.append((name_str, start_date))
                    else:
                        actual_available = max(0, days_in_sprint - len(holidays) - l1_days - social_penalty)
                    if ramp_multiplier < 1.0:
                        ramping = True
                        effective_available = int(round(actual_available * ramp_multiplier))
                        name_display = f"{name_str} *"
                        days_display = f"{actual_available} ({effective_available})"
                        ramping_this_sprint.append((name_str, int(ramp_multiplier * 100)))
                        available = effective_available
                    else:
                        name_display = name_str
                        days_display = f"{actual_available}"
                        available = actual_available
        # Ensure name_display and days_display are always set
        if name_display == "":
            name_display = name_str
        if days_display == "":
            days_display = f"{available}"
        holidays_count = 0 if exclude_from_counts else len(holidays)
        l1_days_count = 0 if exclude_from_counts else l1_days
        l2_days_count = 0 if exclude_from_counts else l2_days
        if not exclude_from_counts:
            rows.append([name_display, days_display, holidays_count, l1_days_count, l2_days_count])
            total_team_days += available
            total_team_holidays += len(holidays)

    sprint_epic_total = _sprint_fte_cache.get(team.jira_key, {}).get(sprint_end_date.strftime(date_format), {}).get("total", 0)
    points = total_team_days * team.load_factor * team.point_capacity
    eng_points = points * team.engineering_split
    prod_points = points - eng_points
    return {
        "rows": sorted(rows, key=lambda row: row[0]),
        "total_team_days": total_team_days,
        "total_team_holidays": total_team_holidays,
        "points": points,
        "eng_points": eng_points,
        "prod_points": prod_points,
        "sprint_epic_total": sprint_epic_total,
        "starters_this_sprint": starters_this_sprint,
        "leavers_this_sprint": leavers_this_sprint,
        "ramping_this_sprint": sorted(set(ramping_this_sprint)),
        "team": team,
    }


def get_sprint_data(team):
    """Gather all sprint data for a team including holidays, on-call, and availability.
    
    Fetches data from BambooHR, PagerDuty, and JIRA APIs and builds a complete
    sprint planning dataset.
    
    Args:
        team: Team object with configuration and member details
        
    Returns:
        Dictionary containing team info, employee IDs, and list of sprint data
    """
    next_sprint = sprint_start(datetime.now()) - timedelta(days=14 * number_of_sprints_back)
    tree = fetch_employee_directory_tree()
    print(tree)
    core_employee_ids, core_display_names, poi_employee_ids, poi_display_names = get_employee_id_list_from_tree(tree, team)
    get_future_sprint_fte()
    pd_names = [getattr(m, "pagerduty_name", m.name) for m in team.team_members]
    pagerduty_id_list = get_pagerduty_user_ids(pd_names)
    end_date = next_sprint + timedelta(days=(number_of_sprints*14))
    start = next_sprint.strftime(date_format)
    end = end_date.strftime(date_format)
    current_start = next_sprint
    all_employee_days = fetch_bamboohr_holidays(next_sprint, end_date, core_employee_ids)
    all_poi_days = fetch_bamboohr_holidays(next_sprint, end_date, poi_employee_ids)
    l1_all = fetch_pagerduty_oncall(level_one_support_id, next_sprint, end_date, pagerduty_id_list)
    l2_all = fetch_pagerduty_oncall(level_two_support_id, next_sprint, end_date, pagerduty_id_list)
    sprints = []
    while current_start <= end_date:
        sprint_number = get_sprint_number(current_start)
        current_end = current_start + timedelta(13)
        socials_in_sprint = [d for d in social_dates if current_start.strftime(date_format) <= d <= current_end.strftime(date_format)]
        social_this_sprint = socials_in_sprint[0] if socials_in_sprint else None
        # Filter absences for this sprint window
        employee_days = filter_absences_by_sprint(all_employee_days, current_start, current_end)
        poi_days = filter_absences_by_sprint(all_poi_days, current_start, current_end)
        holidays_dict = {}
        holiday_rows = []
        for emp in employee_days:
            name = str(emp)
            holidays_dict[name] = set()
            for absence in employee_days[emp]:
                start_hol = datetime.strptime(str(absence[0]), date_format).date()
                end_hol = datetime.strptime(str(absence[1]), date_format).date()
                for n in range((end_hol - start_hol).days + 1):
                    hol_date = start_hol + timedelta(days=n)
                    if hol_date.weekday() < 5 and current_start.date() <= hol_date <= current_end.date():
                        holidays_dict[name].add(hol_date)
            total_days = sum(absence[3] for absence in employee_days[emp])
            holiday_rows.append([name, total_days, str(employee_days[emp])])
        # Manager/POI holidays for this sprint
        poi_holiday_rows = []
        for emp in poi_days:
            name = str(emp)
            absences = poi_days[emp]
            if absences:
                total_days = sum(a[3] for a in absences)
                poi_holiday_rows.append([name, total_days, str(absences)])
        # On-call
        # Ensure date range comparison is inclusive and robust
        sprint_start_str = current_start.strftime(date_format)
        sprint_end_str = current_end.strftime(date_format)
        def in_sprint(d):
            return sprint_start_str <= d <= sprint_end_str
        l1 = {}
        for name, dates in l1_all.items():
            filtered_dates = [d for d in dates if in_sprint(d)]
            if filtered_dates:
                l1[name] = filtered_dates
        l2 = {}
        for name, dates in l2_all.items():
            filtered_dates = [d for d in dates if in_sprint(d)]
            if filtered_dates:
                l2[name] = filtered_dates
        # Team availability
        team_avail = get_team_availability(current_start, current_end, l1, l2, holidays_dict, team)
        sprints.append({
            "sprint_number": sprint_number,
            "start": current_start.strftime(date_format),
            "end": current_end.strftime(date_format),
            "social": social_this_sprint,
            "holidays": holiday_rows,
            "poi_manager_holidays": poi_holiday_rows,
            "l1": l1,
            "l2": l2,
            "team_availability": team_avail,
        })
        current_start = current_start + timedelta(14)
    return {
        "team": team,
        "core_display_names": core_display_names,
        "core_employee_ids": core_employee_ids,
        "sprints": sprints,
    }


# PagerDuty user cache and efficient lookup
_pagerduty_users_cache = None
def get_pagerduty_user_ids(team):
    """Fetch PagerDuty user IDs for team members.
    
    Caches the full user list from PagerDuty and filters by team member names.
    
    Args:
        team: List of team member names to look up
        
    Returns:
        List of PagerDuty user IDs matching team member names
    """
    global _pagerduty_users_cache
    if _pagerduty_users_cache is None:
        url = 'https://api.pagerduty.com/users'
        # limit must be specified, or this will need to be paginated
        # however, the returned data is not returning the total to be able to paginate properly
        # this code therefore defaults to 1000 users to future-proof
        params = {"limit":1000}
        response = requests.get(url, params=params, headers={'Authorization': 'Token token=%s' %  pagerduty_api_key})
        tree = json.loads(response.text)
        _pagerduty_users_cache = {user["name"]: user["id"] for user in tree["users"]}
    # Use dict lookup for efficiency
    return [user_id for name, user_id in _pagerduty_users_cache.items() if name in team]


def fetch_pagerduty_oncall(schedule, start, end, employee_id_list):
    """Fetch on-call schedule data from PagerDuty.
    
    Args:
        schedule: PagerDuty schedule ID (L1 or L2)
        start: Start date for the query range
        end: End date for the query range
        employee_id_list: List of PagerDuty user IDs to filter by
        
    Returns:
        Dictionary mapping user names to lists of on-call dates
    """
    def fetch():
        url = f'https://api.pagerduty.com/schedules/{schedule}'
        params = {"since":start + timedelta(-1),"until":end,"overflow":"true"}
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Token token={pagerduty_api_key}"
        }
        response = requests.get(url, params=params, headers=headers)
        return response.text
    cache_key = f"pagerduty_oncall_{schedule}_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}"
    raw_json = cache_api_response(cache_key, fetch, api_cache_timeout)
    tree = json.loads(raw_json)
    schedule = {}
    for entry in tree["schedule"]["final_schedule"]["rendered_schedule_entries"]:
        user_id = entry["user"]["id"]
        if user_id in employee_id_list:
            if user_id not in schedule:
                schedule[user_id] = []
            schedule[user_id].append([user_id, entry["user"]["summary"], entry["start"], entry["end"]])
    if not schedule:
        return {}
    else:
        output = {}
        for user_id, entries in schedule.items():
            for entry in entries:
                if entry[1] not in output:
                    output[entry[1]] = []
                output[entry[1]].append(entry[2][0:10])
        return output


def filter_absences_by_sprint(absence_dict, sprint_start, sprint_end):
    """Filter absence data to only include absences overlapping the sprint.
    
    Args:
        absence_dict: Dictionary mapping employees to absence periods
        sprint_start: Start date of the sprint
        sprint_end: End date of the sprint
        
    Returns:
        Filtered dictionary with only relevant absences
    """
    filtered = {}
    for emp, absences in absence_dict.items():
        filtered_absences = []
        for absence in absences:
            absence_start = datetime.strptime(str(absence[0]), date_format).date()
            absence_end = datetime.strptime(str(absence[1]), date_format).date()
            if absence_end >= sprint_start.date() and absence_start <= sprint_end.date():
                filtered_absences.append(absence)
        if filtered_absences:
            filtered[emp] = filtered_absences
    return filtered


# Data builder for xmas rota CSV
def build_calendar_data(team, data):
    """Build calendar data showing team and POI availability for next 2 weeks.
    
    Args:
        team: Team object with member and POI details
        data: Sprint data containing holiday information
        
    Returns:
        Tuple of (all_people, absence_map, l1_map, l2_map, today, end_date) for calendar rendering
    """
    today = datetime.now().date()
    end_date = today + timedelta(days=13)  # 2 weeks
    
    # Collect all team members and POIs (remove duplicates)
    team_members = [m.name for m in team.team_members]
    pois = team.people_of_interest + [team.manager]
    all_people = list(dict.fromkeys(team_members + pois))  # Preserves order, removes duplicates
    
    # Build absence map from sprint data
    absence_map = {}
    for person in all_people:
        absence_map[person] = set()
    
    # Build L1/L2 maps (map PagerDuty names to actual names)
    pd_to_name = {}
    for m in team.team_members:
        pd_name = getattr(m, "pagerduty_name", m.name)
        pd_to_name[pd_name] = m.name
    
    l1_map = {}
    l2_map = {}
    for person in all_people:
        l1_map[person] = set()
        l2_map[person] = set()
    
    for sprint in data['sprints']:
        # Process team member holidays
        for row in sprint.get('holidays', []):
            name = row[0]
            if name in all_people:
                absences = SprintPresentation.safe_eval_absences(row[2]) if len(row) > 2 else []
                for a in absences:
                    start = a[0] if isinstance(a[0], str) else a[0].strftime('%Y-%m-%d')
                    end = a[1] if isinstance(a[1], str) else a[1].strftime('%Y-%m-%d')
                    start_dt = datetime.strptime(start, '%Y-%m-%d').date()
                    end_dt = datetime.strptime(end, '%Y-%m-%d').date()
                    for n in range((end_dt - start_dt).days + 1):
                        absence_map[name].add(start_dt + timedelta(days=n))
        
        # Process POI/manager holidays
        for row in sprint.get('poi_manager_holidays', []):
            name = row[0]
            if name in all_people:
                absences = SprintPresentation.safe_eval_absences(row[2]) if len(row) > 2 else []
                for a in absences:
                    start = a[0] if isinstance(a[0], str) else a[0].strftime('%Y-%m-%d')
                    end = a[1] if isinstance(a[1], str) else a[1].strftime('%Y-%m-%d')
                    start_dt = datetime.strptime(start, '%Y-%m-%d').date()
                    end_dt = datetime.strptime(end, '%Y-%m-%d').date()
                    for n in range((end_dt - start_dt).days + 1):
                        absence_map[name].add(start_dt + timedelta(days=n))
        
        # Process L1 assignments
        for pd_name, dates in sprint.get('l1', {}).items():
            actual_name = pd_to_name.get(pd_name, pd_name)
            if actual_name in all_people:
                for date_str in dates:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date() if isinstance(date_str, str) else date_str
                    if today <= date_obj <= end_date:
                        l1_map[actual_name].add(date_obj)
        
        # Process L2 assignments
        for pd_name, dates in sprint.get('l2', {}).items():
            actual_name = pd_to_name.get(pd_name, pd_name)
            if actual_name in all_people:
                for date_str in dates:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date() if isinstance(date_str, str) else date_str
                    if today <= date_obj <= end_date:
                        l2_map[actual_name].add(date_obj)
    
    return all_people, absence_map, l1_map, l2_map, today, end_date


def build_xmas_rota_data():
    """Build Christmas rota data for Tech division employees.
    
    Fetches all Tech division employees from BambooHR and their absences
    during the configured Christmas rota period.
    
    Returns:
        Tuple of (date_list, user_absence_map) for rendering the rota
    """
    start_date = datetime.strptime(xmas_rota_dates[0], "%Y-%m-%d").date()
    end_date = datetime.strptime(xmas_rota_dates[1], "%Y-%m-%d").date()
    tree = fetch_employee_directory_tree()
    # Build mapping from employee id to display name
    all_employee_ids = []
    id_to_name = {}
    for employee in tree.employees.employee:
        employee_id = employee.attrib["id"]
        division_el = employee.find(".//field[@id='division']")
        division_val = division_el.text.strip() if division_el is not None and division_el.text else ""
        if division_val.lower() != "tech":
            continue
        # Name resolution precedence: preferredName + lastName -> displayName -> employee_id
        preferred_el = employee.find(".//field[@id='preferredName']")
        last_el = employee.find(".//field[@id='lastName']")
        display_el = employee.find(".//field[@id='displayName']")
        preferred = preferred_el.text.strip() if preferred_el is not None and preferred_el.text else None
        last_name = last_el.text.strip() if last_el is not None and last_el.text else None
        if preferred and last_name:
            resolved_name = f"{preferred} {last_name}".strip()
        else:
            resolved_name = display_el.text.strip() if display_el is not None and display_el.text else employee_id
        all_employee_ids.append(employee_id)
        id_to_name[employee_id] = resolved_name
    all_employee_days = fetch_bamboohr_holidays(start_date, end_date, all_employee_ids)
    date_list = []
    d = start_date
    while d <= end_date:
        date_list.append(d)
        d += timedelta(days=1)
    # Prepare exclusions (case-insensitive)
    exclusions = {e.strip().lower() for e in xmas_rota_exclusions}
    user_absence_map = {}
    # First collect absences for those who have them
    for emp_obj, absences in all_employee_days.items():
        employee_id = emp_obj.attrib.get("id")
        display_name = id_to_name.get(employee_id, employee_id)
        name_key = display_name.strip()
        if name_key.lower() in exclusions:
            continue
        absence_dates = set()
        for absence in absences:
            start = datetime.strptime(str(absence[0]), "%Y-%m-%d").date()
            end = datetime.strptime(str(absence[1]), "%Y-%m-%d").date()
            for n in range((end - start).days + 1):
                absence_dates.add(start + timedelta(days=n))
        user_absence_map[name_key] = absence_dates
    # Ensure all non-excluded employees appear, even with no absences
    for employee_id, display_name in id_to_name.items():
        name_key = display_name.strip()
        if name_key.lower() in exclusions:
            continue
        if name_key not in user_absence_map:
            user_absence_map[name_key] = set()
    return date_list, user_absence_map


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sprint planner tool")
    parser.add_argument("team_name", type=str, help="Team name")
    parser.add_argument("-capacity", "-c", action="store_true", help="Show capacity summary table")
    parser.add_argument("-absences", "-a", action="store_true", help="Show upcoming absences grouped by person")
    parser.add_argument("-l1", action="store_true", help="Show upcoming L1 assignments")
    parser.add_argument("-l2", action="store_true", help="Show upcoming L2 assignments")
    parser.add_argument("-interest", "-i", action="store_true", help="Show upcoming holidays for people of interest and the manager")
    parser.add_argument("-full", "-f", action="store_true", help="Show full output")
    parser.add_argument("-purge", "-p", action="store_true", help="Delete all cached API data before running")
    parser.add_argument("-slack", "-s", action="store_true", help="Send data to Slack")
    parser.add_argument("-xmas", "-x", action="store_true", help="Show Christmas rota CSV output")
    parser.add_argument("-bankhols", "-b", action="store_true", help="Show next 12 months bank holidays")
    parser.add_argument("-warning", "-w", action="store_true", help="Show warning if a person is absent during L1 or L2 shift")
    parser.add_argument("-debug", "-d", action="store_true", help="Dump employee tree, holidays, and pagerduty shifts for debugging")
    parser.add_argument("-calendar", "-k", action="store_true", help="Show calendar of team and POI availability")

    args = parser.parse_args()

    if args.purge:
        cache_dir = "./.api_cache"
        if os.path.exists(cache_dir):
            for fname in os.listdir(cache_dir):
                fpath = os.path.join(cache_dir, fname)
                try:
                    os.remove(fpath)
                except Exception as e:
                    print(f"Failed to delete {fpath}: {e}")
            print("API cache purged.")
        else:
            print("No API cache directory found.")
        sys.exit(1)

    team_name = args.team_name.lower()
    team = next((t for t in teams if t.name.lower() == team_name), None)
    if not team:
        print(f"Team '{team_name}' not found. Available teams: {[t.name for t in teams]}")
        sys.exit(1)
    data = get_sprint_data(team)
    action = False
    output_map = {
        'capacity': lambda: SprintPresentation.render_capacity_table(data),
        'absences': lambda: SprintPresentation.render_holidays(team, data),
        'l1': lambda: SprintPresentation.render_l1_assignments(data),
        'l2': lambda: SprintPresentation.render_l2_assignments(data),
        'interest': lambda: SprintPresentation.render_manager_and_poi_holidays(team, data),
        'slack': lambda: Slack.send_sprint_data_to_slack(data, team),
        'full': lambda: SprintPresentation.render_sprint_data(data),
        'xmas': lambda: SprintPresentation.render_xmas_rota_csv(*build_xmas_rota_data()),
        'bankhols': lambda: SprintPresentation.render_next_12_months_bank_holidays(),
        'warning': lambda: SprintPresentation.render_l1_l2_absence_warnings(data),
        'debug': lambda: debug_dump(team, data),
        'calendar': lambda: SprintPresentation.render_calendar(*build_calendar_data(team, data)),
    }

    def debug_dump(team, data):
        print("==== RAW EMPLOYEE DIRECTORY API RESPONSE ====")
        # Dump raw employee directory XML
        cache_dir = "./.api_cache"
        directory_cache_file = os.path.join(cache_dir, "bamboohr_directory.pkl")
        if os.path.exists(directory_cache_file):
            with open(directory_cache_file, "rb") as f:
                cached = pickle.load(f)
                raw_xml = cached["data"] if isinstance(cached["data"], str) else str(cached["data"])
                print(raw_xml)
        else:
            print("No cached employee directory found.")

        print("\n==== RAW EMPLOYEE HOLIDAYS API RESPONSE ====")
        # Dump raw holidays XML for core and POI employees
        # Use the same cache key logic as fetch_bamboohr_holidays
        next_sprint = sprint_start(datetime.now()) - timedelta(days=14 * number_of_sprints_back)
        end_date = next_sprint + timedelta(days=(number_of_sprints*14))
        start_str = next_sprint.strftime(date_format)
        end_str = end_date.strftime(date_format)
        core_employee_ids, _, poi_employee_ids, _ = get_employee_id_list_from_tree(fetch_employee_directory_tree(), team)
        core_cache_key = f"bamboohr_holidays_{next_sprint.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        poi_cache_key = f"bamboohr_holidays_{next_sprint.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        core_cache_file = os.path.join(cache_dir, f"{core_cache_key}.pkl")
        poi_cache_file = os.path.join(cache_dir, f"{poi_cache_key}.pkl")
        if os.path.exists(core_cache_file):
            with open(core_cache_file, "rb") as f:
                cached = pickle.load(f)
                raw_xml = cached["data"] if isinstance(cached["data"], str) else str(cached["data"])
                print("-- Core Employee Holidays --")
                print(raw_xml)
        else:
            print("No cached core employee holidays found.")
        if os.path.exists(poi_cache_file):
            with open(poi_cache_file, "rb") as f:
                cached = pickle.load(f)
                raw_xml = cached["data"] if isinstance(cached["data"], str) else str(cached["data"])
                print("-- POI Employee Holidays --")
                print(raw_xml)
        else:
            print("No cached POI employee holidays found.")

        print("\n==== RAW PAGERDUTY SHIFTS API RESPONSE ====")
        # Dump raw PagerDuty shift JSON for L1 and L2
        pd_names = [getattr(m, "pagerduty_name", m.name) for m in team.team_members]
        pagerduty_id_list = get_pagerduty_user_ids(pd_names)
        l1_cache_key = f"pagerduty_oncall_{level_one_support_id}_{next_sprint.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        l2_cache_key = f"pagerduty_oncall_{level_two_support_id}_{next_sprint.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        l1_cache_file = os.path.join(cache_dir, f"{l1_cache_key}.pkl")
        l2_cache_file = os.path.join(cache_dir, f"{l2_cache_key}.pkl")
        if os.path.exists(l1_cache_file):
            with open(l1_cache_file, "rb") as f:
                cached = pickle.load(f)
                raw_json = cached["data"] if isinstance(cached["data"], str) else str(cached["data"])
                print("-- L1 PagerDuty Shifts --")
                print(raw_json)
        else:
            print("No cached L1 PagerDuty shifts found.")
        if os.path.exists(l2_cache_file):
            with open(l2_cache_file, "rb") as f:
                cached = pickle.load(f)
                raw_json = cached["data"] if isinstance(cached["data"], str) else str(cached["data"])
                print("-- L2 PagerDuty Shifts --")
                print(raw_json)
        else:
            print("No cached L2 PagerDuty shifts found.")
        return None
    for arg, func in output_map.items():
        if getattr(args, arg, False):
            result = func()
            if result is not None:
                print(result)
            action = True
    if not action:
        print("No output option specified")
        parser.print_help()
