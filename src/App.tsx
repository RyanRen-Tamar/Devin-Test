import { useEffect, useRef, useState } from 'react'
import Webcam from 'react-webcam'
import { Button } from './components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from './components/ui/card'
import { Alert, AlertDescription } from './components/ui/alert'
import { FaceMesh, Results } from '@mediapipe/face_mesh'
import { Camera } from '@mediapipe/camera_utils'

// Type declarations
interface Point2D {
  x: number
  y: number
}

interface Point3D extends Point2D {
  z: number
}

interface CalibrationState {
  currentPoint: number
  eyePositions: Point3D[]
  headPoses: Point3D[]
}

// Type declarations for webkit message handler
declare global {
  type CursorControl = {
    postMessage: (message: Point2D) => void
  }

  interface Window {
    webkit?: {
      messageHandlers?: {
        cursorControl?: CursorControl
      }
    }
  }
}

// Define window interface for native module
declare global {
  interface Window {
    webkit?: {
      messageHandlers?: {
        cursorControl?: {
          postMessage: (message: { x: number; y: number }) => void;
        };
      };
    };
  }
}

// Calibration points configuration
const CALIBRATION_POINTS = [
  { x: 0.1, y: 0.1 }, { x: 0.5, y: 0.1 }, { x: 0.9, y: 0.1 },
  { x: 0.1, y: 0.5 }, { x: 0.5, y: 0.5 }, { x: 0.9, y: 0.5 },
  { x: 0.1, y: 0.9 }, { x: 0.5, y: 0.9 }, { x: 0.9, y: 0.9 }
]

// Helper function to draw calibration point
const drawCalibrationPoint = (
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  color: string = 'blue',
  size: number = 10
) => {
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height)
  ctx.beginPath()
  ctx.arc(x * ctx.canvas.width, y * ctx.canvas.height, size, 0, 2 * Math.PI)
  ctx.fillStyle = color
  ctx.fill()
}

// Function to adjust gaze vector based on head pose
const adjustGazeForHeadPose = (vector: Point3D, headPose: Point3D): Point3D => {
  // Project gaze vector onto face plane (defined by head pose normal)
  const dot = vector.x * headPose.x + vector.y * headPose.y + vector.z * headPose.z;
  return {
    x: vector.x - dot * headPose.x,
    y: vector.y - dot * headPose.y,
    z: vector.z - dot * headPose.z
  };
};

