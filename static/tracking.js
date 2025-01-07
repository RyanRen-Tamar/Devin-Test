let faceMesh;
let camera;
let canvasCtx;

// Initialize the FaceMesh solution
function initFaceMesh() {
    faceMesh = new FaceMesh({
        locateFile: (file) => {
            return `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`;
        }
    });

    faceMesh.setOptions({
        maxNumFaces: 1,
        refineLandmarks: true,
        minDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5
    });

    faceMesh.onResults(onResults);
}

// Process results from FaceMesh
function onResults(results) {
    canvasCtx.save();
    canvasCtx.clearRect(0, 0, output_canvas.width, output_canvas.height);
    canvasCtx.drawImage(results.image, 0, 0, output_canvas.width, output_canvas.height);

    // Ensure video is mirrored
    const video = document.getElementById('video');
    if (!video.style.transform) {
        video.style.transform = 'scaleX(-1)';
        video.style.webkitTransform = 'scaleX(-1)';
    }

    if (results.multiFaceLandmarks) {
        for (const landmarks of results.multiFaceLandmarks) {
            // Calculate head position and rotation
            const position = calculateHeadPosition(landmarks);
            const rotation = calculateHeadRotation(landmarks);

            // Update UI
            document.getElementById('position').textContent = 
                `X: ${position.x.toFixed(2)}, Y: ${position.y.toFixed(2)}, Z: ${position.z.toFixed(2)}`;
            document.getElementById('rotation').textContent = 
                `X: ${rotation.x.toFixed(2)}°, Y: ${rotation.y.toFixed(2)}°, Z: ${rotation.z.toFixed(2)}°`;

            // Draw face mesh
            drawConnectors(canvasCtx, landmarks, FACEMESH_TESSELATION, 
                {color: '#C0C0C070', lineWidth: 1});
            drawConnectors(canvasCtx, landmarks, FACEMESH_RIGHT_EYE, 
                {color: '#FF3030'});
            drawConnectors(canvasCtx, landmarks, FACEMESH_LEFT_EYE, 
                {color: '#30FF30'});
        }
    }
    canvasCtx.restore();
}

// Calculate head position relative to screen
function calculateHeadPosition(landmarks) {
    // Use nose tip (point 1) as reference
    const nose = landmarks[1];
    
    // Convert to screen space coordinates
    // Note: MediaPipe coordinates are normalized (0-1)
    return {
        x: (nose.x - 0.5) * output_canvas.width,  // Left-right
        y: (nose.y - 0.5) * output_canvas.height, // Up-down
        z: nose.z * -1000                         // Forward-backward
    };
}

// Calculate head rotation in degrees
function calculateHeadRotation(landmarks) {
    // Use key facial points to calculate rotation
    const nose = landmarks[1];
    const leftEye = landmarks[33];
    const rightEye = landmarks[263];
    const leftMouth = landmarks[57];
    const rightMouth = landmarks[287];

    // Calculate rotation angles
    const pitch = Math.atan2(nose.y - (leftEye.y + rightEye.y) / 2, 
                            nose.z - (leftEye.z + rightEye.z) / 2) * 180 / Math.PI;
    const yaw = Math.atan2(nose.x - (leftEye.x + rightEye.x) / 2,
                          nose.z - (leftEye.z + rightEye.z) / 2) * 180 / Math.PI;
    const roll = Math.atan2(rightEye.y - leftEye.y, 
                           rightEye.x - leftEye.x) * 180 / Math.PI;

    return {
        x: pitch,  // Up-down rotation
        y: yaw,    // Left-right rotation
        z: roll    // Tilt rotation
    };
}

// Initialize camera and canvas
async function initCamera() {
    const video = document.getElementById('video');
    // Apply horizontal flip to video element
    video.style.transform = 'scaleX(-1)';
    video.style.webkitTransform = 'scaleX(-1)';
    
    const canvas = document.getElementById('output_canvas');
    canvasCtx = canvas.getContext('2d');

    // Apply transform styles before camera initialization
    video.style.setProperty('transform', 'scaleX(-1)', 'important');
    video.style.setProperty('-webkit-transform', 'scaleX(-1)', 'important');
    
    camera = new Camera(video, {
        onFrame: async () => {
            await faceMesh.send({image: video});
        },
        width: 640,
        height: 480
    });

    await camera.start();
}

// Start everything
document.addEventListener('DOMContentLoaded', () => {
    initFaceMesh();
    initCamera();
});
