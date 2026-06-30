// ---------------------------------------------------------------------------
// Assistant d'enrôlement biométrique obligatoire.
// Étape 1 : consentement. Étape 2 : visage (5 gestes, un par un).
// Étape 3 : voix (5 chiffres, un par un). À chaque échec de validation
// serveur, la séquence concernée est entièrement recommencée (simple et
// sans ambiguïté pour l'utilisateur).
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
        headers: { "Content-Type": "application/json", "X-CSRFToken": CSRF_TOKEN },
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

function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
}

async function runCountdown(el, seconds, finalText) {
    for (let s = seconds; s > 0; s--) {
        el.textContent = String(s);
        await sleep(1000);
    }
    el.textContent = finalText || "";
}

function setStep(stepId, state) {
    document.getElementById(stepId).className = "step " + state;
}

// --- Phase 1 : consentement -------------------------------------------------

const globalConsent = document.getElementById("globalConsent");
const btnStartEnroll = document.getElementById("btnStartEnroll");

globalConsent.addEventListener("change", () => {
    btnStartEnroll.disabled = !globalConsent.checked;
});

btnStartEnroll.addEventListener("click", () => {
    document.getElementById("phase-consent").style.display = "none";
    document.getElementById("phase-face").style.display = "block";
    setStep("step-consent", "done");
    setStep("step-face", "active");
    updateFaceUI();
});

// --- Phase 2 : visage --------------------------------------------------------

const GESTURE_SEQUENCE = ["TURN_HEAD_LEFT", "TURN_HEAD_RIGHT", "BLINK_TWICE", "SMILE", "NOD"];
const GESTURE_LABELS = {
    TURN_HEAD_LEFT: "⬅️ Tournez la tête à GAUCHE",
    TURN_HEAD_RIGHT: "➡️ Tournez la tête à DROITE",
    BLINK_TWICE: "👁️ Clignez des yeux deux fois",
    SMILE: "😊 Souriez",
    NOD: "↕️ Hochez la tête",
};

const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");
let faceCaptures = [];
let gestureIndex = 0;

document.getElementById("btnStartCam").addEventListener("click", async () => {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240 } });
        video.srcObject = stream;
        document.getElementById("btnStartGesture").disabled = false;
        log("Caméra activée.");
    } catch (err) {
        log("Impossible d'accéder à la caméra : " + err.message, false);
    }
});

function captureFrameBase64() {
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.85).split(",")[1];
}

function updateFaceUI() {
    document.getElementById("faceProgress").textContent =
        `Geste ${gestureIndex + 1} / ${GESTURE_SEQUENCE.length}`;
    document.getElementById("faceInstruction").textContent = GESTURE_LABELS[GESTURE_SEQUENCE[gestureIndex]];
}

document.getElementById("btnStartGesture").addEventListener("click", async () => {
    const btn = document.getElementById("btnStartGesture");
    btn.disabled = true;
    const countdownEl = document.getElementById("faceCountdown");

    await runCountdown(countdownEl, 3, "C'est parti !");
    await sleep(300);

    const gesture = GESTURE_SEQUENCE[gestureIndex];
    const frames = [];
    const steps = Math.round(2500 / 120);
    for (let i = 0; i < steps; i++) {
        frames.push(captureFrameBase64());
        await sleep(120);
    }
    countdownEl.textContent = "";

    faceCaptures.push({ gesture, frames });
    gestureIndex++;

    if (gestureIndex < GESTURE_SEQUENCE.length) {
        updateFaceUI();
        btn.disabled = false;
        log(`Geste "${gesture}" capturé (${gestureIndex}/${GESTURE_SEQUENCE.length}).`);
    } else {
        document.getElementById("faceInstruction").textContent = "Validation en cours...";
        log("Tous les gestes capturés, envoi pour validation...");
        const { ok, body } = await postJSON("/api/biometrics/enroll/face/guided/", {
            captures: faceCaptures,
            consent: true,
        });
        if (ok) {
            log("Enrôlement visage : " + body.detail, true);
            document.getElementById("phase-face").style.display = "none";
            document.getElementById("phase-voice").style.display = "block";
            setStep("step-face", "done");
            setStep("step-voice", "active");
            updateVoiceUI();
        } else {
            log("Enrôlement visage : " + (body.detail || "échec"), false);
            faceCaptures = [];
            gestureIndex = 0;
            updateFaceUI();
            btn.disabled = false;
            document.getElementById("faceInstruction").textContent =
                "Échec : " + (body.detail || "") + " — On recommence la séquence depuis le début.";
        }
    }
});

