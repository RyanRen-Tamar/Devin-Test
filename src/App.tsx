import { useEffect, useRef, useState } from 'react';
import { Camera } from '@mediapipe/camera_utils';
import { FaceMesh, FACEMESH_LEFT_EYE, FACEMESH_RIGHT_EYE, FACEMESH_FACE_OVAL } from '@mediapipe/face_mesh';
import { drawConnectors } from '@mediapipe/drawing_utils';
import './App.css';

interface CalibrationPoint {
  x: number;
  y: number;
}

interface CalibrationData {
  gazeX: number;
  gazeY: number;
  headPose: {
    x: number;
    y: number;
    z: number;
  };
  targetX: number;
  targetY: number;
  confidence: number;
}

interface CalibrationMatrix {
  matrix: number[][];
  headPose: {
    x: number;
    y: number;
    z: number;
  };
  confidence: number;
}

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
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [calibrationIndex, setCalibrationIndex] = useState(0);
  const [calibrationData, setCalibrationData] = useState<CalibrationData[]>([]);
  const [calibrationMatrices, setCalibrationMatrices] = useState<CalibrationMatrix[]>([]);
  const [debugInfo, setDebugInfo] = useState<string>('');

  // Define 9-point calibration grid
  const CALIBRATION_POINTS: CalibrationPoint[] = [
    { x: 0.1, y: 0.1 },   // Top-left
    { x: 0.5, y: 0.1 },   // Top-center
    { x: 0.9, y: 0.1 },   // Top-right
    { x: 0.1, y: 0.5 },   // Middle-left
    { x: 0.5, y: 0.5 },   // Center
    { x: 0.9, y: 0.5 },   // Middle-right
    { x: 0.1, y: 0.9 },   // Bottom-left
    { x: 0.5, y: 0.9 },   // Bottom-center
    { x: 0.9, y: 0.9 },   // Bottom-right
  ];

  const startCalibration = () => {
    setIsCalibrating(true);
    setCalibrationIndex(0);
    setCalibrationData([]);
  };

  const collectCalibrationData = (
    gazePoint: GazePoint,
    headPose: { x: number; y: number; z: number }
  ) => {
    if (!isCalibrating || calibrationIndex >= CALIBRATION_POINTS.length) return;

    const currentTarget = CALIBRATION_POINTS[calibrationIndex];
    const targetX = currentTarget.x * window.innerWidth;
    const targetY = currentTarget.y * window.innerHeight;

    setCalibrationData(prev => [...prev, {
      gazeX: gazePoint.x,
      gazeY: gazePoint.y,
      headPose,
      targetX,
      targetY,
      confidence: gazePoint.confidence
    }]);

    setCalibrationIndex(prev => prev + 1);

    if (calibrationIndex === CALIBRATION_POINTS.length - 1) {
      setIsCalibrating(false);
      calculateCalibrationMatrix();
    }
  };

  const calculateCalibrationMatrix = () => {
    // Group calibration data by similar head poses
    const headPoseGroups: { [key: string]: CalibrationData[] } = {};
    
    calibrationData.forEach(data => {
      // Create a key based on discretized head pose angles
      const key = [
        Math.round(data.headPose.x * 10),
        Math.round(data.headPose.y * 10),
        Math.round(data.headPose.z * 10)
      ].join(',');
      
      if (!headPoseGroups[key]) {
        headPoseGroups[key] = [];
      }
      headPoseGroups[key].push(data);
    });

    // Calculate matrices for each head pose group
    const matrices: CalibrationMatrix[] = Object.entries(headPoseGroups)
      .filter(([_, group]) => group.length >= 4) // Need at least 4 points for a reasonable transformation
      .map(([key, group]) => {
        const [headX, headY, headZ] = key.split(',').map(n => parseFloat(n) / 10);

        // Calculate transformation matrix using least squares
        const A: number[][] = [];
        const b: number[][] = [];

        group.forEach(point => {
          // Add row for x coordinate
          A.push([1, point.gazeX, point.gazeY, point.gazeX * point.gazeY]);
          b.push([point.targetX]);
          
          // Add row for y coordinate
          A.push([1, point.gazeX, point.gazeY, point.gazeX * point.gazeY]);
          b.push([point.targetY]);
        });

        // Solve using pseudo-inverse (simplified version)
        const matrix = solveLinearSystem(A, b);
        
        return {
          matrix,
          headPose: { x: headX, y: headY, z: headZ },
          confidence: group.reduce((sum, p) => sum + p.confidence, 0) / group.length
        };
      });

    setCalibrationMatrices(matrices);
  };

  const solveLinearSystem = (A: number[][], b: number[][]): number[][] => {
    // Implement least squares solution using normal equations: (A^T * A)^(-1) * A^T * b
    const AT = transpose(A);
    const ATA = multiply(AT, A);
    const ATb = multiply(AT, b);
    const inverse = invertMatrix(ATA);
    return multiply(inverse, ATb);
  };

  const transpose = (matrix: number[][]): number[][] => {
    const rows = matrix.length;
    const cols = matrix[0].length;
    const result: number[][] = Array(cols).fill(0).map(() => Array(rows).fill(0));
    
    for (let i = 0; i < rows; i++) {
      for (let j = 0; j < cols; j++) {
        result[j][i] = matrix[i][j];
      }
    }
    return result;
  };

  const multiply = (a: number[][], b: number[][]): number[][] => {
    const rows1 = a.length;
    const cols1 = a[0].length;
    const cols2 = b[0].length;
    const result: number[][] = Array(rows1).fill(0).map(() => Array(cols2).fill(0));
    
    for (let i = 0; i < rows1; i++) {
      for (let j = 0; j < cols2; j++) {
        for (let k = 0; k < cols1; k++) {
          result[i][j] += a[i][k] * b[k][j];
        }
      }
    }
    return result;
  };

  const invertMatrix = (matrix: number[][]): number[][] => {
    const n = matrix.length;
    const result: number[][] = Array(n).fill(0).map(() => Array(n).fill(0));
    const temp: number[][] = matrix.map(row => [...row]);
    
    // Initialize result as identity matrix
    for (let i = 0; i < n; i++) {
      result[i][i] = 1;
    }
    
    // Gaussian elimination
    for (let i = 0; i < n; i++) {
      // Find pivot
      let pivot = temp[i][i];
      if (Math.abs(pivot) < 1e-10) {
        // Matrix is singular or nearly singular
        console.warn('Matrix is singular, using pseudo-inverse');
        return pseudoInverse(matrix);
      }
      
      // Divide row by pivot
      for (let j = 0; j < n; j++) {
        temp[i][j] /= pivot;
        result[i][j] /= pivot;
      }
      
      // Subtract from other rows
      for (let k = 0; k < n; k++) {
        if (k !== i) {
          const factor = temp[k][i];
          for (let j = 0; j < n; j++) {
            temp[k][j] -= factor * temp[i][j];
            result[k][j] -= factor * result[i][j];
          }
        }
      }
    }
    
    return result;
  };

  const pseudoInverse = (matrix: number[][]): number[][] => {
    // Simplified Moore-Penrose pseudo-inverse for singular matrices
    const epsilon = 1e-10;
    const n = matrix.length;
    const result: number[][] = Array(n).fill(0).map(() => Array(n).fill(0));
    
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        result[i][j] = Math.abs(matrix[i][j]) < epsilon ? 0 : 1 / matrix[i][j];
      }
    }
    
    return result;
  };

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
        
        if (isCalibrating) {
          collectCalibrationData(gazePoint, headPose);
        } else {
          // Apply calibration transformation if available
          const transformedPoint = transformGazePoint(gazePoint, headPose);
          updateCursorPosition(transformedPoint);
        }

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
          gazePoint,
          calibrationStatus: isCalibrating ? 
            `Calibrating: ${calibrationIndex + 1}/${CALIBRATION_POINTS.length}` : 
            `Calibrated with ${calibrationMatrices.length} matrices`
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
    // Define stable facial landmarks for multiple measurements
    const landmarks = {
      noseTip: face[1],    // Nose tip
      noseBridge: face[6], // Bridge of nose
      noseBottom: face[94], // Bottom of nose
      leftEyeOuter: face[33],  // Left eye outer corner
      leftEyeInner: face[133], // Left eye inner corner
      rightEyeOuter: face[263], // Right eye outer corner
      rightEyeInner: face[362], // Right eye inner corner
      leftEar: face[234],   // Left ear point
      rightEar: face[454],  // Right ear point
      foreheadCenter: face[151], // Center of forehead
      chinCenter: face[152],    // Center of chin
    };

    // Calculate multiple normal vectors using different triplets
    const normalVectors = [
      // Eyes and nose bridge triplet
      calculateNormalVector(
        landmarks.leftEyeOuter,
        landmarks.rightEyeOuter,
        landmarks.noseBridge
      ),
      // Nose and forehead triplet
      calculateNormalVector(
        landmarks.noseTip,
        landmarks.foreheadCenter,
        landmarks.noseBottom
      ),
      // Ears and nose triplet
      calculateNormalVector(
        landmarks.leftEar,
        landmarks.rightEar,
        landmarks.noseTip
      ),
      // Eyes inner corners and nose triplet
      calculateNormalVector(
        landmarks.leftEyeInner,
        landmarks.rightEyeInner,
        landmarks.noseTip
      )
    ].filter(vector => vector !== null);

    if (normalVectors.length === 0) {
      console.warn('No valid normal vectors calculated');
      return { x: 0, y: 0, z: 0 };
    }

    // Average the normal vectors
    const averageNormal = normalVectors.reduce(
      (acc, vector) => ({
        x: acc.x + vector.x,
        y: acc.y + vector.y,
        z: acc.z + vector.z
      }),
      { x: 0, y: 0, z: 0 }
    );

    const magnitude = Math.sqrt(
      averageNormal.x * averageNormal.x +
      averageNormal.y * averageNormal.y +
      averageNormal.z * averageNormal.z
    );

    if (magnitude < 0.0001) {
      console.warn('Invalid averaged normal vector');
      return { x: 0, y: 0, z: 0 };
    }

    // Ensure consistent orientation (nose should point towards +z)
    const noseVector = {
      x: landmarks.noseTip.x - landmarks.noseBridge.x,
      y: landmarks.noseTip.y - landmarks.noseBridge.y,
      z: landmarks.noseTip.z - landmarks.noseBridge.z
    };

    // Dot product to check orientation
    const dotProduct = 
      (averageNormal.x * noseVector.x +
       averageNormal.y * noseVector.y +
       averageNormal.z * noseVector.z);

    // Flip normal if it points in the wrong direction
    const normalizedNormal = {
      x: (averageNormal.x / magnitude) * Math.sign(dotProduct),
      y: (averageNormal.y / magnitude) * Math.sign(dotProduct),
      z: (averageNormal.z / magnitude) * Math.sign(dotProduct)
    };

    return normalizedNormal;
  };

  // Helper function to calculate normal vector from three points
  const calculateNormalVector = (
    p1: { x: number; y: number; z: number },
    p2: { x: number; y: number; z: number },
    p3: { x: number; y: number; z: number }
  ) => {
    // Calculate vectors from p1 to p2 and p1 to p3
    const v1 = {
      x: p2.x - p1.x,
      y: p2.y - p1.y,
      z: p2.z - p1.z
    };

    const v2 = {
      x: p3.x - p1.x,
      y: p3.y - p1.y,
      z: p3.z - p1.z
    };

    // Calculate cross product
    const normal = {
      x: v1.y * v2.z - v1.z * v2.y,
      y: v1.z * v2.x - v1.x * v2.z,
      z: v1.x * v2.y - v1.y * v2.x
    };

    const magnitude = Math.sqrt(
      normal.x * normal.x +
      normal.y * normal.y +
      normal.z * normal.z
    );

    // Return null for invalid calculations
    if (magnitude < 0.0001) {
      return null;
    }

    // Return normalized vector
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
    // Calculate face width using ear landmarks for distance estimation
    const faceWidth = Math.sqrt(
      Math.pow(rightEye.irisCenter.x - leftEye.irisCenter.x, 2) +
      Math.pow(rightEye.irisCenter.y - leftEye.irisCenter.y, 2) +
      Math.pow(rightEye.irisCenter.z - leftEye.irisCenter.z, 2)
    );

    // Estimate distance based on face width (assuming average human face width is ~15cm)
    // and using perspective projection
    const AVERAGE_FACE_WIDTH = 0.15; // 15cm in meters
    const estimatedDistance = (AVERAGE_FACE_WIDTH * window.innerWidth) / (faceWidth * window.screen.width);
    
    // Calculate eye position midpoint
    const eyeMidpoint = {
      x: (leftEye.irisCenter.x + rightEye.irisCenter.x) / 2,
      y: (leftEye.irisCenter.y + rightEye.irisCenter.y) / 2,
      z: (leftEye.irisCenter.z + rightEye.irisCenter.z) / 2
    };

    // Combine eye rotations weighted by confidence
    const totalConfidence = leftEye.confidence + rightEye.confidence;
    const weightedRotation = {
      x: (leftEye.rotation.x * leftEye.confidence + rightEye.rotation.x * rightEye.confidence) / totalConfidence,
      y: (leftEye.rotation.y * leftEye.confidence + rightEye.rotation.y * rightEye.confidence) / totalConfidence,
      z: (leftEye.rotation.z * leftEye.confidence + rightEye.rotation.z * rightEye.confidence) / totalConfidence
    };

    // Compensate for head pose
    const gazeVector = {
      x: weightedRotation.x - headPose.x,
      y: weightedRotation.y - headPose.y,
      z: weightedRotation.z - headPose.z
    };

    // Normalize gaze vector
    const magnitude = Math.sqrt(
      gazeVector.x * gazeVector.x +
      gazeVector.y * gazeVector.y +
      gazeVector.z * gazeVector.z
    );

    if (magnitude < 0.0001) {
      console.warn('Invalid gaze vector');
      return {
        x: window.innerWidth / 2,
        y: window.innerHeight / 2,
        confidence: 0
      };
    }

    const normalizedGaze = {
      x: gazeVector.x / magnitude,
      y: gazeVector.y / magnitude,
      z: gazeVector.z / magnitude
    };

    // Check if looking away from screen
    if (normalizedGaze.z <= 0) {
      console.warn('Looking away from screen');
      return {
        x: window.innerWidth / 2,
        y: window.innerHeight / 2,
        confidence: 0
      };
    }

    // Calculate screen intersection using perspective projection
    const screenIntersectionScale = estimatedDistance / normalizedGaze.z;
    const intersectionPoint = {
      x: eyeMidpoint.x + normalizedGaze.x * screenIntersectionScale,
      y: eyeMidpoint.y + normalizedGaze.y * screenIntersectionScale
    };

    // Convert to screen coordinates
    const screenX = ((intersectionPoint.x + 1) / 2) * window.innerWidth;
    const screenY = ((intersectionPoint.y + 1) / 2) * window.innerHeight;

    // Clamp coordinates to screen bounds
    const finalGazePoint = {
      x: Math.max(0, Math.min(window.innerWidth, screenX)),
      y: Math.max(0, Math.min(window.innerHeight, screenY)),
      confidence: Math.min(leftEye.confidence, rightEye.confidence) * (normalizedGaze.z)
    };

    // Debug logging for gaze tracking verification
    console.log('Gaze Tracking Debug:', {
      screenCoordinates: { x: finalGazePoint.x, y: finalGazePoint.y },
      headPose,
      gazeVector: normalizedGaze,
      eyeMidpoint,
      estimatedDistance,
      confidence: finalGazePoint.confidence
    });

    return finalGazePoint;
  };

  const transformGazePoint = (
    point: GazePoint,
    headPose: { x: number; y: number; z: number }
  ): GazePoint => {
    if (calibrationMatrices.length === 0) {
      return point;
    }

    // Find the best matching calibration matrix based on head pose
    const bestMatrix = calibrationMatrices.reduce((best, current) => {
      const currentDist = Math.sqrt(
        Math.pow(current.headPose.x - headPose.x, 2) +
        Math.pow(current.headPose.y - headPose.y, 2) +
        Math.pow(current.headPose.z - headPose.z, 2)
      );
      const bestDist = Math.sqrt(
        Math.pow(best.headPose.x - headPose.x, 2) +
        Math.pow(best.headPose.y - headPose.y, 2) +
        Math.pow(best.headPose.z - headPose.z, 2)
      );
      return currentDist < bestDist ? current : best;
    });

    // Apply transformation
    const input = [1, point.x, point.y, point.x * point.y];
    const transformedX = input.reduce((sum, val, i) => sum + val * bestMatrix.matrix[i][0], 0);
    const transformedY = input.reduce((sum, val, i) => sum + val * bestMatrix.matrix[i][1], 0);

    return {
      x: transformedX,
      y: transformedY,
      confidence: point.confidence * bestMatrix.confidence
    };
  };

  const updateCursorPosition = (point: GazePoint) => {
    // Update cursor position
    const cursor = document.getElementById('gaze-cursor');
    if (cursor) {
      cursor.style.left = `${point.x}px`;
      cursor.style.top = `${point.y}px`;
      cursor.style.opacity = point.confidence.toString();
    }
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
      <div id="gaze-cursor" style={{
        position: 'fixed',
        width: '10px',
        height: '10px',
        borderRadius: '50%',
        backgroundColor: 'red',
        pointerEvents: 'none',
        transform: 'translate(-50%, -50%)',
        zIndex: 9999
      }} />
      <div className="controls">
        <button onClick={() => setIsTracking(!isTracking)}>
          {isTracking ? 'Stop Tracking' : 'Start Tracking'}
        </button>
        <button 
          onClick={startCalibration}
          disabled={!isTracking || isCalibrating}
        >
          {isCalibrating ? 'Calibrating...' : 'Start Calibration'}
        </button>
        {isCalibrating && (
          <div className="calibration-target" style={{
            position: 'fixed',
            left: `${CALIBRATION_POINTS[calibrationIndex].x * 100}%`,
            top: `${CALIBRATION_POINTS[calibrationIndex].y * 100}%`,
            width: '20px',
            height: '20px',
            borderRadius: '50%',
            border: '2px solid blue',
            transform: 'translate(-50%, -50%)',
            zIndex: 9998
          }} />
        )}
        <pre className="debug-info">
          {debugInfo}
        </pre>
      </div>
    </div>
  );
}

export default App;
