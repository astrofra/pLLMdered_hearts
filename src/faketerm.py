import json
import os
import random
import re
import sys
import time

import ollama
import pexpect

try:
    import pygame
except ImportError:
    pygame = None

# os.environ["OLLAMA_NO_CUDA"] = "1"

## FIXME "[Press RETURN or ENTER to continue.]"

ENABLE_LLM = False
ENABLE_READING_PAUSE = False
ENABLE_C64_RENDERER = True
ENABLE_KEYCLICK_BEEP = True

# Commodore 64 style display settings
C64_COLS = 80
C64_ROWS = 50
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

C64_FONT_PATH = None  # Using built-in fallback font; no external sprite sheet required.
KEY_AUDIO_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "audio")

def llm_response_is_valid(llm_commentary):
    if llm_commentary is None:
        return False
    
    return True

def estimate_reading_time(text, wps=4.0, min_delay=0.3, max_delay=5.0):
    """Estimate a human-readable delay (in seconds) based on word count."""
    word_count = len(text.strip().split())
    delay = word_count / wps
    return max(min_delay, min(delay, max_delay))  # Clamp delay

def extract_and_parse_json(text):
    """
    Extracts the first JSON object found inside triple backticks or code-like blocks from the input text,
    and returns it as a Python dictionary.
    """

    stop_strings = ["```json", "```", "\n"]
    for _stop in stop_strings:
        text = text.replace(_stop, '')

    # Try to find JSON inside ```json ... ``` blocks
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not match:
        # If no fenced block, try raw { ... } block (useful for degraded format)
        match = re.search(r"(\{[\s\S]*?\})", text)
    
    if match:
        try:
            json_str = match.group(1)
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print("JSON parsing failed:", e)
            return None
    else:
        print("No JSON block found.")
        return None

# Match ANSI escape sequences like ESC[31m or ESC[2J
ansi_escape = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
# Match cursor position commands like [24d (often without ESC, incomplete sequences)
cursor_directives = re.compile(r'\[\d{1,3}d')
# Match charset switch like ESC(A or ESC(B
charset_switch = re.compile(r'\x1b\([A-B]')

# Escape sequences that usually correspond to "clear screen", "move cursor", etc.
line_breaking_escapes = re.compile(r'\x1b\[[0-9;]*([HJfABCD])')

def clean_output(text):
    # Replace certain ANSI codes with newlines (those likely to imply line moves)
    def replace_with_newline(match):
        command = match.group(1)
        if command in ['H', 'f', 'A', 'B', 'C', 'D']:
            return '\n'
        return ''

    text = line_breaking_escapes.sub(replace_with_newline, text)
    # Remove charset switch sequences
    text = charset_switch.sub('', text)
    # Remove cursor directives like [24d
    text = cursor_directives.sub('', text)
    # Remove remaining ANSI escape codes
    text = ansi_escape.sub('', text)

    # Remove lines containing only a number (like score or parser noise)
    lines = text.strip().splitlines()
    lines = [line for line in lines if not line.strip().isdigit()]
    # Remove repeated empty lines
    clean_lines = []
    for i, line in enumerate(lines):
        if line.strip() == '' and (i == 0 or lines[i - 1].strip() == ''):
            continue
        clean_lines.append(line)
    return '\n'.join(clean_lines).strip()

_KEY_SOUNDS = []
_MIXER_READY = False


def _ensure_key_sounds_loaded():
    """Lazy-load key click sounds from assets/audio/*.ogg."""
    global _KEY_SOUNDS, _MIXER_READY
    if _MIXER_READY:
        return
    if not pygame:
        return
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=256)
        if not os.path.isdir(KEY_AUDIO_DIR):
            return
        oggs = [f for f in os.listdir(KEY_AUDIO_DIR) if f.lower().endswith(".ogg")]
        oggs.sort()
        for fname in oggs:
            try:
                sound = pygame.mixer.Sound(os.path.join(KEY_AUDIO_DIR, fname))
                _KEY_SOUNDS.append(sound)
            except Exception:
                continue
        _MIXER_READY = True
    except Exception:
        _MIXER_READY = False

