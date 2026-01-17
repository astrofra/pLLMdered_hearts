extends Control

@onready var video_player: VideoStreamPlayer = $Margin/VideoFrame/VideoPlayer
@onready var subtitle_label: Label = $Subtitles/SubtitlePanel/SubtitleLabel
@onready var subtitle_panel: PanelContainer = $Subtitles/SubtitlePanel

const VIDEO_PATH = "res://video/abriggs-itw.ogv"
const SUBTITLE_VTT_PATH = "res://video/abriggs-itw.vtt"
const SUBTITLE_TXT_PATH = "res://video/abriggs-itw.txt"
const SUBTITLE_FONT_PATH = "res://fonts/RobotoCondensed-Regular.ttf"

var subtitles: Array = []
var current_subtitle_index := -1

func _ready() -> void:
	var stream = load(VIDEO_PATH)
	if stream == null:
		push_error("Video not found or unsupported: %s" % VIDEO_PATH)
		return
	video_player.stream = stream
	video_player.play()
	subtitle_panel.visible = false
	subtitles = _load_subtitles()
	var font = load(SUBTITLE_FONT_PATH) as FontFile
	if font != null:
		subtitle_label.add_theme_font_override("font", font)
	else:
		push_error("Subtitle font not found: %s" % SUBTITLE_FONT_PATH)
	subtitle_label.add_theme_font_size_override("font_size", 24)
	_update_subtitle(0.0)

func _process(_delta: float) -> void:
	if subtitles.is_empty():
		return
	var current_time = _get_video_time()
	_update_subtitle(current_time)

func _load_subtitles() -> Array:
	if FileAccess.file_exists(SUBTITLE_VTT_PATH):
		return _parse_vtt(SUBTITLE_VTT_PATH)
	if FileAccess.file_exists(SUBTITLE_TXT_PATH):
		return _parse_txt(SUBTITLE_TXT_PATH)
	push_error("Subtitle file not found.")
	return []

func _parse_vtt(path: String) -> Array:
	var cues: Array = []
	var file = FileAccess.open(path, FileAccess.READ)
	if file == null:
		push_error("Failed to open subtitles: %s" % path)
		return cues
	var lines = file.get_as_text().split("\n", false)
	var idx = 0
	while idx < lines.size():
		var line = lines[idx].strip_edges()
		if line == "" or line.begins_with("WEBVTT"):
			idx += 1
			continue
		if line.find("-->") == -1:
			idx += 1
			continue
		var parts = line.split("-->")
		var start = _parse_timecode(parts[0].strip_edges())
		var end_part = parts[1].strip_edges()
		var end_str = end_part.split(" ")[0]
		var end = _parse_timecode(end_str)
		idx += 1
		var text_lines: Array = []
		while idx < lines.size() and lines[idx].strip_edges() != "":
			text_lines.append(lines[idx].strip_edges())
			idx += 1
		var cue_text = " ".join(text_lines).strip_edges()
		if start >= 0.0 and end >= 0.0 and cue_text != "":
			cues.append({"start": start, "end": end, "text": cue_text})
		idx += 1
	return cues

func _parse_txt(path: String) -> Array:
	var cues: Array = []
	var file = FileAccess.open(path, FileAccess.READ)
	if file == null:
		push_error("Failed to open subtitles: %s" % path)
		return cues
	var lines = file.get_as_text().split("\n", false)
	var idx = 0
	while idx < lines.size():
		var line = lines[idx].strip_edges()
		if line == "":
			idx += 1
			continue
		if line.find(",") == -1:
			idx += 1
			continue
		var parts = line.split(",")
		if parts.size() < 2:
			idx += 1
			continue
		var start = _parse_timecode(parts[0].strip_edges())
		var end = _parse_timecode(parts[1].strip_edges())
		idx += 1
		var text_lines: Array = []
		while idx < lines.size() and lines[idx].strip_edges() != "":
			text_lines.append(lines[idx].strip_edges())
			idx += 1
		var cue_text = " ".join(text_lines).strip_edges()
		if start >= 0.0 and end >= 0.0 and cue_text != "":
			cues.append({"start": start, "end": end, "text": cue_text})
		idx += 1
	return cues

func _parse_timecode(text: String) -> float:
	var cleaned = text.strip_edges()
	if cleaned == "":
		return -1.0
	var parts = cleaned.split(":")
	var hours = 0
	var minutes = 0
	var seconds = 0.0
	if parts.size() == 3:
		hours = int(parts[0])
		minutes = int(parts[1])
		seconds = float(parts[2])
	elif parts.size() == 2:
		minutes = int(parts[0])
		seconds = float(parts[1])
	else:
		return -1.0
	return hours * 3600.0 + minutes * 60.0 + seconds

func _get_video_time() -> float:
	if video_player.has_method("get_stream_position"):
		return video_player.get_stream_position()
	if video_player.has_method("get_playback_position"):
		return video_player.get_playback_position()
	var pos = video_player.get("stream_position")
	if typeof(pos) == TYPE_FLOAT:
		return pos
	return 0.0

func _find_cue_index(time_sec: float) -> int:
	var low = 0
	var high = subtitles.size() - 1
	while low <= high:
		var mid = int((low + high) / 2)
		var cue = subtitles[mid]
		if time_sec < cue["start"]:
			high = mid - 1
		elif time_sec > cue["end"]:
			low = mid + 1
		else:
			return mid
	return -1

func _update_subtitle(time_sec: float) -> void:
	var idx = _find_cue_index(time_sec)
	if idx == -1:
		if subtitle_label.text != "":
			subtitle_label.text = ""
		if subtitle_panel.visible:
			subtitle_panel.visible = false
		current_subtitle_index = -1
		return
	if idx != current_subtitle_index:
		current_subtitle_index = idx
		subtitle_label.text = subtitles[idx]["text"]
		if not subtitle_panel.visible:
			subtitle_panel.visible = true