function App() {
  const webcamRef = useRef<Webcam>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [isTracking, setIsTracking] = useState(false)
  const [calibrationMode, setCalibrationMode] = useState<'idle' | 'collecting' | 'complete'>('idle')
  const [calibrationMatrix, setCalibrationMatrix] = useState<number[][]>([])
  const [error, setError] = useState<string | null>(null)
  const [webcamInitialized, setWebcamInitialized] = useState(false)

  // Initialize webcam and MediaPipe
  useEffect(() => {
    let faceMeshInstance: FaceMesh | null = null
    let cameraInstance: Camera | null = null

    const initializeWebcam = async () => {
      try {
        // Request webcam access first
        await navigator.mediaDevices.getUserMedia({ 
          video: { 
            width: 640,
            height: 480,
            facingMode: 'user'
          } 
        })

        setWebcamInitialized(true)
        setError(null)

        // Initialize MediaPipe Face Mesh after webcam access is granted
        faceMeshInstance = new FaceMesh({
          locateFile: (file) => {
            return `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`
          }
        })

        faceMeshInstance.setOptions({
          maxNumFaces: 1,
          refineLandmarks: true,
          minDetectionConfidence: 0.5,
          minTrackingConfidence: 0.5
        })

        faceMeshInstance.onResults(onResults)

        // Start camera after everything is initialized
        if (webcamRef.current?.video) {
          cameraInstance = new Camera(webcamRef.current.video, {
            onFrame: async () => {
              if (webcamRef.current?.video && faceMeshInstance) {
                await faceMeshInstance.send({ image: webcamRef.current.video })
              }
            },
            width: 640,
            height: 480
          })
          await cameraInstance.start()
        }
      } catch (err) {
        console.error('Initialization error:', err)
        setError('Failed to access webcam. Please ensure you have granted camera permissions.')
        setWebcamInitialized(false)
      }
    }

    initializeWebcam()

    // Cleanup
    return () => {
      cameraInstance?.stop()
      faceMeshInstance?.close()
    }
  }, [])

  // Draw eye position on canvas with depth indication
  const drawEyePosition = (
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    z: number,
    gazeVector?: { x: number; y: number; z: number }
  ) => {
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height)
    
    const screenX = x * ctx.canvas.width
    const screenY = y * ctx.canvas.height
    
    // Draw current gaze position
    ctx.beginPath()
    const size = Math.max(3, Math.min(8, 5 * (1 - z)))
    ctx.arc(screenX, screenY, size, 0, 2 * Math.PI)
    const intensity = Math.floor(255 * (1 - z))
    ctx.fillStyle = `rgb(${intensity}, 0, 0)`
    ctx.fill()
    
    // Draw gaze vector and screen intersection if provided
    if (gazeVector) {
      // Draw gaze direction line
      const vectorScale = 100 // Scale factor for vector visualization
      const endX = screenX + gazeVector.x * vectorScale
      const endY = screenY + gazeVector.y * vectorScale
      
      ctx.beginPath()
      ctx.moveTo(screenX, screenY)
      ctx.lineTo(endX, endY)
      ctx.strokeStyle = 'rgba(0, 0, 255, 0.5)'
      ctx.lineWidth = 2
      ctx.stroke()
      
      // Draw screen intersection point
      ctx.beginPath()
      ctx.arc(endX, endY, 4, 0, 2 * Math.PI)
      ctx.fillStyle = 'rgba(0, 255, 0, 0.7)'
      ctx.fill()
      
      // Add debug information
      ctx.font = '12px Arial'
      ctx.fillStyle = 'black'
      ctx.fillText(`Depth: ${z.toFixed(3)}`, screenX + 10, screenY - 10)
      ctx.fillText(`Gaze: (${gazeVector.x.toFixed(2)}, ${gazeVector.y.toFixed(2)}, ${gazeVector.z.toFixed(2)})`, 
        screenX + 10, screenY + 20)
    }
  }

  useEffect(() => {
    if (!webcamInitialized || !isTracking) return

    const faceMesh = new FaceMesh({
      locateFile: (file) => {
        return `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`
      }
    })

    faceMesh.setOptions({
      maxNumFaces: 1,
      refineLandmarks: true,
      minDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5
    })

    faceMesh.onResults(onResults)

    if (webcamRef.current && webcamRef.current.video) {
      const camera = new Camera(webcamRef.current.video, {
        onFrame: async () => {
          if (webcamRef.current && webcamRef.current.video) {
            await faceMesh.send({ image: webcamRef.current.video })
          }
        },
        width: 640,
        height: 480
      })
      camera.start()

      return () => {
        camera.stop()
      }
    }
  }, [webcamInitialized, isTracking])

  const [calibrationState, setCalibrationState] = useState<CalibrationState>(
    { currentPoint: 0, eyePositions: [], headPoses: [] }
  )

  const onResults = (results: Results) => {
    if (!results.multiFaceLandmarks) return
    if (!isTracking && calibrationMode !== 'collecting') return

    const face = results.multiFaceLandmarks[0]
    if (!face) return

    // Check if we have advanced 3D tracking capabilities (iris landmarks)
    const hasIrisLandmarks = face[468] && face[473]; // Check left and right iris centers
    const has3DTracking = hasIrisLandmarks && face[468].z !== undefined;

    // Fallback to 2D tracking if 3D features aren't available
    if (!has3DTracking) {
      // Use basic eye contour points for 2D tracking
      const leftEyePoints = face.filter((_, i) => [33, 246, 161, 160, 159, 158, 157, 173].includes(i));
      const rightEyePoints = face.filter((_, i) => [398, 384, 385, 386, 387, 388, 466, 263].includes(i));

      // Calculate eye centers in 2D
      const leftEyeCenter = {
        x: leftEyePoints.reduce((sum, p) => sum + p.x, 0) / leftEyePoints.length,
        y: leftEyePoints.reduce((sum, p) => sum + p.y, 0) / leftEyePoints.length
      };
      const rightEyeCenter = {
        x: rightEyePoints.reduce((sum, p) => sum + p.x, 0) / rightEyePoints.length,
        y: rightEyePoints.reduce((sum, p) => sum + p.y, 0) / rightEyePoints.length
      };

      // Average both eyes for gaze position
      const gazeX = (leftEyeCenter.x + rightEyeCenter.x) / 2;
      const gazeY = (leftEyeCenter.y + rightEyeCenter.y) / 2;

      // Convert to screen coordinates
      let screenX = gazeX * window.innerWidth;
      let screenY = gazeY * window.innerHeight;

      // Apply calibration if available
      if (calibrationMatrix.length > 0) {
        const [[a, b, c], [d, e, f]] = calibrationMatrix;
        screenX = a * gazeX + b * gazeY + c;
        screenY = d * gazeX + e * gazeY + f;
      }

      // Clamp to screen bounds
      screenX = Math.max(0, Math.min(screenX, window.innerWidth));
      screenY = Math.max(0, Math.min(screenY, window.innerHeight));

      // Draw debug visualization
      const ctx = canvasRef.current?.getContext('2d');
      if (ctx) {
        ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
        ctx.beginPath();
        ctx.arc(screenX, screenY, 5, 0, 2 * Math.PI);
        ctx.fillStyle = 'orange'; // Different color to indicate 2D mode
        ctx.fill();
      }

      // Move cursor if calibrated
      if (calibrationMatrix.length > 0 && window.webkit?.messageHandlers?.cursorControl) {
        window.webkit.messageHandlers.cursorControl.postMessage({ x: screenX, y: screenY });
      }

      return; // Exit early, skip 3D processing
    }

    try {
      // Calculate head pose from face mesh landmarks
      const faceOval = face.filter((_, i) => [
        10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152
      ].includes(i));

      if (faceOval.length === 0) {
        throw new Error('Failed to detect face oval points');
      }

      // Calculate face normal vector from face oval points

      // Calculate face plane normal vector using three points from the face oval
      const facePoint1 = faceOval[0];  // Top of face
      const facePoint2 = faceOval[8];  // Left side
      const facePoint3 = faceOval[16]; // Right side;

      if (!facePoint1 || !facePoint2 || !facePoint3) {
        throw new Error('Missing required face landmarks for head pose calculation');
      }

      let headPose: Point3D;

      // Calculate vectors from points
      const vector1 = { 
        x: facePoint2.x - facePoint1.x, 
        y: facePoint2.y - facePoint1.y, 
        z: facePoint2.z - facePoint1.z 
      };
      const vector2 = { 
        x: facePoint3.x - facePoint1.x, 
        y: facePoint3.y - facePoint1.y, 
        z: facePoint3.z - facePoint1.z 
      };

      // Cross product to get normal vector
      const normalVector = {
        x: vector1.y * vector2.z - vector1.z * vector2.y,
        y: vector1.z * vector2.x - vector1.x * vector2.z,
        z: vector1.x * vector2.y - vector1.y * vector2.x
      };

      // Normalize the vector
      const normalMagnitude = Math.sqrt(
        normalVector.x * normalVector.x + 
        normalVector.y * normalVector.y + 
        normalVector.z * normalVector.z
      );
      if (normalMagnitude === 0) {
        throw new Error('Invalid head pose calculation: zero magnitude');
      }

      // Calculate head pose vector (normalized face normal)
      headPose = {
        x: normalVector.x / normalMagnitude,
        y: normalVector.y / normalMagnitude,
        z: normalVector.z / normalMagnitude
      };

      // Enhanced 3D eye landmarks with precise iris tracking
      const leftEye = {
        center: face[468], // Left iris center
        outline: face.filter((_, i) => [33, 246, 161, 160, 159, 158, 157, 173].includes(i)),
        iris: [face[468], face[469], face[470], face[471], face[472]],
        centerZ: face[468].z,
        position: {
          x: face[468].x - (face[33].x + face[133].x) / 2,
          y: face[468].y - (face[159].y + face[145].y) / 2,
          z: face[468].z - (face[33].z + face[133].z) / 2
        }
      };

      if (!leftEye.center || leftEye.outline.length === 0 || leftEye.iris.length !== 5) {
        throw new Error('Invalid left eye landmarks');
      }

      const rightEye = {
        center: face[473], // Right iris center
        outline: face.filter((_, i) => [398, 384, 385, 386, 387, 388, 466, 263].includes(i)),
        iris: [face[473], face[474], face[475], face[476], face[477]],
        centerZ: face[473].z,
        position: {
          x: face[473].x - (face[362].x + face[263].x) / 2,
          y: face[473].y - (face[386].y + face[374].y) / 2,
          z: face[473].z - (face[362].z + face[263].z) / 2
        }
      };

      if (!rightEye.center || rightEye.outline.length === 0 || rightEye.iris.length !== 5) {
        throw new Error('Invalid right eye landmarks');
      }

      // Use the previously calculated head pose for gaze adjustment

      // Calculate adjusted gaze vectors for both eyes using head pose
      const leftGazeAdjusted = adjustGazeForHeadPose(leftEye.position, headPose);
      const rightGazeAdjusted = adjustGazeForHeadPose(rightEye.position, headPose);

      // Calculate combined gaze vector from adjusted vectors
      const gazeVector = {
        x: (leftGazeAdjusted.x + rightGazeAdjusted.x) / 2,
        y: (leftGazeAdjusted.y + rightGazeAdjusted.y) / 2,
        z: (leftGazeAdjusted.z + rightGazeAdjusted.z) / 2
      };

      // Calculate screen intersection using the combined gaze vector
      const gazeVectorMagnitude = Math.sqrt(
        gazeVector.x * gazeVector.x + 
        gazeVector.y * gazeVector.y + 
        gazeVector.z * gazeVector.z
      );

      if (gazeVectorMagnitude === 0) {
        throw new Error('Invalid gaze vector: zero magnitude');
      }

      const normalizedGaze = {
        x: gazeVector.x / gazeVectorMagnitude,
        y: gazeVector.y / gazeVectorMagnitude,
        z: gazeVector.z / gazeVectorMagnitude
      };

      // Calculate screen intersection
      const screenDistance = 0.6; // Typical distance from camera to screen in meters
      const t = -screenDistance / normalizedGaze.z;

      if (!isFinite(t) || t < 0) {
        throw new Error('No valid screen intersection - gaze may be parallel to screen or looking away');
      }

      // Calculate intersection point in 3D space
      const intersectionX = gazeVector.x + normalizedGaze.x * t;
      const intersectionY = gazeVector.y + normalizedGaze.y * t;

      // Convert to relative screen coordinates (-1 to 1 range)
      const screenWidth = 0.4; // Approximate screen width in meters
      const screenHeight = screenWidth * (window.innerHeight / window.innerWidth);
      
      const relativeGazeX = intersectionX / (screenWidth / 2);
      const relativeGazeY = intersectionY / (screenHeight / 2);

      // Convert to screen coordinates
      let screenX = ((relativeGazeX + 1) / 2) * window.innerWidth;
      let screenY = ((relativeGazeY + 1) / 2) * window.innerHeight;

      // Apply calibration if available
      if (calibrationMatrix.length > 0) {
        const [[a, b, c], [d, e, f]] = calibrationMatrix;
        screenX = a * relativeGazeX + b * relativeGazeY + c;
        screenY = d * relativeGazeX + e * relativeGazeY + f;
      }

      // Clamp to screen bounds
      screenX = Math.max(0, Math.min(screenX, window.innerWidth));
      screenY = Math.max(0, Math.min(screenY, window.innerHeight));

      // Draw debug visualization
      const ctx = canvasRef.current?.getContext('2d');
      if (!ctx) return;

      // Clear canvas and draw gaze point
      ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
      ctx.beginPath();
      ctx.arc(screenX, screenY, 5, 0, 2 * Math.PI);
      ctx.fillStyle = 'red';
      ctx.fill();
      
      // Draw eye positions and gaze vector for debugging
      drawEyePosition(ctx, leftEye.center.x, leftEye.center.y, leftEye.center.z, gazeVector);
      drawEyePosition(ctx, rightEye.center.x, rightEye.center.y, rightEye.center.z);

      // Move cursor if calibrated
      if (calibrationMatrix.length > 0 && window.webkit?.messageHandlers?.cursorControl) {
        window.webkit.messageHandlers.cursorControl.postMessage({ x: screenX, y: screenY });
      }

      return; // Exit early, skip further processing</old_str>

    } catch (error) {
      console.error('3D tracking error:', error);
      // Fallback to 2D tracking
      const leftEyePoints = face.filter((_, i) => [33, 246, 161, 160, 159, 158, 157, 173].includes(i));
      const rightEyePoints = face.filter((_, i) => [398, 384, 385, 386, 387, 388, 466, 263].includes(i));

      if (leftEyePoints.length === 0 || rightEyePoints.length === 0) {
        console.error('Failed to detect eye landmarks');
        return;
      }

      // Calculate eye centers in 2D
      const leftEyeCenter = {
        x: leftEyePoints.reduce((sum, p) => sum + p.x, 0) / leftEyePoints.length,
        y: leftEyePoints.reduce((sum, p) => sum + p.y, 0) / leftEyePoints.length
      };
      const rightEyeCenter = {
        x: rightEyePoints.reduce((sum, p) => sum + p.x, 0) / rightEyePoints.length,
        y: rightEyePoints.reduce((sum, p) => sum + p.y, 0) / rightEyePoints.length
      };

      // Average both eyes for gaze position
      const gazeX = (leftEyeCenter.x + rightEyeCenter.x) / 2;
      const gazeY = (leftEyeCenter.y + rightEyeCenter.y) / 2;

      // Convert to screen coordinates
      let screenX = gazeX * window.innerWidth;
      let screenY = gazeY * window.innerHeight;

      // Apply calibration if available
      if (calibrationMatrix.length > 0) {
        const [[a, b, c], [d, e, f]] = calibrationMatrix;
        screenX = a * gazeX + b * gazeY + c;
        screenY = d * gazeX + e * gazeY + f;
      }

      // Clamp to screen bounds
      screenX = Math.max(0, Math.min(screenX, window.innerWidth));
      screenY = Math.max(0, Math.min(screenY, window.innerHeight));

      // Draw debug visualization
      const ctx = canvasRef.current?.getContext('2d');
      if (ctx) {
        ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
        ctx.beginPath();
        ctx.arc(screenX, screenY, 5, 0, 2 * Math.PI);
        ctx.fillStyle = 'orange'; // Different color to indicate 2D mode
        ctx.fill();
      }

      // Move cursor if calibrated
      if (calibrationMatrix.length > 0 && window.webkit?.messageHandlers?.cursorControl) {
        window.webkit.messageHandlers.cursorControl.postMessage({ x: screenX, y: screenY });
      }

      return; // Exit early, skip 3D processing
    }

    // Enhanced 3D eye landmarks with precise iris tracking
    const leftEye = {
      center: face[468], // Left iris center
      outline: face.filter((_, i) => [33, 246, 161, 160, 159, 158, 157, 173].includes(i)),
      iris: [face[468], face[469], face[470], face[471], face[472]],
      centerZ: face[468].z,
      position: {
        x: face[468].x - (face[33].x + face[133].x) / 2,
        y: face[468].y - (face[159].y + face[145].y) / 2,
        z: face[468].z - (face[33].z + face[133].z) / 2
      }
    };

    if (!leftEye.center || leftEye.outline.length === 0 || leftEye.iris.length !== 5) {
      throw new Error('Invalid left eye landmarks');
    }

    const rightEye = {
      center: face[473], // Right iris center
      outline: face.filter((_, i) => [398, 384, 385, 386, 387, 388, 466, 263].includes(i)),
      iris: [face[473], face[474], face[475], face[476], face[477]],
      centerZ: face[473].z,
      position: {
        x: face[473].x - (face[362].x + face[263].x) / 2,
        y: face[473].y - (face[386].y + face[374].y) / 2,
        z: face[473].z - (face[362].z + face[263].z) / 2
      }
    };

    if (!rightEye.center || rightEye.outline.length === 0 || rightEye.iris.length !== 5) {
      throw new Error('Invalid right eye landmarks');
    }

    // Calculate vectors from points
    const vector1 = { 
      x: face[33].x - face[133].x,
      y: face[33].y - face[133].y,
      z: face[33].z - face[133].z
    };
    const vector2 = {
      x: face[362].x - face[263].x,
      y: face[362].y - face[263].y,
      z: face[362].z - face[263].z
    };

    // Calculate normal vector (cross product)
    const normalVector = {
      x: vector1.y * vector2.z - vector1.z * vector2.y,
      y: vector1.z * vector2.x - vector1.x * vector2.z,
      z: vector1.x * vector2.y - vector1.y * vector2.x
    };

    // Normalize the vector
    const normalMagnitude = Math.sqrt(
      normalVector.x * normalVector.x +
      normalVector.y * normalVector.y +
      normalVector.z * normalVector.z
    );

    if (normalMagnitude === 0) {
      throw new Error('Invalid normal vector: zero magnitude');
    }

    // Calculate head pose from normalized normal vector
    const headPose: Point3D = {
      x: normalVector.x / normalMagnitude,
      y: normalVector.y / normalMagnitude,
      z: normalVector.z / normalMagnitude
    };

    // Calculate adjusted gaze vectors using head pose
    const leftGazeAdjusted = adjustGazeForHeadPose(leftEye.position, headPose);
    const rightGazeAdjusted = adjustGazeForHeadPose(rightEye.position, headPose);

    // Average the adjusted gaze vectors
    const gazeX = (leftGazeAdjusted.x + rightGazeAdjusted.x) / 2;
    const gazeY = (leftGazeAdjusted.y + rightGazeAdjusted.y) / 2;
    const gazeZ = (leftGazeAdjusted.z + rightGazeAdjusted.z) / 2;

    // Calculate combined gaze vector from adjusted eye vectors
    const gazeVector = {
      x: (leftGazeAdjusted.x + rightGazeAdjusted.x) / 2,
      y: (leftGazeAdjusted.y + rightGazeAdjusted.y) / 2,
      z: (leftGazeAdjusted.z + rightGazeAdjusted.z) / 2
    };

    // Normalize gaze vector
    const gazeVectorMagnitude = Math.sqrt(
      gazeVector.x * gazeVector.x + 
      gazeVector.y * gazeVector.y + 
      gazeVector.z * gazeVector.z
    );

    if (gazeVectorMagnitude === 0) {
      throw new Error('Invalid gaze vector: zero magnitude');
    }

    const normalizedGaze = {
      x: gazeVector.x / gazeVectorMagnitude,
      y: gazeVector.y / gazeVectorMagnitude,
      z: gazeVector.z / gazeVectorMagnitude
    };

    // Calculate screen intersection
    const screenDistance = 0.6; // Typical distance from camera to screen in meters
    
    // Calculate intersection point of gaze vector with screen plane
    const t = -screenDistance / normalizedGaze.z;
    
    // Check if gaze is parallel to screen or looking away
    if (!isFinite(t) || t < 0) {
      throw new Error('No valid screen intersection - gaze may be parallel to screen or looking away');
    }
    
    // Calculate intersection point in 3D space
    const intersectionX = gazeVector.x + normalizedGaze.x * t;
    const intersectionY = gazeVector.y + normalizedGaze.y * t;
    
    // Convert to relative screen coordinates (-1 to 1 range)
    const screenWidth = 0.4 // Approximate screen width in meters
    const screenHeight = screenWidth * (window.innerHeight / window.innerWidth)
    
    // Convert to relative coordinates (-1 to 1 range)
    const relativeGazeX = (intersectionX / (screenWidth / 2))
    const relativeGazeY = (intersectionY / (screenHeight / 2))
    const relativeGazeZ = 0 // On screen surface

    // Apply calibration matrix if available
    let screenX: number, screenY: number
    if (calibrationMatrix.length > 0) {
      // Apply calibration transformation
      const [[a, b, c], [d, e, f]] = calibrationMatrix
      screenX = a * relativeGazeX + b * relativeGazeY + c
      screenY = d * relativeGazeX + e * relativeGazeY + f
    } else {
      // Convert relative coordinates to screen pixels
      screenX = ((relativeGazeX + 1) / 2) * window.innerWidth
      screenY = ((relativeGazeY + 1) / 2) * window.innerHeight
    }

    // Clamp to screen bounds
    screenX = Math.max(0, Math.min(screenX, window.innerWidth))
    screenY = Math.max(0, Math.min(screenY, window.innerHeight))

    // Get canvas context for all drawing operations
    const ctx = canvasRef.current?.getContext('2d')
    if (!ctx) return

    // Clear previous drawings
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height)

    // Draw debug visualization
    ctx.beginPath()
    ctx.arc(screenX, screenY, 5, 0, 2 * Math.PI)
    ctx.fillStyle = 'red'
    ctx.fill()
    
    // Draw gaze vector
    const startX = (leftEye.center.x + rightEye.center.x) / 2 * window.innerWidth;
    const startY = (leftEye.center.y + rightEye.center.y) / 2 * window.innerHeight;
    ctx.beginPath();
    ctx.moveTo(startX, startY);
    ctx.lineTo(screenX, screenY);
    ctx.strokeStyle = 'blue';
    ctx.stroke();

    // Draw eye position feedback with depth and gaze direction
    drawEyePosition(ctx, relativeGazeX, relativeGazeY, relativeGazeZ);

    // Move cursor if calibrated
    if (calibrationMatrix.length > 0) {
      const handleCursorMove = (x: number, y: number): void => {
        const control = window.webkit?.messageHandlers?.cursorControl;
        if (!control?.postMessage) {
          console.warn('Cursor control not available');
          return;
        }

        const boundedX = Math.max(0, Math.min(x, window.innerWidth));
        const boundedY = Math.max(0, Math.min(y, window.innerHeight));

        try {
          control.postMessage({ x: boundedX, y: boundedY });
        } catch (err) {
          console.error('Failed to move cursor:', err);
        }
      };

      // Use 2D tracking if 3D is not available
      const usePosition = has3DTracking 
        ? { x: screenX, y: screenY } 
        : { x: relativeGazeX, y: relativeGazeY };
      handleCursorMove(usePosition.x, usePosition.y);
    }


    if (calibrationMode === 'collecting') {
      const { currentPoint, eyePositions } = calibrationState
      eyePositions.push({ x: gazeX, y: gazeY, z: gazeZ })
      calibrationState.headPoses.push(headPose)
      
      // Collect multiple samples per point
      if (eyePositions.length >= 30) { // 30 samples per point
        // Average the collected samples
        const avgX = eyePositions.reduce((sum, pos) => sum + pos.x, 0) / eyePositions.length
        const avgY = eyePositions.reduce((sum, pos) => sum + pos.y, 0) / eyePositions.length
        const avgZ = eyePositions.reduce((sum, pos) => sum + pos.z, 0) / eyePositions.length
        
        if (currentPoint < 8) { // 9 calibration points total
          setCalibrationState({ currentPoint: currentPoint + 1, eyePositions: [], headPoses: [] })
          // Update calibration point display
          const point = CALIBRATION_POINTS[currentPoint + 1]
          drawCalibrationPoint(ctx, point.x, point.y, 'blue', 10)
        } else {
          // Calibration complete
          const matrix = calculateCalibrationMatrix(
            [{ x: avgX, y: avgY, z: avgZ }],
            [CALIBRATION_POINTS[currentPoint]],
            [calibrationState.headPoses[calibrationState.headPoses.length - 1]]
          )
          setCalibrationMatrix(matrix)
          setCalibrationMode('complete')
        }
      }
      return
    }

    // Apply calibration if available
    let adjustedX = gazeX
    let adjustedY = gazeY
    
    if (calibrationMatrix.length > 0) {
      // Apply calibration transformation
      const [a, b, c] = calibrationMatrix[0]
      const [d, e, f] = calibrationMatrix[1]
      adjustedX = a * relativeGazeX + b * relativeGazeY + c
      adjustedY = d * relativeGazeX + e * relativeGazeY + f
    }

    // Move cursor using native module
    try {
      window.webkit?.messageHandlers?.cursorControl?.postMessage({
        x: adjustedX * window.innerWidth,
        y: adjustedY * window.innerHeight
      })
    } catch (e) {
      setError('Failed to control cursor. Please ensure the native module is properly installed.')
    }
  }

  const startCalibration = () => {
    setCalibrationMode('collecting')
    setCalibrationMatrix([])
    setCalibrationState({ currentPoint: 0, eyePositions: [], headPoses: [] })
    
    // Draw initial calibration point
    const ctx = canvasRef.current?.getContext('2d')
    if (ctx) {
      const point = CALIBRATION_POINTS[0]
      drawCalibrationPoint(ctx, point.x, point.y, 'blue', 10)
    }
  }
  
  // Calculate calibration matrix using least squares method
  const calculateCalibrationMatrix = (
    eyePositions: Point3D[],
    screenPositions: Point2D[],
    headPoses?: Point3D[]
  ): number[][] => {
    // Enhanced 3D-aware transformation matrix with head pose compensation
    const n = eyePositions.length
    let sumX = 0, sumY = 0, sumZ = 0, sumXX = 0, sumXY = 0, sumYY = 0
    let sumXZ = 0, sumYZ = 0, sumScreenX = 0, sumScreenY = 0
    let sumXScreenX = 0, sumYScreenX = 0, sumZScreenX = 0
    let sumXScreenY = 0, sumYScreenY = 0, sumZScreenY = 0
    
    for (let i = 0; i < n; i++) {
      const { x, y, z } = eyePositions[i]
      const screen = screenPositions[i]
      const headPose = headPoses?.[i] || { x: 0, y: 0, z: 1 }
      
      
      // Apply head pose compensation
      const headFactor = Math.abs(headPose.z) // Forward-facing weight
      const depthFactor = 1 / (1 + Math.abs(z)) // Inverse depth weighting
      const weight = headFactor * depthFactor
      
      // Weighted accumulation for least squares
      const wx = x * weight
      const wy = y * weight
      const wz = z * weight
      
      sumX += wx
      sumY += wy
      sumZ += wz
      sumXX += wx * x
      sumXY += wx * y
      sumYY += wy * y
      sumXZ += wx * z
      sumYZ += wy * z
      
      sumXScreenX += wx * screen.x
      sumYScreenX += wy * screen.x
      sumZScreenX += wz * screen.x
      sumXScreenY += wx * screen.y
      sumYScreenY += wy * screen.y
      sumZScreenY += wz * screen.y
      
      sumScreenX += screen.x
      sumScreenY += screen.y
    }
    
    // Solve the system using weighted least squares
    const det = sumXX * sumYY - sumXY * sumXY
    if (Math.abs(det) < 1e-10) return [[1, 0, 0], [0, 1, 0]]
    
    // Calculate transformation coefficients
    const a = (sumXScreenX * sumYY - sumYScreenX * sumXY) / det
    const b = (sumXX * sumYScreenX - sumXY * sumXScreenX) / det
    const c = (sumScreenX - a * sumX - b * sumY) / n
    
    const d = (sumXScreenY * sumYY - sumYScreenY * sumXY) / det
    const e = (sumXX * sumYScreenY - sumXY * sumXScreenY) / det
    const f = (sumScreenY - d * sumX - e * sumY) / n
    
    // Apply depth and head pose influence to the coefficients
    const depthScale = 1 / (1 + Math.abs(sumZ / n))
    return [
      [a * depthScale, b * depthScale, c],
      [d * depthScale, e * depthScale, f]
    ]
  }

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <Card className="max-w-2xl mx-auto">
        <CardHeader>
          <CardTitle>Eye Gaze Cursor Control</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="relative aspect-video max-w-3xl mx-auto">
            {webcamInitialized ? (
              <>
                <Webcam
                  ref={webcamRef}
                  className="w-full rounded-lg"
                  mirrored
                  videoConstraints={{
                    width: 640,
                    height: 480,
                    facingMode: 'user'
                  }}
                />
                <canvas
                  ref={canvasRef}
                  className="absolute top-0 left-0 w-full h-full"
                />
                {calibrationMode === 'collecting' && (
                  <div className="absolute top-0 left-0 w-full h-full flex items-center justify-center">
                    <div className="bg-black/50 text-white p-4 rounded-lg">
                      Look at the blue dot ({calibrationState.currentPoint + 1}/5)
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="w-full h-full bg-gray-100 rounded-lg flex items-center justify-center">
                <p className="text-gray-500">Waiting for camera access...</p>
              </div>
            )}
          </div>
          <div className="mt-4 space-y-4">
            <div className="flex gap-4 justify-center">
              <Button
                onClick={() => setIsTracking(!isTracking)}
                variant={isTracking ? "destructive" : "default"}
                disabled={!webcamInitialized || calibrationMode === 'collecting'}
              >
                {isTracking ? 'Stop Tracking' : 'Start Tracking'}
              </Button>
              <Button
                onClick={startCalibration}
                variant="outline"
                disabled={!webcamInitialized || isTracking || calibrationMode === 'collecting'}
              >
                {calibrationMode === 'complete' ? 'Recalibrate' : 'Calibrate'}
              </Button>
            </div>
            {error && (
              <div className="max-w-md mx-auto">
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              </div>
            )}
          </div>
          {error && (
            <Alert className="mt-4" variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export default App
