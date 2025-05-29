#!/usr/bin/env python3

'''
Main components for rendering the display.
- BaseRenderer: Basic drawing utilities (styled text, shapes, images).
- TotalRenderer: Composes the complete schedule image including header, timeline panels, and footer.
- TimelineVRenderer: Draws vertical timeline panels with adaptive task layout, time axes, and indicators.

[ TotalRenderer << 2*TimelineVRenderer ] ==> display.image

main entry point:
TotalRenderer().create_schedule_image(routine)
'''

import os
import locale
from datetime import datetime, date, timedelta
import platform

from numpy import linspace
from PIL import Image, ImageDraw

import lunar_python

from coords import layout_coords, timeline_left_coords, timeline_right_coords, top_vert_line_coords
from display import INKY_AVAILABLE, display, mixColors
from task import Task, find_current_task, find_next_task
from routines import rt_workday, routines
from uploader import TimelineUploader
from style import text_styles

try:
    if platform.system() == "Windows":
        locale.setlocale(locale.LC_CTYPE, 'Chinese')
    else:
        locale.setlocale(locale.LC_CTYPE, 'zh_CN.UTF-8')
except locale.Error as e:
    print(f'Locale setting failed. Code may crash later: {e}')

VER_IDENTIFIER = 'C'

#TODO move these later
radius = 4 # task rect round corner
sleep_hours = (0, 6)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class BaseRenderer:
    def __init__(self):
        self.styles = text_styles

    def _draw_styled_text(self, draw, text, position, style_name):
        """Draw text with predefined style"""
        try:
            style = self.styles[style_name]
        except KeyError:
            print('_draw_styled_text: Invalid style name was passed!')
            return
        draw.text(position, text, 
                fill=style.color, 
                font=style.font, 
                anchor=style.anchor)
    
    def _draw_rounded_line(self, draw, start, end, fill=display.BLACK, width=2):
        """Draw line with rounded ends"""
        x1, y1 = start
        x2, y2 = end
        
        # Draw main line
        draw.line([start, end], fill=fill, width=width)
        
        # Draw rounded caps
        radius = width // 2
        draw.ellipse([(x1-radius, y1-radius), (x1+radius, y1+radius)], fill=fill)
        draw.ellipse([(x2-radius, y2-radius), (x2+radius, y2+radius)], fill=fill)
    
    def _draw_rounded_rect(self, draw, pos, radius=10, fill=None, outline=None, width=1):
        """Draw rounded rectangle with optional fill and border. excluding lt border"""
        x1, y1 = pos[0]
        x2, y2 = pos[1]
        
        # Draw two rectangles that form a cross shape
        draw.rectangle([(x1+radius, y1), (x2-radius, y2)], fill=fill, outline=None)
        draw.rectangle([(x1, y1+radius), (x2, y2-radius)], fill=fill, outline=None)
        
        # Draw corner circles at the correct positions
        corners = [
            (x1, y1),                    # Top-left
            (x2-2*radius, y1),           # Top-right
            (x1, y2-2*radius),           # Bottom-left
            (x2-2*radius, y2-2*radius)   # Bottom-right
        ]
        
        for x, y in corners:
            draw.ellipse([(x, y), (x+2*radius, y+2*radius)], fill=fill, outline=None)
        
        # Draw the outline separately if needed
        if outline:
            # Draw rounded border
            # draw.arc([(x1, y1), (x1+2*radius, y1+2*radius)], 180, 270, fill=outline, width=width)
            draw.arc([(x2-2*radius, y1), (x2, y1+2*radius)], 270, 0, fill=outline, width=width)
            draw.arc([(x1, y2-2*radius), (x1+2*radius, y2)], 90, 180, fill=outline, width=width)
            draw.arc([(x2-2*radius, y2-2*radius), (x2, y2)], 0, 90, fill=outline, width=width)
            
            # Draw straight lines
            draw.line([(x1, y1), (x2-radius, y1)], fill=outline, width=width)
            draw.line([(x1+radius, y2), (x2-radius, y2)], fill=outline, width=width)
            draw.line([(x1, y1), (x1, y2-radius)], fill=outline, width=width)
            draw.line([(x2, y1+radius), (x2, y2-radius)], fill=outline, width=width)
    
    # def _draw_triangle

    def _insert_img(self, draw, pos, img_path, size=None, anchor="lt"):
        """Insert image with anchor positioning"""
        if not os.path.isabs(img_path):
            img_path = os.path.join(BASE_DIR, 'resources', img_path)
        
        x, y = pos
        try:
            img = Image.open(img_path)
            if size:
                img = img.resize(size)
            
            # Adjust position based on anchor
            w, h = img.size
            if 'm' in anchor: x -= w // 2  # middle
            if 'r' in anchor: x -= w       # right
            if 'm' in anchor: y -= h // 2  # middle  
            if 'b' in anchor: y -= h       # bottom
            
            draw.paste(img, (x, y), img)
        except FileNotFoundError:
            print('Lost a wifi icon')
            pass

    def _get_text_size(self, text, style_name):
        """Get text width and height"""
        font = self.styles[style_name].font
        bbox = font.getbbox(text)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        return width, height  

