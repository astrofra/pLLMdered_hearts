extends Control

@onready var video_player: VideoStreamPlayer = $Margin/VideoFrame/VideoPlayer

const VIDEO_PATH = "res://video/abriggs-itw.ogv"

func _ready() -> void:
	var stream = load(VIDEO_PATH)
	if stream == null:
		push_error("Video not found or unsupported: %s" % VIDEO_PATH)
		return
	video_player.stream = stream
	video_player.play()
