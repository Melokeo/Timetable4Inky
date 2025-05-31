import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw, ImageTk
import threading
import time
from typing import Any, Callable, Optional, Tuple, Union

class DebugDraw(ImageDraw.ImageDraw):
    """
    A debug version of PIL.ImageDraw that shows real-time drawing operations
    and allows stepping through each drawing command.
    """
    
    def __init__(self, im: Image.Image, mode: Optional[str] = None, auto_step: bool = False):
        super().__init__(im, mode)
        self.pil_image = im  # Keep reference to the actual PIL Image
        self.auto_step = auto_step
        self.step_delay = 1.0
        self.debug_window = None
        self.canvas = None
        self.photo = None
        self.root = None
        self.step_event = threading.Event()
        self.continue_event = threading.Event()
        self.operation_count = 0
        self.window_closed = False
        
        # Initialize the debug window in a separate thread
        self._init_debug_window()
    
    def _init_debug_window(self):
        """Initialize the debug window in the main thread"""
        def create_window():
            self.root = tk.Tk()
            self.root.title("Debug ImageDraw - Real-time Visualization")
            self.root.geometry("800x700")
            
            # Create main frame
            main_frame = ttk.Frame(self.root)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Canvas for image display
            self.canvas = tk.Canvas(main_frame, bg='white', relief=tk.SUNKEN, borderwidth=2)
            self.canvas.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            
            # Control frame
            control_frame = ttk.Frame(main_frame)
            control_frame.pack(fill=tk.X)
            
            # Buttons
            ttk.Button(control_frame, text="Step", command=self._step).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(control_frame, text="Continue", command=self._continue).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(control_frame, text="Auto Step", command=self._toggle_auto_step).pack(side=tk.LEFT, padx=(0, 5))
            
            # Status label
            self.status_label = ttk.Label(control_frame, text="Operations: 0")
            self.status_label.pack(side=tk.RIGHT)
            
            # Auto-step control
            auto_frame = ttk.Frame(main_frame)
            auto_frame.pack(fill=tk.X, pady=(5, 0))
            
            ttk.Label(auto_frame, text="Auto-step delay (s):").pack(side=tk.LEFT)
            self.delay_var = tk.DoubleVar(value=self.step_delay)
            delay_scale = ttk.Scale(auto_frame, from_=0.1, to=3.0, variable=self.delay_var, 
                                  orient=tk.HORIZONTAL, length=200)
            delay_scale.pack(side=tk.LEFT, padx=(5, 0))
            delay_scale.bind("<Motion>", lambda e: setattr(self, 'step_delay', self.delay_var.get()))
            
            # Initial image display
            self._update_display()
            
            # Handle window closing
            self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
            
            # Start the GUI loop
            self.root.mainloop()
        
        # Run the window creation in a separate thread
        self.gui_thread = threading.Thread(target=create_window, daemon=True)
        self.gui_thread.start()
        
        # Wait a bit for the window to initialize
        time.sleep(0.5)
    
    def _update_display(self):
        """Update the image display in the debug window"""
        if self.window_closed or not self.root or not self.canvas:
            return
            
        try:
            # Use the PIL Image reference we saved
            display_image = self.pil_image.copy()
            
            # Scale image to fit canvas while maintaining aspect ratio
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            if canvas_width > 1 and canvas_height > 1:  # Canvas is initialized
                img_width, img_height = display_image.size
                scale = min(canvas_width / img_width, canvas_height / img_height)
                
                if scale < 1:
                    new_width = int(img_width * scale)
                    new_height = int(img_height * scale)
                    display_image = display_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            self.photo = ImageTk.PhotoImage(display_image)
            self.canvas.delete("all")
            
            # Center the image in the canvas
            if canvas_width > 1 and canvas_height > 1:
                self.canvas.create_image(canvas_width//2, canvas_height//2, image=self.photo)
            else:
                # Fallback for initial display
                self.canvas.create_image(200, 150, image=self.photo)
            
            # Update status
            if hasattr(self, 'status_label'):
                self.status_label.config(text=f"Operations: {self.operation_count}")
            
        except Exception as e:
            if not self.window_closed:
                print(f"Display update error: {e}")
    
    def _step(self):
        """Signal that user wants to step to next operation"""
        self.step_event.set()
    
    def _continue(self):
        """Signal that user wants to continue without stepping"""
        self.continue_event.set()
    
    def _toggle_auto_step(self):
        """Toggle auto-stepping mode"""
        self.auto_step = not self.auto_step
        if self.auto_step:
            self.continue_event.set()
    
    def _on_closing(self):
        """Handle window closing"""
        self.window_closed = True
        self.continue_event.set()
        self.step_event.set()
        if self.root:
            self.root.quit()  # Use quit() instead of destroy() for cleaner shutdown
            self.root.destroy()
            self.root = None
    
    def _wait_for_step(self, operation_name: str):
        """Wait for user to step or continue, update display"""
        if self.window_closed:
            return
            
        self.operation_count += 1
        
        # Update display
        if self.root and not self.window_closed:
            self.root.after(0, self._update_display)
        
        # If window is closed, don't wait
        if self.window_closed:
            return
        
        # Wait for step or continue
        if not self.continue_event.is_set():
            if self.auto_step:
                for _ in range(int(self.step_delay * 10)):  # Check window status while waiting
                    if self.window_closed:
                        return
                    time.sleep(0.1)
            else:
                print(f"Waiting for step after {operation_name} operation...")
                while not self.step_event.is_set() and not self.continue_event.is_set() and not self.window_closed:
                    self.step_event.wait(timeout=0.1)  # Use timeout to check window status
                if not self.window_closed:
                    self.step_event.clear()
    
    # Override all drawing methods to add debug functionality
    def arc(self, xy, start, end, fill=None, width=0):
        result = super().arc(xy, start, end, fill, width)
        self._wait_for_step("arc")
        return result
    
    def bitmap(self, xy, bitmap, fill=None):
        result = super().bitmap(xy, bitmap, fill)
        self._wait_for_step("bitmap")
        return result
    
    def chord(self, xy, start, end, fill=None, outline=None, width=1):
        result = super().chord(xy, start, end, fill, outline, width)
        self._wait_for_step("chord")
        return result
    
    def ellipse(self, xy, fill=None, outline=None, width=1):
        result = super().ellipse(xy, fill, outline, width)
        self._wait_for_step("ellipse")
        return result
    
    def line(self, xy, fill=None, width=0, joint=None):
        result = super().line(xy, fill, width, joint)
        self._wait_for_step("line")
        return result
    
    def pieslice(self, xy, start, end, fill=None, outline=None, width=1):
        result = super().pieslice(xy, start, end, fill, outline, width)
        self._wait_for_step("pieslice")
        return result
    
    def point(self, xy, fill=None):
        result = super().point(xy, fill)
        self._wait_for_step("point")
        return result
    
    def polygon(self, xy, fill=None, outline=None, width=1):
        result = super().polygon(xy, fill, outline, width)
        self._wait_for_step("polygon")
        return result
    
    def rectangle(self, xy, fill=None, outline=None, width=1):
        result = super().rectangle(xy, fill, outline, width)
        self._wait_for_step("rectangle")
        return result
    
    def rounded_rectangle(self, xy, radius=0, fill=None, outline=None, width=1):
        result = super().rounded_rectangle(xy, radius, fill, outline, width)
        self._wait_for_step("rounded_rectangle")
        return result
    
    def text(self, xy, text, fill=None, font=None, anchor=None, spacing=4, 
             align="left", direction=None, features=None, language=None, 
             stroke_width=0, stroke_fill=None, embedded_color=False):
        result = super().text(xy, text, fill, font, anchor, spacing, align, 
                            direction, features, language, stroke_width, 
                            stroke_fill, embedded_color)
        self._wait_for_step("text")
        return result
    
    def multiline_text(self, xy, text, fill=None, font=None, anchor=None,
                      spacing=4, align="left", direction=None, features=None,
                      language=None, stroke_width=0, stroke_fill=None,
                      embedded_color=False):
        result = super().multiline_text(xy, text, fill, font, anchor, spacing,
                                      align, direction, features, language,
                                      stroke_width, stroke_fill, embedded_color)
        self._wait_for_step("multiline_text")
        return result
