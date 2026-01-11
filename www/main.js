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
