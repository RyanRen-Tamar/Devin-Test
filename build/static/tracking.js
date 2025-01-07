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

            // Calculate gaze vector and screen intersection
            const gazeVector = calculateEyeGazeVector(landmarks);
            
            // Calculate screen intersection point
            // Assuming a virtual screen plane at z = -500 (adjust as needed)
            const screenZ = -500;
            const t = (screenZ - position.z) / gazeVector.z;
            const screenX = position.x + gazeVector.x * t;
            const screenY = position.y + gazeVector.y * t;
            
            // Update UI
            document.getElementById('position').textContent = 
                `X: ${position.x.toFixed(2)}, Y: ${position.y.toFixed(2)}, Z: ${position.z.toFixed(2)}`;
            document.getElementById('rotation').textContent = 
                `X: ${rotation.x.toFixed(2)}°, Y: ${rotation.y.toFixed(2)}°, Z: ${rotation.z.toFixed(2)}°`;
            document.getElementById('coordinates').innerHTML = 
                `Position: ${position.x.toFixed(2)}, ${position.y.toFixed(2)}, ${position.z.toFixed(2)}<br>
                 Rotation: ${rotation.x.toFixed(2)}°, ${rotation.y.toFixed(2)}°, ${rotation.z.toFixed(2)}°<br>
                 Gaze Point: ${screenX.toFixed(2)}, ${screenY.toFixed(2)}`;
            
            // Draw gaze point on canvas
            canvasCtx.beginPath();
            canvasCtx.arc(screenX + output_canvas.width/2, screenY + output_canvas.height/2, 5, 0, 2 * Math.PI);
            canvasCtx.fillStyle = 'red';
            canvasCtx.fill();
            
            // Draw gaze direction vector
            canvasCtx.beginPath();
            canvasCtx.moveTo(position.x + output_canvas.width/2, position.y + output_canvas.height/2);
            canvasCtx.lineTo(
                position.x + gazeVector.x * 100 + output_canvas.width/2,
                position.y + gazeVector.y * 100 + output_canvas.height/2
            );
            canvasCtx.strokeStyle = 'green';
            canvasCtx.lineWidth = 2;
            canvasCtx.stroke();
            
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
    // Since video is mirrored, we invert the x-coordinate calculation
    return {
        x: (0.5 - nose.x) * output_canvas.width,  // Left-right (inverted for mirrored video)
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
    // Invert yaw calculation for mirrored video
    const yaw = -Math.atan2(nose.x - (leftEye.x + rightEye.x) / 2,
                          nose.z - (leftEye.z + rightEye.z) / 2) * 180 / Math.PI;
    const roll = Math.atan2(rightEye.y - leftEye.y, 
                           rightEye.x - leftEye.x) * 180 / Math.PI;

    return {
        x: pitch,  // Up-down rotation
        y: yaw,    // Left-right rotation
        z: roll    // Tilt rotation
    };
}

// Calculate eye gaze direction vector
function calculateEyeGazeVector(landmarks) {
    // Use iris landmarks (468-478 for right eye, 473-477 for left eye)
    const leftIris = landmarks[473];
    const rightIris = landmarks[468];
    
    // Use eye corners as reference points
    const leftEyeLeft = landmarks[263];
    const leftEyeRight = landmarks[362];
    const rightEyeLeft = landmarks[133];
    const rightEyeRight = landmarks[33];
    
    // Calculate iris position relative to eye corners for both eyes
    const leftEyeCenter = {
        x: (leftEyeLeft.x + leftEyeRight.x) / 2,
        y: (leftEyeLeft.y + leftEyeRight.y) / 2,
        z: (leftEyeLeft.z + leftEyeRight.z) / 2
    };
    
    const rightEyeCenter = {
        x: (rightEyeLeft.x + rightEyeRight.x) / 2,
        y: (rightEyeLeft.y + rightEyeRight.y) / 2,
        z: (rightEyeLeft.z + rightEyeRight.z) / 2
    };
    
    // Calculate offset from eye center to iris for both eyes (with x-inversion for mirrored video)
    const leftIrisOffset = {
        x: -(leftIris.x - leftEyeCenter.x),  // Invert x-offset for mirrored video
        y: leftIris.y - leftEyeCenter.y,
        z: leftIris.z - leftEyeCenter.z
    };
    
    const rightIrisOffset = {
        x: -(rightIris.x - rightEyeCenter.x),  // Invert x-offset for mirrored video
        y: rightIris.y - rightEyeCenter.y,
        z: rightIris.z - rightEyeCenter.z
    };
    
    // Average the offsets from both eyes
    const avgOffset = {
        x: (leftIrisOffset.x + rightIrisOffset.x) / 2,
        y: (leftIrisOffset.y + rightIrisOffset.y) / 2,
        z: (leftIrisOffset.z + rightIrisOffset.z) / 2
    };
    
    // Normalize the vector
    const magnitude = Math.sqrt(
        avgOffset.x * avgOffset.x +
        avgOffset.y * avgOffset.y +
        avgOffset.z * avgOffset.z
    );
    
    // Return normalized gaze vector (note: no x-inversion since video is already mirrored)
    return {
        x: avgOffset.x / magnitude,
        y: avgOffset.y / magnitude,
        z: avgOffset.z / magnitude
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

    // Ensure video element has mirrored class
    video.classList.add('mirrored-video');
    
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
