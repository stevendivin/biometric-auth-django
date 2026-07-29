// Used only by voice_capture.html (login verification). Voice ENROLLMENT is
// now handled by the inline script in register.html, which captures a single
// clip and stores it as a base64 hidden field on the main form instead of
// posting per-word clips here.

(function () {
  const recordBtn = document.getElementById("record-btn");
  if (!recordBtn) return;

  let mediaRecorder, chunks = [];

  recordBtn.addEventListener("click", async () => {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
      recordBtn.textContent = "🎙️ Enregistrer";
      return;
    }

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    chunks = [];

    mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
    mediaRecorder.onstop = async () => {
      const blob = new Blob(chunks, { type: "audio/webm" });
      await submitClip(blob);
    };

    mediaRecorder.start();
    recordBtn.textContent = "⏹️ Arrêter";
  });

  async function submitClip(blob) {
    const form = new FormData();
    form.append("audio", blob, "clip.webm");
    form.append("csrfmiddlewaretoken", getCsrfToken());

    const status = document.getElementById("voice-status");
    status.textContent = "Vérification…";
    const res = await fetch(window.VOICE_VERIFY_URL, { method: "POST", body: form });
    const data = await res.json();

    if (data.status === "success") {
      status.textContent = "✅ Voix reconnue, connexion…";
      window.location.href = "/dashboard/";
    } else if (data.status === "retry") {
      status.textContent = `❌ Non reconnu, ${data.attempts_left} essai(s) restant(s)`;
    } else {
      status.textContent = "❌ Échec de la vérification vocale";
    }
  }

  function getCsrfToken() {
    return document.querySelector("[name=csrfmiddlewaretoken]").value;
  }
})();