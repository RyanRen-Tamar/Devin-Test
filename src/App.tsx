import React, { useEffect, useRef, useState } from 'react';
import { Camera } from '@mediapipe/camera_utils';
import { FaceMesh } from '@mediapipe/face_mesh';

interface Point {
  x: number;
  y: number;
}

interface CalibrationPoint extends Point {
  screenX: number;
  screenY: number;
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

  useEffect(() => {
    const initializeCamera = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ 
          video: { 
            width: 1280,
            height: 720,
            facingMode: 'user'
          } 
        });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      } catch (err) {
        setError('Camera access denied. Please enable camera permissions.');
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
    // Get eye landmarks
    const leftEye = {
      center: landmarks[33],
      outer: landmarks[130],
      inner: landmarks[133],
      top: landmarks[159],
      bottom: landmarks[145]
    };
    const rightEye = {
      center: landmarks[263],
      outer: landmarks[359],
      inner: landmarks[362],
      top: landmarks[386],
      bottom: landmarks[374]
    };
    
    
    // Calculate head pose
    const nose = landmarks[1];
    const headPose = {
      pitch: Math.atan2(nose.y - leftEye.center.y, nose.z - leftEye.center.z),
      yaw: Math.atan2(rightEye.center.x - leftEye.center.x, rightEye.center.z - leftEye.center.z),
      roll: Math.atan2(rightEye.center.y - leftEye.center.y, rightEye.center.x - leftEye.center.x)
    };
    
    // Calculate gaze direction vector
    const leftGazeVector = {
      x: leftEye.inner.x - leftEye.outer.x,
      y: (leftEye.top.y + leftEye.bottom.y) / 2 - leftEye.center.y,
      z: (leftEye.inner.z - leftEye.outer.z)
    };
    const rightGazeVector = {
      x: rightEye.inner.x - rightEye.outer.x,
      y: (rightEye.top.y + rightEye.bottom.y) / 2 - rightEye.center.y,
      z: (rightEye.inner.z - rightEye.outer.z)
    };
    
    // Combine gaze vectors and head pose
    const x = (leftGazeVector.x + rightGazeVector.x) / 2 + headPose.yaw * 0.5;
    const y = (leftGazeVector.y + rightGazeVector.y) / 2 + headPose.pitch * 0.5;
    
    return { x, y };
  };

  const startCalibration = () => {
    const points: CalibrationPoint[] = [
      { x: 0.1, y: 0.1, screenX: window.innerWidth * 0.1, screenY: window.innerHeight * 0.1 },
      { x: 0.5, y: 0.1, screenX: window.innerWidth * 0.5, screenY: window.innerHeight * 0.1 },
      { x: 0.9, y: 0.1, screenX: window.innerWidth * 0.9, screenY: window.innerHeight * 0.1 },
      { x: 0.1, y: 0.5, screenX: window.innerWidth * 0.1, screenY: window.innerHeight * 0.5 },
      { x: 0.5, y: 0.5, screenX: window.innerWidth * 0.5, screenY: window.innerHeight * 0.5 },
      { x: 0.9, y: 0.5, screenX: window.innerWidth * 0.9, screenY: window.innerHeight * 0.5 },
      { x: 0.1, y: 0.9, screenX: window.innerWidth * 0.1, screenY: window.innerHeight * 0.9 },
      { x: 0.5, y: 0.9, screenX: window.innerWidth * 0.5, screenY: window.innerHeight * 0.9 },
      { x: 0.9, y: 0.9, screenX: window.innerWidth * 0.9, screenY: window.innerHeight * 0.9 }
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
      y: gazePoint.y
    };
    setCalibrationPoints(updatedPoints);
    setCurrentCalibrationPoint(prev => prev + 1);
  };

  const calculateCalibrationMatrix = () => {
    // Simple linear transformation matrix
    const sumX = calibrationPoints.reduce((acc, point) => acc + point.x, 0) / calibrationPoints.length;
    const sumY = calibrationPoints.reduce((acc, point) => acc + point.y, 0) / calibrationPoints.length;
    const sumScreenX = calibrationPoints.reduce((acc, point) => acc + point.screenX, 0) / calibrationPoints.length;
    const sumScreenY = calibrationPoints.reduce((acc, point) => acc + point.screenY, 0) / calibrationPoints.length;

    setCalibrationMatrix([
      [sumScreenX / sumX, 0],
      [0, sumScreenY / sumY]
    ]);
  };

  const transformGazeToScreen = (gazePoint: Point): Point => {
    if (!calibrationMatrix.length) return gazePoint;

    return {
      x: gazePoint.x * calibrationMatrix[0][0],
      y: gazePoint.y * calibrationMatrix[1][1]
    };
  };

  const updateCursor = (point: Point) => {
    if (canvasRef.current) {
      const ctx = canvasRef.current.getContext('2d');
      if (ctx) {
        ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
        ctx.beginPath();
        ctx.arc(point.x, point.y, 10, 0, 2 * Math.PI);
        ctx.fillStyle = 'red';
        ctx.fill();
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
