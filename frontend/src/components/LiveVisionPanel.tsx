import {
  useEffect,
  useMemo,
  useState,
} from "react";

import "./LiveVisionPanel.css";


type Detection = {
  label: string;
  score: number;
  x: number;
  y: number;
  width: number;
  height: number;
  area_pixels: number;
};


type VisionStatus = {
  service: string;
  camera_online: boolean;
  camera_topic: string | null;
  camera_format: string | null;
  frame_age_s: number | null;
  frame_count: number;
  processing_fps: number;
  frame_width: number;
  frame_height: number;
  detection_count: number;
  detections: Detection[];
  last_capture_path: string | null;
};


const initialStatus: VisionStatus = {
  service: "offline",
  camera_online: false,
  camera_topic: null,
  camera_format: null,
  frame_age_s: null,
  frame_count: 0,
  processing_fps: 0,
  frame_width: 0,
  frame_height: 0,
  detection_count: 0,
  detections: [],
  last_capture_path: null,
};


export default function LiveVisionPanel() {
  const [status, setStatus] =
    useState<VisionStatus>(
      initialStatus,
    );

  const [captureMessage, setCaptureMessage] =
    useState("");

  const [captureRunning, setCaptureRunning] =
    useState(false);

  const baseUrl = useMemo(
    () =>
      `${window.location.protocol}//` +
      `${window.location.hostname}:8002`,
    [],
  );

  useEffect(() => {
    let active = true;

    const loadStatus = async () => {
      try {
        const response = await fetch(
          `${baseUrl}/api/vision/latest`,
        );

        if (!response.ok) {
          throw new Error(
            `HTTP ${response.status}`,
          );
        }

        const payload =
          (await response.json()) as VisionStatus;

        if (active) {
          setStatus(payload);
        }
      } catch {
        if (active) {
          setStatus((current) => ({
            ...current,
            service: "offline",
            camera_online: false,
          }));
        }
      }
    };

    loadStatus();

    const interval = window.setInterval(
      loadStatus,
      1000,
    );

    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [baseUrl]);

  const captureImage = async () => {
    setCaptureRunning(true);
    setCaptureMessage("");

    try {
      const response = await fetch(
        `${baseUrl}/api/vision/capture`,
        {
          method: "POST",
        },
      );

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(
          payload.detail ??
            "Capture failed",
        );
      }

      setCaptureMessage(
        `Saved: ${payload.path}`,
      );
    } catch (error) {
      setCaptureMessage(
        error instanceof Error
          ? error.message
          : "Capture failed",
      );
    } finally {
      setCaptureRunning(false);
    }
  };

  return (
    <section className="live-vision-panel">
      <div className="vision-header">
        <div>
          <span className="vision-kicker">
            GAZEBO CAMERA + COMPUTER VISION
          </span>

          <h2>Live Robot Vision</h2>

          <p>
            Annotated camera stream, simulated
            object detection and inspection
            capture.
          </p>
        </div>

        <div className="vision-statuses">
          <span
            className={
              status.service === "online"
                ? "vision-badge online"
                : "vision-badge offline"
            }
          >
            Vision service{" "}
            {status.service}
          </span>

          <span
            className={
              status.camera_online
                ? "vision-badge online"
                : "vision-badge offline"
            }
          >
            Camera{" "}
            {status.camera_online
              ? "online"
              : "offline"}
          </span>

          <span className="vision-badge neutral">
            {status.processing_fps.toFixed(
              1,
            )}{" "}
            FPS
          </span>
        </div>
      </div>

      <div className="vision-content">
        <article className="camera-card">
          <div className="camera-toolbar">
            <div>
              <span>LIVE ANNOTATED FEED</span>
              <strong>
                {status.camera_topic ??
                  "Searching for camera"}
              </strong>
            </div>

            <button
              type="button"
              onClick={captureImage}
              disabled={
                captureRunning ||
                !status.camera_online
              }
            >
              {captureRunning
                ? "Capturing..."
                : "Capture inspection image"}
            </button>
          </div>

          <div className="camera-frame">
            <img
              src={`${baseUrl}/api/vision/stream`}
              alt="Live TurtleBot camera"
            />

            <div className="camera-overlay">
              <span>
                {status.frame_width} ×{" "}
                {status.frame_height}
              </span>

              <span>
                Frame {status.frame_count}
              </span>

              <span>
                {status.detection_count}{" "}
                detections
              </span>
            </div>
          </div>

          {captureMessage && (
            <div className="capture-result">
              {captureMessage}
            </div>
          )}
        </article>

        <article className="detections-card">
          <div className="detections-heading">
            <div>
              <span>DETECTION RESULTS</span>
              <h3>Objects in view</h3>
            </div>

            <strong>
              {status.detection_count}
            </strong>
          </div>

          <div className="detection-list">
            {status.detections.length ===
            0 ? (
              <div className="no-detections">
                <span>No colored objects detected</span>
                <small>
                  Move the robot toward visible
                  green structures or a red marker.
                </small>
              </div>
            ) : (
              status.detections.map(
                (detection, index) => (
                  <div
                    className="detection-item"
                    key={`${detection.label}-${index}`}
                  >
                    <div className="detection-icon">
                      {detection.label ===
                      "red_marker"
                        ? "R"
                        : "G"}
                    </div>

                    <div className="detection-copy">
                      <strong>
                        {detection.label.replace(
                          "_",
                          " ",
                        )}
                      </strong>

                      <span>
                        Box {detection.width} ×{" "}
                        {detection.height}
                      </span>
                    </div>

                    <div className="detection-score">
                      {Math.round(
                        detection.score * 100,
                      )}
                      %
                    </div>
                  </div>
                ),
              )
            )}
          </div>

          <dl className="vision-details">
            <div>
              <dt>Camera format</dt>
              <dd>
                {status.camera_format ??
                  "—"}
              </dd>
            </div>

            <div>
              <dt>Frame age</dt>
              <dd>
                {status.frame_age_s !== null
                  ? `${status.frame_age_s.toFixed(
                      2,
                    )} s`
                  : "—"}
              </dd>
            </div>

            <div>
              <dt>Last capture</dt>
              <dd>
                {status.last_capture_path ??
                  "None"}
              </dd>
            </div>
          </dl>
        </article>
      </div>
    </section>
  );
}
