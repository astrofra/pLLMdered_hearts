function enableCaptions(video) {
  if (video && video.textTracks && video.textTracks.length > 0) {
    video.textTracks[0].mode = "showing";
  }
}

function setupStartOverlay() {
  const startScreen = document.getElementById("start-screen");
  const startButton = document.getElementById("start-button");
  const video = document.getElementById("side-video");
  if (!startScreen || !startButton || !video) return;

  enableCaptions(video);

  const onStart = () => {
    document.body.classList.remove("needs-start");
    startScreen.hidden = true;
    startScreen.style.display = "none";
    video.muted = false;
    const playAttempt = video.play();
    if (playAttempt && typeof playAttempt.catch === "function") {
      playAttempt.catch((err) => {
        console.warn("Video play failed:", err);
      });
    }
  };

  startButton.addEventListener("click", onStart, { once: true });
}

setupStartOverlay();
