let faceMesh;
let camera;
let canvasCtx;
let screenWidth = window.innerWidth;
let screenHeight = window.innerHeight;

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

    if (results.multiFaceLandmarks) {
        for (const landmarks of results.multiFaceLandmarks) {
            // Calculate head position and rotation
            const position = calculateHeadPosition(landmarks);
            const rotation = calculateHeadRotation(landmarks);
            
            // Calculate gaze direction and screen intersection
            const gazeIntersection = calculateGazeIntersection(landmarks);

            // Update UI
            document.getElementById('position').textContent = 
                `X: ${position.x.toFixed(2)}, Y: ${position.y.toFixed(2)}, Z: ${position.z.toFixed(2)}`;
            document.getElementById('rotation').textContent = 
                `X: ${rotation.x.toFixed(2)}°, Y: ${rotation.y.toFixed(2)}°, Z: ${rotation.z.toFixed(2)}°`;
            document.getElementById('gaze_coords').textContent = 
                `X: ${gazeIntersection.x.toFixed(2)}, Y: ${gazeIntersection.y.toFixed(2)}`;

            // Update gaze point indicator
            updateGazePointPosition(gazeIntersection.x, gazeIntersection.y);

            // Draw face mesh
            drawConnectors(canvasCtx, landmarks, FACEMESH_TESSELATION, 
                {color: '#C0C0C070', lineWidth: 1});
            drawConnectors(canvasCtx, landmarks, FACEMESH_RIGHT_EYE, 
                {color: '#FF3030'});
            drawConnectors(canvasCtx, landmarks, FACEMESH_LEFT_EYE, 
                {color: '#30FF30'});
            
            // Draw gaze vectors
            drawGazeVectors(landmarks);
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

// Calculate gaze direction and screen intersection
function calculateGazeIntersection(landmarks) {
    // Eye landmarks
    const leftIris = landmarks[468];  // MediaPipe iris center point
    const rightIris = landmarks[473];
    const leftEyeOuter = landmarks[33];
    const rightEyeOuter = landmarks[263];
    const leftEyeInner = landmarks[133];
    const rightEyeInner = landmarks[362];

    // Calculate gaze direction vectors for both eyes
    const leftGazeVector = calculateEyeGazeVector(leftIris, leftEyeInner, leftEyeOuter);
    const rightGazeVector = calculateEyeGazeVector(rightIris, rightEyeInner, rightEyeOuter);

    // Average the gaze vectors and apply scaling
    const gazeScalingFactor = 2.0;  // Increased sensitivity for eye movement
    const avgGazeVector = {
        x: (leftGazeVector.x + rightGazeVector.x) / 2 * gazeScalingFactor,
        y: (leftGazeVector.y + rightGazeVector.y) / 2 * gazeScalingFactor,
        z: (leftGazeVector.z + rightGazeVector.z) / 2
    };

    // Calculate screen intersection
    const eyeMidpoint = {
        x: (leftIris.x + rightIris.x) / 2,
        y: (leftIris.y + rightIris.y) / 2,
        z: (leftIris.z + rightIris.z) / 2
    };

    // Project gaze vector to screen (assumed to be at z=0)
    const t = -eyeMidpoint.z / avgGazeVector.z;
    const intersectionX = eyeMidpoint.x + avgGazeVector.x * t;
    const intersectionY = eyeMidpoint.y + avgGazeVector.y * t;

    // Convert to screen coordinates
    return {
        x: intersectionX * screenWidth,
        y: intersectionY * screenHeight
    };
}

// Calculate gaze vector for a single eye
function calculateEyeGazeVector(iris, inner, outer) {
    // Calculate eye width for normalization
    const eyeWidth = Math.sqrt(
        Math.pow(outer.x - inner.x, 2) +
        Math.pow(outer.y - inner.y, 2) +
        Math.pow(outer.z - inner.z, 2)
    );

    // Calculate iris position relative to eye center
    const irisOffset = {
        x: (iris.x - (inner.x + outer.x) / 2) / eyeWidth,
        y: (iris.y - (inner.y + outer.y) / 2) / eyeWidth,
        z: (iris.z - (inner.z + outer.z) / 2) / eyeWidth
    };

    // Normalize vector
    const magnitude = Math.sqrt(
        irisOffset.x * irisOffset.x +
        irisOffset.y * irisOffset.y +
        irisOffset.z * irisOffset.z
    );

    return {
        x: -(irisOffset.x / magnitude),  // Invert X to correct left-right reversal
        y: irisOffset.y / magnitude,
        z: irisOffset.z / magnitude
    };
}

// Draw gaze vectors for visualization
function drawGazeVectors(landmarks) {
    const leftIris = landmarks[468];
    const rightIris = landmarks[473];
    const scale = 50;  // Length of the visualization line

    const leftVector = calculateEyeGazeVector(
        leftIris,
        landmarks[133],
        landmarks[33]
    );

    const rightVector = calculateEyeGazeVector(
        rightIris,
        landmarks[362],
        landmarks[263]
    );

    // Draw left eye gaze vector
    canvasCtx.beginPath();
    canvasCtx.moveTo(
        leftIris.x * output_canvas.width,
        leftIris.y * output_canvas.height
    );
    canvasCtx.lineTo(
        (leftIris.x + leftVector.x * scale) * output_canvas.width,
        (leftIris.y + leftVector.y * scale) * output_canvas.height
    );
    canvasCtx.strokeStyle = '#00FF00';
    canvasCtx.stroke();

    // Draw right eye gaze vector
    canvasCtx.beginPath();
    canvasCtx.moveTo(
        rightIris.x * output_canvas.width,
        rightIris.y * output_canvas.height
    );
    canvasCtx.lineTo(
        (rightIris.x + rightVector.x * scale) * output_canvas.width,
        (rightIris.y + rightVector.y * scale) * output_canvas.height
    );
    canvasCtx.strokeStyle = '#00FF00';
    canvasCtx.stroke();
}

// Update the position of the gaze point indicator
function updateGazePointPosition(x, y) {
    const gazePoint = document.getElementById('gaze_point');
    gazePoint.style.left = `${x}px`;
    gazePoint.style.top = `${y}px`;
}

// Initialize camera and canvas
async function initCamera() {
    const video = document.getElementById('video');
    const canvas = document.getElementById('output_canvas');
    canvasCtx = canvas.getContext('2d');

    // Apply transform styles programmatically
    video.style.setProperty('transform', 'scaleX(-1)', 'important');
    video.style.setProperty('-webkit-transform', 'scaleX(-1)', 'important');
    video.style.setProperty('transform', 'scaleX(-1)', 'important');  // Apply twice to ensure it sticks

    camera = new Camera(video, {
        onFrame: async () => {
            // Apply transform after stream starts
            if (!video.style.transform) {
                video.style.setProperty('transform', 'scaleX(-1)', 'important');
                video.style.setProperty('-webkit-transform', 'scaleX(-1)', 'important');
            }
            await faceMesh.send({image: video});
        },
        width: 640,
        height: 480
    });

    await camera.start();
}

// Handle window resize
window.addEventListener('resize', () => {
    screenWidth = window.innerWidth;
    screenHeight = window.innerHeight;
});

// Start everything
document.addEventListener('DOMContentLoaded', () => {
    initFaceMesh();
    initCamera();
});
