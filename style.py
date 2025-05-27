import os
from PIL import ImageFont

from display import display

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Font loading with Chinese support
def load_fonts():
    fonts = {}
    
    # Windows fonts with emoji support
    font_candidates = [
        #'C:/Windows/Fonts/seguiemj.ttf',   # Segoe UI Emoji
        os.path.join(BASE_DIR, 'resources', "NotoSansCJKsc-Regular.otf"),
        'C:/Windows/Fonts/msyh.ttc',       # Microsoft YaHei (Chinese)
        'C:/Windows/Fonts/arial.ttf'       # Arial fallback
    ]
    
    for name, size in [
        ('title', 28), ('date', 34), ('body', 16), ('now_hint', 34), ('task_now', 50), ('task_now_small', 32), 
        ('time', 14), ('small', 14), ('smaller', 12), ('timetick', 12)
    ]:
        fonts[name] = None
        
        for font_file in font_candidates:
            try:
                fonts[name] = ImageFont.truetype(font_file, size)
                # print(f"✓ {name}: {font_file}")
                break
            except (OSError, IOError):
                continue
        
        if not fonts[name]:
            fonts[name] = ImageFont.load_default()
            print(f"⚠ {name}: default font")
    
    fonts['date'] = ImageFont.truetype(os.path.join(BASE_DIR, 'resources', "NotoSansCJKsc-Bold.otf"), 34)
    fonts['task_now'] = ImageFont.truetype(os.path.join(BASE_DIR, 'resources', "NotoSansCJKsc-Bold.otf"), 50)
    fonts['task_now_small'] = ImageFont.truetype(os.path.join(BASE_DIR, 'resources', "NotoSansCJKsc-Bold.otf"), 32)
    # fonts['timetick'] = ImageFont.truetype(r"C:\Users\Melokeo\Documents\ttb\NotoSansCJKsc-Bold.otf", 12)

    return fonts

def check_font_available(font_path, size):
    """Check if font file exists and can be loaded"""
    import os
    
    # Check file existence first
    if not os.path.exists(font_path):
        # Try system font paths
        system_paths = [
            f"/usr/share/fonts/opentype/noto/{font_path}",
            f"/usr/share/fonts/truetype/dejavu/{font_path}",
            f"/System/Library/Fonts/{font_path}",
            f"C:/Windows/Fonts/{font_path}"
        ]
        
        font_path = next((p for p in system_paths if os.path.exists(p)), font_path)
    
    # Try loading the font
    try:
        ImageFont.truetype(font_path, size)
        return True
    except:
        return False
   
class TextStyle:
   def __init__(self, font, color, anchor="lt"):
       self.font = font
       self.color = color
       self.anchor = anchor  # "lt"=left-top, "mm"=middle-middle, rt - right top, lb - left bottom

fonts = load_fonts()
text_styles = {
    'header':           TextStyle(fonts['title'], display.BLACK, "lt"),
    'time':             TextStyle(fonts['time'], display.RED, "rt"),
    'task':             TextStyle(fonts['body'], display.BLACK, "lm"),
    'task_small':       TextStyle(fonts['smaller'], display.BLACK, "lm"),
    'footer':           TextStyle(fonts['small'], display.BLACK, "lb"),
    "updated_time":     TextStyle(fonts['small'], display.BLACK, "lb"),   
    "wifi":             TextStyle(fonts['small'], display.BLACK, "lb"),           
    "task_now_hint":    TextStyle(fonts['now_hint'], display.BLACK, "lb"),     
    "task_now":         TextStyle(fonts['task_now'], display.RED, "mb"),     
    "task_now_small":   TextStyle(fonts['task_now_small'], display.RED, "mb"),     
    "date":             TextStyle(fonts['date'], display.BLACK, "rb"),          
    "ganzhi":           TextStyle(fonts['small'], display.BLACK, "rb"),        
    "ver_ident":        TextStyle(fonts['smaller'], display.BLACK, "lb"), 
    "timetick":         TextStyle(fonts['timetick'], display.BLACK, "rt"),      
}  