// --- Phase 3 : voix ----------------------------------------------------------

function randomDigits(n) {
    const digits = [];
    for (let i = 0; i < n; i++) digits.push(String(Math.floor(Math.random() * 10)));
    return digits;
}

const VOICE_DIGITS = randomDigits(5);
let digitIndex = 0;
let voiceRecordings = [];
let micStream = null;

document.getElementById("btnStartMic").addEventListener("click", async () => {
    try {
        micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        document.getElementById("btnStartDigit").disabled = false;
        log("Micro activé.");
    } catch (err) {
        log("Impossible d'accéder au micro : " + err.message, false);
    }
});

function updateVoiceUI() {
    document.getElementById("digitProgress").textContent =
        `Chiffre ${digitIndex + 1} / ${VOICE_DIGITS.length}`;
    document.getElementById("digitDisplay").textContent = VOICE_DIGITS[digitIndex];
}

function recordSegment(stream, durationMs) {
    return new Promise((resolve, reject) => {
        try {
            const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const source = audioCtx.createMediaStreamSource(stream);
            const processor = audioCtx.createScriptProcessor(4096, 1, 1);
            const chunks = [];

            source.connect(processor);
            processor.connect(audioCtx.destination);
            document.getElementById("recIndicator").textContent = "🔴 Enregistrement...";

            processor.onaudioprocess = (e) => chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));

            setTimeout(async () => {
                processor.disconnect();
                source.disconnect();
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
                const base64 = await blobToBase64(wavBlob);
                resolve(base64);
            }, durationMs);
        } catch (err) {
            reject(err);
        }
    });
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
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
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

document.getElementById("btnStartDigit").addEventListener("click", async () => {
    const btn = document.getElementById("btnStartDigit");
    btn.disabled = true;
    const countdownEl = document.getElementById("voiceCountdown");

    await runCountdown(countdownEl, 2, "Parlez maintenant !");

    const digit = VOICE_DIGITS[digitIndex];
    try {
        const audio = await recordSegment(micStream, 1600);
        countdownEl.textContent = "";
        voiceRecordings.push({ digit, audio });
        digitIndex++;

        if (digitIndex < VOICE_DIGITS.length) {
            updateVoiceUI();
            btn.disabled = false;
            log(`Chiffre "${digit}" enregistré (${digitIndex}/${VOICE_DIGITS.length}).`);
        } else {
            document.getElementById("digitDisplay").textContent = "...";
            log("Tous les chiffres enregistrés, envoi pour validation...");
            const { ok, body } = await postJSON("/api/biometrics/enroll/voice/guided/", {
                digit_recordings: voiceRecordings,
                consent: true,
            });
            if (ok) {
                log("Enrôlement voix : " + body.detail, true);
                if (micStream) micStream.getTracks().forEach((t) => t.stop());
                document.getElementById("phase-voice").style.display = "none";
                document.getElementById("phase-done").style.display = "block";
                setStep("step-voice", "done");
                setTimeout(() => { window.location.href = "/"; }, 1800);
            } else {
                log("Enrôlement voix : " + (body.detail || "échec"), false);
                voiceRecordings = [];
                digitIndex = 0;
                updateVoiceUI();
                btn.disabled = false;
                document.getElementById("digitDisplay").textContent =
                    VOICE_DIGITS[0] + " (recommencer)";
            }
        }
    } catch (err) {
        log("Erreur micro : " + err.message, false);
        btn.disabled = false;
    }
});
