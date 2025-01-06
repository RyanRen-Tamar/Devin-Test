import React, { useEffect, useRef, useState } from 'react';
import { Camera } from '@mediapipe/camera_utils';
import { FaceMesh } from '@mediapipe/face_mesh';

interface Point {
  x: number;
  y: number;
  z?: number;
}

const App: React.FC = () => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [error, setError] = useState<string>('');
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
          
          // Verify that we have all required landmarks
          const requiredIndices = [33, 133, 159, 145, 468, 469, 471, 470, 472,  // Left eye
                                 263, 362, 386, 374, 473, 474, 476, 475, 477,   // Right eye
                                 234, 454, 10, 152];  // Face orientation
          
          // Log raw landmark data for debugging
          console.log('Raw Landmark Data:', {
            requiredLandmarks: requiredIndices.map(index => ({
              index,
              position: landmarks[index]
            }))
          });

          const hasAllLandmarks = requiredIndices.every(index => 
            landmarks[index] && 
            typeof landmarks[index].x === 'number' &&
            typeof landmarks[index].y === 'number' &&
            typeof landmarks[index].z === 'number'
          );

          if (!hasAllLandmarks) {
            console.error('Missing required landmarks');
            return;
          }

          // Log raw landmark positions for verification
          console.log('Face Landmarks:', {
            leftEye: {
              center: landmarks[33],
              iris: landmarks[468]
            },
            rightEye: {
              center: landmarks[263],
              iris: landmarks[473]
            },
            face: {
              leftEar: landmarks[234],
              rightEar: landmarks[454],
              forehead: landmarks[10],
              chin: landmarks[152]
            }
          });

          const gazePoint = calculateGazePoint(landmarks);
          
          // Only update if we have valid coordinates
          if (!isNaN(gazePoint.x) && !isNaN(gazePoint.y)) {
            const screenPoint = {
              x: (gazePoint.x + 1) * window.innerWidth / 2,  // Map [-1,1] to [0,width]
              y: (gazePoint.y + 1) * window.innerHeight / 2  // Map [-1,1] to [0,height]
            };
            updateCursor(screenPoint);
          } else {
            console.error('Invalid gaze point calculated:', gazePoint);
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
      const EPSILON = 1e-6; // Minimum threshold for vector magnitude
      
      if (magnitude < EPSILON) {
        console.error('Vector magnitude below threshold:', { vector: v, magnitude });
        // Return a default forward-facing vector for extremely small magnitudes
        return { x: 0, y: 0, z: 1 };
      }

      // Additional validation for NaN values
      const normalized = {
        x: v.x / magnitude,
        y: v.y / magnitude,
        z: v.z / magnitude
      };

      if (isNaN(normalized.x) || isNaN(normalized.y) || isNaN(normalized.z)) {
        console.error('Normalization produced NaN values:', { input: v, magnitude, normalized });
        return { x: 0, y: 0, z: 1 };
      }

      return normalized;
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

    // Log raw landmark positions before any calculations
    console.log('Raw Landmark Positions:', {
      leftEye: {
        center: {
          x: landmarks[33].x,
          y: landmarks[33].y,
          z: landmarks[33].z
        },
        irisCenter: {
          x: landmarks[468].x,
          y: landmarks[468].y,
          z: landmarks[468].z
        }
      },
      rightEye: {
        center: {
          x: landmarks[263].x,
          y: landmarks[263].y,
          z: landmarks[263].z
        },
        irisCenter: {
          x: landmarks[473].x,
          y: landmarks[473].y,
          z: landmarks[473].z
        }
      }
    });
    
    // Calculate eye rotations
    const calculateEyeRotation = (eye: any) => {
      const EPSILON = 1e-6; // Minimum threshold for measurements

      // Validate input landmarks
      if (!eye.irisCenter || !eye.center || !eye.irisLeft || !eye.irisRight || !eye.irisTop || !eye.irisBottom) {
        console.error('Missing eye landmarks:', eye);
        return { x: 0, y: 0, z: 0 };
      }

      // Calculate iris diameter in x and y directions with validation
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

      // Log iris measurements for debugging
      console.log('Eye Rotation Calculations:', {
        irisWidthX,
        irisHeightY,
        eyeCenter: eye.center,
        irisCenter: eye.irisCenter,
        landmarks: {
          left: eye.irisLeft,
          right: eye.irisRight,
          top: eye.irisTop,
          bottom: eye.irisBottom
        }
      });

      // Ensure we have valid measurements
      if (irisWidthX < EPSILON || irisHeightY < EPSILON) {
        console.error('Invalid iris measurements:', { irisWidthX, irisHeightY });
        return { x: 0, y: 0, z: 0 };
      }


      // Calculate eye direction vector with validation
      const eyeVector = {
        x: eye.irisCenter.x - eye.center.x,
        y: eye.irisCenter.y - eye.center.y,
        z: eye.irisCenter.z - eye.center.z
      };

      // Validate vector components
      if (isNaN(eyeVector.x) || isNaN(eyeVector.y) || isNaN(eyeVector.z)) {
        console.error('Invalid eye vector components:', eyeVector);
        return { x: 0, y: 0, z: 0 };
      }

      // Ensure the eye vector is valid
      const eyeVectorMagnitude = Math.sqrt(
        eyeVector.x * eyeVector.x +
        eyeVector.y * eyeVector.y +
        eyeVector.z * eyeVector.z
      );

      if (eyeVectorMagnitude < EPSILON) {
        console.error('Eye vector magnitude too small:', { vector: eyeVector, magnitude: eyeVectorMagnitude });
        return { x: 0, y: 0, z: 0 };
      }

      // Calculate rotation angles with validation
      const aspectRatio = irisHeightY / irisWidthX;
      if (aspectRatio < EPSILON || aspectRatio > 1/EPSILON) {
        console.error('Invalid iris aspect ratio:', aspectRatio);
        return { x: 0, y: 0, z: 0 };
      }

      let rotationX = Math.acos(Math.min(1, Math.max(-1, aspectRatio)));
      let rotationY = Math.atan2(eyeVector.z, eyeVector.x);
      let rotationZ = Math.atan2(eyeVector.y, eyeVector.x);

      // Ensure rotations are within valid ranges
      rotationX = isNaN(rotationX) ? 0 : rotationX;
      rotationY = isNaN(rotationY) ? 0 : rotationY;
      rotationZ = isNaN(rotationZ) ? 0 : rotationZ;

      const rotations = { x: rotationX, y: rotationY, z: rotationZ };
      console.log('Calculated eye rotations:', rotations);
      
      return rotations;
    };
    
    const leftEyeRotation = calculateEyeRotation(leftEye);
    const rightEyeRotation = calculateEyeRotation(rightEye);
    
    // Calculate head pose using facial landmarks with validation
    const leftEar = landmarks[234];  // Left ear landmark
    const rightEar = landmarks[454]; // Right ear landmark
    const foreHead = landmarks[10];  // Forehead landmark
    const chin = landmarks[152];     // Chin landmark

    // Validate head pose landmarks
    if (!leftEar || !rightEar || !foreHead || !chin) {
      console.error('Missing head pose landmarks:', { leftEar, rightEar, foreHead, chin });
      return { x: 0, y: 0, z: 0 };
    }

    // Log raw landmark positions for debugging
    console.log('Head Pose Landmarks:', {
      leftEar: { x: leftEar.x, y: leftEar.y, z: leftEar.z },
      rightEar: { x: rightEar.x, y: rightEar.y, z: rightEar.z },
      foreHead: { x: foreHead.x, y: foreHead.y, z: foreHead.z },
      chin: { x: chin.x, y: chin.y, z: chin.z }
    });

    // Calculate and validate ear-to-ear vector
    const earVector = {
      x: rightEar.x - leftEar.x,
      y: rightEar.y - leftEar.y,
      z: rightEar.z - leftEar.z
    };

    // Calculate and validate vertical face vector
    const verticalVector = {
      x: foreHead.x - chin.x,
      y: foreHead.y - chin.y,
      z: foreHead.z - chin.z
    };

    const EPSILON = 1e-6;
    const earDistance = Math.sqrt(
      earVector.x * earVector.x +
      earVector.y * earVector.y +
      earVector.z * earVector.z
    );
    const verticalDistance = Math.sqrt(
      verticalVector.x * verticalVector.x +
      verticalVector.y * verticalVector.y +
      verticalVector.z * verticalVector.z
    );

    // Validate vector magnitudes
    if (earDistance < EPSILON || verticalDistance < EPSILON) {
      console.error('Invalid head pose vectors:', { earDistance, verticalDistance });
      return { x: 0, y: 0, z: 0 };
    }

    // Calculate face normal vector (perpendicular to face plane)
    const faceNormal = normalizeVector(earVector);

    // Calculate up vector (from chin to forehead)
    const upVector = normalizeVector(verticalVector);

    // Calculate right vector (cross product of up and normal)
    const rightVector = normalizeVector({
      x: upVector.y * faceNormal.z - upVector.z * faceNormal.y,
      y: upVector.z * faceNormal.x - upVector.x * faceNormal.z,
      z: upVector.x * faceNormal.y - upVector.y * faceNormal.x
    });

    // Calculate rotation angles from orthonormal basis with validation
    const headPose = {
      // Pitch (rotation around X-axis)
      pitch: Math.atan2(-faceNormal.y, Math.sqrt(faceNormal.x * faceNormal.x + faceNormal.z * faceNormal.z)),
      // Yaw (rotation around Y-axis)
      yaw: Math.atan2(-faceNormal.x, faceNormal.z),
      // Roll (rotation around Z-axis)
      roll: Math.atan2(rightVector.y, upVector.y)
    };

    // Validate head pose angles
    if (isNaN(headPose.pitch) || isNaN(headPose.yaw) || isNaN(headPose.roll)) {
      console.error('Invalid head pose angles:', headPose);
      return { x: 0, y: 0, z: 0 };
    }

    // Log calculated head pose for debugging
    console.log('Head Pose Calculation:', {
      faceNormal,
      upVector,
      rightVector,
      angles: headPose
    });
    
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
    
    // Store debug values and log detailed calculations
    const debugState = {
      headPose,
      leftGaze: rotatedLeftGaze,
      rightGaze: rotatedRightGaze
    };
    setDebugValues(debugState);
    
    // Log raw landmark data for debugging
    console.log('Raw Landmark Data:', {
      requiredLandmarks: requiredIndices.map(index => ({
        index,
        position: landmarks[index]
      }))
    });

    // Log detailed eye tracking debug information
    console.log('Eye Tracking Debug Information:', {
      leftEye: {
        raw: leftGazeVector,
        rotated: rotatedLeftGaze,
        center: leftEye.center,
        iris: leftEye.irisCenter,
        measurements: {
          widthX: Math.sqrt(
            Math.pow(leftEye.irisRight.x - leftEye.irisLeft.x, 2) +
            Math.pow(leftEye.irisRight.y - leftEye.irisLeft.y, 2) +
            Math.pow(leftEye.irisRight.z - leftEye.irisLeft.z, 2)
          ),
          heightY: Math.sqrt(
            Math.pow(leftEye.irisTop.x - leftEye.irisBottom.x, 2) +
            Math.pow(leftEye.irisTop.y - leftEye.irisBottom.y, 2) +
            Math.pow(leftEye.irisTop.z - leftEye.irisBottom.z, 2)
          )
        }
      },
      rightEye: {
        raw: rightGazeVector,
        rotated: rotatedRightGaze,
        center: rightEye.center,
        iris: rightEye.irisCenter,
        measurements: {
          widthX: Math.sqrt(
            Math.pow(rightEye.irisRight.x - rightEye.irisLeft.x, 2) +
            Math.pow(rightEye.irisRight.y - rightEye.irisLeft.y, 2) +
            Math.pow(rightEye.irisRight.z - rightEye.irisLeft.z, 2)
          ),
          heightY: Math.sqrt(
            Math.pow(rightEye.irisTop.x - rightEye.irisBottom.x, 2) +
            Math.pow(rightEye.irisTop.y - rightEye.irisBottom.y, 2) +
            Math.pow(rightEye.irisTop.z - rightEye.irisBottom.z, 2)
          )
        }
      },
      headPose: {
        raw: headPose,
        vectors: {
          faceNormal,
          upVector,
          rightVector
        }
      }
    });

    // Log specific eye vectors and head pose for debugging
    console.log('Eye Vectors:', {
      left: leftGazeVector,
      right: rightGazeVector
    });
    console.log('Head Pose:', {
      pitch: headPose.pitch,
      yaw: headPose.yaw,
      roll: headPose.roll
    });

    // Combine rotated gaze vectors and head pose with validation
    const combinedGaze = {
      x: (rotatedLeftGaze.x + rotatedRightGaze.x) / 2 + headPose.yaw * 0.5,
      y: (rotatedLeftGaze.y + rotatedRightGaze.y) / 2 + headPose.pitch * 0.5,
      z: (rotatedLeftGaze.z + rotatedRightGaze.z) / 2
    };

    console.log('Combined Gaze:', combinedGaze);

    return combinedGaze;
    
    return { x, y, z };
  };

  // Removed calibration-related functions as we're using direct gaze tracking

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
    </div>
  );
};

export default App;
