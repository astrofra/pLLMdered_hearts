import sys

import pygame

# Toggle for Windows "always on top" behavior.
ENABLE_ALWAYS_ON_TOP = True
ALWAYS_ON_TOP_REFRESH_MS = 100

# Commodore 64 style display settings
C64_COLS = 78
C64_ROWS = 30
C64_STATUS_ROWS = 1  # Reserve top row for status/title bar.
C64_CELL_SIZE_H = 8
C64_CELL_SIZE_V = 10
LOGICAL_WIDTH = C64_COLS * C64_CELL_SIZE_H
LOGICAL_HEIGHT = C64_ROWS * C64_CELL_SIZE_V

C64_BLUE = (64, 49, 141)
C64_LIGHT_BLUE = (64 * 3 // 2, 49 * 3 // 2, 141 * 3 // 2)
C64_LIGHT_GRAY = (202, 202, 202)
C64_WHITE = (255, 255, 255)
C64_BLACK = (0, 0, 0)

# Distinct border styling so it stays visible against the screen background.
C64_BORDER_COLOR = C64_BLUE
BORDER_THICKNESS = 64

class C64Renderer:
    def __init__(
        self,
        font_path=None,
        scale=None,
        fps=60,
        fullscreen=False,
        display_index=None,
        always_on_top=None,
        output_scale=1,
        fit_to_display=False,
    ):
        if pygame is None:
            raise ImportError("pygame is required for the C64 renderer. Install pygame to enable it.")

        pygame.init()
        pygame.display.set_caption("Plundered Hearts - C64 view")

        self.fullscreen = bool(fullscreen)
        self.display_index = self._normalize_display_index(display_index)
        if always_on_top is None:
            self.always_on_top = ENABLE_ALWAYS_ON_TOP
        else:
            self.always_on_top = bool(always_on_top)
        self.display_size = self._get_display_size(self.display_index)
        self.fps = fps
        try:
            self.output_scale = max(1, int(output_scale))
        except (TypeError, ValueError):
            self.output_scale = 1
        self.fit_to_display = bool(fit_to_display)
        self.scale = self._determine_scale(scale, self.display_size)
        self.total_width = LOGICAL_WIDTH * self.scale * self.output_scale + BORDER_THICKNESS * 2
        self.total_height = LOGICAL_HEIGHT * self.scale * self.output_scale + BORDER_THICKNESS * 2
        if self.fullscreen and self.display_size:
            self.window_width, self.window_height = self.display_size
            if self.fit_to_display:
                self.render_offset_x = 0
                self.render_offset_y = 0
            else:
                self.render_offset_x = max(0, (self.window_width - self.total_width) // 2)
                self.render_offset_y = max(0, (self.window_height - self.total_height) // 2)
            window_flags = pygame.FULLSCREEN
        else:
            self.window_width = self.total_width
            self.window_height = self.total_height
            self.render_offset_x = 0
            self.render_offset_y = 0
            window_flags = 0
        self.window = self._create_window(window_flags)
        if self.always_on_top:
            self._set_always_on_top()
            self._next_topmost_check_ms = pygame.time.get_ticks() + ALWAYS_ON_TOP_REFRESH_MS
        else:
            self._next_topmost_check_ms = None
        self.clock = pygame.time.Clock()

        self.logical_surface = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT), pygame.SRCALPHA).convert_alpha()

        self.cursor_x = 0
        self.cursor_y = 0  # Content row index; status bar is separate.
        self.status_text = ""
        self.status_bar_bg = C64_LIGHT_BLUE
        self.content_rows = C64_ROWS - C64_STATUS_ROWS
        self.buffer = [[" "] * C64_COLS for _ in range(self.content_rows)]
        self.glyphs = self._load_font(font_path)
        self.default_glyph = self._render_pattern(self._fallback_pattern("?"))

    def _determine_scale(self, forced_scale, display_size=None):
        if forced_scale:
            return max(1, int(forced_scale))
        if display_size:
            usable_w = max(1, display_size[0] - BORDER_THICKNESS * 2)
            usable_h = max(1, display_size[1] - BORDER_THICKNESS * 2)
            max_w = max(1, usable_w // LOGICAL_WIDTH)
            max_h = max(1, usable_h // LOGICAL_HEIGHT)
            return max(1, min(max_w, max_h))
        try:
            info = pygame.display.Info()
            usable_w = max(1, info.current_w - BORDER_THICKNESS * 2)
            usable_h = max(1, info.current_h - BORDER_THICKNESS * 2)
            max_w = max(1, usable_w // LOGICAL_WIDTH)
            max_h = max(1, usable_h // LOGICAL_HEIGHT)
            return max(1, min(max_w, max_h))
        except pygame.error:
            return 2

    def _normalize_display_index(self, display_index):
        if display_index is None:
            return None
        try:
            index = int(display_index)
        except (TypeError, ValueError):
            return None
        if index < 0:
            return None
        try:
            num_displays = pygame.display.get_num_displays()
        except Exception:
            return index
        if index >= num_displays:
            return None
        return index

    def _get_display_size(self, display_index):
        if display_index is not None:
            try:
                sizes = pygame.display.get_desktop_sizes()
                if sizes and 0 <= display_index < len(sizes):
                    return sizes[display_index]
            except Exception:
                pass
        try:
            info = pygame.display.Info()
            if info.current_w and info.current_h:
                return (info.current_w, info.current_h)
        except pygame.error:
            return None
        return None

    def _create_window(self, window_flags):
        try:
            if self.display_index is not None:
                return pygame.display.set_mode(
                    (self.window_width, self.window_height),
                    window_flags,
                    display=self.display_index,
                )
        except TypeError:
            pass
        return pygame.display.set_mode((self.window_width, self.window_height), window_flags)

    def _set_always_on_top(self):
        if not sys.platform.startswith("win"):
            return
        try:
            import ctypes

            wm_info = pygame.display.get_wm_info()
            hwnd = wm_info.get("window")
            if not hwnd:
                return
            HWND_TOPMOST = -1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_SHOWWINDOW = 0x0040
            ctypes.windll.user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
            )
        except Exception:
            pass

    def _refresh_always_on_top(self):
        if not self.always_on_top or self._next_topmost_check_ms is None:
            return
        now_ms = pygame.time.get_ticks()
        if now_ms < self._next_topmost_check_ms:
            return
        self._set_always_on_top()
        self._next_topmost_check_ms = now_ms + ALWAYS_ON_TOP_REFRESH_MS

    def _load_font(self, font_path):
        # Always use the built-in placeholder font to avoid external dependencies.
        return self._build_placeholder_font()

    def _fallback_pattern(self, char):
        patterns = {
            " ": ["     "] * 7,
            "?": [
                " XXX ",
                "X   X",
                "    X",
                "  XX ",
                "  X  ",
                "     ",
                "  X  ",
            ],
            "!": [
                "  X  ",
                "  X  ",
                "  X  ",
                "  X  ",
                "  X  ",
                "     ",
                "  X  ",
            ],
            ".": [
                "     ",
                "     ",
                "     ",
                "     ",
                "     ",
                " XXX ",
                " XXX ",
            ],
            ",": [
                "     ",
                "     ",
                "     ",
                "     ",
                " XXX ",
                "   X ",
                "  X  ",
            ],
            ":": [
                "     ",
                "  X  ",
                "     ",
                "     ",
                "  X  ",
                "     ",
                "     ",
            ],
            ";": [
                "     ",
                "  X  ",
                "     ",
                "     ",
                "  X  ",
                "  X  ",
                " X   ",
            ],
            "-": [
                "     ",
                "     ",
                "XXXXX",
                "     ",
                "     ",
                "     ",
                "     ",
            ],
            "_": [
                "     ",
                "     ",
                "     ",
                "     ",
                "     ",
                "     ",
                "XXXXX",
            ],
            "'": [
                "  X  ",
                "  X  ",
                "  X  ",
                "     ",
                "     ",
                "     ",
                "     ",
            ],
            "’": [
                "  X  ",
                "  X  ",
                "  X  ",
                "     ",
                "     ",
                "     ",
                "     ",
            ],
            '"': [
                " X X ",
                " X X ",
                " X X ",
                "     ",
                "     ",
                "     ",
                "     ",
            ],
            "(": [
                "   X ",
                "  X  ",
                " X   ",
                " X   ",
                " X   ",
                "  X  ",
                "   X ",
            ],
            ")": [
                " X   ",
                "  X  ",
                "   X ",
                "   X ",
                "   X ",
                "  X  ",
                " X   ",
            ],
            "/": [
                "    X",
                "   X ",
                "  X  ",
                " X   ",
                "X    ",
                "     ",
                "     ",
            ],
            "\\": [
                "X    ",
                " X   ",
                "  X  ",
                "   X ",
                "    X",
                "     ",
                "     ",
            ],
            "+": [
                "     ",
                "  X  ",
                "  X  ",
                "XXXXX",
                "  X  ",
                "  X  ",
                "     ",
            ],
            "*": [
                "X   X",
                " X X ",
                "  X  ",
                "XXXXX",
                "  X  ",
                " X X ",
                "X   X",
            ],
            "<": [
                "    X",
                "   X ",
                "  X  ",
                " X   ",
                "  X  ",
                "   X ",
                "    X",
            ],
            ">": [
                "X    ",
                " X   ",
                "  X  ",
                "   X ",
                "  X  ",
                " X   ",
                "X    ",
            ],
            "[": [
                " XXX ",
                " X   ",
                " X   ",
                " X   ",
                " X   ",
                " X   ",
                " XXX ",
            ],
            "]": [
                " XXX ",
                "   X ",
                "   X ",
                "   X ",
                "   X ",
                "   X ",
                " XXX ",
            ],
            "(": [
                "   X ",
                "  X  ",
                " X   ",
                " X   ",
                " X   ",
                "  X  ",
                "   X ",
            ],
            ")": [
                " X   ",
                "  X  ",
                "   X ",
                "   X ",
                "   X ",
                "  X  ",
                " X   ",
            ],
            "{": [
                "   XX",
                "  X  ",
                "  X  ",
                " XX  ",
                "  X  ",
                "  X  ",
                "   XX",
            ],
            "}": [
                "XX   ",
                "  X  ",
                "  X  ",
                "  XX ",
                "  X  ",
                "  X  ",
                "XX   ",
            ],
        }
        if char in patterns:
            return patterns[char]
        return patterns["?"]

    def _build_placeholder_font(self):
        letters = {
            "A": [
                " XXX ",
                "X   X",
                "X   X",
                "XXXXX",
                "X   X",
                "X   X",
                "X   X",
            ],
            "B": [
                "XXXX ",
                "X   X",
                "X   X",
                "XXXX ",
                "X   X",
                "X   X",
                "XXXX ",
            ],
            "C": [
                " XXX ",
                "X   X",
                "X    ",
                "X    ",
                "X    ",
                "X   X",
                " XXX ",
            ],
            "D": [
                "XXXX ",
                "X   X",
                "X   X",
                "X   X",
                "X   X",
                "X   X",
                "XXXX ",
            ],
            "E": [
                "XXXXX",
                "X    ",
                "X    ",
                "XXXX ",
                "X    ",
                "X    ",
                "XXXXX",
            ],
            "F": [
                "XXXXX",
                "X    ",
                "X    ",
                "XXXX ",
                "X    ",
                "X    ",
                "X    ",
            ],
            "G": [
                " XXX ",
                "X   X",
                "X    ",
                "X XXX",
                "X   X",
                "X   X",
                " XXX ",
            ],
            "H": [
                "X   X",
                "X   X",
                "X   X",
                "XXXXX",
                "X   X",
                "X   X",
                "X   X",
            ],
            "I": [
                " XXX ",
                "  X  ",
                "  X  ",
                "  X  ",
                "  X  ",
                "  X  ",
                " XXX ",
            ],
            "J": [
                "  XXX",
                "   X ",
                "   X ",
                "   X ",
                "   X ",
                "X  X ",
                " XX  ",
            ],
            "K": [
                "X   X",
                "X  X ",
                "X X  ",
                "XX   ",
                "X X  ",
                "X  X ",
                "X   X",
            ],
            "L": [
                "X    ",
                "X    ",
                "X    ",
                "X    ",
                "X    ",
                "X    ",
                "XXXXX",
            ],
            "M": [
                "X   X",
                "XX XX",
                "X X X",
                "X   X",
                "X   X",
                "X   X",
                "X   X",
            ],
            "N": [
                "X   X",
                "XX  X",
                "X X X",
                "X  XX",
                "X   X",
                "X   X",
                "X   X",
            ],
            "O": [
                " XXX ",
                "X   X",
                "X   X",
                "X   X",
                "X   X",
                "X   X",
                " XXX ",
            ],
            "P": [
                "XXXX ",
                "X   X",
                "X   X",
                "XXXX ",
                "X    ",
                "X    ",
                "X    ",
            ],
            "Q": [
                " XXX ",
                "X   X",
                "X   X",
                "X   X",
                "X X X",
                "X  X ",
                " XX X",
            ],
            "R": [
                "XXXX ",
                "X   X",
                "X   X",
                "XXXX ",
                "X X  ",
                "X  X ",
                "X   X",
            ],
            "S": [
                " XXXX",
                "X    ",
                "X    ",
                " XXX ",
                "    X",
                "    X",
                "XXXX ",
            ],
            "T": [
                "XXXXX",
                "  X  ",
                "  X  ",
                "  X  ",
                "  X  ",
                "  X  ",
                "  X  ",
            ],
            "U": [
                "X   X",
                "X   X",
                "X   X",
                "X   X",
                "X   X",
                "X   X",
                " XXX ",
            ],
            "V": [
                "X   X",
                "X   X",
                "X   X",
                "X   X",
                "X   X",
                " X X ",
                "  X  ",
            ],
            "W": [
                "X   X",
                "X   X",
                "X   X",
                "X X X",
                "X X X",
                "XX XX",
                "X   X",
            ],
            "X": [
                "X   X",
                "X   X",
                " X X ",
                "  X  ",
                " X X ",
                "X   X",
                "X   X",
            ],
            "Y": [
                "X   X",
                "X   X",
                " X X ",
                "  X  ",
                "  X  ",
                "  X  ",
                "  X  ",
            ],
            "Z": [
                "XXXXX",
                "    X",
                "   X ",
                "  X  ",
                " X   ",
                "X    ",
                "XXXXX",
            ],
            "0": [
                " XXX ",
                "X   X",
                "X  XX",
                "X X X",
                "XX  X",
                "X   X",
                " XXX ",
            ],
            "1": [
                "  X  ",
                " XX  ",
                "  X  ",
                "  X  ",
                "  X  ",
                "  X  ",
                " XXX ",
            ],
            "2": [
                " XXX ",
                "X   X",
                "    X",
                "   X ",
                "  X  ",
                " X   ",
                "XXXXX",
            ],
            "3": [
                " XXX ",
                "X   X",
                "    X",
                "  XX ",
                "    X",
                "X   X",
                " XXX ",
            ],
            "4": [
                "   X ",
                "  XX ",
                " X X ",
                "X  X ",
                "XXXXX",
                "   X ",
                "   X ",
            ],
            "5": [
                "XXXXX",
                "X    ",
                "X    ",
                "XXXX ",
                "    X",
                "    X",
                "XXXX ",
            ],
            "6": [
                " XXX ",
                "X    ",
                "X    ",
                "XXXX ",
                "X   X",
                "X   X",
                " XXX ",
            ],
            "7": [
                "XXXXX",
                "    X",
                "   X ",
                "  X  ",
                "  X  ",
                "  X  ",
                "  X  ",
            ],
            "8": [
                " XXX ",
                "X   X",
                "X   X",
                " XXX ",
                "X   X",
                "X   X",
                " XXX ",
            ],
            "9": [
                " XXX ",
                "X   X",
                "X   X",
                " XXXX",
                "    X",
                "    X",
                " XXX ",
            ],
        }

        glyphs = {}
        for code in range(256):
            char = chr(code)
            upper_char = char.upper()
            pattern = letters.get(upper_char) or self._fallback_pattern(char) or self._fallback_pattern("?")
            glyphs[code] = self._render_pattern(pattern)
        glyphs[ord("’")] = glyphs.get(ord("'"), self._render_pattern(self._fallback_pattern("'")))
        return glyphs

    def _render_pattern(self, pattern_lines):
        surface = pygame.Surface((C64_CELL_SIZE_H, C64_CELL_SIZE_V), pygame.SRCALPHA).convert_alpha()
        surface.fill((*C64_BLUE, 0))
        top_margin = 1
        left_margin = 1
        for row_idx, line in enumerate(pattern_lines):
            for col_idx, char in enumerate(line):
                if char != " ":
                    surface.set_at((left_margin + col_idx, top_margin + row_idx), C64_LIGHT_GRAY)
        return surface

    def clear(self):
        self.buffer = [[" "] * C64_COLS for _ in range(self.content_rows)]
        self.cursor_x = 0
        self.cursor_y = 0

    def _newline(self):
        self.cursor_x = 0
        self.cursor_y += 1
        if self.cursor_y >= self.content_rows:
            self.buffer.pop(0)
            self.buffer.append([" "] * C64_COLS)
            self.cursor_y = self.content_rows - 1

    def _glyph_for_char(self, char):
        code = ord(char) if char else ord("?")
        return self.glyphs.get(code, self.default_glyph)

    def process_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)

    def write(self, text):
        for ch in text:
            if ch == "\n":
                self._newline()
                continue
            if ch == "\f":
                self.clear()
                continue
            sanitized = ch
            if not sanitized.isprintable() or sanitized == "\r":
                sanitized = " "
            sanitized = sanitized.upper()
            self.buffer[self.cursor_y][self.cursor_x] = sanitized
            self.cursor_x += 1
            if self.cursor_x >= C64_COLS:
                self._newline()

    def set_status_bar(self, text):
        """Update the persistent status/title bar shown on the top row."""
        self.status_text = (text or "").strip().upper()

    def set_status_bar_color(self, color):
        if color:
            self.status_bar_bg = color

    def _draw_status_bar(self):
        if not self.status_text:
            return
        pygame.draw.rect(
            self.logical_surface,
            self.status_bar_bg,
            pygame.Rect(0, 0, LOGICAL_WIDTH, C64_CELL_SIZE_V),
        )
        truncated = self.status_text[:C64_COLS].ljust(C64_COLS)
        for x, ch in enumerate(truncated):
            glyph = self._glyph_for_char(ch)
            self.logical_surface.blit(glyph, (x * C64_CELL_SIZE_H, 0))

    def _draw_buffer(self):
        self.logical_surface.fill(C64_BLUE)
        self._draw_status_bar()
        for y, row in enumerate(self.buffer):
            for x, ch in enumerate(row):
                glyph = self._glyph_for_char(ch)
                self.logical_surface.blit(
                    glyph, (x * C64_CELL_SIZE_H, (y + C64_STATUS_ROWS) * C64_CELL_SIZE_V)
                )

    def render_frame(self, show_cursor=False):
        self._refresh_always_on_top()
        self._draw_buffer()
        frame = self.logical_surface.copy()
        if show_cursor:
            cursor_color = C64_LIGHT_BLUE
            cursor_rect = (
                self.cursor_x * C64_CELL_SIZE_H,
                (self.cursor_y + C64_STATUS_ROWS) * C64_CELL_SIZE_V,
                C64_CELL_SIZE_H,
                C64_CELL_SIZE_V,
            )
            pygame.draw.rect(frame, cursor_color, cursor_rect)
        scaled_w = LOGICAL_WIDTH * self.scale * self.output_scale
        scaled_h = LOGICAL_HEIGHT * self.scale * self.output_scale
        scaled = pygame.transform.smoothscale(frame, (scaled_w, scaled_h)).convert_alpha()
        if self.fit_to_display:
            target_w = max(1, self.window_width - BORDER_THICKNESS * 2)
            target_h = max(1, self.window_height - BORDER_THICKNESS * 2)
            if scaled_w != target_w or scaled_h != target_h:
                scaled = pygame.transform.smoothscale(scaled, (target_w, target_h)).convert_alpha()
        self.window.fill(C64_BORDER_COLOR)
        dest_x = self.render_offset_x + BORDER_THICKNESS
        dest_y = self.render_offset_y + BORDER_THICKNESS
        self.window.blit(scaled, (dest_x, dest_y))
        if BORDER_THICKNESS > 0:
            border_rect = pygame.Rect(
                self.render_offset_x,
                self.render_offset_y,
                self.total_width,
                self.total_height,
            )
            pygame.draw.rect(self.window, C64_BORDER_COLOR, border_rect, BORDER_THICKNESS)
        pygame.display.flip()
        self.clock.tick(self.fps)
