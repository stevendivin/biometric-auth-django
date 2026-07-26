// Records a short audio clip via MediaRecorder and posts it either to the
// enrollment endpoint (register.html) or the verification endpoint
// (voice_capture.html), one word per request.

(function () {
  const recordBtn = document.getElementById("record-btn");
  if (!recordBtn) return;

  let mediaRecorder, chunks = [];
  let wordIndex = 0;

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

    if (window.VOICE_VERIFY_MODE) {
      const status = document.getElementById("voice-status");
      status.textContent = "Vérification…";
      const res = await fetch(window.VOICE_VERIFY_URL, { method: "POST", body: form });
      const data = await res.json();

      if (data.status === "next") {
        document.getElementById("current-word").textContent = data.word;
        status.textContent = "✅ Mot validé, au suivant";
      } else if (data.status === "success") {
        status.textContent = "✅ Voix reconnue, connexion…";
        window.location.href = "/dashboard/";
      } else if (data.status === "retry") {
        status.textContent = `❌ Non reconnu, ${data.attempts_left} essai(s) restant(s)`;
      } else {
        status.textContent = "❌ Échec de la vérification vocale";
      }
    } else {
      form.append("word", window.VOICE_WORDS[wordIndex]);
      const res = await fetch(window.ENROLL_VOICE_URL, { method: "POST", body: form });
      const data = await res.json();
      wordIndex++;
      document.getElementById("voice-status").textContent = `${data.count}/3 mots enregistrés`;
      if (wordIndex < window.VOICE_WORDS.length) {
        document.getElementById("current-word").textContent = window.VOICE_WORDS[wordIndex];
      } else {
        document.getElementById("current-word").textContent = "✅ Terminé";
        recordBtn.disabled = true;
      }
    }
  }

  function getCsrfToken() {
    return document.querySelector("[name=csrfmiddlewaretoken]").value;
  }
})();
