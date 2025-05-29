import json
import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from pathlib import Path

import httplib2
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from calendarSync import CalendarSourceAdapter, CalendarConfig
from task import Task, Tag
from display import mixColors

BASE_DIR = os.path.dirname(__file__)

class GoogleCalendarAdapter(CalendarSourceAdapter):
    """
    Google Calendar API adapter using official Google Calendar API v3
    Supports both OAuth2 (user authentication) and Service Account authentication
    """
    
    # Scopes needed for calendar access
    SCOPES = [
        'https://www.googleapis.com/auth/calendar.readonly',
    ]
    
    def __init__(self, config: CalendarConfig):
        super().__init__(config)
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google Calendar API"""
        auth_config = self.config.auth_config or {}
        auth_type = auth_config.get('type', 'oauth2')
        
        if auth_type == 'oauth2':
            self._authenticate_oauth2()
        elif auth_type == 'service_account':
            self._authenticate_service_account()
        else:
            raise ValueError(f"Unsupported auth type: {auth_type}")
    
    def _authenticate_oauth2(self):
        """OAuth2 authentication for user accounts"""
        auth_config = self.config.auth_config
        credentials_file = auth_config.get('credentials_file', 'credentials.json')
        token_file = auth_config.get('token_file', 'token.json')
        # Handle relative paths
        if not os.path.isabs(credentials_file):
            credentials_file = os.path.join(BASE_DIR, 'cfg', 'calendars', credentials_file)
        if not os.path.isabs(token_file):
            token_file = os.path.join(BASE_DIR,  'cfg', 'calendars', token_file)
        print('f'+credentials_file)
        
        creds = None
        
        # Load existing token
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, self.SCOPES)
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing token: {e}")
                    creds = None
            
            if not creds:
                if not os.path.exists(credentials_file):
                    raise FileNotFoundError(
                        f"Credentials file not found: {credentials_file}. "
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_file, self.SCOPES
                )
                # Use run_local_server for desktop apps, or run_console for headless
                port = auth_config.get('redirect_port', 0)
                if auth_config.get('headless', False):
                    creds = flow.run_console()
                else:
                    creds = flow.run_local_server(port=port)
            
            # Save credentials for next run
            with open(token_file, 'w') as token:
                token.write(creds.to_json())
        
        self.service = build('calendar', 'v3', credentials=creds)
    
    def _authenticate_service_account(self):
        """Service account authentication for server-to-server access"""
        auth_config = self.config.auth_config
        service_account_file = auth_config.get('service_account_file')
        # Handle relative paths
        if service_account_file and not os.path.isabs(service_account_file):
            service_account_file = os.path.join(os.getcwd(), service_account_file)

        subject = auth_config.get('subject')  # For domain-wide delegation
        
        if not service_account_file:
            raise ValueError("service_account_file required for service account auth")
        
        if not os.path.exists(service_account_file):
            raise FileNotFoundError(f"Service account file not found: {service_account_file}")
        
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file, scopes=self.SCOPES
        )
        
        # For domain-wide delegation
        if subject:
            credentials = credentials.with_subject(subject)
        
        self.service = build('calendar', 'v3', credentials=credentials)
    
    def fetch_tasks_for_date(self, date: datetime.date) -> List[Task]:
        """Fetch tasks from Google Calendar for specific date"""
        if not self.service:
            return []
        
        all_tasks = []
        
        try:
            # Get calendars to process
            calendars_config = self.config.source_config.get('calendars', [])
            
            if calendars_config:
                # Process multiple specific calendars
                for cal_config in calendars_config:
                    if not cal_config.get('enabled', True):
                        continue
                    
                    calendar_id = cal_config['id']
                    tag = self._create_tag(
                        cal_config.get('name', calendar_id), 
                        cal_config.get('color_config')
                    )
                    
                    tasks = self._fetch_calendar_events(calendar_id, date, tag)
                    all_tasks.extend(tasks)
            else:
                # Process primary calendar only
                calendar_id = self.config.source_config.get('calendar_id', 'primary')
                tasks = self._fetch_calendar_events(calendar_id, date)
                all_tasks.extend(tasks)
        
        except HttpError as error:
            print(f"Google Calendar API error for {self.config.name}: {error}")
        except Exception as error:
            print(f"Unexpected error fetching Google Calendar {self.config.name}: {error}")
        
        return all_tasks
    
    def _fetch_calendar_events(self, calendar_id: str, date: datetime.date, 
                              tag: Tag = None) -> List[Task]:
        """Fetch events from a specific calendar"""
        # Set up time range for the specific date
        start_of_day = datetime.combine(date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_of_day = start_of_day + timedelta(days=1)
        
        time_min = start_of_day.isoformat()
        time_max = end_of_day.isoformat()
        
        try:
            # Fetch events from Google Calendar API
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime',
                maxResults=self.config.source_config.get('max_results', 250)
            ).execute()
            
            events = events_result.get('items', [])
            tasks = []
            
            for event in events:
                task = self._convert_event_to_task(event, tag)
                if task:
                    tasks.append(task)
            
            return tasks
            
        except HttpError as error:
            print(f"Error fetching calendar {calendar_id}: {error}")
            return []
    
    def _convert_event_to_task(self, event: Dict, tag: Tag = None) -> Optional[Task]:
        """Convert Google Calendar event to Task object"""
        
        # Get event title
        title = event.get('summary', 'No Title')
        
        # Handle start time
        start_data = event.get('start', {})
        if 'dateTime' in start_data:
            # Timed event
            start_dt = datetime.fromisoformat(
                start_data['dateTime'].replace('Z', '+00:00')
            )
        elif 'date' in start_data:
            # All-day event
            start_dt = datetime.fromisoformat(start_data['date'] + 'T00:00:00+00:00')
        else:
            return None
        
        # Handle end time
        end_data = event.get('end', {})
        if 'dateTime' in end_data:
            end_dt = datetime.fromisoformat(
                end_data['dateTime'].replace('Z', '+00:00')
            )
        elif 'date' in end_data:
            end_dt = datetime.fromisoformat(end_data['date'] + 'T00:00:00+00:00')
        else:
            # Default duration if no end time
            end_dt = start_dt + timedelta(hours=1)
        
        # Get description
        description = event.get('description', '')
        
        # Handle colors from Google Calendar
        event_colors = self._get_event_colors(event)
        if event_colors and not tag:
            tag = Tag(
                f"gcal_{event.get('id', 'unknown')}",
                fill_color=event_colors.get('background', self.default_tag.fill_color),
                border_color=event_colors.get('foreground', self.default_tag.border_color)
            )
        
        return self._event_to_task(
            title=title,
            start=start_dt,
            end=end_dt,
            description=description,
            tag=tag or self.default_tag
        )
    
    def _get_event_colors(self, event: Dict) -> Optional[Dict]:
        """Get color information from Google Calendar event"""
        color_id = event.get('colorId')
        if not color_id:
            return None
        
        try:
            # Fetch color definitions (cached would be better in production)
            colors = self.service.colors().get().execute()
            event_colors = colors.get('event', {}).get(color_id, {})
            
            if event_colors:
                return {
                    'background': self._hex_to_rgb(event_colors.get('background', '#ffffff')),
                    'foreground': self._hex_to_rgb(event_colors.get('foreground', '#000000'))
                }
        except HttpError:
            pass
        
        return None
    
    def _hex_to_rgb(self, hex_color: str) -> tuple:
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def get_calendar_list(self) -> List[Dict]:
        """Get list of available calendars for the authenticated user"""
        if not self.service:
            return []
        
        try:
            calendar_list = self.service.calendarList().list().execute()
            calendars = []
            
            for calendar_entry in calendar_list.get('items', []):
                calendars.append({
                    'id': calendar_entry['id'],
                    'name': calendar_entry.get('summary', 'Untitled'),
                    'description': calendar_entry.get('description', ''),
                    'primary': calendar_entry.get('primary', False),
                    'access_role': calendar_entry.get('accessRole', 'reader'),
                    'background_color': calendar_entry.get('backgroundColor', '#ffffff'),
                    'foreground_color': calendar_entry.get('foregroundColor', '#000000')
                })
            
            return calendars
            
        except HttpError as error:
            print(f"Error fetching calendar list: {error}")
            return []


# Helper function to create configuration
def create_google_calendar_config(
    name: str,
    auth_type: str = 'oauth2',
    credentials_file: str = 'credentials.json',
    token_file: str = 'token.json',
    calendars: List[Dict] = None,
    calendar_id: str = 'primary',
    **kwargs
) -> CalendarConfig:
    """
    Helper function to create Google Calendar configuration
    
    Args:
        name: Configuration name
        auth_type: 'oauth2' or 'service_account'
        credentials_file: Path to Google credentials file
        token_file: Path to token file (OAuth2 only)
        calendars: List of calendar configurations for multiple calendars
        calendar_id: Single calendar ID if not using multiple calendars
        **kwargs: Additional configuration options
    """
    
    auth_config = {
        'type': auth_type,
        'credentials_file': credentials_file,
    }
    
    if auth_type == 'oauth2':
        auth_config.update({
            'token_file': token_file,
            'headless': kwargs.get('headless', False),
            'redirect_port': kwargs.get('redirect_port', 0)
        })
    elif auth_type == 'service_account':
        auth_config.update({
            'service_account_file': kwargs.get('service_account_file', 'service-account.json'),
            'subject': kwargs.get('subject')  # For domain-wide delegation
        })
    
    source_config = {
        'max_results': kwargs.get('max_results', 250)
    }
    
    if calendars:
        source_config['calendars'] = calendars
    else:
        source_config['calendar_id'] = calendar_id
    
    return CalendarConfig(
        name=name,
        source_type='google_calendar',
        enabled=kwargs.get('enabled', True),
        auth_config=auth_config,
        color_config=kwargs.get('color_config'),
        source_config=source_config
    )