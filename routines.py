from datetime import time
from task import DayPreset
from taskTemplates import RoutineBuilder, parse_routine, TASK_PRESET

# ROUTINE DEFINITION USER GUIDE
# ============================
#
# METHOD 1: Tuple-based (explicit times)
# -------------------------------------
# Use (task_name, time(hour, minute)) tuples when you want specific times:
#
# morning = DayPreset("Morning", routine(
#     ("standup", time(8, 0)),
#     ("focus", time(9, 0)),
#     ("run", time(10, 0)),
# ))
#
# METHOD 2: String-based (compact syntax)
# --------------------------------------
# Use parse_routine() for quick definitions with "HH:MM task_name," format:
#
# morning = DayPreset("Morning", 
#     routine(*parse_routine("8:00 standup, 9:00 focus, 10:00 run"))
# )
#
# STOP TIME SYNTAX:
# Use "--HH:MM" to set custom end times:
# "8:00 standup --8:15, 9:00 focus --9:30, 10:00 run"
# This makes standup end at 8:15 (instead of default 15 min), focus end at 9:30
#
# AVAILABLE TASKS:
# ---------------
# standup  - Morning Standup (15 min)
# drawing  - 画画 (120 min)
# music    - 作曲/练琴 (30 min)
# focus    - 干活！(60 min)
# run      - 跑步！(50 min)
# gym      - 去健身房 (40 min)
# class    - 上课 (120 min)
# care     - 清洁 (25 min)
# cook     - 做饭 (45 min)
# dine     - 干饭 (25 min)
#
# NOTES:
# ------
# - Task names must match TASK_PRESET keys exactly
# - Times use 24-hour format
# - Tasks inherit all properties (colors, tags, duration) from templates
# - Parse format: comma-separated "HH:MM task_name" entries
# - Both methods produce identical DayPreset objects

routine = RoutineBuilder(TASK_PRESET) # routine(sth) -> list[Task]

# Example routine
morning_routine = DayPreset("Morning", routine(
    ("standup", time(8, 0)),
    ("focus", time(9, 0)),
    ("run", time(10, 0)),
    ("dine", time(11, 20)),
))

rt_workday = DayPreset('ReallyWorking', 
    routine(*parse_routine('6:50 standup --7:10, 8:00 focus --12:00, 13:00 focus --17:00, \
                   17:40 dine, 18:30 drawing --22:30, 22:42 sleep --23:59'))
)