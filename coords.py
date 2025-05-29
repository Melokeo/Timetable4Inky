# l = left, r = right
# t = top, b = bottom
# m = middle

layout_coords = {
    "updated_time": (36, 27),   # lb
    "wifi": (8, 29),            # lb
    "ver_ident": (25, 31),      # lb
    "refresh_ico": (9, 52),     # lb
    "routine_ident": (36, 52),  # lb
    
    "task_stat": (218, 28),     # mm
    "next_task": (405, 29),     # mm
    "hint_next": (300, 27),     # lb
    "time_next": (300, 52),     # lb

    "logo": (5, 479),           # lb

    "task_now_hint": (25, 110), # lb
    "task_now_hint": (25, 121), # lb
    "task_now": (150, 184),     # mb

    "date": (795, 43),          # rb
    "ganzhi": (783, 71),        # rb
    "lineTitle_left": (482, 48),
    "lineTitle_rt": (782, 48),
}

top_vert_line_coords = {
    '1t': (150, 10),
    '1b': (150, 52),
    '2t': (286, 10),
    '2b': (286, 52),
}

timeline_left_coords = {
    "line_top": (315, 86),
    "line_bottom": (315, 468),
    "grid_lt": (315, 92),
    "grid_rb": (538, 464),
    "tick_rt": (315+1, 92+1),   # same as grid_lt
    "tick_lb": (315-4+1, 464+1),
}

timeline_right_coords = {
    "line_top": (558, 86),
    "line_bottom": (558, 468),
    "grid_lt": (558, 92),
    "grid_rb": (782, 464),
    "tick_rt": (558+1, 92+1),   # same as grid_lt
    "tick_lb": (558-4+1, 464+1),
}