class C64Renderer:
    def __init__(
        self,
        font_path=None,
        scale=None,
        fps=60,
        enable_scanlines=False,
        enable_flicker=False,
        enable_blur=False,
    ):
        if pygame is None:
            raise ImportError("pygame is required for the C64 renderer. Install pygame to enable it.")

        pygame.init()
        pygame.display.set_caption("Plundered Hearts - C64 view")

        self.fps = fps
        self.enable_scanlines = enable_scanlines
        self.enable_flicker = enable_flicker
        self.enable_blur = enable_blur
        self.scale = self._determine_scale(scale)
        self.window_width = LOGICAL_WIDTH * self.scale + BORDER_THICKNESS * 2
        self.window_height = LOGICAL_HEIGHT * self.scale + BORDER_THICKNESS * 2
        self.window = pygame.display.set_mode((self.window_width, self.window_height))
        self.clock = pygame.time.Clock()

        # Use per-pixel alpha so scanline overlay blends correctly; fill with opaque blue each frame.
        self.logical_surface = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT), pygame.SRCALPHA).convert_alpha()
        self.scanline_overlay = self._build_scanline_overlay()

        self.cursor_x = 0
        self.cursor_y = 0
        self.buffer = [[" "] * C64_COLS for _ in range(C64_ROWS)]
        self.glyphs = self._load_font(font_path)
        self.default_glyph = self._render_pattern(self._fallback_pattern("?"))

    def _determine_scale(self, forced_scale):
        if forced_scale:
            return max(1, int(forced_scale))
        try:
            info = pygame.display.Info()
            usable_w = max(1, info.current_w - BORDER_THICKNESS * 2)
            usable_h = max(1, info.current_h - BORDER_THICKNESS * 2)
            max_w = max(1, usable_w // LOGICAL_WIDTH)
            max_h = max(1, usable_h // LOGICAL_HEIGHT)
            return max(1, min(max_w, max_h))
        except pygame.error:
            return 2

    def _build_scanline_overlay(self):
        overlay = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT), pygame.SRCALPHA)
        # Start with opaque white so BLEND_RGBA_MULT keeps base pixels as-is except where lines draw.
        overlay.fill((255, 255, 255, 255))
        for y in range(0, LOGICAL_HEIGHT, 2):
            pygame.draw.line(overlay, (*C64_BLACK, 64), (0, y), (LOGICAL_WIDTH, y))
        return overlay

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
            "'": [
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
        self.buffer = [[" "] * C64_COLS for _ in range(C64_ROWS)]
        self.cursor_x = 0
        self.cursor_y = 0

    def _newline(self):
        self.cursor_x = 0
        self.cursor_y += 1
        if self.cursor_y >= C64_ROWS:
            self.buffer.pop(0)
            self.buffer.append([" "] * C64_COLS)
            self.cursor_y = C64_ROWS - 1

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

    def _draw_buffer(self):
        self.logical_surface.fill(C64_BLUE)
        for y, row in enumerate(self.buffer):
            for x, ch in enumerate(row):
                glyph = self._glyph_for_char(ch)
                self.logical_surface.blit(glyph, (x * C64_CELL_SIZE_H, y * C64_CELL_SIZE_V))

    def render_frame(self):
        self._draw_buffer()
        frame = self.logical_surface.copy()
        if self.enable_scanlines:
            frame.blit(self.scanline_overlay, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        if self.enable_blur:
            downscaled = pygame.transform.scale(
                frame, (int(LOGICAL_WIDTH * 0.9), int(LOGICAL_HEIGHT * 0.9))
            )
            frame = pygame.transform.scale(downscaled, (LOGICAL_WIDTH, LOGICAL_HEIGHT))

        scaled = pygame.transform.scale(
            frame, (LOGICAL_WIDTH * self.scale, LOGICAL_HEIGHT * self.scale)
        ).convert_alpha()
        if self.enable_flicker:
            flicker = random.uniform(-0.02, 0.02)
            if flicker != 0:
                overlay = pygame.Surface(scaled.get_size(), pygame.SRCALPHA)
                if flicker > 0:
                    overlay.fill((*C64_WHITE, int(255 * flicker)))
                    scaled.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
                else:
                    overlay.fill((*C64_BLACK, int(255 * abs(flicker))))
                    scaled.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)

        self.window.fill(C64_BORDER_COLOR)
        self.window.blit(scaled, (BORDER_THICKNESS, BORDER_THICKNESS))
        if BORDER_THICKNESS > 0:
            pygame.draw.rect(self.window, C64_BORDER_COLOR, self.window.get_rect(), BORDER_THICKNESS)
        pygame.display.flip()
        self.clock.tick(self.fps)


def _play_key_beep(ch=" "):
    """Play a key click sound mapped from ASCII; fallback to terminal bell."""
    if not ENABLE_KEYCLICK_BEEP:
        return
    _ensure_key_sounds_loaded()
    if _KEY_SOUNDS:
        try:
            idx = ord(ch) % len(_KEY_SOUNDS)
            _KEY_SOUNDS[idx].play()
            return
        except Exception:
            pass
    # Fallback: terminal bell
    try:
        sys.stdout.write("\a")
        sys.stdout.flush()
    except Exception:
        pass


def type_to_renderer(renderer, text, base_delay=0.01, min_delay=0.005, max_delay=0.12, beep=True):
    """
    Simulate typing to the renderer: emit characters one by one with a delay
    proportional to ASCII distance from the previous character.
    """
    if not renderer:
        return
    prev = " "
    for ch in text:
        renderer.write(ch)
        renderer.render_frame()
        distance = abs(ord(ch) - ord(prev))
        delay = max(min_delay, min(max_delay, distance * base_delay))
        if beep:
            _play_key_beep(ch)
        time.sleep(delay)
        prev = ch

# official Amiga solution
plundered_hearts_commands = [
    "stand up", "inventory", "examine smelling salts", "read tag", "examine banknote",
    "examine coffer", "examine door", "open door", "z", "scream", "e", "examine falcon",
    "read missive", "falcon, yes", "examine davis", "examine ring", "examine falcon", "z", "z",
    "stand up", "look around", "look through window", "open curtain", "examine cupboard",
    "examine table", "examine bed", "z", "examine brooch", "open coffer", "take invitation",
    "read invitation", "n", "down", "n", "examine gate", "n", "take bottle", "take mirror",
    "examine bottle", "read label", "s", "s", "up", "open door", "enter", "take clothes",
    "remove dress", "wear breeches", "wear shirt", "z", "out", "s", "take coffer", "z",
    "throw coffer through window", "sit on ledge", "put all in reticule", "take ladder",
    "up", "up", "up", "up", "n", "n", "n", "examine winch", "read lever", "pull lever up",
    "s", "examine barrels", "tear dress", "put rag in water", "open hatch", "down",
    "throw rag over gate", "up", "s", "examine casks", "n", "n", "enter shack", "take dagger",
    "e", "s", "s", "look in cask", "enter cask", "take pork", "put all in reticule except dagger",
    "cut rope", "examine pork", "z", "z", "z", "leave cask", "examine skiff", "w", "n", "e",
    "pull slat", "z", "z", "falcon, yes", "z", "e", "n", "open window", "w", "examine portrait",
    "examine bookshelves", "examine globe", "take hat", "s", "w", "e", "examine lucy",
    "take garter", "w", "s", "ne", "climb vine", "remove clothes", "wear ball gown",
    "take invitation", "put garter in reticule", "n", "n", "take pistols", "s", "e", "e",
    "open door", "s", "n", "w", "down", "give invitation", "s", "dance", "dance", "dance",
    "dance", "w", "examine orchestra", "e", "dance", "examine lafond", "examine ring",
    "open door", "s", "n", "n", "e", "s", "e", "n", "n", "take treatise", "take hat",
    "press sinistra on globe", "n", "down", "e", "e", "take key and horn", "w", "s",
    "open door", "e", "w", "n", "w", "s", "squeeze bottle on pork", "throw pork at crocodile",
    "z", "z", "s", "w", "unlock door", "open door", "n", "give garter to papa", "z", "s",
    "e", "n", "n", "up", "s", "s", "n", "n", "s", "s", "s", "n", "n", "s", "up", "e",
    "knock on door", "open door", "n", "drink wine", "pour wine into green goblet",
    "squeeze bottle into green goblet", "pour wine into blue goblet", "z", "lafond, no",
    "drink wine", "take spice", "throw spice at lafond", "wave mirror at window", "s",
    "w", "down", "s", "z", "cookie, yes", "n", "e", "n", "take treatise", "take hat",
    "press sinistra", "n", "down", "s", "s", "take rapier", "kill crulley", "g",
    "close trapdoor", "pick lock", "wave smelling salts", "n", "n", "z", "up", "s",
    "s", "w", "up", "e", "s", "untie rope", "climb down rope", "take horn", "s", "s", "s",
    "look at nicholas", "push nicholas", "nicholas, yes", "take pistol", "load pistol",
    "fire pistol at crulley"
]

# wikipedia article about Plundered Hearts
plundered_hearts_wiki = """Plundered Hearts is an interactive fiction video game created by Amy Briggs and published by Infocom in 1987. Infocom's only game in the romance genre, it was released simultaneously for the Apple II, Commodore 64, Atari 8-bit computers, Atari ST, Amiga, Mac, and MS-DOS. It is Infocom's 28th game.
Plundered Hearts casts the player in a well-defined role. The lead character is a young woman in the late 17th century who has received a letter. Jean Lafond, the governor of the small West Indies island of St. Sinistra, says that the player's father has contracted a wasting tropical disease. Lafond suggests that his recovery would be greatly helped by the loving presence of his daughter, and sends his ship (the Lafond Deux) to transport her.
As the game begins, the ship is attacked by pirates and the player's character is kidnapped. Eventually, the player's character finds that two men are striving for her affections: dashing pirate Nicholas Jamison, and the conniving Jean Lafond. As the intrigue plays out, the lady does not sit idly by and watch the men duel over her; she must help Jamison overcome the evil plans of Lafond so that they have a chance to live happily ever after.
As early as 1984, Infocom employees joked about the possibility of a romance text adventure. By 1987, the year of Plundered Hearts's release, Infocom no longer rated its games on difficulty level.
Although this was not the only Infocom game designed in an effort to attract female players (one example being Moonmist), it is the only game where the lead character is always female.
The Plundered Hearts package included an elegant velvet reticule (pouch) containing the following items:
- A 50 guinea banknote from St. Sinistra
- A letter from Jean Lafond reporting the illness of the player character's father
Game reviewers complimented Plundered Hearts for its gripping prose, challenging predicaments, and scenes of derring-do. Other publications said it was a good introduction to interactive fiction, with writing suitable for both men and women. Some noted that the genre might have alienated Infocom's typical audience, but praised its bold direction nonetheless.
"""

plundered_hearts_fandom = """
You play Lady Dimsford, a young, aristocratic woman in the 17th century. She receives a letter from Jean Lafond, the governor of an island in the West Indies, informing her that her father is dying of a tropical disease. Lafond sends a ship to bring her to his island. The ship is then intercepted by notorious pirate Captain Jamison. However, it turns out that Lafond has kidnapped Lady Dimsford's father for his own purposes. The Lady and the pirate work together to defeat him.
The game can be played to completion with four potential endings. However, in only one ending do all of the Lady's loved ones survive. If another ending is arrived at, the user is informed that "There are other, perhaps more satisfying, conclusions."
There was a divide within Infocom regarding whether interactive fiction protagonists should be "audience stand-ins", or whether they should have defined characters. For instance, after negative reaction to the anti-hero protagonist of Infidel, implementor Michael Berlyn concluded that "People really don’t want to know who they are [in a game]." Plundered Hearts falls on the opposite side of the spectrum. Lady Dimsford's capable and spunky personality subverts the game's "damsel in distress" setup.
"""

# run frotz through a terminal emulator, using the ascii mode
# child = pexpect.spawn("frotz -p roms/PLUNDERE.z3", encoding='utf-8', timeout=5)
from pexpect.popen_spawn import PopenSpawn
child = PopenSpawn("frotz -p roms/PLUNDERE.z3", encoding='utf-8', timeout=5)

renderer = None
if ENABLE_C64_RENDERER:
    try:
        renderer = C64Renderer(font_path=C64_FONT_PATH, fps=50)
    except Exception as exc:
        print(f"Unable to start C64 renderer: {exc}")
        renderer = None


# Catch the intro message
child.expect("Press RETURN or ENTER to begin")
intro_text = clean_output(child.before)
print(intro_text)
if renderer and intro_text:
    renderer.write(intro_text + "\n")
    renderer.render_frame()

# Answer the intro message by pressing "enter"
child.sendline("")

time.sleep(0.5)

# Initial output
# child.expect("\r\x1b", timeout=5)
# print(repr(child.before))
buffer = ""
for _ in range(50):  # max itérations (sécurité)
    buffer += child.read_nonblocking(size=1024, timeout=0.2)
    if ">" in buffer[-10:]:
        break
# print(child.before)
print("\n")
initial_clean = clean_output(buffer)
if renderer and initial_clean:
    renderer.write(initial_clean + "\n")
    renderer.render_frame()

prev_output = initial_clean or ""
cmd_index = 0
prev_cmd = None

# automated walkthrough
while True : # for step, cmd in enumerate(plundered_hearts_commands):
    if renderer:
        renderer.process_events()

    cmd = plundered_hearts_commands[cmd_index]

    if ENABLE_LLM:
        prompt = "You are playing Pludered Hearts, a text interactive fiction by Amy Briggs."
        prompt = prompt + "Here is what Wikipedia says about this game : "
        prompt = prompt + plundered_hearts_wiki
        prompt = prompt + plundered_hearts_fandom

        prompt = prompt + "Here is the latest output from the game : "
        prompt = prompt + prev_output

        prompt = prompt + "From the known solution of the game, you know the next good command will be : " + cmd
        prompt = prompt + "Please o give a detailled feminist point of view over the current situation, in a familiar or slang-ish way, without mentioning the feminism, IN FRENCH ARGOT, FIRST PERSON, then explain, IN FRENCH ARGOT, FIRST PERSON, what to do and why this is the best thing in this context."
        prompt = prompt + "When thinking out loud, you refer yourself (and yourself only) as 'meuf' or 'frère'"
        llm_commentary = None

        retry = 0
        while llm_commentary is None: # llm_commentary is None or not("comment" in llm_commentary) or not("command" in llm_commentary):
            response = ollama.chat(
                model= 'ministral-3:14b', # , 'qwen3:8b', # 'gpt-oss:20b', # 'llama3:8b', # model = 'deepseek-r1:7b',
                messages=[{
                    'role': 'user',
                    'content': prompt
                    }]
            )
            # print(response.message.content)
            llm_commentary = response.message.content # extract_and_parse_json(response.message.content)
            if retry > 0:
                print("Retry #" + str(retry))
            retry = retry + 1

        # print("\n")
        ai_thinking = llm_commentary + "\n"
        print("<AI thinks : '" + ai_thinking + "'>\n")

        if ENABLE_READING_PAUSE:
            time.sleep(estimate_reading_time(ai_thinking))

    display_cmd = "> " + cmd.strip()
    print(display_cmd + "\n")
    if renderer:
        type_to_renderer(renderer, display_cmd + "\n", beep=True)
    child.sendline(" " + cmd)
    prev_output = ""
    prev_cmd = cmd

    # Flush output after command
    buffer = ""
    start_time = time.time()
    timeout_seconds = 4  # How long do we wait for the output to finish ?
    while time.time() - start_time < timeout_seconds:
        try:
            if renderer:
                renderer.process_events()
            chunk = child.read_nonblocking(size=1024, timeout=0.3)
            buffer += chunk

            # Some screens pause with "***MORE***" and wait for an ENTER key.
            if "***MORE***" in buffer:
                buffer = buffer.replace("***MORE***", "")
                child.sendline("")
                # Give the game a moment to continue output.
                time.sleep(0.1)
                continue
        except pexpect.exceptions.TIMEOUT:
            break

    cleaned = clean_output(buffer)
    if renderer:
        if cleaned:
            type_to_renderer(
                renderer,
                cleaned + "\n",
                base_delay=1 / 240.0,
                min_delay=1 / 240.0,
                max_delay=1 / 240.0,
                beep=False,
            )
        else:
            renderer.render_frame()
    print(cleaned)
    prev_output = cleaned

    if ENABLE_READING_PAUSE:
        time.sleep(0.3)  # artificially wait to allow reading

    cmd_index = cmd_index + 1
