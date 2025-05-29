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

rt_workday_01 = DayPreset('0528-1', 
    routine(*parse_routine('8:15 standup --8:35, 9:45 focus --12:00, 13:00 focus --18:25, 19:15 dine, 20:15 drawing --23:59, 1:15 sleep'))
)

rt_workday_02 = DayPreset('0529-2', 
    routine(*parse_routine('8:00 standup --8:20, 9:30 focus --12:00, 13:00 focus --18:10, 19:00 dine, 20:00 drawing --23:59, 1:00 sleep'))
)

rt_workday_03 = DayPreset('0530-3', 
    routine(*parse_routine('7:45 standup --8:05, 9:15 focus --12:00, 13:00 focus --17:55, 18:45 dine, 19:45 drawing --23:59, 0:45 sleep'))
)

rt_workday_04 = DayPreset('0531-4', 
    routine(*parse_routine('7:30 standup --7:50, 9:00 focus --12:00, 13:00 focus --17:40, 18:30 dine, 19:30 drawing --23:59, 0:30 sleep'))
)

rt_workday_05 = DayPreset('0601-5', 
    routine(*parse_routine('7:15 standup --7:35, 8:45 focus --12:00, 13:00 focus --17:25, 18:15 dine, 19:15 drawing --23:59, 0:15 sleep'))
)

rt_workday_06 = DayPreset('0602-6', 
    routine(*parse_routine('7:00 standup --7:20, 8:30 focus --12:00, 13:00 focus --17:10, 18:00 dine, 19:00 drawing --23:59'))
)

rt_workday_07 = DayPreset('0603-7', 
    routine(*parse_routine('6:45 standup --7:05, 8:15 focus --12:00, 13:00 focus --16:55, 17:45 dine, 18:45 drawing --23:45'))
)

rt_workday_08 = DayPreset('0604-8', 
    routine(*parse_routine('6:50 standup --7:10, 8:00 focus --12:00, 13:00 focus --16:40, 17:30 dine, 18:30 drawing --23:30'))
)

rt_workday_09 = DayPreset('0605-9', 
    routine(*parse_routine('6:50 standup --7:10, 8:00 focus --12:00, 13:00 focus --16:25, 17:15 dine, 18:30 drawing --23:15'))
)

rt_workday_10 = DayPreset('0606-10', 
    routine(*parse_routine('6:50 standup --7:10, 8:00 focus --12:00, 13:00 focus --17:10, 17:40 dine, 18:30 drawing --23:00'))
)

rt_workday_11 = DayPreset('0607-11', 
    routine(*parse_routine('6:50 standup --7:10, 8:00 focus --12:00, 13:00 focus --16:55, 17:40 dine, 18:30 drawing --22:45'))
)

rt_workday_12 = DayPreset('0608-12', 
    routine(*parse_routine('6:50 standup --7:10, 8:00 focus --12:00, 13:00 focus --17:00, 17:40 dine, 18:30 drawing --22:42'))
)

routines = {
    '0528': rt_workday_01,
    '0529': rt_workday_02,
    '0530': rt_workday_03,
    '0531': rt_workday_04,
    '0601': rt_workday_05,
    '0602': rt_workday_06,
    '0603': rt_workday_07,
    '0604': rt_workday_08,
    '0605': rt_workday_09,
    '0606': rt_workday_10,
    '0607': rt_workday_11,
    '0608': rt_workday_12,
}
