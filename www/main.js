const POLL_INTERVAL_MS = 800;
const OUTPUT_DIR = "/llm_out/";

let latestFile = null;

async function fetchDirectoryListing() {
  try {
    const res = await fetch(OUTPUT_DIR, { cache: "no-store" });
    if (!res.ok) {
      throw new Error(`Directory fetch failed: ${res.status}`);
    }
    return await res.text();
  } catch (err) {
    console.error(err);
    return "";
  }
}

function extractMarkdownFiles(htmlText) {
  const files = [];
  const regex = /href="([^"]+\.md)"/gi;
  let match;
  while ((match = regex.exec(htmlText)) !== null) {
    files.push(match[1]);
  }
  return files.sort();
}

async function fetchLatestFile(filePath) {
  try {
    const res = await fetch(filePath, { cache: "no-store" });
    if (!res.ok) {
      throw new Error(`File fetch failed: ${res.status}`);
    }
    return await res.text();
  } catch (err) {
    console.error(err);
    return null;
  }
}

function parseTimecodeToSeconds(timecode) {
  if (!timecode) return null;
  const match = /(\d+):(\d+):(\d+)(?:\.(\d+))?/.exec(timecode);
  if (!match) return null;
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  const seconds = Number(match[3]);
  const millis = match[4] ? Number(match[4].padEnd(3, "0")) : 0;
  if ([hours, minutes, seconds, millis].some((v) => Number.isNaN(v))) {
    return null;
  }
  return hours * 3600 + minutes * 60 + seconds + millis / 1000;
}

function parseTimecodeRange(rangeText) {
  if (!rangeText) return null;
  const parts = rangeText.split("-->");
  if (!parts.length) return null;
  return parseTimecodeToSeconds(parts[0].trim());
}

async function fetchTimecodeMetadata(filePath) {
  try {
    const res = await fetch(filePath, { cache: "no-store" });
    if (!res.ok) {
      return null;
    }
    return await res.json();
  } catch (err) {
    console.warn("Timecode metadata fetch failed:", err);
    return null;
  }
}

function seekVideoToTimecode(timecodeText) {
  const video = document.getElementById("side-video");
  if (!video) return;
  const seconds = parseTimecodeRange(timecodeText);
  if (seconds === null) return;
  if (!Number.isFinite(seconds)) return;
  try {
    video.currentTime = seconds;
  } catch (err) {
    console.warn("Video seek failed:", err);
  }
}

function renderMarkdown(mdText) {
  const container = document.getElementById("content");
  if (!container) return;
  container.classList.remove("visible");
  const parsed = mdText ? marked.parse(mdText) : "";
  container.innerHTML = parsed;
  // allow CSS transition to apply
  requestAnimationFrame(() => {
    container.classList.add("visible");
  });
}

async function poll() {
  const listing = await fetchDirectoryListing();
  if (!listing) return;
  const files = extractMarkdownFiles(listing);
  if (files.length === 0) return;
  const newest = files[files.length - 1];
  if (newest === latestFile) return;
  latestFile = newest;
  const text = await fetchLatestFile(OUTPUT_DIR + newest);
  if (text !== null) {
    renderMarkdown(text);
    const metaPath = OUTPUT_DIR + newest.replace(/\.md$/i, ".json");
    const meta = await fetchTimecodeMetadata(metaPath);
    if (meta && meta.timecode) {
      seekVideoToTimecode(meta.timecode);
    }
  }
}

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
setInterval(poll, POLL_INTERVAL_MS);
poll();
