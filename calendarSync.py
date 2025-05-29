from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, time
from typing import List, Dict, Optional, Any
from pathlib import Path
import json
import requests
import base64
from icalendar import Calendar

from task import Task, Tag
from display import mixColors


@dataclass
class CalendarConfig:
    """Configuration for any calendar source"""
    name: str
    source_type: str  # 'ical', 'ticktick', etc.
    enabled: bool = True
    auth_config: Optional[Dict] = None
    color_config: Optional[Dict] = None
    source_config: Optional[Dict] = None  # Source-specific config
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


class CalendarSourceAdapter(ABC):
    """Base class for calendar source adapters"""
    
    def __init__(self, config: CalendarConfig):
        self.config = config
        self.default_tag = self._create_default_tag()
    
    @abstractmethod
    def fetch_tasks_for_date(self, date: datetime.date) -> List[Task]:
        """Fetch tasks from source for specific date"""
        pass
    
    def _create_default_tag(self) -> Tag:
        """Create default tag for this source"""
        return Tag(
            f"{self.config.source_type}_{self.config.name}",
            fill_color=mixColors(b=3, g=3, w=20),
            border_color=mixColors(b=3, g=3, w=10)
        )
    
    def _create_tag(self, sub_name: str = None, custom_colors: Dict = None) -> Tag:
        """Create tag with custom colors"""
        name = f"{self.config.name}_{sub_name}" if sub_name else self.config.name
        colors = custom_colors or self.config.color_config or {}
        
        return Tag(
            name,
            fill_color=tuple(colors.get('fill_color', self.default_tag.fill_color)),
            border_color=tuple(colors.get('border_color', self.default_tag.border_color))
        )
    
    def _event_to_task(self, title: str, start: datetime, end: datetime,
                      description: str = "", tag: Tag = None) -> Task:
        """Convert generic event data to Task"""
        if not tag:
            tag = self.default_tag
            
        duration = end - start if end else timedelta(hours=1)
        
        return Task(
            title=title,
            description=description,
            start_time=start,
            duration=duration,
            tags={tag},
            fill_color=tag.fill_color,
            border_color=tag.border_color,
            text_color=tag.text_color
        )


class ICalAdapter(CalendarSourceAdapter):
    """Adapter for iCal-based sources (Google, Outlook, CalDAV)"""
    
    def fetch_tasks_for_date(self, date: datetime.date) -> List[Task]:
        all_tasks = []
        
        calendars = self.config.source_config.get('calendars', [])
        if calendars:
            # Multiple sub-calendars
            for cal_config in calendars:
                if not cal_config.get('enabled', True):
                    continue
                    
                url = self._build_url(cal_config['id'])
                ical_data = self._fetch_ical(url)
                
                if ical_data:
                    tag = self._create_tag(cal_config.get('name', cal_config['id']), 
                                         cal_config.get('color_config'))
                    tasks = self._parse_ical(ical_data, date, tag)
                    all_tasks.extend(tasks)
        else:
            # Single calendar
            url = self.config.source_config.get('url')
            ical_data = self._fetch_ical(url)
            
            if ical_data:
                tasks = self._parse_ical(ical_data, date)
                all_tasks.extend(tasks)
                
        return all_tasks
    
    def _build_url(self, calendar_id: str) -> str:
        """Build URL for specific calendar"""
        base_url = self.config.source_config.get('base_url', '')
        cal_type = self.config.source_config.get('calendar_type', 'ical')
        
        if cal_type == 'google':
            return f"https://calendar.google.com/calendar/ical/{calendar_id}/public/basic.ics"
        elif cal_type == 'outlook':
            return f"{base_url}/{calendar_id}/calendar.ics"
        elif cal_type == 'caldav':
            return f"{base_url}/calendars/{calendar_id}/"
        else:
            return f"{base_url}/{calendar_id}"
    
    def _fetch_ical(self, url: str) -> Optional[Calendar]:
        """Fetch and parse iCal data"""
        headers = {}
        auth = self.config.auth_config or {}
        
        if auth.get('type') == 'basic':
            credentials = base64.b64encode(
                f"{auth['username']}:{auth['password']}".encode()
            ).decode()
            headers['Authorization'] = f'Basic {credentials}'
        elif auth.get('type') == 'oauth2':
            headers['Authorization'] = f'Bearer {auth["token"]}'
            
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return Calendar.from_ical(response.content)
        except Exception as e:
            print(f"Error fetching calendar {self.config.name}: {e}")
            return None
    
    def _parse_ical(self, cal: Calendar, date: datetime.date, 
                   tag: Tag = None) -> List[Task]:
        """Parse iCal events into Tasks"""
        tasks = []
        
        for component in cal.walk():
            if component.name != "VEVENT":
                continue
                
            dtstart = component.get('dtstart')
            if not dtstart:
                continue
                
            start_dt = dtstart.dt
            if not isinstance(start_dt, datetime):
                start_dt = datetime.combine(start_dt, time(0, 0))
                
            if start_dt.date() != date:
                continue
                
            dtend = component.get('dtend')
            end_dt = dtend.dt if dtend else start_dt + timedelta(hours=1)
            if not isinstance(end_dt, datetime):
                end_dt = datetime.combine(end_dt, time(0, 0))
                
            task = self._event_to_task(
                title=str(component.get('summary', 'Untitled')),
                start=start_dt,
                end=end_dt,
                description=str(component.get('description', '')),
                tag=tag
            )
            tasks.append(task)
            
        return tasks


