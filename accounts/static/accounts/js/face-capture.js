// static/accounts/js/face-capture.js

let stream = null;
let videoElement = null;
let canvasElement = null;
let capturedImageData = null;

// Initialisation des éléments DOM (appelée une fois le DOM chargé)
function initFaceCapture() {
    videoElement = document.getElementById('video');
    canvasElement = document.createElement('canvas');
    canvasElement.style.display = 'none';
    document.body.appendChild(canvasElement);

    // Le bouton de capture déclenche la prise de vue
    const captureBtn = document.getElementById('capture-face-btn');
    if (captureBtn) {
        captureBtn.addEventListener('click', captureFace);
    }
}

// Démarrer la caméra
function startCamera() {
    if (stream) {
        // déjà en cours
        return;
    }
    if (!videoElement) {
        console.error('Video element not found');
        return;
    }
    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } })
        .then(s => {
            stream = s;
            videoElement.srcObject = stream;
            videoElement.play();
            document.getElementById('face-status').textContent = 'Caméra active';
        })
        .catch(err => {
            console.error('Erreur d\'accès à la caméra :', err);
            document.getElementById('face-status').textContent = 'Erreur caméra : ' + err.message;
        });
}

// Arrêter la caméra
function stopCamera() {
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
    }
    if (videoElement) {
        videoElement.srcObject = null;
        videoElement.pause();
    }
    // Réinitialiser l'image capturée
    capturedImageData = null;
    document.getElementById('face_image_data').value = '';
    document.getElementById('face-status').textContent = 'Caméra arrêtée';
}

// Capturer une photo et la stocker en base64
function captureFace() {
    if (!videoElement || !stream) {
        document.getElementById('face-status').textContent = 'Veuillez d\'abord activer la caméra';
        return;
    }
    // Vérifier que la vidéo a une image
    if (videoElement.readyState < 2) {
        document.getElementById('face-status').textContent = 'Vidéo pas encore prête, réessayez';
        return;
    }

    const canvas = canvasElement;
    const context = canvas.getContext('2d');
    canvas.width = videoElement.videoWidth;
    canvas.height = videoElement.videoHeight;
    context.drawImage(videoElement, 0, 0, canvas.width, canvas.height);

    // Convertir en base64 (format PNG)
    const dataUrl = canvas.toDataURL('image/png');
    capturedImageData = dataUrl;
    document.getElementById('face_image_data').value = dataUrl;
    document.getElementById('face-status').textContent = 'Visage capturé !';
}

// Initialiser au chargement du DOM
document.addEventListener('DOMContentLoaded', initFaceCapture);

// Exposer les fonctions globalement pour les utiliser depuis le template
window.startCamera = startCamera;
window.stopCamera = stopCamera;
window.captureFace = captureFace;