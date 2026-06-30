// ---------------------------------------------------------------------------
// Interface de test pour l'API d'authentification biométrique.
// Tout se passe en mémoire navigateur : pas de stockage local des
// images/audio, juste capture -> encodage base64 -> envoi -> suppression.
// ---------------------------------------------------------------------------

function getCookie(name) {
    const match = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return match ? decodeURIComponent(match.pop()) : "";
}
const CSRF_TOKEN = getCookie("csrftoken");

function log(message, ok = null) {
    const el = document.getElementById("log");
    const badge = ok === null ? "" : ok ? '<span class="badge ok">OK</span> ' : '<span class="badge ko">ÉCHEC</span> ';
    const time = new Date().toLocaleTimeString();
    el.innerHTML = `[${time}] ${badge}${message}\n` + el.innerHTML;
}

async function postJSON(url, data) {
    const res = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": CSRF_TOKEN,
        },
        credentials: "same-origin",
        body: JSON.stringify(data),
    });
    let body;
    try {
        body = await res.json();
    } catch {
        body = { detail: "Réponse non-JSON (erreur serveur probable)." };
    }
    return { ok: res.ok, status: res.status, body };
}

// --- Caméra / visage --------------------------------------------------------

const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");
let cameraStream = null;

document.getElementById("btnStartCam").addEventListener("click", async () => {
    try {
        cameraStream = await navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240 } });
        video.srcObject = cameraStream;
        document.getElementById("btnEnrollFace").disabled = false;
        document.getElementById("btnVerifyFace").disabled = false;
        log("Caméra activée.");
    } catch (err) {
        log("Impossible d'accéder à la caméra : " + err.message, false);
    }
});

function captureFrameBase64() {
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
    return dataUrl.split(",")[1]; // retire le préfixe "data:image/jpeg;base64,"
}

document.getElementById("btnEnrollFace").addEventListener("click", async () => {
    if (!document.getElementById("faceConsent").checked) {
        log("Consentement requis avant l'enrôlement du visage.", false);
        return;
    }
    const frame = captureFrameBase64();
    const { ok, body } = await postJSON("/api/biometrics/enroll/face/", { frame, consent: true });
    log("Enrôlement visage : " + (body.detail || JSON.stringify(body)), ok);
});

document.getElementById("btnVerifyFace").addEventListener("click", async () => {
    const start = await postJSON("/api/biometrics/challenge/face/start/", {});
    if (!start.ok) {
        log("Échec démarrage challenge visage : " + (start.body.detail || ""), false);
        return;
    }
    const { challenge_id, gesture } = start.body;
    const gestureLabels = {
        BLINK_TWICE: "👁️ Clignez des yeux deux fois",
        TURN_HEAD_LEFT: "⬅️ Tournez la tête à GAUCHE",
        TURN_HEAD_RIGHT: "➡️ Tournez la tête à DROITE",
        SMILE: "😊 Souriez",
        NOD: "↕️ Hochez la tête",
    };
    const gestureEl = document.getElementById("faceGesture");
    gestureEl.textContent = gestureLabels[gesture] || gesture;
    log("Challenge reçu : " + gesture + ". Exécutez le geste maintenant...");

    // Capture une rafale de frames pendant ~2.5s pour laisser le temps d'exécuter le geste.
    const frames = [];
    const captureDurationMs = 2500;
    const intervalMs = 120;
    const steps = Math.floor(captureDurationMs / intervalMs);
    for (let i = 0; i < steps; i++) {
        frames.push(captureFrameBase64());
        await new Promise((r) => setTimeout(r, intervalMs));
    }
    gestureEl.textContent = "";

    const verify = await postJSON("/api/biometrics/challenge/face/verify/", { challenge_id, frames });
    log("Vérification visage : " + (verify.body.detail || JSON.stringify(verify.body)) +
        (verify.body.score !== undefined ? ` (score=${verify.body.score.toFixed(3)})` : ""), verify.ok);
});

// --- Micro / voix : enregistrement WAV PCM 16-bit ---------------------------

async function recordWavBase64(durationMs = 4000) {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioCtx.createMediaStreamSource(stream);
    const processor = audioCtx.createScriptProcessor(4096, 1, 1);
    const chunks = [];

    source.connect(processor);
    processor.connect(audioCtx.destination);

    document.getElementById("recIndicator").textContent = "🔴 Enregistrement en cours...";

    processor.onaudioprocess = (e) => {
        chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
    };

    await new Promise((r) => setTimeout(r, durationMs));

    processor.disconnect();
    source.disconnect();
    stream.getTracks().forEach((t) => t.stop());
    document.getElementById("recIndicator").textContent = "";

    const totalLength = chunks.reduce((sum, c) => sum + c.length, 0);
    const merged = new Float32Array(totalLength);
    let offset = 0;
    for (const c of chunks) {
        merged.set(c, offset);
        offset += c.length;
    }

    const wavBlob = encodeWAV(merged, audioCtx.sampleRate);
    await audioCtx.close();
    return await blobToBase64(wavBlob);
}

function encodeWAV(samples, sampleRate) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    const writeString = (offset, str) => {
        for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
    };

    writeString(0, "RIFF");
    view.setUint32(4, 36 + samples.length * 2, true);
    writeString(8, "WAVE");
    writeString(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true); // PCM
    view.setUint16(22, 1, true); // mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeString(36, "data");
    view.setUint32(40, samples.length * 2, true);

    let pos = 44;
    for (let i = 0; i < samples.length; i++, pos += 2) {
        const s = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(pos, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }

    return new Blob([view], { type: "audio/wav" });
}

function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result.split(",")[1]);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });
}

document.getElementById("btnEnrollVoice").addEventListener("click", async () => {
    if (!document.getElementById("voiceConsent").checked) {
        log("Consentement requis avant l'enrôlement de la voix.", false);
        return;
    }
    try {
        log("Parlez normalement pendant 4 secondes...");
        const audio = await recordWavBase64(4000);
        const { ok, body } = await postJSON("/api/biometrics/enroll/voice/", { audio, consent: true });
        log("Enrôlement voix : " + (body.detail || JSON.stringify(body)), ok);
    } catch (err) {
        log("Erreur micro : " + err.message, false);
    }
});

document.getElementById("btnVerifyVoice").addEventListener("click", async () => {
    const start = await postJSON("/api/biometrics/challenge/voice/start/", {});
    if (!start.ok) {
        log("Échec démarrage challenge voix : " + (start.body.detail || ""), false);
        return;
    }
    const { challenge_id, say_these_digits } = start.body;
    const challengeEl = document.getElementById("voiceChallenge");
    challengeEl.textContent = "Dites : " + say_these_digits;
    log("Challenge vocal reçu : " + say_these_digits);

    try {
        const audio = await recordWavBase64(4000);
        challengeEl.textContent = "";
        const verify = await postJSON("/api/biometrics/challenge/voice/verify/", { challenge_id, audio });
        log("Vérification voix : " + (verify.body.detail || JSON.stringify(verify.body)) +
            (verify.body.score !== undefined ? ` (score=${verify.body.score.toFixed(3)})` : ""), verify.ok);
    } catch (err) {
        log("Erreur micro : " + err.message, false);
    }
});
