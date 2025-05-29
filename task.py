from dataclasses import dataclass, field
from datetime import time, datetime, timedelta
from typing import Optional, Set, List
from display import display, mixColors
from alarm import Sound

@dataclass(frozen=True)
class Tag:
    name: str
    text_color: tuple = field(default_factory=lambda: display.BLACK)
    border_color: tuple = field(default_factory=lambda: mixColors(r=5,w=18))
    fill_color: tuple = field(default_factory=lambda: display.WHITE)
    has_alarm: bool = False
    alarm_sound: Sound = Sound.DEFAULT

@dataclass
class TaskTemplate:
    title: str
    start_time: time  # time of day (e.g., time(9, 30))
    duration_minutes: int
    description: str = ""
    tags: Set[Tag] = field(default_factory=set)
    text_color: Optional[tuple] = None
    border_color: Optional[tuple] = None
    fill_color: Optional[tuple] = None
    has_alarm: Optional[bool] = None
    alarm_sound: Optional[Sound] = None
   
    def __post_init__(self):
        if self.tags:
            tag = next(iter(self.tags))
            # Apply tag colors individually for undefined colors
            if self.text_color is None:
                self.text_color = tag.text_color
            if self.border_color is None:
                self.border_color = tag.border_color
            if self.fill_color is None:
                self.fill_color = tag.fill_color
            if self.has_alarm is None:
                self.has_alarm = tag.has_alarm
            if self.alarm_sound is None:
                self.alarm_sound = tag.alarm_sound
            

@dataclass
class DayPreset:            # intended for a daily routine with time set, ready for use.
    name: str
    tasks: List[TaskTemplate] = field(default_factory=list)
    
    def create_schedule(self, date: datetime.date) -> List['Task']:
        """Convert templates to actual tasks for a specific date"""
        return [
            Task(
                title=template.title,
                description=template.description,
                start_time=datetime.combine(date, template.start_time),
                duration=timedelta(minutes=template.duration_minutes),
                tags=template.tags,
                text_color=template.text_color,
                border_color=template.border_color,
                fill_color=template.fill_color,
                has_alarm=template.has_alarm,
                alarm_sound=template.alarm_sound
            )
            for template in self.tasks
        ]
    
    def __add__(self, other:'DayPreset') -> 'DayPreset':
        return DayPreset(name=f'{self.name}+{other.name}', tasks=self.tasks+other.tasks)

@dataclass
class Task:
    title: str
    start_time: datetime
    duration: timedelta
    description: str = ""
    tags: Set[Tag] = field(default_factory=set)
    text_color: Optional[tuple] = None
    border_color: Optional[tuple] = None
    fill_color: Optional[tuple] = None
    has_alarm: bool = False
    alarm_sound: str = "default"
    
    @property
    def end_time(self) -> datetime:
        return self.start_time + self.duration
    
def find_current_task(task_instances, current_time=None):
    """
    Find the task that is currently active at the given time.
    
    Args:
        task_instances: List of Task objects
        current_time: datetime object (defaults to now)
    
    Returns:
        Task object if found, None if no current task
    """
    from datetime import datetime
    
    if current_time is None:
        current_time = datetime.now()
    
    for task in task_instances:
        if task.start_time <= current_time <= task.end_time:
            return task
    
    return None

def find_next_task(task_instances, current_time=None):
    """
    Find the next upcoming task after the current time.
    
    Args:
        task_instances: List of Task objects
        current_time: datetime object (defaults to now)
    
    Returns:
        Task object if found, None if no upcoming tasks
    """
    from datetime import datetime
    
    if current_time is None:
        current_time = datetime.now()
    
    upcoming_tasks = [task for task in task_instances if task.start_time > current_time]
    
    if not upcoming_tasks:
        return None
    
    return min(upcoming_tasks, key=lambda t: t.start_time)

def find_tasks_in_range(task_instances, start_time, end_time):
    """
    Find all tasks that overlap with the given time range.
    
    Args:
        task_instances: List of Task objects
        start_time: datetime object
        end_time: datetime object
    
    Returns:
        List of Task objects that overlap with the range
    """
    overlapping_tasks = []
    
    for task in task_instances:
        # Check if task overlaps with range
        if not (task.end_time <= start_time or task.start_time >= end_time):
            overlapping_tasks.append(task)
    
    return overlapping_tasks