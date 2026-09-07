// ==========================================================================
// HandGuard AI - Frontend Controller & Real-Time SSE Streamer
// ==========================================================================

document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const dropzone = document.getElementById("dropzone");
  const dropzoneCard = document.getElementById("dropzoneCard");
  const videoFileInput = document.getElementById("videoFileInput");
  const btnBrowseFile = document.getElementById("btnBrowseFile");
  const filePreviewBar = document.getElementById("filePreviewBar");
  const previewFileName = document.getElementById("previewFileName");
  const previewFileSize = document.getElementById("previewFileSize");
  const btnChangeFile = document.getElementById("btnChangeFile");
  const btnStartAnalyze = document.getElementById("btnStartAnalyze");

  const thresholdSlider = document.getElementById("thresholdSlider");
  const thresholdValue = document.getElementById("thresholdValue");
  const thresholdHintText = document.getElementById("thresholdHintText");
  const strictModeToggle = document.getElementById("strictModeToggle");
  const renderDebugToggle = document.getElementById("renderDebugToggle");
  const strideSelect = document.getElementById("strideSelect");

  // Mode Switcher
  const modeUploadBtn = document.getElementById("modeUploadBtn");
  const modeLiveBtn = document.getElementById("modeLiveBtn");
  const uploadModePanel = document.getElementById("uploadModePanel");
  const liveModePanel = document.getElementById("liveModePanel");
  const webcamSettingsCard = document.getElementById("webcamSettingsCard");

  const progressCard = document.getElementById("progressCard");
  const progressBarFill = document.getElementById("progressBarFill");
  const progressPercent = document.getElementById("progressPercent");
  const progressStatusText = document.getElementById("progressStatusText");
  const progressSubText = document.getElementById("progressSubText");
  const progFrameCount = document.getElementById("progFrameCount");
  const progValidCount = document.getElementById("progValidCount");
  const progCurrentRatio = document.getElementById("progCurrentRatio");
  const progThreshold = document.getElementById("progThreshold");

  const resultsContainer = document.getElementById("resultsContainer");
  const verdictCard = document.getElementById("verdictCard");
  const verdictIcon = document.getElementById("verdictIcon");
  const verdictHeadline = document.getElementById("verdictHeadline");
  const verdictTag = document.getElementById("verdictTag");
  const verdictDesc = document.getElementById("verdictDesc");
  const verdictScore = document.getElementById("verdictScore");

  const kpiValidFrames = document.getElementById("kpiValidFrames");
  const kpiValidSub = document.getElementById("kpiValidSub");
  const kpiInvalidFrames = document.getElementById("kpiInvalidFrames");
  const kpiDuration = document.getElementById("kpiDuration");
  const kpiFpsRes = document.getElementById("kpiFpsRes");
  const kpiViolationsCount = document.getElementById("kpiViolationsCount");
  const kpiViolationStatus = document.getElementById("kpiViolationStatus");

  const mainVideoPlayer = document.getElementById("mainVideoPlayer");
  const playerVideoTitle = document.getElementById("playerVideoTitle");
  const tabDebugVideo = document.getElementById("tabDebugVideo");
  const tabOriginalVideo = document.getElementById("tabOriginalVideo");
  const violationTimelineTrack = document.getElementById("violationTimelineTrack");
  const violationsTableBody = document.getElementById("violationsTableBody");
  const violationsCard = document.getElementById("violationsCard");

  const btnDownloadDebugVideo = document.getElementById("btnDownloadDebugVideo");
  const btnDownloadReportJson = document.getElementById("btnDownloadReportJson");
  const btnScanAnother = document.getElementById("btnScanAnother");
  const historyTableBody = document.getElementById("historyTableBody");
  const btnRefreshHistory = document.getElementById("btnRefreshHistory");

  let selectedFile = null;
  let currentEventSource = null;
  let currentResultData = null;

  // ------------------------------------------------------------------------
  // Mode Switcher Logic
  // ------------------------------------------------------------------------
  modeUploadBtn.addEventListener("click", () => switchMode("upload"));
  modeLiveBtn.addEventListener("click", () => switchMode("live"));

  function switchMode(mode) {
    if (mode === "upload") {
      modeUploadBtn.classList.add("active");
      modeLiveBtn.classList.remove("active");
      uploadModePanel.classList.remove("hidden");
      liveModePanel.classList.add("hidden");
      webcamSettingsCard.classList.add("hidden");
      // Stop live stream if switching away
      if (liveStream) {
        stopLiveSession(false);
        stopLiveStream();
      }
    } else {
      modeLiveBtn.classList.add("active");
      modeUploadBtn.classList.remove("active");
      liveModePanel.classList.remove("hidden");
      uploadModePanel.classList.add("hidden");
      webcamSettingsCard.classList.remove("hidden");
      // Auto-open camera when switching to live mode
      if (!liveStream) {
        openLiveCamera();
      }
    }
  }

  // ------------------------------------------------------------------------
  // Threshold Slider Handling
  // ------------------------------------------------------------------------
  thresholdSlider.addEventListener("input", (e) => {
    const val = e.target.value;
    thresholdValue.textContent = `${val}%`;
    thresholdHintText.textContent = `${val}%`;
    progThreshold.textContent = `${val}.0%`;
  });

  // ------------------------------------------------------------------------
  // Drag and Drop & File Upload
  // ------------------------------------------------------------------------
  btnBrowseFile.addEventListener("click", () => videoFileInput.click());
  dropzone.addEventListener("click", (e) => {
    if (e.target !== btnBrowseFile && !btnBrowseFile.contains(e.target)) {
      videoFileInput.click();
    }
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      handleFileSelected(files[0]);
    }
  });

  videoFileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  });

  function handleFileSelected(file) {
    const validExtensions = [".mp4", ".mov", ".avi", ".webm", ".mkv"];
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
    if (!validExtensions.includes(ext)) {
      alert(`Định dạng file không được hỗ trợ (${ext}). Hãy chọn file .mp4, .mov, .avi hoặc .webm!`);
      return;
    }
    selectedFile = file;
    previewFileName.textContent = file.name;
    previewFileSize.textContent = formatBytes(file.size);
    filePreviewBar.classList.remove("hidden");
  }

  btnChangeFile.addEventListener("click", () => {
    selectedFile = null;
    videoFileInput.value = "";
    filePreviewBar.classList.add("hidden");
  });

  function formatBytes(bytes) {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  }

  // ------------------------------------------------------------------------
  // Start Analysis
  // ------------------------------------------------------------------------
  btnStartAnalyze.addEventListener("click", () => {
    if (!selectedFile) return;
    startVideoUploadAndAnalysis(selectedFile);
  });

  async function startVideoUploadAndAnalysis(file) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("threshold", thresholdSlider.value);
    formData.append("strict_left_right", strictModeToggle.checked);
    formData.append("stride", strideSelect.value);
    formData.append("render_debug", renderDebugToggle.checked);

    // Update UI to analyzing state
    dropzoneCard.classList.add("hidden");
    resultsContainer.classList.add("hidden");
    progressCard.classList.remove("hidden");
    resetProgressUI();

    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Không thể tải file lên server");
      }

      const taskData = await response.json();
      subscribeToProgress(taskData.task_id);
    } catch (err) {
      alert("Lỗi: " + err.message);
      progressCard.classList.add("hidden");
      dropzoneCard.classList.remove("hidden");
    }
  }

  // ------------------------------------------------------------------------
  // Server-Sent Events (SSE) Progress Subscription
  // ------------------------------------------------------------------------
  function subscribeToProgress(taskId) {
    if (currentEventSource) {
      currentEventSource.close();
    }

    currentEventSource = new EventSource(`/api/progress/${taskId}`);

    currentEventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.status === "PROCESSING" || data.status === "PENDING") {
          updateProgressUI(data.progress);
        } else if (data.status === "COMPLETED") {
          currentEventSource.close();
          currentEventSource = null;
          updateProgressUI({ percent: 100, message: "Hoàn tất!" });
          setTimeout(() => {
            progressCard.classList.add("hidden");
            renderResults(data.result);
            loadHistory();
          }, 400);
        } else if (data.status === "FAILED") {
          currentEventSource.close();
          currentEventSource = null;
          alert("Quá trình phân tích thất bại: " + (data.error || "Lỗi không xác định"));
          progressCard.classList.add("hidden");
          dropzoneCard.classList.remove("hidden");
        }
      } catch (e) {
        console.error("Lỗi parse SSE:", e);
      }
    };

    currentEventSource.onerror = (e) => {
      console.warn("Mất kết nối SSE, thử thăm dò task status...");
      setTimeout(() => pollTaskStatus(taskId), 1000);
    };
  }

  async function pollTaskStatus(taskId) {
    try {
      const res = await fetch(`/api/tasks/${taskId}`);
      if (!res.ok) return;
      const data = await res.json();
      if (data.status === "COMPLETED") {
        progressCard.classList.add("hidden");
        renderResults(data.result);
        loadHistory();
      } else if (data.status === "FAILED") {
        alert("Lỗi: " + data.error);
        progressCard.classList.add("hidden");
        dropzoneCard.classList.remove("hidden");
      } else {
        updateProgressUI(data.progress);
        setTimeout(() => pollTaskStatus(taskId), 1000);
      }
    } catch (e) {
      console.error(e);
    }
  }

  function resetProgressUI() {
    progressBarFill.style.width = "0%";
    progressPercent.textContent = "0%";
    progressStatusText.textContent = "Khởi tạo tác vụ...";
    progressSubText.textContent = "Đang nạp mô hình MediaPipe Tasks...";
    progFrameCount.textContent = "0 / 0";
    progValidCount.textContent = "0";
    progCurrentRatio.textContent = "0.0%";
  }

  function updateProgressUI(prog) {
    if (!prog) return;
    const pct = prog.percent || 0;
    progressBarFill.style.width = `${pct}%`;
    progressPercent.textContent = `${pct}%`;
    if (prog.message) {
      progressStatusText.textContent = prog.message;
    }
    if (prog.frame && prog.total_frames) {
      progFrameCount.textContent = `${prog.frame} / ${prog.total_frames}`;
      progressSubText.textContent = `Tốc độ phân tích: tối ưu CPU XNNPACK`;
    }
    if (prog.valid_count !== undefined) {
      progValidCount.textContent = prog.valid_count;
    }
    if (prog.current_ratio !== undefined) {
      progCurrentRatio.textContent = `${prog.current_ratio}%`;
    }
  }


  // ------------------------------------------------------------------------
  // Render Results Dashboard
  // ------------------------------------------------------------------------
  function renderResults(data) {
    currentResultData = data;
    const summary = data.summary;
    const vi = data.video_info;
    const violations = data.intervals_missing_hands || [];

    // Verdict Hero Banner
    verdictCard.className = "card verdict-card " + (summary.is_valid ? "valid" : "invalid");
    if (summary.is_valid) {
      verdictTag.textContent = "KẾT QUẢ ĐÁNH GIÁ: ĐẠT TIÊU CHUẨN";
      verdictHeadline.textContent = "HỢP LỆ (VALID)";
      verdictDesc.textContent = `Tỷ lệ số khung hình nhận diện đủ cả 2 tay đạt ${summary.ratio_percent}%, đạt yêu cầu tối thiểu (ngưỡng ${summary.threshold_percent}%).`;
      verdictIcon.innerHTML = `
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
      `;
    } else {
      verdictTag.textContent = "KẾT QUẢ ĐÁNH GIÁ: KHÔNG ĐẠT";
      verdictHeadline.textContent = "KHÔNG HỢP LỆ (INVALID)";
      verdictDesc.textContent = `Tỷ lệ số khung hình đủ cả 2 tay chỉ đạt ${summary.ratio_percent}%, không đủ điều kiện tối thiểu (ngưỡng ${summary.threshold_percent}%).`;
      verdictIcon.innerHTML = `
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      `;
    }
    verdictScore.textContent = `${summary.ratio_percent}%`;

    // KPI Metrics
    kpiValidFrames.textContent = summary.frames_valid;
    kpiValidSub.textContent = `trên ${summary.frames_analyzed} khung hình`;
    kpiInvalidFrames.textContent = summary.frames_invalid;
    kpiDuration.textContent = `${vi.duration_seconds}s`;
    kpiFpsRes.textContent = `${vi.fps.toFixed(1)} FPS • ${vi.resolution}`;
    kpiViolationsCount.textContent = `${violations.length} đoạn`;
    kpiViolationStatus.textContent = violations.length === 0 ? "Tuyệt đối không mất tay" : "Cần xem lại vị trí mất tay";

    // Video Player & Playback Card
    const playerCard = document.querySelector(".player-card");
    const defaultVideoUrl = summary.debug_video_url || summary.original_video_url;

    if (defaultVideoUrl) {
      if (playerCard) playerCard.classList.remove("hidden");
      playerVideoTitle.textContent = vi.filename;
      mainVideoPlayer.src = defaultVideoUrl;
      tabDebugVideo.classList.toggle("active", Boolean(summary.debug_video_url));
      tabOriginalVideo.classList.toggle("active", !summary.debug_video_url);

      tabDebugVideo.onclick = () => {
        if (summary.debug_video_url) {
          tabDebugVideo.classList.add("active");
          tabOriginalVideo.classList.remove("active");
          mainVideoPlayer.src = summary.debug_video_url;
          mainVideoPlayer.play();
        } else {
          alert("Video debug không được tạo cho lượt phân tích này.");
        }
      };

      tabOriginalVideo.onclick = () => {
        tabOriginalVideo.classList.add("active");
        tabDebugVideo.classList.remove("active");
        mainVideoPlayer.src = summary.original_video_url;
        mainVideoPlayer.play();
      };
    } else {
      if (playerCard) playerCard.classList.add("hidden");
      mainVideoPlayer.removeAttribute("src");
    }

    // Render Timeline Scrubber Violations
    renderTimelineViolations(violations, vi.duration_seconds);

    // Render Violations Table
    renderViolationsTable(violations);

    // Show Results
    resultsContainer.classList.remove("hidden");
    resultsContainer.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderTimelineViolations(violations, totalDuration) {
    violationTimelineTrack.innerHTML = "";
    if (totalDuration <= 0) return;

    violations.forEach((v) => {
      const leftPct = (v.start_time_sec / totalDuration) * 100;
      const widthPct = Math.max(0.5, ((v.end_time_sec - v.start_time_sec) / totalDuration) * 100);

      const block = document.createElement("div");
      block.className = "timeline-violation-block";
      block.style.left = `${leftPct}%`;
      block.style.width = `${widthPct}%`;
      block.title = `Thiếu tay: ${v.start_time_sec}s - ${v.end_time_sec}s (Bấm để tua)`;

      block.addEventListener("click", (e) => {
        e.stopPropagation();
        mainVideoPlayer.currentTime = v.start_time_sec;
        mainVideoPlayer.play();
      });

      violationTimelineTrack.appendChild(block);
    });

    violationTimelineTrack.onclick = (e) => {
      const rect = violationTimelineTrack.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const ratio = clickX / rect.width;
      mainVideoPlayer.currentTime = ratio * totalDuration;
      mainVideoPlayer.play();
    };
  }

  function renderViolationsTable(violations) {
    violationsTableBody.innerHTML = "";
    if (violations.length === 0) {
      violationsCard.classList.add("hidden");
      return;
    }
    violationsCard.classList.remove("hidden");

    violations.forEach((v, idx) => {
      const duration = (v.end_time_sec - v.start_time_sec).toFixed(2);
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><b>#${idx + 1}</b></td>
        <td>Frame <code>${v.start_frame}</code> &rarr; <code>${v.end_frame}</code></td>
        <td>${v.start_time_sec}s &mdash; ${v.end_time_sec}s</td>
        <td><span class="value-badge">${duration}s</span></td>
        <td>
          <button class="btn btn-sm btn-outline btn-jump" data-time="${v.start_time_sec}">
            Tua Tới Đây
          </button>
        </td>
      `;
      violationsTableBody.appendChild(tr);
    });

    document.querySelectorAll(".btn-jump").forEach((btn) => {
      btn.addEventListener("click", () => {
        const t = parseFloat(btn.getAttribute("data-time"));
        mainVideoPlayer.currentTime = t;
        mainVideoPlayer.play();
        mainVideoPlayer.scrollIntoView({ behavior: "smooth", block: "center" });
      });
    });
  }

  // ------------------------------------------------------------------------
  // Export & Action Buttons
  // ------------------------------------------------------------------------
  btnDownloadDebugVideo.addEventListener("click", () => {
    if (currentResultData && currentResultData.summary.debug_video_url) {
      window.open(currentResultData.summary.debug_video_url, "_blank");
    } else {
      alert("Không có video debug để tải về.");
    }
  });

  btnDownloadReportJson.addEventListener("click", () => {
    if (currentResultData && currentResultData.summary.report_url) {
      window.open(currentResultData.summary.report_url, "_blank");
    } else {
      alert("Không có báo cáo JSON.");
    }
  });

  // Show results - also switch back to upload mode to see dashboard
  function showResults(data) {
    if (!uploadModePanel.classList.contains("hidden") === false) {
      // Already in upload mode or switching
    }
    renderResults(data);
    loadHistory();
  }

  btnRefreshHistory.addEventListener("click", loadHistory);
  loadHistory();

  // ==========================================================================
  // LIVE WEBCAM DETECTION MODULE (WebSocket Real-Time)
  // ==========================================================================

  const btnOpenLiveDetect = document.getElementById("btnOpenLiveDetect");
  const btnCloseLiveDetect = document.getElementById("btnCloseLiveDetect");
  const liveDetectPanel = document.getElementById("liveDetectPanel");
  const btnStartLive = document.getElementById("btnStartLive");
  const btnStopLive = document.getElementById("btnStopLive");
  const btnLiveViewResults = document.getElementById("btnLiveViewResults");
  const liveDurationSelect = document.getElementById("liveDurationSelect");
  const liveWebcamVideo = document.getElementById("liveWebcamVideo");
  const liveOverlayCanvas = document.getElementById("liveOverlayCanvas");
  const liveHudBadge = document.getElementById("liveHudBadge");
  const liveHudIcon = document.getElementById("liveHudIcon");
  const liveHudStatus = document.getElementById("liveHudStatus");
  const liveRatioVal = document.getElementById("liveRatioVal");
  const liveValidCount = document.getElementById("liveValidCount");
  const liveTotalCount = document.getElementById("liveTotalCount");
  const liveTimer = document.getElementById("liveTimer");
  const liveProgressFill = document.getElementById("liveProgressFill");
  const liveProgressLabel = document.getElementById("liveProgressLabel");
  const liveSessionVerdict = document.getElementById("liveSessionVerdict");
  const liveVerdictIcon = document.getElementById("liveVerdictIcon");
  const liveVerdictText = document.getElementById("liveVerdictText");
  const liveVerdictSub = document.getElementById("liveVerdictSub");

  let liveStream = null;
  let liveWs = null;
  let liveFrameInterval = null;
  let liveTimerInterval = null;
  let liveSessionStartTime = 0;
  let liveSessionResult = null;

  // Skeleton connections (21 landmarks, 0-indexed)
  const HAND_CONNECTIONS = [
    [0,1],[1,2],[2,3],[3,4],
    [0,5],[5,6],[6,7],[7,8],
    [5,9],[9,10],[10,11],[11,12],
    [9,13],[13,14],[14,15],[15,16],
    [13,17],[17,18],[18,19],[19,20],
    [0,17],
  ];

  // ─── syncLiveDimensions ───────────────────────────────────────────────────
  // Sets the canvas pixel buffer to match the video's ACTUAL decoded resolution.
  // Must be called after the stream is ready (loadedmetadata) and on every resize,
  // because the canvas buffer ≠ CSS size by default, which causes landmark offset.
  function syncLiveDimensions() {
    const vw = liveWebcamVideo.videoWidth;
    const vh = liveWebcamVideo.videoHeight;
    if (!vw || !vh) return; // stream not ready yet — skip
    liveOverlayCanvas.width  = vw;
    liveOverlayCanvas.height = vh;
  }

  // Open camera function (called when switching to live mode)
  async function openLiveCamera() {
    try {
      liveStream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
        audio: false,
      });
      liveWebcamVideo.srcObject = liveStream;
      // Sync canvas buffer once metadata (resolution) is known
      liveWebcamVideo.addEventListener("loadedmetadata", syncLiveDimensions, { once: false });
      await new Promise((resolve) => { liveWebcamVideo.onloadedmetadata = () => { syncLiveDimensions(); resolve(); }; });
      resetLiveUI();
    } catch (err) {
      alert("Khong the mo webcam: " + err.message);
      // Switch back to upload mode if camera fails
      switchMode("upload");
    }
  }

  function stopLiveStream() {
    if (liveStream) {
      liveStream.getTracks().forEach((t) => t.stop());
      liveStream = null;
    }
  }

  function resetLiveUI() {
    liveHudBadge.className = "live-hud-badge";
    liveHudIcon.textContent = "○";
    liveHudStatus.textContent = "Đang chờ bắt đầu...";
    liveRatioVal.textContent = "–";
    liveValidCount.textContent = "0";
    liveTotalCount.textContent = "0";
    liveTimer.textContent = "0s";
    liveProgressFill.style.width = "0%";
    liveSessionVerdict.classList.add("hidden");
    btnStartLive.classList.remove("hidden");
    btnStopLive.classList.add("hidden");
    btnStopLive.disabled = false;
    btnStopLive.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"></rect></svg><span>Dừng & Xuất Kết Quả</span>';
    btnLiveViewResults.classList.add("hidden");
    liveSessionResult = null;

    // Sync threshold label
    liveProgressLabel.textContent = `Ngưỡng: ${thresholdSlider.value}%`;

    // Sync canvas dimensions to actual video resolution
    syncLiveDimensions();
  }

  // Start live session
  btnStartLive.addEventListener("click", startLiveSession);

  async function startLiveSession() {
    if (!liveStream) return;

    resetLiveUI();
    liveSessionStartTime = Date.now();

    // Sync canvas buffer to actual decoded video resolution (1:1 pixel mapping)
    syncLiveDimensions();

    // Connect WebSocket
    const wsUrl = `ws://${window.location.host}/ws/live-webcam`;
    liveWs = new WebSocket(wsUrl);
    liveWs.binaryType = "arraybuffer";

    liveWs.onopen = async () => {
      // Send configuration first
      const config = {
        action: "start",
        threshold: parseFloat(thresholdSlider.value),
        strict_left_right: strictModeToggle.checked,
      };
      liveWs.send(JSON.stringify(config));
    };

    liveWs.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "ready") {
          // Model ready → start sending frames
          btnStartLive.classList.add("hidden");
          btnStopLive.classList.remove("hidden");

          // Start session timer
          const maxDuration = parseInt(liveDurationSelect ? liveDurationSelect.value : "0", 10);
          liveTimerInterval = setInterval(() => {
            const elapsed = Math.floor((Date.now() - liveSessionStartTime) / 1000);
            liveTimer.textContent = `${elapsed}s`;
            if (maxDuration > 0 && elapsed >= maxDuration) {
              stopLiveSession(true);
            }
          }, 250);

          startFrameSendLoop();

        } else if (data.type === "frame") {
          updateLiveHUD(data);
          drawLandmarks(data.landmarks, data.handedness);

        } else if (data.type === "session_summary") {
          // Final summary received with recorded video & report
          liveSessionResult = buildResultFromSummary(data);
          stopFrameSendLoop();
          clearInterval(liveTimerInterval);
          stopLiveStream();
          if (liveWs) {
            liveWs.close();
            liveWs = null;
          }
          // Switch back to upload panel and show dashboard
          switchMode("upload");
          dropzoneCard.classList.add("hidden");
          progressCard.classList.add("hidden");
          renderResults(liveSessionResult);
          loadHistory();
        } else if (data.type === "error") {
          console.error("Live WS error:", data.message);
          alert("Lỗi từ server: " + data.message);
          stopLiveSession(false);
        }
      } catch (e) {
        console.error("Parse error:", e);
      }
    };

    liveWs.onerror = (e) => {
      console.error("WebSocket error:", e);
      alert("Lỗi kết nối WebSocket. Hãy thử tải lại trang.");
      stopLiveSession(false);
    };

    liveWs.onclose = () => {
      stopFrameSendLoop();
      clearInterval(liveTimerInterval);
    };
  }

  // Send frames loop at ~25 FPS
  function startFrameSendLoop() {
    const captureCanvas = document.createElement("canvas");
    // Use actual decoded video resolution for capture — same as canvas buffer
    captureCanvas.width  = liveWebcamVideo.videoWidth  || liveOverlayCanvas.width  || 640;
    captureCanvas.height = liveWebcamVideo.videoHeight || liveOverlayCanvas.height || 480;
    const ctx = captureCanvas.getContext("2d");

    liveFrameInterval = setInterval(() => {
      if (!liveWs || liveWs.readyState !== WebSocket.OPEN || !liveStream) return;
      if (liveWebcamVideo.readyState < 2) return;

      // Draw current video frame to capture canvas (don't mirror — let server mirror)
      ctx.drawImage(liveWebcamVideo, 0, 0, captureCanvas.width, captureCanvas.height);

      captureCanvas.toBlob((blob) => {
        if (!blob || !liveWs || liveWs.readyState !== WebSocket.OPEN) return;
        blob.arrayBuffer().then((buf) => {
          if (liveWs.readyState === WebSocket.OPEN) {
            liveWs.send(buf);
          }
        });
      }, "image/jpeg", 0.85); // 85% quality - giảm nhiễu nén DCT khi tay chuyển động nhanh

    }, 1000 / 25); // 25 FPS
  }

  function stopFrameSendLoop() {
    if (liveFrameInterval) {
      clearInterval(liveFrameInterval);
      liveFrameInterval = null;
    }
  }

  function stopLiveSession(sendStop = true) {
    stopFrameSendLoop();
    clearInterval(liveTimerInterval);

    if (liveWs && liveWs.readyState === WebSocket.OPEN) {
      if (sendStop) {
        liveWs.send(JSON.stringify({ action: "stop" }));
      }
      // Give server up to 5s to finalize MP4 video files
      setTimeout(() => {
        if (liveWs) {
          liveWs.close();
          liveWs = null;
        }
      }, 5000);
    }
  }

  btnStopLive.addEventListener("click", () => {
    btnStopLive.disabled = true;
    btnStopLive.innerHTML = '<span class="pulse-dot"></span><span>Đang xử lý xuất video...</span>';
    stopLiveSession(true);
  });

  // Update HUD stats
  function updateLiveHUD(data) {
    const ratio = data.current_ratio || 0;
    const hasTwoHands = data.has_two_hands;
    const detectionSource = data.detection_source || 'NONE';

    liveRatioVal.textContent = `${ratio}%`;
    liveValidCount.textContent = data.valid_frames || 0;
    liveTotalCount.textContent = data.total_frames || 0;

    // Cập nhật badge trạng thái theo nguồn nhận diện (Kalman Tracker)
    const liveStatusBadge = document.getElementById('live-status-badge');
    if (liveStatusBadge) {
      if (!hasTwoHands && detectionSource === 'NONE') {
        liveStatusBadge.textContent = '✋ THIẾU TAY';
        liveStatusBadge.style.background = 'rgba(220,30,30,0.85)';
      } else if (detectionSource === 'POSE_CLASPED') {
        liveStatusBadge.textContent = '🤝 2 TAY CHẬP NHAU';
        liveStatusBadge.style.background = 'rgba(0,160,220,0.85)';
      } else if (detectionSource === 'POSE_MOTION') {
        liveStatusBadge.textContent = '⚡ CHUYỂN ĐỘNG NHANH';
        liveStatusBadge.style.background = 'rgba(200,160,0,0.85)';
      } else if (hasTwoHands) {
        liveStatusBadge.textContent = '✅ ĐỦ 2 BÀN TAY';
        liveStatusBadge.style.background = 'rgba(20,180,80,0.85)';
      }
    }

    liveProgressFill.style.width = `${Math.min(ratio, 100)}%`;

    if (hasTwoHands) {
      liveHudBadge.className = "live-hud-badge hud-ok";
      liveHudIcon.textContent = "✓";
      liveHudStatus.textContent = `ĐỦ 2 TAY  (${data.handedness?.join(" + ") || ""})`;
    } else {
      liveHudBadge.className = "live-hud-badge hud-miss";
      liveHudIcon.textContent = "✗";
      liveHudStatus.textContent = `THIẾU TAY (${data.hand_count} bàn tay)`;
    }
  }

  // Draw hand landmarks on canvas
  function drawLandmarks(landmarksPerHand, handedness) {
    const canvas = liveOverlayCanvas;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!landmarksPerHand || landmarksPerHand.length === 0) return;

    // Color definitions: Orange for Left hand, Emerald/Cyan for Right hand
    const COLORS = ["#FFA500", "#10B981"];

    landmarksPerHand.forEach((landmarks, handIdx) => {
      const color = COLORS[handIdx % COLORS.length];

      // Mirror X coordinate (1 - lm.x) so it aligns perfectly with the mirrored <video>
      const pts = landmarks.map((lm) => ({
        x: (1.0 - lm.x) * canvas.width,
        y: lm.y * canvas.height,
      }));

      // Draw skeleton connections
      ctx.strokeStyle = color;
      ctx.lineWidth = 3;
      ctx.shadowBlur = 8;
      ctx.shadowColor = color;
      HAND_CONNECTIONS.forEach(([a, b]) => {
        if (pts[a] && pts[b]) {
          ctx.beginPath();
          ctx.moveTo(pts[a].x, pts[a].y);
          ctx.lineTo(pts[b].x, pts[b].y);
          ctx.stroke();
        }
      });

      // Draw joint dots
      ctx.fillStyle = "#FFFFFF";
      ctx.shadowBlur = 6;
      pts.forEach((pt) => {
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 4.5, 0, 2 * Math.PI);
        ctx.fill();
      });

      // Draw palm center circle
      if (pts[0] && pts[9]) {
        const cx = (pts[0].x + pts[9].x) / 2;
        const cy = (pts[0].y + pts[9].y) / 2;
        ctx.beginPath();
        ctx.arc(cx, cy, 7, 0, 2 * Math.PI);
        ctx.fillStyle = color;
        ctx.fill();
      }

      // Draw handedness label at wrist (landmark 0) - completely upright
      if (pts[0]) {
        ctx.shadowBlur = 0;
        const rawLabel = handedness?.[handIdx] || (handIdx === 0 ? "Tay 1" : "Tay 2");
        const viLabel = rawLabel === "Left" ? "Tay Trái (Left)" : (rawLabel === "Right" ? "Tay Phải (Right)" : rawLabel);

        ctx.font = "bold 13px Outfit, sans-serif";
        const textMetrics = ctx.measureText(viLabel);
        const padX = 8;
        const padY = 4;
        const badgeW = textMetrics.width + padX * 2;
        const badgeH = 22;
        const bx = pts[0].x - badgeW / 2;
        const by = pts[0].y + 12;

        // Background pill
        ctx.fillStyle = "rgba(0, 0, 0, 0.75)";
        ctx.beginPath();
        ctx.roundRect ? ctx.roundRect(bx, by, badgeW, badgeH, 6) : ctx.rect(bx, by, badgeW, badgeH);
        ctx.fill();

        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Upright text
        ctx.fillStyle = color;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(viLabel, pts[0].x, by + badgeH / 2);
      }
    });

    ctx.shadowBlur = 0;
  }

  // Show session verdict overlay on camera
  function showSessionVerdict(data) {
    const isValid = data.is_valid;
    liveSessionVerdict.classList.remove("hidden");

    if (isValid) {
      liveVerdictIcon.textContent = "✅";
      liveVerdictText.textContent = "HỢP LỆ (VALID)";
      liveVerdictText.style.color = "#10B981";
      liveVerdictSub.textContent = `Tỷ lệ đạt ${data.ratio_percent}% — vượt ngưỡng ${data.threshold_percent}%`;
    } else {
      liveVerdictIcon.textContent = "❌";
      liveVerdictText.textContent = "KHÔNG HỢP LỆ (INVALID)";
      liveVerdictText.style.color = "#F43F5E";
      liveVerdictSub.textContent = `Tỷ lệ chỉ đạt ${data.ratio_percent}% — dưới ngưỡng ${data.threshold_percent}%`;
    }

    btnLiveViewResults.classList.remove("hidden");
  }

  // Build result payload for renderResults()
  function buildResultFromSummary(data) {
    return {
      video_info: {
        path: data.original_video_url || "webcam_live",
        filename: `[Webcam Live] ${data.duration_sec}s`,
        fps: 25.0,
        total_frames: data.total_frames,
        resolution: "640x480",
        duration_seconds: data.duration_sec,
      },
      summary: {
        frames_analyzed: data.total_frames,
        frames_valid: data.valid_frames,
        frames_invalid: data.invalid_frames,
        frames_corrupted: 0,
        ratio_percent: data.ratio_percent,
        threshold_percent: data.threshold_percent,
        verdict: data.verdict,
        is_short_video_warning: data.total_frames < 10,
        is_valid: data.is_valid,
        debug_video_url: data.debug_video_url,
        original_video_url: data.original_video_url,
        report_url: data.report_url,
      },
      intervals_missing_hands: (data.violations || []).map((v, i) => ({
        start_frame: Math.floor(v.start_sec * 25),
        end_frame: Math.floor(v.end_sec * 25),
        start_time_sec: v.start_sec,
        end_time_sec: v.end_sec,
      })),
    };
  }

  // View full results from live session
  btnLiveViewResults.addEventListener("click", () => {
    if (!liveSessionResult) return;
    stopLiveStream();
    switchMode("upload");
    dropzoneCard.classList.add("hidden");
    progressCard.classList.add("hidden");
    renderResults(liveSessionResult);
  });

  // Scan another video
  btnScanAnother.addEventListener("click", () => {
    resultsContainer.classList.add("hidden");
    dropzoneCard.classList.remove("hidden");
    filePreviewBar.classList.add("hidden");
    selectedFile = null;
    videoFileInput.value = "";
    switchMode("upload");
    dropzoneCard.scrollIntoView({ behavior: "smooth" });
  });

  // History Loading
  async function loadHistory() {
    try {
      const res = await fetch("/api/history");
      if (!res.ok) return;
      const list = await res.json();
      historyTableBody.innerHTML = "";

      if (list.length === 0) {
        historyTableBody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">Chua co lich su quet</td></tr>`;
        return;
      }

      list.forEach((t) => {
        if (!t.result) return;
        const s = t.result.summary;
        const isOk = s.is_valid;
        const tr = document.createElement("tr");
        const timeStr = new Date(t.created_at * 1000).toLocaleTimeString("vi-VN", {
          hour: "2-digit",
          minute: "2-digit",
        });

        tr.innerHTML = `
          <td><b>${t.filename}</b></td>
          <td>${timeStr}</td>
          <td><span class="value-badge">${s.ratio_percent}%</span></td>
          <td>${s.threshold_percent}%</td>
          <td>
            <span class="badge-verdict ${isOk ? "valid" : "invalid"}">
              ${isOk ? "HOP LE" : "KHONG DAT"}
            </span>
          </td>
          <td>
            <button class="btn btn-sm btn-outline btn-view-hist" data-task-id="${t.task_id}">Xem</button>
          </td>
        `;
        historyTableBody.appendChild(tr);
      });

      document.querySelectorAll(".btn-view-hist").forEach((btn) => {
        btn.addEventListener("click", () => {
          const tid = btn.getAttribute("data-task-id");
          const found = list.find((item) => item.task_id === tid);
          if (found && found.result) {
            switchMode("upload");
            dropzoneCard.classList.add("hidden");
            renderResults(found.result);
          }
        });
      });
    } catch (e) {
      console.error("Loi nap lich su:", e);
    }
  }

});