class TotalRenderer(BaseRenderer):
    def __init__(self):
        super().__init__()
        self.curr_routine_ident = None
        
    def create_schedule_image(self, routine, date_str=None):
        self.img = Image.new("RGB" if not INKY_AVAILABLE else "P", 
                       (display.width, display.height), display.WHITE)
        draw = ImageDraw.Draw(self.img)

        # Add semi-transparent background
        try:
            bg = Image.open(os.path.join(BASE_DIR, 'resources', "background.jpg")).resize((display.width, display.height))
            # Create semi-transparent overlay
            overlay = Image.new("RGBA", (display.width, display.height), (255, 255, 255, 0))
            bg = bg.convert("RGBA")
            bg = Image.alpha_composite(bg, overlay)
            self.img.paste(bg.convert("RGB"), (0, 0))
        except FileNotFoundError:
            print('Lost background img.')
            pass
        except Exception as e:
            print(e)
            pass  

        # init task list
        self.task_instances = routine.create_schedule(date.today())
        self.curr_routine_ident = routine.name
        
        # ═══════════════════════════════════════════════════════════
        # HEADER ZONE - Draw your header layout here
        # ═══════════════════════════════════════════════════════════
        self._draw_header(draw, date_str)
        self._draw_task_now(draw)

        # ═══════════════════════════════════════════════════════════
        # TIMELINE ZONE - Draw your timeline layout here  
        # ═══════════════════════════════════════════════════════════
        # TimelineRenderer
        rng_left, rng_right = get_timeline_panel_ranges()
        tl_renderer_left = TimelineVRenderer(timeline_left_coords, rng_left)
        tl_renderer_right = TimelineVRenderer(timeline_right_coords, rng_right)  # (12,18) / (0,6) / (18,24)
        tl_renderer_left.draw_timeline(draw, self.task_instances)
        tl_renderer_right.draw_timeline(draw, self.task_instances)
        
        # ═══════════════════════════════════════════════════════════
        # FOOTER ZONE - Draw your footer layout here
        # ═══════════════════════════════════════════════════════════
        self._draw_footer(draw)
        
        return self.img
    
    def _draw_header(self, draw, date_str):
        """CUSTOMIZE YOUR HEADER LAYOUT HERE"""
        if not date_str:
            date_str = datetime.now().strftime('%Y年 ') + datetime.now().strftime('%m月').lstrip('0') \
                + datetime.now().strftime('%d日 ') #  + dict_wk[datetime.now().strftime('%A')]
        lunar = lunar_python.Solar.fromDate(datetime.now())
        lunar = lunar.getLunar()
        date_str_lunar = f"{lunar.getYearInGanZhi()}年 {lunar.getMonthInGanZhi()}月 {lunar.getDayInGanZhi()}日 （{lunar.getDayXunKong()}） {dict_wk[datetime.now().strftime('%A')]}"
        current_time = datetime.now().strftime('%H:%M')
        #draw.text((LAYOUT['margin'], LAYOUT['margin']), date_str,
               #   fill=display.BLACK, font=self.fonts['title'])
        
        # -------- left top --------
        self._insert_img(self.img, layout_coords['wifi'], img_path="icons8-wifi-48.png", anchor='lb', size=(24,24))

        # dividers
        '''self._draw_rounded_line(
            draw,
            top_vert_line_coords['1t'],
            top_vert_line_coords['1b'],
            width=3,
            fill=mixColors(k=5, w=8),
        )

        self._draw_rounded_line(
            draw,
            top_vert_line_coords['2t'],
            top_vert_line_coords['2b'],
            width=3,
            fill=mixColors(k=5, w=8),
        )'''
        draw.line(
            (top_vert_line_coords['1t'],
            top_vert_line_coords['1b']),
            width=2,
            fill=mixColors(k=5, w=8),
        )

        draw.line(
            (top_vert_line_coords['2t'],
            top_vert_line_coords['2b']),
            width=2,
            fill=mixColors(k=5, w=8),
        )

        self._draw_styled_text(
            draw,
            VER_IDENTIFIER,
            layout_coords['ver_ident'],
            style_name='ver_ident',
        )
        
        self._draw_styled_text(
            draw,
            f'更新于 {current_time}', 
            layout_coords['updated_time'],
            style_name='updated_time',
        )

        self._insert_img(self.img, layout_coords['refresh_ico'], "refr.png", size=(21,21), anchor='lb')

        self._draw_styled_text(
            draw,
            self.curr_routine_ident or 'UNKNOWN RT',
            layout_coords['routine_ident'],
            style_name='updated_time',
        )

        self._draw_styled_text(
            draw,
            '*未接受*',
            layout_coords['task_stat'],
            style_name='task_stat',
        )

        next_task:Task = find_next_task(self.task_instances)
        self._draw_styled_text(
            draw,
            '下一项',
            layout_coords['hint_next'],
            style_name='hint_next',
        )
        
        self._draw_styled_text(
            draw,
            '--' if not next_task else next_task.start_time.strftime('%H:%M'),
            layout_coords['time_next'],
            style_name='time_next',
        )

        self._draw_styled_text(
            draw,
            '--' if not next_task else next_task.title,
            layout_coords['next_task'],
            style_name='next_task',
        )

        # -------- right top --------
        self._draw_rounded_line(
            draw, 
            layout_coords['lineTitle_left'], 
            layout_coords['lineTitle_rt'], 
            width=3, 
            fill=display.RED,
        )

        self._draw_styled_text(
            draw,
            date_str,
            layout_coords['date'],
            style_name='date',
        )

        self._draw_styled_text(
            draw,
            date_str_lunar,
            layout_coords['ganzhi'],
            style_name='ganzhi',
        )
    
    '''def _draw_task_now(self, draw):
        self._draw_styled_text(
            draw,
            '现在应该...',
            layout_coords['task_now_hint'],
            style_name='task_now_hint',
        )

        # background emphasis line of task now
        curr_task = find_current_task(self.task_instances)
        str_task = '啥都没有，画画吧？' if not curr_task else curr_task.title
        width_task, _ = self._get_text_size(str_task, 'task_now')
        coord_anchor_task = layout_coords['task_now']
        height_bgrect = 20
        yoffset_bgrect = -3
            # here it assumes that task text is aligned as 'mb' !!
        coord_bgrectL = (coord_anchor_task[0]- width_task//2, coord_anchor_task[1] - height_bgrect + yoffset_bgrect)
        coord_bgrectR = (coord_anchor_task[0]+ width_task//2, coord_anchor_task[1] + yoffset_bgrect)
        draw.rectangle(
            [coord_bgrectL, coord_bgrectR],
            fill = mixColors(r=5,w=20),
            ) 
        
        self._draw_styled_text(
            draw,
            str_task,
            coord_anchor_task,
            style_name='task_now',
        )'''
        
    def _draw_task_now(self, draw):
        self._draw_styled_text(
            draw,
            '现在应该...',
            layout_coords['task_now_hint'],
            style_name='task_now_hint',
        )

        # get task
        curr_task = find_current_task(self.task_instances)
        default_task = '困觉' if sleep_hours[0] < datetime.now().hour < sleep_hours[1] else '啥都没有，画画吧？'
        str_task = default_task if not curr_task else curr_task.title
        
        # use smaller font if too long
        max_width = 300  
        normal_width = self._get_text_size(str_task, 'task_now')[0]
        font_style = 'task_now_small' if normal_width > max_width else 'task_now'
        
        # background rect
        width_task = self._get_text_size(str_task, font_style)[0]
        coord_anchor_task = layout_coords['task_now']
        height_bgrect = 20
        yoffset_bgrect = -3
        
        coord_bgrectL = (coord_anchor_task[0] - width_task//2, coord_anchor_task[1] - height_bgrect + yoffset_bgrect)
        coord_bgrectR = (coord_anchor_task[0] + width_task//2, coord_anchor_task[1] + yoffset_bgrect)
        
        draw.rectangle(
            [coord_bgrectL, coord_bgrectR],
            fill=mixColors(r=5, w=20),
        ) 
        
        # text
        self._draw_styled_text(
            draw,
            str_task,
            coord_anchor_task,
            style_name=font_style,
        )

    def _wrap_text_for_display(self, text, max_width, font, max_lines=2):
        """Wrap text with Chinese character breaking and English word wrapping"""
        lines = []
        current_line = ""
        i = 0
        
        while i < len(text) and len(lines) < max_lines:
            char = text[i]
            
            # Check if current character is part of an English word
            if char.isalpha() and char.isascii():
                # Find the complete English word
                word_start = i
                while i < len(text) and text[i].isalpha() and text[i].isascii():
                    i += 1
                word = text[word_start:i]
                
                # Try to add the whole word
                test_line = f"{current_line}{word}".strip()
                if font.getbbox(test_line)[2] <= max_width:
                    current_line = test_line
                else:
                    # Word doesn't fit, start new line
                    if current_line:
                        lines.append(current_line)
                        current_line = word
                    else:
                        # Single word too long, force break
                        lines.append(word)
                        current_line = ""
            else:
                # Chinese character, space, or punctuation - can break anywhere
                test_line = current_line + char
                if font.getbbox(test_line)[2] <= max_width:
                    current_line = test_line
                else:
                    # Character doesn't fit, start new line
                    if current_line:
                        lines.append(current_line)
                        current_line = char
                    else:
                        # Single character too wide (shouldn't happen)
                        lines.append(char)
                        current_line = ""
                i += 1
        
        # Add remaining text if within line limit
        if current_line and len(lines) < max_lines:
            lines.append(current_line)
        
        return lines

    def _is_chinese_char(self, char):
        """Check if character is Chinese/CJK"""
        return '\u4e00' <= char <= '\u9fff'

    def _draw_multiline_text(self, draw, lines, anchor_coord, style_name, line_height=24):
        """Draw multiple lines of text centered around anchor point"""
        if not lines:
            return
        
        x, y = anchor_coord
        total_height = len(lines) * line_height
        
        # Start from anchor point, offset by half total height (for 'mb' behavior)
        start_y = y - total_height
        
        for i, line in enumerate(lines):
            line_y = start_y + i * line_height
            self._draw_styled_text(
                draw,
                line,
                (x, line_y),
                style_name=style_name,
            )
    
    def _draw_footer(self, draw):
        """CUSTOMIZE YOUR FOOTER LAYOUT HERE"""
        self._insert_img(self.img, layout_coords['logo'], img_path="logo.png", size=(32,32), anchor='lb')

class TimelineVRenderer(BaseRenderer):
    """
    Renders timeline grid, axes, and tasks for specified time range.
    
    Args:
        coords_dict: Contains 'grid_lt', 'grid_rb', 'line_top', 'line_bottom', 'tick_rt', 'tick_lb'
        hour_range: (start_hour, end_hour) tuple, e.g. (6, 12)
    
    Call draw_timeline(draw, task_instances) to render.
    """
    def __init__(self, coords_dict:dict, hour_range:tuple):     # the draw object should be passed when calling functions
        super().__init__()
        self.coords = coords_dict
        self.hour_start, self.hour_end = hour_range
    
    def draw_timeline(self, draw, task_instances):
        # draws background + all tasks
        self.draw_task_background(draw)
        self.draw_tasks(draw, task_instances)
        self.draw_current_time_overlay(draw)

    def draw_task_background(self, draw):
        '''background grids for task panel in one col'''
        # grid for tasks
        self._draw_horiz_grid(
            draw,
            self.coords['grid_lt'],
            self.coords['grid_rb'],
            width=1,
            split=6*4+1,         # 6hrs per col * 4 quarters/h
            fill=mixColors(w=18,k=5),
        )
        
        # time axis ticks
        self._draw_horiz_grid(
            draw,
            self.coords['tick_rt'],
            self.coords['tick_lb'],
            width=2,
            split=7,
            fill=mixColors(w=4,k=5),
            skip='e',
        )

        # hour numbers HERE IS TIME/MODE DEPENDENT
        self._distrib_hours_vert(
            draw,
            self.coords['tick_rt'],
            self.coords['tick_lb'],
            range(self.hour_start, self.hour_end),
        )

        # time axis (vert. bold line)
        self._draw_rounded_line(
            draw,
            self.coords["line_top"], self.coords["line_bottom"],
            fill=tuple(int(0.5*w + 0.5*k) for w, k in zip(display.WHITE, display.BLACK)),
            width=3,
        )

    def draw_tasks(self, draw, task_instances):
        """Updated main method with timepoint spans"""
        if not task_instances:
            return
        
        visible_tasks = self._filter_and_clamp_tasks(task_instances)
        lane_assignments = self._assign_lanes_adaptive(visible_tasks)
        
        # task rectangles
        for task, lane, local_lanes in lane_assignments:
            rect_coords = self._calculate_task_rect_adaptive(task, lane, local_lanes)
            shifted_coords = self._shift_task_rect_from_axis(rect_coords, "l5r0")
            self._render_task_rect(draw, task, shifted_coords)
            
        # timepoint dots
        self._draw_task_timedots(draw, visible_tasks)

        # Draw timepoint spans
        self._draw_timepoint_spans(draw, task_instances)
        
    def draw_current_time_overlay(self, draw):
        """Draw current time indicator directly on the timeline"""
        from datetime import datetime
        
        current_time = datetime.now()
        current_hour = current_time.hour + current_time.minute/60
        
        # Check if current time is within visible range
        if not (self.hour_start <= current_hour <= self.hour_end):
            return
        
        # Calculate y position
        current_y = self.hour_to_y(current_time.hour, current_time.minute)
        
        # Get coordinates
        axis_x = self.coords["line_top"][0]
        grid_x1, _ = self.coords['grid_lt']
        grid_x2, _ = self.coords['grid_rb']

        # dot ver
        '''
        # Draw dot on axis (with white outline for visibility)
        dot_radius = 3
        # White outline
        draw.ellipse([
            (axis_x - dot_radius - 1, current_y - dot_radius - 1),
            (axis_x + dot_radius + 1, current_y + dot_radius + 1)
        ], fill=display.WHITE)
        # Red center
        draw.ellipse([
            (axis_x - dot_radius, current_y - dot_radius),
            (axis_x + dot_radius, current_y + dot_radius)
        ], fill=display.RED)
        '''

        # Triangle with white border
        triangle_size = 6
        border_width = 1

        # Outer triangle (white border) - slightly larger
        outer_points = [
        (axis_x, current_y + int((triangle_size + border_width) * 1.73)),
        (axis_x - (triangle_size + border_width), current_y - border_width),
        (axis_x + (triangle_size + border_width), current_y - border_width)
        ]
        draw.polygon(outer_points, fill=display.WHITE)

        # Inner triangle (red fill)
        inner_points = [
        (axis_x, current_y + int(triangle_size * 1.73)),
        (axis_x - triangle_size, current_y),
        (axis_x + triangle_size, current_y)
        ]
        draw.polygon(inner_points, fill=display.RED)

        line_color = display.RED
        draw.line([
            (axis_x, current_y), 
            (grid_x2, current_y)
        ], fill=line_color, width=2)

    def hour_to_y(self, hour, minute=0):
        """Convert time to y-coordinate on timeline axis"""
        time_fraction = (hour - self.hour_start) + (minute / 60)
        total_hours = self.hour_end - self.hour_start
        
        y1 = self.coords['grid_lt'][1]  # top y
        y2 = self.coords['grid_rb'][1]  # bottom y
        
        return y1 + (time_fraction / total_hours) * (y2 - y1)

    def y_to_hour(self, y):
        """Convert y-coordinate to (hour, minute) tuple"""
        y1 = self.coords['grid_lt'][1]
        y2 = self.coords['grid_rb'][1]
        
        time_fraction = (y - y1) / (y2 - y1)
        total_minutes = time_fraction * (self.hour_end - self.hour_start) * 60
        
        hour = self.hour_start + int(total_minutes // 60)
        minute = int(total_minutes % 60)
        
        return (hour, minute)

    def _filter_visible_tasks(self, tasks):
        """Filter tasks that overlap with timeline range"""
        visible = []
        for task in tasks:
            start_hour = task.start_time.hour + task.start_time.minute/60
            end_hour = start_hour + task.duration.total_seconds()/3600
            
            if (start_hour < self.hour_end and end_hour > self.hour_start):
                visible.append(task)
        return visible
    
    def _filter_and_clamp_tasks(self, tasks):
        """Filter tasks to panel range and clamp overflows"""
        clamped_tasks = []
        
        for task in tasks:
            start_hour = task.start_time.hour + task.start_time.minute/60
            end_hour = start_hour + task.duration.total_seconds()/3600
            
            # Skip if completely outside panel
            if end_hour <= self.hour_start or start_hour >= self.hour_end:
                continue
                
            # Clamp to panel boundaries
            clamped_start = max(start_hour, self.hour_start)
            clamped_end = min(end_hour, self.hour_end)
            
            # Create clamped task copy
            clamped_task = Task(
                title=task.title,
                start_time=task.start_time,
                duration=timedelta(hours=clamped_end - clamped_start),
                description=task.description,
                tags=task.tags,
                text_color=task.text_color,
                border_color=task.border_color,
                fill_color=task.fill_color,
            )
            
            # Adjust start time if clamped
            if clamped_start > start_hour:
                clamped_task.start_time = task.start_time.replace(
                    hour=int(clamped_start), 
                    minute=int((clamped_start % 1) * 60)
                )
            
            # Show caption only in primary panel (where task starts)
            if start_hour < self.hour_start:
                clamped_task.title = ""  # Hide caption in continuation panels
                
            clamped_tasks.append(clamped_task)
        
        return clamped_tasks

    def _assign_lanes_adaptive(self, tasks):
        """Assign lanes with adaptive width based on local overlap density"""
        if not tasks:
            return []
        
        sorted_tasks = sorted(tasks, key=lambda t: t.start_time)
        assignments = []
        
        for task in sorted_tasks:
            task_start = task.start_time
            task_end = task.start_time + task.duration
            
            # Find overlapping tasks
            overlapping = []
            for other_task in sorted_tasks:
                other_start = other_task.start_time
                other_end = other_task.start_time + other_task.duration
                
                if not (task_end <= other_start or task_start >= other_end):
                    overlapping.append(other_task)
            
            # Assign lane within overlapping group
            used_lanes = set()
            for other_task in overlapping:
                for assigned_task, lane, _ in assignments:
                    if assigned_task == other_task:
                        used_lanes.add(lane)
                        break
            
            # Find first available lane
            lane = 0
            while lane in used_lanes:
                lane += 1
            
            max_lanes = max(len(overlapping), 1)  # Ensure at least 1 lane
            assignments.append((task, lane, max_lanes))
        
        return assignments

    def _calculate_task_rect_adaptive(self, task, lane, local_lanes):
        """Calculate rectangle with adaptive width based on local lane count"""
        start_hour = task.start_time.hour + task.start_time.minute/60
        end_hour = start_hour + task.duration.total_seconds()/3600
        
        y1 = self.hour_to_y(int(start_hour), int((start_hour % 1) * 60))
        y2 = self.hour_to_y(int(end_hour), int((end_hour % 1) * 60))
        
        grid_x1, _ = self.coords['grid_lt']
        grid_x2, _ = self.coords['grid_rb']
        
        # Use local lane count for width calculation
        lane_width = (grid_x2 - grid_x1) / local_lanes
        x1 = grid_x1 + lane * lane_width + 2
        x2 = x1 + lane_width - 4
        
        return ((x1, y1), (x2, y2))

    def _render_task_rect(self, draw, task, rect_coords):
        """Render individual task rectangle with adaptive content"""
        (x1, y1), (x2, y2) = rect_coords
        width = x2 - x1
        height = y2 - y1
        
        # Get colors with fallbacks
        fill_color = task.fill_color or display.WHITE
        border_color = task.border_color or display.BLACK
        text_color = task.text_color or display.BLACK
        
        # Adaptive content based on height
        if height < 15:  # Very short task - line mode
            self._render_line_mode(draw, task, (x1, y1, x2, y2), text_color)
        elif height < 40:  # Short task - small text
            self._draw_rounded_rect(draw, rect_coords, radius=radius, 
                            fill=fill_color, outline=border_color, width=2)
            self._render_compact_mode(draw, task, (x1, y1, x2, y2), text_color)
        else:  # Normal task - full content
            self._draw_rounded_rect(draw, rect_coords, radius=radius, 
                            fill=fill_color, outline=border_color, width=2)
            content = self._calculate_adaptive_content(task, width, height)
            self._render_task_text(draw, content, (x1, y1, x2, y2), text_color)

    def _render_line_mode(self, draw, task, rect, color):
        """Line display for very short tasks - draws horizontal line with text"""
        x1, y1, x2, y2 = rect
        center_y = (y1 + y2) // 2
        
        # Get task color for line
        line_color = task.border_color or color
        
        # Draw horizontal line across the width
        draw.line([(x1 + 4, y1), (x2 - 4, y1)], 
                fill=line_color, width=3)
        
        # Add title text on the line
        title = task.title
        max_chars = max(1, (x2 - x1 - 16) // 6)  # Account for line padding
        if len(title) > max_chars:
            title = title[:max_chars-1] + "…"
        
        # Draw text with background for readability
        text_x = x1 + 8
        text_bbox = self.styles['task'].font.getbbox(title)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        '''# Small background rectangle behind text
        pad = 2
        draw.rectangle([
            (text_x - pad, center_y - text_height//2 - pad),
            (text_x + text_width + pad, center_y + text_height//2 + pad)
        ], fill=display.WHITE, outline=None)'''
        
        # Draw text
        draw.text((text_x, center_y), title, fill=color,
                font=self.styles['task'].font, anchor='lm')
    
    def _render_compact_mode(self, draw, task, rect, color):
        """Compact display with smaller text"""
        x1, y1, x2, y2 = rect
        center_x = (x1 + x2) // 2
        
        # Try to fit title + time
        title = task.title
        max_chars = max(1, (x2 - x1 - 8) // 5)
        if len(title) > max_chars:
            title = title[:max_chars-1] + "…"
        
        # Small font for compact mode
        small_font = self.styles['task_small'].font  # Use smaller font
        
        draw.text((center_x, y1+1), title, fill=color,
                font=small_font, anchor='mt')
        
        # Add time if space allows
        if (y2 - y1) > 20:
            time_str = task.start_time.strftime("%H:%M")
            draw.text((center_x, y2+3), time_str, fill=color, #TODO magic numbers
                    font=small_font, anchor='mb')
    
    def _draw_timepoint_spans(self, draw, task_instances):
        """Draw lines from time axis timepoints across task lengths"""
        if not task_instances:
            return
        
        visible_tasks = self._filter_visible_tasks(task_instances)
        lane_assignments = self._assign_lanes_adaptive(visible_tasks)
        
        axis_x = self.coords["line_top"][0]
        
        for task, lane, local_lanes in lane_assignments:
            color = task.border_color or display.WHITE
            # Calculate task's horizontal span
            grid_x1, _ = self.coords['grid_lt']
            grid_x2, _ = self.coords['grid_rb']
            lane_width = (grid_x2 - grid_x1) / local_lanes
            task_x1 = grid_x1 + lane * lane_width + 2
            task_x2 = task_x1 + lane_width - 4

            final_x1 = task_x1
            final_x2 = task_x2
            
            # Draw start timepoint span
            start_hour = task.start_time.hour + task.start_time.minute/60
            if self.hour_start <= start_hour <= self.hour_end:
                start_y = self.hour_to_y(task.start_time.hour, task.start_time.minute)
                # Line from axis to start of task area
                draw.line([(axis_x, start_y), (final_x1, start_y)], 
                        fill=color, width=3)
                # Span across task width
                draw.line([(final_x1, start_y), (final_x2 - int(radius*.8), start_y)], 
                        fill=color, width=3)
                
            '''
            # Draw end timepoint span
            end_hour = start_hour + task.duration.total_seconds()/3600
            if self.hour_start <= end_hour <= self.hour_end:
                end_time = task.start_time + task.duration
                end_y = self.hour_to_y(end_time.hour, end_time.minute)
                # Line from axis to start of task area
                draw.line([(axis_x, end_y), (final_x1, end_y)], 
                        fill=display.BLUE, width=1)
                # Span across task width
                draw.line([(final_x1, end_y), (final_x2, end_y)], 
                        fill=mixColors(w=15, k=3), width=2)
            '''

    def _shift_task_rect_from_axis(self, rect_coords, code="l8r0"):
        """
        Shift rectangle with string format: 'l{left}r{right}' 
        Examples: 'l8r0' = left +8px, right +0px
                'l0r-5' = left +0px, right -5px
        """
        (x1, y1), (x2, y2) = rect_coords

        # parse
        import re
        pattern = r'l(-?\d+)r(-?\d+)'
        match = re.match(pattern, code)
        
        if not match:
            print(f"Invalid shift code")
            return
            shift_l, shift_r = 8, 0
        else:
            shift_l = int(match.group(1))
            shift_r = int(match.group(2))
        
        new_x1 = x1 + shift_l  
        new_x2 = x2 + shift_r 
        
        return ((new_x1, y1), (new_x2, y2))

    def _calculate_adaptive_content(self, task, width, height):
        """Determine what content fits in available space with better logic"""
        content = {'title': task.title, 'description': '', 'time': ''}
        
        # Estimate text dimensions
        title_font = self.styles['task'].font
        line_height = 16
        margin = 8
        
        # Always try to show title (with line breaks if needed)
        title_lines = self._wrap_text(task.title, width - margin, title_font, max_lines=2)
        content['title'] = '\n'.join(title_lines)
        title_height = len(title_lines) * line_height
        
        # Calculate remaining space
        remaining_height = height - title_height - margin
        available_width = width - margin
        
        # Time strings
        start_time = task.start_time.strftime("%H:%M")
        end_time = task.end_time.strftime("%H:%M")
        time_both = f"{start_time}-{end_time}"
        
        # Check what fits
        time_width_both = self._get_text_size(time_both, 'task')[0]
        time_width_start = self._get_text_size(start_time, 'task')[0]
        desc_width = self._get_text_size(task.description[:15], 'task')[0] if task.description else 0
        
        # Priority: Title > Time > Description
        if remaining_height >= line_height:  # Space for at least one more line
            if time_width_both <= available_width and remaining_height >= line_height:
                content['time'] = time_both
                remaining_height -= line_height
            elif time_width_start <= available_width:
                content['time'] = start_time
                remaining_height -= line_height
        
        # Add description if space allows
        if remaining_height >= line_height and task.description:
            if desc_width <= available_width:
                content['description'] = task.description[:15]
                if len(task.description) > 15:
                    content['description'] += "..."
            elif remaining_height >= line_height and available_width > 50:  # Minimum width
                # Try abbreviated description
                max_chars = max(3, available_width // 8)  # Rough char width
                content['description'] = task.description[:max_chars] + "..."
        
        return content

    def _wrap_text(self, text, max_width, font, max_lines=2):
        """Wrap text to fit width with line limit"""
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if font.getbbox(test_line)[2] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                    current_line = word
                else:
                    lines.append(word)  # Single word too long
                
                if len(lines) >= max_lines:
                    break
        
        if current_line and len(lines) < max_lines:
            lines.append(current_line)
        
        return lines[:max_lines]

    def _render_task_text(self, draw, content, rect, color):
        """Render text content centered within rectangle"""
        x1, y1, x2, y2 = rect
        center_x = (x1 + x2) // 2
        
        # Stack content vertically, centered
        elements = []
        if content['title']:
            elements.append(('title', content['title']))
        if content['time']:
            elements.append(('time', content['time']))
        if content['description']:
            elements.append(('desc', content['description']))
        
        if not elements:
            return
        
        # Calculate total content height
        font = self.styles['task'].font
        bbox = font.getbbox('Ay')
        line_height = bbox[3] - bbox[1] + 4
        total_lines = sum(len(text.split('\n')) for _, text in elements)
        total_height = total_lines * line_height
        
        # Start from center, offset by half total height
        rect_center_y = (y1 + y2) // 2
        start_y = rect_center_y - total_height // 2
        
        current_y = start_y
        for element_type, text in elements:
            for line in text.split('\n'):
                draw.text((center_x, current_y), line, fill=color,
                        font=self.styles['task'].font, anchor='mt')
                current_y += line_height

    def _draw_task_timedots(self, draw, task_instances):
        """Draw dots on time axis for task start/end points"""
        axis_x = self.coords["line_top"][0]
        
        for task in task_instances:
            start_hour = task.start_time.hour + task.start_time.minute/60
            end_hour = start_hour + task.duration.total_seconds()/3600
            
            # Only draw if within visible range
            if self.hour_start <= start_hour <= self.hour_end:
                start_y = self.hour_to_y(task.start_time.hour, task.start_time.minute)
                self._draw_time_dot(draw, (axis_x, start_y), task.border_color)
            
            '''
            if self.hour_start <= end_hour <= self.hour_end:
                end_time = task.start_time + task.duration
                end_y = self.hour_to_y(end_time.hour, end_time.minute)
                self._draw_time_dot(draw, (axis_x, end_y), display.BLUE)
            '''

    def _draw_time_dot(self, draw, center, color, radius=3):
        """Draw solid dot at timepoint"""
        x, y = center
        border = 1
        draw.ellipse([(x-radius-border, y-radius-border), (x+radius+border, y+radius+border)], fill=display.WHITE)
        draw.ellipse([(x-radius, y-radius), (x+radius, y+radius)], fill=color)

    def _draw_horiz_grid(self, draw, lt:tuple, rb:tuple, width:int, split:int, fill:tuple, skip:str=''):
        x1, y1 = lt
        x2, y2 = rb
        ys = list(linspace(y1, y2, split))
        if 's' in skip: ys.pop(0)
        if 'e' in skip: ys.pop(-1)
        starts = [(x1, int(y)) for y in ys]
        ends   = [(x2, int(y)) for y in ys]
        for s, e in zip(starts, ends):
            draw.line([s, e], fill=fill, width=width)

    def _distrib_hours_vert(self, draw, top:tuple, bottom:tuple, hrs, skip:str='e', style:str='timetick', xoffset:int=-3):
        '''
        distribute hour ticks vertically on the axes.
        Note that it by default discards last coord. i.e. bottom tick is not assigned a number.
        '''
        try:
            self.styles[style]
        except KeyError:
            print('_distrib_hours: Invalid style name was passed!')
            return
        
        x, y1 = top
        _, y2 = bottom
        x = x + xoffset
        
        # Create grid points including endpoints
        grid_points = len(hrs)
        if 's' not in skip: grid_points += 1  
        if 'e' not in skip: grid_points += 1 
        ys = list(linspace(y1, y2, grid_points))
        
        # Remove skipped points
        if 's' in skip: ys.pop(0)
        if 'e' in skip: ys.pop(-1)
        assert len(ys) == len(hrs)
        anchors = [(x, int(y)) for y in ys]

        for i in range(len(hrs)): 
            self._draw_styled_text(
                draw,
                str(hrs[i]),
                position=anchors[i],
                style_name=style,
            )

def update_display(routine):
    renderer = TotalRenderer()
    # tasks = build_day_schedule(schedule_data)
    img = renderer.create_schedule_image(routine)
    
    display.set_image(img)
    if platform.system == 'Windows':
        display.show()
    
    if not INKY_AVAILABLE:
        out_path = os.path.join(BASE_DIR, 'output')
        if not os.path.exists(out_path): os.mkdir(out_path)
        img.save(os.path.join(out_path, 'schedule_preview.png'))
        print("Preview saved as schedule_preview.png")

def get_timeline_panel_ranges(current_time=None, panel_hours=6, total_hours=24):
   """
   Determine which time panels to display based on current time.
   
   Args:
       current_time: datetime object (defaults to now)
       panel_hours: hours per panel (default 6)
       total_hours: total hours in cycle (default 24 for single day)
   
   Returns:
       tuple of (left_panel, right_panel) as (start_hour, end_hour)
   """
   from datetime import datetime
   
   if current_time is None:
       current_time = datetime.now()
   
   current_hour = current_time.hour
   panels_per_day = total_hours // panel_hours
   
   # Calculate which panel current time falls into
   current_panel = current_hour // panel_hours
   
   # Skip first panel (0-6) unless it's the only option
   if panels_per_day > 2 and current_panel == 0:
       # Show panels 1 and 2
       left_start = panel_hours
       right_start = panel_hours * 2
   elif current_panel >= panels_per_day - 1:
       # At last panel: show previous and current
       left_start = (panels_per_day - 2) * panel_hours
       right_start = (panels_per_day - 1) * panel_hours
   else:
       # Normal case: show current and next
       left_start = current_panel * panel_hours
       right_start = (current_panel + 1) * panel_hours
   
   return (left_start, left_start + panel_hours), (right_start, right_start + panel_hours)

dict_wk = {
   'Monday': '周一',
   'Tuesday': '周二', 
   'Wednesday': '周三',
   'Thursday': '周四',
   'Friday': '周五',
   'Saturday': '周六',
   'Sunday': '周日'
}

if __name__ == "__main__":
    if (d:=datetime.now().strftime('%m%d')) in routines.keys():
        update_display(routines[d])
    else:
        update_display(rt_workday)
    uploader = TimelineUploader(os.path.join(BASE_DIR, 'cfg', 'upload_config.json'))
    try:
        uploader.upload_png(note='Bolus exec')
    except Exception as e:
        print(e)