class TickTickAdapter(CalendarSourceAdapter):
    """Adapter for TickTick API"""
    
    def __init__(self, config: CalendarConfig):
        super().__init__(config)
        self.base_url = "https://dida365.com/open/v1"
        self.access_token = config.auth_config.get('access_token')
    
    def fetch_tasks_for_date(self, date: datetime.date) -> List[Task]:
        all_tasks = []
        
        for project in self.config.source_config.get('projects', []):
            if not project.get('enabled', True):
                continue
                
            try:
                tasks_data = self._fetch_project_tasks(project['id'])
                tag = self._create_tag(project['name'], project.get('color_config'))
                
                for task_data in tasks_data:
                    task = self._parse_task(task_data, date, tag)
                    if task:
                        all_tasks.append(task)
                        
            except Exception as e:
                print(f"Error fetching TickTick project {project['id']}: {e}")
                
        return all_tasks
    
    def _fetch_project_tasks(self, project_id: str) -> List[Dict]:
        """Fetch tasks from TickTick project"""
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f"{self.base_url}/project/{project_id}/tasks",
            headers=headers
        )
        response.raise_for_status()
        return response.json()
    
    def _parse_task(self, task_data: Dict, date: datetime.date, 
                   tag: Tag) -> Optional[Task]:
        """Parse TickTick task data"""
        if not task_data.get('dueDate'):
            return None
            
        due_date = datetime.fromisoformat(
            task_data['dueDate'].replace('Z', '+00:00')
        )
        
        if due_date.date() != date:
            return None
            
        duration = timedelta(minutes=task_data.get('duration', 30))
        
        return self._event_to_task(
            title=task_data['title'],
            start=due_date,
            end=due_date + duration,
            description=task_data.get('content', ''),
            tag=tag
        )


class CalendarSync:
    """Main calendar synchronization manager"""
    
    def __init__(self, config_dir: str = None):
        self.adapters: List[CalendarSourceAdapter] = []
        
        if config_dir:
            self.load_configs(config_dir)
    
    def load_configs(self, config_dir: str):
        """Load all calendar configurations"""
        config_path = Path(config_dir)
        if not config_path.exists():
            config_path.mkdir(parents=True, exist_ok=True)
            return
            
        for json_file in config_path.glob("*.json"):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                if isinstance(data, list):
                    for config_data in data:
                        self._create_adapter(config_data)
                else:
                    self._create_adapter(data)
                    
            except Exception as e:
                print(f"Error loading {json_file}: {e}")
    
    def _create_adapter(self, config_data: Dict):
        """Create appropriate adapter for config"""
        cfg = CalendarConfig.from_dict(config_data)
        
        if not cfg.enabled:
            return
            
        if cfg.source_type in ['ical', 'google', 'outlook', 'caldav']:
            adapter = ICalAdapter(cfg)
        elif cfg.source_type == 'ticktick':
            adapter = TickTickAdapter(cfg)
        elif cfg.source_type == 'google_api':
            from googleCalender import GoogleCalendarAdapter # circular import
            adapter = GoogleCalendarAdapter(cfg)
        else:
            print(f"Unknown source type: {cfg.source_type}")
            return
            
        self.adapters.append(adapter)
    
    def fetch_tasks_for_date(self, date: datetime.date) -> List[Task]:
        """Fetch all tasks for date from all sources"""
        all_tasks = []
        
        for adapter in self.adapters:
            tasks = adapter.fetch_tasks_for_date(date)
            all_tasks.extend(tasks)
            
        all_tasks.sort(key=lambda t: t.start_time)
        return all_tasks


def create_hybrid_schedule(preset_routine: List, calendar_tasks: List[Task],
                          date: datetime.date) -> List[Task]:
    """Merge routine with calendar tasks"""
    from task import TaskTemplate
    
    routine_tasks = []
    for template in preset_routine:
        routine_tasks.append(Task(
            title=template.title,
            description=template.description,
            start_time=datetime.combine(date, template.start_time),
            duration=timedelta(minutes=template.duration_minutes),
            tags=template.tags,
            text_color=template.text_color,
            border_color=template.border_color,
            fill_color=template.fill_color
        ))
    
    # Calendar events take priority over routine
    all_tasks = []
    for task in routine_tasks:
        overlaps = any(
            not (task.end_time <= cal.start_time or task.start_time >= cal.end_time)
            for cal in calendar_tasks
        )
        if not overlaps:
            all_tasks.append(task)
    
    all_tasks.extend(calendar_tasks)
    all_tasks.sort(key=lambda t: t.start_time)
    
    return all_tasks