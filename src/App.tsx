import React, { useEffect, useRef, useState } from 'react';
import { Camera } from '@mediapipe/camera_utils';
import { FaceMesh, FACEMESH_LEFT_EYE, FACEMESH_RIGHT_EYE, FACEMESH_FACE_OVAL } from '@mediapipe/face_mesh';
import { drawConnectors } from '@mediapipe/drawing_utils';
import './App.css';

// Constants for iris landmarks
const LEFT_IRIS_CENTER = 468;
const LEFT_IRIS_LANDMARKS = [469, 470, 471, 472];
const RIGHT_IRIS_CENTER = 473;
const RIGHT_IRIS_LANDMARKS = [474, 475, 476, 477];

interface EyeData {
  irisCenter: { x: number; y: number; z: number };
  irisLandmarks: Array<{ x: number; y: number; z: number }>;
  rotation: { x: number; y: number; z: number };
  confidence: number;
}

interface GazePoint {
  x: number;
  y: number;
  confidence: number;
}

function App() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isTracking, setIsTracking] = useState(false);
  const [debugInfo, setDebugInfo] = useState<string>('');

  useEffect(() => {
    if (!videoRef.current || !canvasRef.current) return;

    const faceMesh = new FaceMesh({
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

    faceMesh.onResults((results) => {
      if (!results.multiFaceLandmarks?.[0]) return;

      const face = results.multiFaceLandmarks[0];
      const canvas = canvasRef.current!;
      const ctx = canvas.getContext('2d')!;

      // Clear canvas
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Draw face mesh for debugging
      drawConnectors(ctx, face, FACEMESH_FACE_OVAL, { color: '#E0E0E0' });
      drawConnectors(ctx, face, FACEMESH_LEFT_EYE, { color: '#30FF30' });
      drawConnectors(ctx, face, FACEMESH_RIGHT_EYE, { color: '#30FF30' });

      // Calculate eye data with precise iris tracking
      const leftEye = calculateEyeData(face, true);
      const rightEye = calculateEyeData(face, false);

      // Calculate head pose for compensation
      const headPose = calculateHeadPose(face);

      // Calculate final gaze point
      if (isTracking) {
        const gazePoint = calculateGazePoint(leftEye, rightEye, headPose);
        updateCursorPosition(gazePoint);

        // Update debug information
        setDebugInfo(JSON.stringify({
          leftEye: {
            rotation: leftEye.rotation,
            confidence: leftEye.confidence
          },
          rightEye: {
            rotation: rightEye.rotation,
            confidence: rightEye.confidence
          },
          headPose,
          gazePoint
        }, null, 2));
      }
    });

    const camera = new Camera(videoRef.current, {
      onFrame: async () => {
        if (videoRef.current) {
          await faceMesh.send({ image: videoRef.current });
        }
      },
      width: 640,
      height: 480
    });

    camera.start();

    return () => {
      camera.stop();
      faceMesh.close();
    };
  }, [isTracking]);

  const calculateEyeData = (face: any, isLeft: boolean): EyeData => {
    const irisCenter = isLeft ? face[LEFT_IRIS_CENTER] : face[RIGHT_IRIS_CENTER];
    const irisLandmarks = (isLeft ? LEFT_IRIS_LANDMARKS : RIGHT_IRIS_LANDMARKS)
      .map((index: number) => face[index]);

    // Calculate eye rotation using iris outline
    const rotation = calculateEyeRotation(irisCenter, irisLandmarks);
    
    // Calculate confidence based on iris visibility
    const confidence = calculateConfidence(irisCenter, irisLandmarks);

    return {
      irisCenter,
      irisLandmarks,
      rotation,
      confidence
    };
  };

  const calculateEyeRotation = (
    center: { x: number; y: number; z: number },
    landmarks: Array<{ x: number; y: number; z: number }>
  ) => {
    // Calculate vectors from center to each landmark
    const vectors = landmarks.map(point => ({
      x: point.x - center.x,
      y: point.y - center.y,
      z: point.z - center.z
    }));

    // Filter out zero-magnitude vectors
    const validVectors = vectors.filter(v => {
      const magnitude = Math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z);
      return magnitude > 0.0001;
    });

    if (validVectors.length < 2) {
      console.warn('Not enough valid vectors for rotation calculation');
      return { x: 0, y: 0, z: 0 };
    }

    // Calculate rotation using cross product of two vectors
    const v1 = validVectors[0];
    const v2 = validVectors[1];
    
    const normal = {
      x: v1.y * v2.z - v1.z * v2.y,
      y: v1.z * v2.x - v1.x * v2.z,
      z: v1.x * v2.y - v1.y * v2.x
    };

    const magnitude = Math.sqrt(
      normal.x * normal.x + normal.y * normal.y + normal.z * normal.z
    );

    if (magnitude < 0.0001) {
      console.warn('Invalid rotation calculation - zero magnitude normal');
      return { x: 0, y: 0, z: 0 };
    }

    // Convert to rotation angles
    return {
      x: Math.atan2(normal.x, magnitude),
      y: Math.atan2(normal.y, magnitude),
      z: Math.atan2(normal.z, magnitude)
    };
  };

  const calculateConfidence = (
    center: { x: number; y: number; z: number },
    landmarks: Array<{ x: number; y: number; z: number }>
  ): number => {
    // Calculate average distance from center to landmarks
    const distances = landmarks.map(point => {
      const dx = point.x - center.x;
      const dy = point.y - center.y;
      const dz = point.z - center.z;
      return Math.sqrt(dx * dx + dy * dy + dz * dz);
    });

    const mean = distances.reduce((a, b) => a + b, 0) / distances.length;
    const variance = distances.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / distances.length;

    // Higher variance indicates less reliable tracking
    return Math.exp(-variance * 100);
  };

  const calculateHeadPose = (face: any) => {
    // Use stable facial landmarks for head pose
    const nose = face[1];  // Nose tip
    const leftEye = face[33];  // Left eye outer corner
    const rightEye = face[263];  // Right eye outer corner
    const chin = face[152];  // Chin center

    // Calculate face normal using cross product
    const v1 = {
      x: rightEye.x - leftEye.x,
      y: rightEye.y - leftEye.y,
      z: rightEye.z - leftEye.z
    };

    const v2 = {
      x: chin.x - nose.x,
      y: chin.y - nose.y,
      z: chin.z - nose.z
    };

    const normal = {
      x: v1.y * v2.z - v1.z * v2.y,
      y: v1.z * v2.x - v1.x * v2.z,
      z: v1.x * v2.y - v1.y * v2.x
    };

    const magnitude = Math.sqrt(
      normal.x * normal.x + normal.y * normal.y + normal.z * normal.z
    );

    if (magnitude < 0.0001) {
      console.warn('Invalid head pose calculation');
      return { x: 0, y: 0, z: 0 };
    }

    return {
      x: normal.x / magnitude,
      y: normal.y / magnitude,
      z: normal.z / magnitude
    };
  };

  const calculateGazePoint = (
    leftEye: EyeData,
    rightEye: EyeData,
    headPose: { x: number; y: number; z: number }
  ): GazePoint => {
    // Combine eye rotations weighted by confidence
    const totalConfidence = leftEye.confidence + rightEye.confidence;
    const weightedRotation = {
      x: (leftEye.rotation.x * leftEye.confidence + rightEye.rotation.x * rightEye.confidence) / totalConfidence,
      y: (leftEye.rotation.y * leftEye.confidence + rightEye.rotation.y * rightEye.confidence) / totalConfidence,
      z: (leftEye.rotation.z * leftEye.confidence + rightEye.rotation.z * rightEye.confidence) / totalConfidence
    };

    // Compensate for head pose
    const compensatedRotation = {
      x: weightedRotation.x - headPose.x,
      y: weightedRotation.y - headPose.y,
      z: weightedRotation.z - headPose.z
    };

    // Map rotation to screen coordinates
    return {
      x: (compensatedRotation.x + 1) * window.innerWidth / 2,
      y: (compensatedRotation.y + 1) * window.innerHeight / 2,
      confidence: Math.min(leftEye.confidence, rightEye.confidence)
    };
  };

  const updateCursorPosition = (point: GazePoint) => {
    // Log gaze point for debugging
    console.log('Gaze point:', point);
  };

  return (
    <div className="App">
      <video
        ref={videoRef}
        style={{ display: 'none' }}
      />
      <canvas
        ref={canvasRef}
        width={640}
        height={480}
        style={{ border: '1px solid black' }}
      />
      <div className="controls">
        <button onClick={() => setIsTracking(!isTracking)}>
          {isTracking ? 'Stop Tracking' : 'Start Tracking'}
        </button>
        <pre className="debug-info">
          {debugInfo}
        </pre>
      </div>
    </div>
  );
}

export default App;
