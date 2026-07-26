// Handles webcam access + a snapshot capture, used both at enrollment
// (register.html) and at verification time (face_capture.html).
// The blink-liveness challenge itself runs via MediaPipe Face Landmarker,
// loaded from a CDN so the project needs no local model download step.

(async function () {
  const video = document.getElementById("video");
  if (!video) return;

  const stream = await navigator.mediaDevices.getUserMedia({ video: true });
  video.srcObject = stream;

  function snapshotAsBase64() {
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    return canvas.toDataURL("image/jpeg", 0.9);
  }

  const captureBtn = document.getElementById("capture-face-btn");
  if (!captureBtn) return;

  captureBtn.addEventListener("click", async () => {
    const imageData = snapshotAsBase64();
    const status = document.getElementById("face-status");

    if (window.FACE_VERIFY_MODE) {
      status.textContent = "Vérification en cours…";
      const form = new FormData();
      form.append("face_image_data", imageData);
      form.append("csrfmiddlewaretoken", getCsrfToken());

      const res = await fetch(window.FACE_VERIFY_URL, { method: "POST", body: form });
      const data = await res.json();
      if (data.match) {
        status.textContent = "✅ Visage reconnu, connexion…";
        window.location.href = "/dashboard/";
      } else {
        status.textContent = "❌ Visage non reconnu (" + (data.error || "score insuffisant") + ")";
      }
    } else {
      // Enrollment mode: just stash the snapshot for the register form to submit
      document.getElementById("face_image_data").value = imageData;
      status.textContent = "✅ Visage capturé";
    }
  });

  function getCsrfToken() {
    return document.querySelector("[name=csrfmiddlewaretoken]").value;
  }
})();
