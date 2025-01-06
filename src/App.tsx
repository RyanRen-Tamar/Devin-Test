import React, { useEffect, useRef, useState } from 'react';
import { Camera } from '@mediapipe/camera_utils';
import { FaceMesh } from '@mediapipe/face_mesh';

interface Point {
  x: number;
  y: number;
  z?: number;
}

interface CalibrationPoint extends Point {
  screenX: number;
  screenY: number;
  z: number;
}

const App: React.FC = () => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [error, setError] = useState<string>('');
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [calibrationPoints, setCalibrationPoints] = useState<CalibrationPoint[]>([]);
  const [calibrationComplete, setCalibrationComplete] = useState(false);
  const [calibrationMatrix, setCalibrationMatrix] = useState<number[][]>([]);
  const [currentCalibrationPoint, setCurrentCalibrationPoint] = useState(0);
  const [debugValues, setDebugValues] = useState<{
    headPose: { pitch: number; yaw: number; roll: number; } | null;
    leftGaze: { x: number; y: number; z: number; } | null;
    rightGaze: { x: number; y: number; z: number; } | null;
  }>({
    headPose: null,
    leftGaze: null,
    rightGaze: null
  });

  useEffect(() => {
    const initializeCamera = async () => {
      try {
        // First check if any video input devices are available
        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoDevices = devices.filter(device => device.kind === 'videoinput');
        
        if (videoDevices.length === 0) {
          setError('No camera detected. Please connect a camera and refresh the page.');
          console.error('No video input devices found');
          return;
        }

        const stream = await navigator.mediaDevices.getUserMedia({ 
          video: { 
            width: 1280,
            height: 720,
            facingMode: 'user',
            deviceId: videoDevices[0].deviceId // Use the first available camera
          } 
        });
        
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      } catch (err) {
        if (err instanceof DOMException) {
          if (err.name === 'NotAllowedError') {
            setError('Camera access denied. Please enable camera permissions.');
          } else if (err.name === 'NotFoundError') {
            setError('Camera not found or disconnected. Please check your camera connection.');
          } else {
            setError(`Camera error: ${err.name}. Please check your camera settings.`);
          }
        }
        console.error('Camera error:', err);
      }
    };

    const initializeFaceMesh = () => {
      const faceMesh = new FaceMesh({
        locateFile: (file) => {
          return `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`;
        },
      });

      faceMesh.setOptions({
        maxNumFaces: 1,
        refineLandmarks: true,
        minDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5,
      });

      faceMesh.onResults((results) => {
        if (results.multiFaceLandmarks && results.multiFaceLandmarks.length > 0) {
          const landmarks = results.multiFaceLandmarks[0];
          const gazePoint = calculateGazePoint(landmarks);
          if (calibrationComplete) {
            updateCursor(transformGazeToScreen(gazePoint));
          } else if (isCalibrating) {
            handleCalibrationPoint(gazePoint);
          }
        }
      });

      if (videoRef.current) {
        const camera = new Camera(videoRef.current, {
          onFrame: async () => {
            if (videoRef.current) {
              await faceMesh.send({ image: videoRef.current });
            }
          },
          width: 1280,
          height: 720,
        });
        camera.start();
      }
    };

    initializeCamera();
    initializeFaceMesh();
  }, []);

  const calculateGazePoint = (landmarks: any): Point => {
    // Utility functions for vector calculations
    const normalizeVector = (v: { x: number, y: number, z: number }) => {
      const magnitude = Math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z);
      return {
        x: v.x / magnitude,
        y: v.y / magnitude,
        z: v.z / magnitude
      };
    };

    const rotateVector = (v: { x: number, y: number, z: number }, rotation: { x: number, y: number, z: number }) => {
      // Apply rotation matrices in order: Z, Y, X
      // First rotate around Z
      const cosZ = Math.cos(rotation.z);
      const sinZ = Math.sin(rotation.z);
      const xZ = v.x * cosZ - v.y * sinZ;
      const yZ = v.x * sinZ + v.y * cosZ;
      const zZ = v.z;

      // Then rotate around Y
      const cosY = Math.cos(rotation.y);
      const sinY = Math.sin(rotation.y);
      const xY = xZ * cosY + zZ * sinY;
      const yY = yZ;
      const zY = -xZ * sinY + zZ * cosY;

      // Finally rotate around X
      const cosX = Math.cos(rotation.x);
      const sinX = Math.sin(rotation.x);
      const xX = xY;
      const yX = yY * cosX - zY * sinX;
      const zX = yY * sinX + zY * cosX;

      return { x: xX, y: yX, z: zX };
    };

    // Get eye and iris landmarks
    const leftEye = {
      center: landmarks[33],
      outer: landmarks[130],
      inner: landmarks[133],
      top: landmarks[159],
      bottom: landmarks[145],
      // Iris landmarks
      irisCenter: landmarks[468],
      irisLeft: landmarks[469],
      irisRight: landmarks[471],
      irisTop: landmarks[470],
      irisBottom: landmarks[472]
    };
    const rightEye = {
      center: landmarks[263],
      outer: landmarks[359],
      inner: landmarks[362],
      top: landmarks[386],
      bottom: landmarks[374],
      // Iris landmarks
      irisCenter: landmarks[473],
      irisLeft: landmarks[474],
      irisRight: landmarks[476],
      irisTop: landmarks[475],
      irisBottom: landmarks[477]
    };
    
    // Calculate eye rotations
    const calculateEyeRotation = (eye: any) => {
      // Calculate iris diameter in x and y directions
      const irisWidthX = Math.sqrt(
        Math.pow(eye.irisRight.x - eye.irisLeft.x, 2) +
        Math.pow(eye.irisRight.y - eye.irisLeft.y, 2) +
        Math.pow(eye.irisRight.z - eye.irisLeft.z, 2)
      );
      const irisHeightY = Math.sqrt(
        Math.pow(eye.irisTop.x - eye.irisBottom.x, 2) +
        Math.pow(eye.irisTop.y - eye.irisBottom.y, 2) +
        Math.pow(eye.irisTop.z - eye.irisBottom.z, 2)
      );
      
      // Calculate rotation angles based on iris deformation
      const rotationX = Math.acos(irisHeightY / irisWidthX);
      const rotationY = Math.atan2(
        eye.irisCenter.z - eye.center.z,
        eye.irisCenter.x - eye.center.x
      );
      const rotationZ = Math.atan2(
        eye.irisCenter.y - eye.center.y,
        eye.irisCenter.x - eye.center.x
      );
      
      return { x: rotationX, y: rotationY, z: rotationZ };
    };
    
    const leftEyeRotation = calculateEyeRotation(leftEye);
    const rightEyeRotation = calculateEyeRotation(rightEye);
    
    // Calculate head pose using facial landmarks
    const leftEar = landmarks[234];  // Left ear landmark
    const rightEar = landmarks[454]; // Right ear landmark
    const foreHead = landmarks[10];  // Forehead landmark
    const chin = landmarks[152];     // Chin landmark

    // Calculate face normal vector (perpendicular to face plane)
    const faceNormal = normalizeVector({
      x: (rightEar.x - leftEar.x),
      y: (rightEar.y - leftEar.y),
      z: (rightEar.z - leftEar.z)
    });

    // Calculate up vector (from chin to forehead)
    const upVector = normalizeVector({
      x: foreHead.x - chin.x,
      y: foreHead.y - chin.y,
      z: foreHead.z - chin.z
    });

    // Calculate right vector (cross product of up and normal)
    const rightVector = {
      x: upVector.y * faceNormal.z - upVector.z * faceNormal.y,
      y: upVector.z * faceNormal.x - upVector.x * faceNormal.z,
      z: upVector.x * faceNormal.y - upVector.y * faceNormal.x
    };

    // Calculate rotation angles from orthonormal basis
    const headPose = {
      // Pitch (rotation around X-axis)
      pitch: Math.atan2(-faceNormal.y, Math.sqrt(faceNormal.x * faceNormal.x + faceNormal.z * faceNormal.z)),
      // Yaw (rotation around Y-axis)
      yaw: Math.atan2(-faceNormal.x, faceNormal.z),
      // Roll (rotation around Z-axis)
      roll: Math.atan2(rightVector.y, upVector.y)
    };
    
    // Calculate base gaze vectors from iris centers
    const leftGazeVector = normalizeVector({
      x: leftEye.irisCenter.x - leftEye.center.x,
      y: leftEye.irisCenter.y - leftEye.center.y,
      z: leftEye.irisCenter.z - leftEye.center.z
    });
    const rightGazeVector = normalizeVector({
      x: rightEye.irisCenter.x - rightEye.center.x,
      y: rightEye.irisCenter.y - rightEye.center.y,
      z: rightEye.irisCenter.z - rightEye.center.z
    });

    // Apply eye rotations to gaze vectors
    const rotatedLeftGaze = rotateVector(leftGazeVector, leftEyeRotation);
    const rotatedRightGaze = rotateVector(rightGazeVector, rightEyeRotation);
    
    // Store debug values and log raw calculations
    const debugState = {
      headPose,
      leftGaze: rotatedLeftGaze,
      rightGaze: rotatedRightGaze
    };
    setDebugValues(debugState);
    
    // Log raw values for debugging
    console.log('Raw Eye Tracking Debug:', {
      leftEyeRaw: leftGazeVector,
      rightEyeRaw: rightGazeVector,
      rotatedLeft: rotatedLeftGaze,
      rotatedRight: rotatedRightGaze,
      headPoseRaw: headPose
    });

    // Combine rotated gaze vectors and head pose
    const x = (rotatedLeftGaze.x + rotatedRightGaze.x) / 2 + headPose.yaw * 0.5;
    const y = (rotatedLeftGaze.y + rotatedRightGaze.y) / 2 + headPose.pitch * 0.5;
    const z = (rotatedLeftGaze.z + rotatedRightGaze.z) / 2;
    
    return { x, y, z };
  };

  const startCalibration = () => {
    const points: CalibrationPoint[] = [
      { x: 0.1, y: 0.1, z: 0, screenX: window.innerWidth * 0.1, screenY: window.innerHeight * 0.1 },
      { x: 0.5, y: 0.1, z: 0, screenX: window.innerWidth * 0.5, screenY: window.innerHeight * 0.1 },
      { x: 0.9, y: 0.1, z: 0, screenX: window.innerWidth * 0.9, screenY: window.innerHeight * 0.1 },
      { x: 0.1, y: 0.5, z: 0, screenX: window.innerWidth * 0.1, screenY: window.innerHeight * 0.5 },
      { x: 0.5, y: 0.5, z: 0, screenX: window.innerWidth * 0.5, screenY: window.innerHeight * 0.5 },
      { x: 0.9, y: 0.5, z: 0, screenX: window.innerWidth * 0.9, screenY: window.innerHeight * 0.5 },
      { x: 0.1, y: 0.9, z: 0, screenX: window.innerWidth * 0.1, screenY: window.innerHeight * 0.9 },
      { x: 0.5, y: 0.9, z: 0, screenX: window.innerWidth * 0.5, screenY: window.innerHeight * 0.9 },
      { x: 0.9, y: 0.9, z: 0, screenX: window.innerWidth * 0.9, screenY: window.innerHeight * 0.9 }
    ];
    setCalibrationPoints(points);
    setIsCalibrating(true);
    setCurrentCalibrationPoint(0);
  };

  const handleCalibrationPoint = (gazePoint: Point) => {
    if (currentCalibrationPoint >= calibrationPoints.length) {
      calculateCalibrationMatrix();
      setCalibrationComplete(true);
      setIsCalibrating(false);
      return;
    }

    const updatedPoints = [...calibrationPoints];
    updatedPoints[currentCalibrationPoint] = {
      ...updatedPoints[currentCalibrationPoint],
      x: gazePoint.x,
      y: gazePoint.y,
      z: gazePoint.z || 0
    };
    setCalibrationPoints(updatedPoints);
    setCurrentCalibrationPoint(prev => prev + 1);
  };

  const calculateCalibrationMatrix = () => {
    // Calculate 3x3 transformation matrix using least squares
    // We'll solve Ax = b for each coordinate (x and y)
    const A: number[][] = [];
    const bx: number[] = [];
    const by: number[] = [];

    calibrationPoints.forEach(point => {
      // Each row in A represents [x, y, z, 1] for homogeneous coordinates
      A.push([point.x, point.y, point.z, 1]);
      bx.push(point.screenX);
      by.push(point.screenY);
    });

    // Solve using pseudo-inverse (least squares)
    const solve = (A: number[][], b: number[]) => {
      // Calculate A^T * A
      const ATA = A[0].map((_, i) => 
        A[0].map((_, j) => 
          A.reduce((sum, row) => sum + row[i] * row[j], 0)
        )
      );

      // Calculate A^T * b
      const ATb = A[0].map((_, i) =>
        b.reduce((sum, bVal, j) => sum + A[j][i] * bVal, 0)
      );

      // Solve system using Gaussian elimination
      const n = ATA.length;
      const augmented = ATA.map((row, i) => [...row, ATb[i]]);

      // Forward elimination
      for (let i = 0; i < n; i++) {
        const pivot = augmented[i][i];
        for (let j = i; j <= n; j++) {
          augmented[i][j] /= pivot;
        }
        for (let k = i + 1; k < n; k++) {
          const factor = augmented[k][i];
          for (let j = i; j <= n; j++) {
            augmented[k][j] -= factor * augmented[i][j];
          }
        }
      }

      // Back substitution
      const x = new Array(n).fill(0);
      for (let i = n - 1; i >= 0; i--) {
        x[i] = augmented[i][n];
        for (let j = i + 1; j < n; j++) {
          x[i] -= augmented[i][j] * x[j];
        }
      }

      return x;
    };

    // Solve for x and y coordinates separately
    const transformX = solve(A, bx);
    const transformY = solve(A, by);

    // Create 3x3 transformation matrix
    setCalibrationMatrix([
      [transformX[0], transformX[1], transformX[2]],
      [transformY[0], transformY[1], transformY[2]],
      [0, 0, 1]  // Homogeneous coordinate
    ]);
  };

  const transformGazeToScreen = (gazePoint: Point): Point => {
    if (!calibrationMatrix.length) return gazePoint;

    // Apply homogeneous transformation
    const x = gazePoint.x * calibrationMatrix[0][0] + 
              gazePoint.y * calibrationMatrix[0][1] + 
              (gazePoint.z || 0) * calibrationMatrix[0][2];
    
    const y = gazePoint.x * calibrationMatrix[1][0] + 
              gazePoint.y * calibrationMatrix[1][1] + 
              (gazePoint.z || 0) * calibrationMatrix[1][2];

    return { x, y };
  };

  const updateCursor = (point: Point) => {
    if (canvasRef.current) {
      const ctx = canvasRef.current.getContext('2d');
      if (ctx) {
        ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
        
        // Draw cursor point
        ctx.beginPath();
        ctx.arc(point.x, point.y, 10, 0, 2 * Math.PI);
        ctx.fillStyle = 'red';
        ctx.fill();
        
        // Draw debug information
        ctx.font = '14px Arial';
        ctx.fillStyle = 'black';
        ctx.textAlign = 'left';
        
        const debugInfo = [
          `Gaze Point: (${point.x.toFixed(2)}, ${point.y.toFixed(2)}, ${(point.z || 0).toFixed(2)})`,
          `Head Pose:`,
          `  Pitch: ${(debugValues.headPose?.pitch || 0).toFixed(2)}`,
          `  Yaw: ${(debugValues.headPose?.yaw || 0).toFixed(2)}`,
          `  Roll: ${(debugValues.headPose?.roll || 0).toFixed(2)}`,
          `Left Eye Vector:`,
          `  (${debugValues.leftGaze?.x.toFixed(2)}, ${debugValues.leftGaze?.y.toFixed(2)}, ${debugValues.leftGaze?.z.toFixed(2)})`,
          `Right Eye Vector:`,
          `  (${debugValues.rightGaze?.x.toFixed(2)}, ${debugValues.rightGaze?.y.toFixed(2)}, ${debugValues.rightGaze?.z.toFixed(2)})`
        ];
        
        debugInfo.forEach((text, index) => {
          ctx.fillText(text, 20, 30 + index * 20);
        });
      }
    }
  };

  return (
    <div style={{ position: 'relative', width: '100vw', height: '100vh' }}>
      {error && (
        <div style={{ 
          position: 'absolute', 
          top: '50%', 
          left: '50%', 
          transform: 'translate(-50%, -50%)',
          background: 'rgba(255, 0, 0, 0.8)',
          padding: '20px',
          borderRadius: '5px',
          color: 'white',
          zIndex: 1000
        }}>
          {error}
        </div>
      )}
      
      <video
        ref={videoRef}
        style={{
          position: 'absolute',
          width: '320px',
          height: '240px',
          right: '20px',
          bottom: '20px',
        }}
        autoPlay
        playsInline
        muted
      />
      
      <canvas
        ref={canvasRef}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
        }}
        width={window.innerWidth}
        height={window.innerHeight}
      />
      
      {!calibrationComplete && !isCalibrating && (
        <button
          onClick={startCalibration}
          style={{
            position: 'absolute',
            top: '20px',
            left: '20px',
            padding: '10px 20px',
            fontSize: '16px',
          }}
        >
          Start Calibration
        </button>
      )}
      
      {isCalibrating && currentCalibrationPoint < calibrationPoints.length && (
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          textAlign: 'center',
        }}>
          <h2>Follow the calibration point with your eyes</h2>
          <div
            style={{
              position: 'absolute',
              left: calibrationPoints[currentCalibrationPoint].screenX,
              top: calibrationPoints[currentCalibrationPoint].screenY,
              width: '20px',
              height: '20px',
              background: 'blue',
              borderRadius: '50%',
              transform: 'translate(-50%, -50%)',
            }}
          />
        </div>
      )}
    </div>
  );
};

export default App;
