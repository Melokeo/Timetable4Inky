# Test mode detection
try:
    from inky.auto import auto as inky_auto # type: ignore[import]
    INKY_AVAILABLE = True
    true_display = inky_auto()
except ImportError:
    INKY_AVAILABLE = False

class MockDisplay:
    def __init__(self):
        self.width, self.height = 800, 480
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.RED = (196, 85, 49)    #(255, 0, 0)
        self.YELLOW = (255, 255, 0)
        self.GREEN = (0, 255, 0)
        self.BLUE = (0, 0, 255)
    def set_image(self, img): self.img = img
    def show(self): self.img.show()
display = MockDisplay()

def mixColors(**weights):
    """Mix display colors with given weights (must sum to 1)
    Usage: mixColors(w=0.4, k=0.6) -> gray color
    """
    color_map = {
        'w': display.WHITE,   'k': display.BLACK,
        'r': display.RED,     'y': display.YELLOW, 
        'g': display.GREEN,   'b': display.BLUE
    }
    
    # Normalize weights to sum to 1
    total = sum(weights.values())
    weights = {k: v/total for k, v in weights.items()}
    
    # Mix RGB values
    mixed = [0, 0, 0]
    for key, weight in weights.items():
        color = color_map[key]
        for i in range(3):
            mixed[i] += color[i] * weight
    
    return tuple(int(c) for c in mixed)