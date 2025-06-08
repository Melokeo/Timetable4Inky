from task import TaskTemplate, Tag
from datetime import time
from display import display, mixColors
from typing import Dict, List, Union
from alarm import Sound

TAGS = {
   "survive": Tag(
        "survive", 
        fill_color=mixColors(b=5, r=3, w=38),
        border_color=mixColors(b=5, r=3, w=8, k=1.5),
        has_alarm=True,
        alarm_sound=Sound._173,
    ),
   "self": Tag(
        "self", 
        fill_color=mixColors(y=5, r=5, w=15),
        border_color=mixColors(y=2, r=5, w=8, k=1.5),
        has_alarm=True,
        alarm_sound=Sound.DEFAULT,
    ), 
   "work": Tag(
        "work", 
        fill_color=mixColors(r=5, w=15),
        border_color=mixColors(r=5, w=8, k=1.5),
    ),
   "exer": Tag(
        "exer", 
        fill_color=mixColors(r=10, w=15),
        border_color=mixColors(r=10, w=6, k=1.5),
        has_alarm=True,
        alarm_sound=Sound.UPRISING,
    ),
}

TASK_PRESET = {
    "standup": TaskTemplate(
        title="Morning Standup",
        start_time=time(0, 0),
        duration_minutes=15,
        tags={TAGS["survive"]},
        fill_color=mixColors(b=1, g=0.3, w=6),
        border_color=mixColors(b=1, w=1),
        alarm_sound=Sound.EWMF,
    ),
    
    "drawing": TaskTemplate(
        title="画画",
        start_time=time(0, 0),
        duration_minutes=120,
        tags={TAGS["self"]}
    ),
    
    "music": TaskTemplate(
        title="作曲/练琴",
        start_time=time(0, 0),
        duration_minutes=30,
        tags={TAGS["self"]}
    ),
    
    "focus": TaskTemplate(
        title="干活！",
        start_time=time(0, 0),
        duration_minutes=60,
        tags={TAGS["work"]}
    ),
    
    "run": TaskTemplate(
        title="跑步！",
        start_time=time(0, 0),
        duration_minutes=50,
        tags={TAGS["exer"]}
    ),
    
    "gym": TaskTemplate(
        title="去健身房",
        start_time=time(0, 0),
        duration_minutes=40,
        tags={TAGS["exer"]}
    ),
    
    "class": TaskTemplate(
        title="上课",
        start_time=time(0, 0),
        duration_minutes=120,
        tags={TAGS["self"]}
    ),
    
    "care": TaskTemplate(
        title="清洁",
        start_time=time(0, 0),
        duration_minutes=25,
        tags={TAGS["survive"]}
    ),
    
    "cook": TaskTemplate(
        title="做饭",
        start_time=time(0, 0),
        duration_minutes=45,
        tags={TAGS["survive"]}
    ),
    
    "dine": TaskTemplate(
        title="干饭",
        start_time=time(0, 0),
        duration_minutes=25,
        tags={TAGS["survive"]}
    ),

    "sleep": TaskTemplate(
        title="KuenGao",
        start_time=time(0, 0),
        duration_minutes=680,
        tags={TAGS["survive"]}
    ),
}

class RoutineBuilder:
    def __init__(self, presets: Dict[str, TaskTemplate]):
        self.presets = presets
    
    def __call__(self, *tasks: Union[tuple, str]):
        """Build routine from task definitions"""
        routine_tasks = []
        for task_def in tasks:
            if isinstance(task_def, tuple):
                name = task_def[0]
                start_time = task_def[1]
                
                if name in self.presets:
                    template = self.presets[name]
                    duration = task_def[2] if len(task_def) > 2 else template.duration_minutes
                    
                    routine_tasks.append(TaskTemplate(
                        template.title, start_time, duration,
                        template.description, template.tags, template.text_color,
                        template.border_color, template.fill_color, 
                        template.has_alarm, template.alarm_sound
                    ))
                else:
                    # Create default task for unknown names
                    duration = task_def[2] if len(task_def) > 2 else 30
                    routine_tasks.append(TaskTemplate(
                        title=name,
                        start_time=start_time,
                        duration_minutes=duration,
                        tags={TAGS["self"]}  # Default tag
                    ))
            else:
                routine_tasks.append(self.presets[task_def])
        return routine_tasks

def parse_routine(schedule_string: str) -> List[tuple]:
    """Parse compact schedule string with optional stop times
    
    Format: "HH:MM task_name [--HH:MM], HH:MM task_name, ..."
    Use "--HH:MM" after a task to override its default duration
    
    Example: "8:00 standup --8:15, 9:00 focus --9:30, 10:00 run" 
    """
    tasks = []
    items = [item.strip() for item in schedule_string.split(',') if item.strip()]
    
    i = 0
    while i < len(items):
        parts = items[i].split('--')
        time_str, task_name = parts[0].strip().split(' ', 1)
        hour, minute = map(int, time_str.split(':'))
        start = time(hour, minute)

        if len(parts) > 1:      # defined duration
            end_hour, end_minute = map(int, parts[1].strip().split(':'))
            duration_minutes = (end_hour * 60 + end_minute) - (hour * 60 + minute)
            tasks.append((task_name, start, duration_minutes))
        else:
            # either until next start or use default duration
            if i + 1 < len(items):
                next_time_str = items[i + 1].split('--')[0].strip().split(' ', 1)[0]
                next_hour, next_minute = map(int, next_time_str.split(':'))
                duration_minutes = (next_hour * 60 + next_minute) - (hour * 60 + minute)
                if duration_minutes >= TASK_PRESET[task_name].duration_minutes:
                    tasks.append((task_name, start))
                else:
                    tasks.append((task_name, start, duration_minutes))

            else:
                tasks.append((task_name, start))  

        i += 1
    
    return tasks

# Initialize builder

# test method, in case you messed up the parsing func :<
def test_parse_routine():
    """Test parse_routine with various input formats"""
    
    # Test 1: Basic parsing
    tasks = parse_routine("8:00 standup, 9:00 focus, 10:00 run")
    assert len(tasks) == 3
    assert tasks[0] == ("standup", time(8, 0))
    assert tasks[1] == ("focus", time(9, 0))
    assert tasks[2] == ("run", time(10, 0))
    
    # Test 2: With custom end times
    tasks = parse_routine("8:00 standup --8:10, 9:00 focus --10:30")
    assert len(tasks) == 2
    assert tasks[0] == ("standup", time(8, 0), 10)  # 10 minutes
    assert tasks[1] == ("focus", time(9, 0), 90)     # 90 minutes
    
    # Test 3: Mixed format
    tasks = parse_routine("8:00 standup --8:15, 9:00 focus, 10:00 run --10:30")
    assert len(tasks) == 3
    assert tasks[0] == ("standup", time(8, 0), 15)
    assert tasks[1] == ("focus", time(9, 0))
    assert tasks[2] == ("run", time(10, 0), 30)
    
    # Test 4: Build actual routine
    routine_tasks = routine(*parse_routine("8:00 standup --8:15, 9:00 focus"))
    assert len(routine_tasks) == 2
    assert routine_tasks[0].duration_minutes == 15
    assert routine_tasks[1].duration_minutes == 60  # Default focus duration
    
    print("All parsing tests passed!")

if __name__ == '__main__':
    routine = RoutineBuilder(TASK_PRESET)
    test_parse_routine()
    # print(TASK_PRESET['sleep'])