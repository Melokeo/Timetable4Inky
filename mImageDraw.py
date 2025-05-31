from PIL import ImageDraw, Image
import os

from debugDrawer import DebugDraw
from style import text_styles

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# change inherit to DebugDraw for step by step testing.
class MImageDraw(ImageDraw.ImageDraw):
    def __init__(self, im, mode=None):
        super().__init__(im, mode)
        self.styles = text_styles 
    
    def styledText(self, text, position, style_name):
        """Draw text with predefined style"""
        try:
            style = self.styles[style_name]
        except KeyError:
            print('drawStyledText: Invalid style name was passed!')
            return
        self.text(position, text, 
                 fill=style.color, 
                 font=style.font, 
                 anchor=style.anchor)
    
    def roundedLine(self, start, end, fill='black', width=2):
        """Draw line with rounded ends"""
        x1, y1 = start
        x2, y2 = end
        
        # Draw main line
        self.line([start, end], fill=fill, width=width)
        
        # Draw rounded caps
        radius = width // 2
        self.ellipse([(x1-radius, y1-radius), (x1+radius, y1+radius)], fill=fill)
        self.ellipse([(x2-radius, y2-radius), (x2+radius, y2+radius)], fill=fill)
    
    def roundedRect(self, pos, radius=10, fill=None, outline=None, width=1, 
                       skip_corners=None):
        """
        Draw rounded rectangle with configurable corner skipping.
        
        Args:
            pos: ((x1, y1), (x2, y2)) - rectangle coordinates
            radius: corner radius
            fill: fill color
            outline: outline color
            width: outline width
            skip_corners: list of corners to skip rounding ['lt', 'rt', 'lb', 'rb']
                         None for regular rounded rect, ['lt'] to skip top-left, etc.
        """
        x1, y1 = pos[0]
        x2, y2 = pos[1]
        
        if skip_corners is None:
            skip_corners = []
        
        # Draw two rectangles that form a cross shape
        self.rectangle([(x1+radius, y1), (x2-radius, y2)], fill=fill, outline=None)
        self.rectangle([(x1, y1+radius), (x2, y2-radius)], fill=fill, outline=None)
        
        # Define corner positions and their identifiers
        corner_info = [
            ('lt', x1, y1),                    # Top-left
            ('rt', x2-2*radius, y1),           # Top-right
            ('lb', x1, y2-2*radius),           # Bottom-left
            ('rb', x2-2*radius, y2-2*radius)   # Bottom-right
        ]
        
        # Draw corner circles (skip specified corners)
        for corner_id, x, y in corner_info:
            if corner_id not in skip_corners:
                self.ellipse([(x, y), (x+2*radius, y+2*radius)], fill=fill, outline=None)
            else:
                # Fill the corner area for skipped corners
                if corner_id == 'lt':
                    self.rectangle([(x1, y1), (x1+radius, y1+radius)], fill=fill, outline=None)
                elif corner_id == 'rt':
                    self.rectangle([(x2-radius, y1), (x2, y1+radius)], fill=fill, outline=None)
                elif corner_id == 'lb':
                    self.rectangle([(x1, y2-radius), (x1+radius, y2)], fill=fill, outline=None)
                elif corner_id == 'rb':
                    self.rectangle([(x2-radius, y2-radius), (x2, y2)], fill=fill, outline=None)
        
        # Draw the outline separately if needed
        if outline:
            # Draw corner arcs (skip specified corners)
            arc_info = [
                ('lt', (x1, y1), (x1+2*radius, y1+2*radius), 180, 270),
                ('rt', (x2-2*radius, y1), (x2, y1+2*radius), 270, 0),
                ('lb', (x1, y2-2*radius), (x1+2*radius, y2), 90, 180),
                ('rb', (x2-2*radius, y2-2*radius), (x2, y2), 0, 90)
            ]
            
            for corner_id, start_pos, end_pos, start_angle, end_angle in arc_info:
                if corner_id not in skip_corners:
                    self.arc([start_pos, end_pos], start_angle, end_angle, 
                            fill=outline, width=width)
            
            # Draw straight lines, adjusting for skipped corners
            top_start = x1 if 'lt' in skip_corners else x1 + radius
            top_end = x2 if 'rt' in skip_corners else x2 - radius
            bottom_start = x1 if 'lb' in skip_corners else x1 + radius
            bottom_end = x2 if 'rb' in skip_corners else x2 - radius
            left_start = y1 if 'lt' in skip_corners else y1 + radius
            left_end = y2 if 'lb' in skip_corners else y2 - radius
            right_start = y1 if 'rt' in skip_corners else y1 + radius
            right_end = y2 if 'rb' in skip_corners else y2 - radius
            
            self.line([(top_start, y1), (top_end, y1)], fill=outline, width=width)
            self.line([(bottom_start, y2), (bottom_end, y2)], fill=outline, width=width)
            self.line([(x1, left_start), (x1, left_end)], fill=outline, width=width)
            self.line([(x2, right_start), (x2, right_end)], fill=outline, width=width)
    
    def insertImage(self, pos, img_path, size=None, anchor="lt", base_dir=BASE_DIR):
        """Insert image with anchor positioning"""
        if not os.path.isabs(img_path):
            img_path = os.path.join(base_dir, 'resources', img_path)
        
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
            
            # Handle paste with transparency
            if img.mode == 'RGBA' or 'transparency' in img.info:
                self._image.paste(img, (x, y), img)
            else:
                self._image.paste(img, (x, y))
        except FileNotFoundError:
            print(f'Image not found: {img_path}')
    
    def getTextSize(self, text, style_name):
        """Get text width and height"""
        font = self.styles[style_name].font
        bbox = font.getbbox(text)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        return width, height
