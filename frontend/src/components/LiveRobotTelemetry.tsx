import {
  useEffect,
  useMemo,
  useState,
} from "react";

import "./LiveRobotTelemetry.css";


type Point = {
  x: number;
  y: number;
};


type Telemetry = {
  connection: {
    ros_online: boolean;
    last_update_age_s: number | null;
  };
  simulation: {
    running: boolean;
    sim_time_s: number;
  };
  robot: {
    x: number | null;
    y: number | null;
    yaw_rad: number | null;
    yaw_deg: number | null;
    pose_source: string | null;
    linear_speed_mps: number;
    angular_speed_rps: number;
    command_linear_mps: number;
    command_angular_rps: number;
  };
  sensors: {
    laser_online: boolean;
    minimum_obstacle_distance_m: number | null;
    valid_laser_points: number;
  };
  navigation: {
    status: string;
    goal_x: number | null;
    goal_y: number | null;
    distance_remaining_m: number | null;
    elapsed_s: number | null;
    path: Point[];
    path_point_count: number;
  };
  mission: {
    mission_id: string | null;
    plan_id: string | null;
    status: string;
    current_step: number | null;
    total_steps: number;
    step_status: string | null;
    progress_percent: number;
    action: string | null;
    target: string | null;
    description: string | null;
    error: string | null;
  };
  map: {
    available: boolean;
    frame_id: string;
    width: number;
    height: number;
    resolution: number | null;
    origin_x: number | null;
    origin_y: number | null;
  };
};


const initialTelemetry: Telemetry = {
  connection: {
    ros_online: false,
    last_update_age_s: null,
  },
  simulation: {
    running: false,
    sim_time_s: 0,
  },
  robot: {
    x: null,
    y: null,
    yaw_rad: null,
    yaw_deg: null,
    pose_source: null,
    linear_speed_mps: 0,
    angular_speed_rps: 0,
    command_linear_mps: 0,
    command_angular_rps: 0,
  },
  sensors: {
    laser_online: false,
    minimum_obstacle_distance_m: null,
    valid_laser_points: 0,
  },
  navigation: {
    status: "idle",
    goal_x: null,
    goal_y: null,
    distance_remaining_m: null,
    elapsed_s: null,
    path: [],
    path_point_count: 0,
  },
  mission: {
    mission_id: null,
    plan_id: null,
    status: "idle",
    current_step: null,
    total_steps: 0,
    step_status: null,
    progress_percent: 0,
    action: null,
    target: null,
    description: null,
    error: null,
  },
  map: {
    available: false,
    frame_id: "map",
    width: 0,
    height: 0,
    resolution: null,
    origin_x: null,
    origin_y: null,
  },
};


const formatNumber = (
  value: number | null,
  digits = 2,
): string => {
  if (value === null || Number.isNaN(value)) {
    return "—";
  }

  return value.toFixed(digits);
};


const formatTime = (
  totalSeconds: number,
): string => {
  const safeSeconds = Math.max(
    0,
    Math.floor(totalSeconds),
  );

  const minutes = Math.floor(
    safeSeconds / 60,
  );

  const seconds = safeSeconds % 60;

  return `${minutes}:${seconds
    .toString()
    .padStart(2, "0")}`;
};


export default function LiveRobotTelemetry() {
  const [telemetry, setTelemetry] =
    useState<Telemetry>(initialTelemetry);

  const [socketConnected, setSocketConnected] =
    useState(false);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retryTimer: number | undefined;
    let disposed = false;

    const connect = () => {
      const protocol =
        window.location.protocol === "https:"
          ? "wss"
          : "ws";

      const websocketUrl =
        `${protocol}://${window.location.hostname}` +
        ":8001/ws/telemetry";

      socket = new WebSocket(websocketUrl);

      socket.onopen = () => {
        if (!disposed) {
          setSocketConnected(true);
        }
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(
            event.data,
          ) as Telemetry;

          setTelemetry(payload);
        } catch (error) {
          console.error(
            "Invalid telemetry message",
            error,
          );
        }
      };

      socket.onerror = () => {
        socket?.close();
      };

      socket.onclose = () => {
        if (disposed) {
          return;
        }

        setSocketConnected(false);

        retryTimer = window.setTimeout(
          connect,
          1500,
        );
      };
    };

    connect();

    return () => {
      disposed = true;

      if (retryTimer !== undefined) {
        window.clearTimeout(retryTimer);
      }

      socket?.close();
    };
  }, []);

  const drawing = useMemo(() => {
    const width = 760;
    const height = 330;

    const home: Point = {
      x: -2.0,
      y: -0.5,
    };

    const roomA: Point = {
      x: -1.0,
      y: -0.5,
    };

    const robot =
      telemetry.robot.x !== null &&
      telemetry.robot.y !== null
        ? {
            x: telemetry.robot.x,
            y: telemetry.robot.y,
          }
        : home;

    const goal =
      telemetry.navigation.goal_x !== null &&
      telemetry.navigation.goal_y !== null
        ? {
            x: telemetry.navigation.goal_x,
            y: telemetry.navigation.goal_y,
          }
        : null;

    const allPoints = [
      home,
      roomA,
      robot,
      ...telemetry.navigation.path,
      ...(goal ? [goal] : []),
    ];

    const xValues = allPoints.map(
      (point) => point.x,
    );

    const yValues = allPoints.map(
      (point) => point.y,
    );

    let minimumX = Math.min(...xValues);
    let maximumX = Math.max(...xValues);
    let minimumY = Math.min(...yValues);
    let maximumY = Math.max(...yValues);

    const minimumRange = 3.0;

    if (maximumX - minimumX < minimumRange) {
      const centre =
        (maximumX + minimumX) / 2;

      minimumX = centre - minimumRange / 2;
      maximumX = centre + minimumRange / 2;
    }

    if (maximumY - minimumY < minimumRange) {
      const centre =
        (maximumY + minimumY) / 2;

      minimumY = centre - minimumRange / 2;
      maximumY = centre + minimumRange / 2;
    }

    const padding = 0.35;

    minimumX -= padding;
    maximumX += padding;
    minimumY -= padding;
    maximumY += padding;

    const convertX = (x: number) =>
      ((x - minimumX) /
        (maximumX - minimumX)) *
      width;

    const convertY = (y: number) =>
      height -
      ((y - minimumY) /
        (maximumY - minimumY)) *
        height;

    return {
      width,
      height,
      home,
      roomA,
      robot,
      goal,
      convertX,
      convertY,
    };
  }, [telemetry]);

  const {
    width,
    height,
    home,
    roomA,
    robot,
    goal,
    convertX,
    convertY,
  } = drawing;

  const yaw =
    telemetry.robot.yaw_rad ?? 0;

  const robotScreenX = convertX(robot.x);
  const robotScreenY = convertY(robot.y);

  const headingLength = 28;

  const headingX =
    robotScreenX +
    Math.cos(yaw) * headingLength;

  const headingY =
    robotScreenY -
    Math.sin(yaw) * headingLength;

  const progress = Math.min(
    100,
    Math.max(
      0,
      telemetry.mission.progress_percent ?? 0,
    ),
  );

  return (
    <section className="live-telemetry-panel">
      <div className="telemetry-header">
        <div>
          <span className="telemetry-kicker">
            REAL GAZEBO + NAV2 TELEMETRY
          </span>

          <h2>Live Robot Operations</h2>

          <p>
            Real-time position, route, sensors,
            navigation and mission execution.
          </p>
        </div>

        <div className="telemetry-status-group">
          <span
            className={
              socketConnected
                ? "telemetry-badge online"
                : "telemetry-badge offline"
            }
          >
            {socketConnected
              ? "WebSocket connected"
              : "WebSocket disconnected"}
          </span>

          <span
            className={
              telemetry.connection.ros_online
                ? "telemetry-badge online"
                : "telemetry-badge offline"
            }
          >
            {telemetry.connection.ros_online
              ? "ROS2 online"
              : "ROS2 offline"}
          </span>

          <span
            className={
              telemetry.simulation.running
                ? "telemetry-badge running"
                : "telemetry-badge offline"
            }
          >
            {telemetry.simulation.running
              ? "Simulation running"
              : "Simulation stopped"}
          </span>
        </div>
      </div>

      <div className="telemetry-stat-grid">
        <article className="telemetry-stat">
          <span>Robot position</span>
          <strong>
            X {formatNumber(telemetry.robot.x)}
            {" · "}
            Y {formatNumber(telemetry.robot.y)}
          </strong>
          <small>
            {telemetry.robot.pose_source ??
              "Waiting for pose"}
          </small>
        </article>

        <article className="telemetry-stat">
          <span>Heading</span>
          <strong>
            {formatNumber(
              telemetry.robot.yaw_deg,
              1,
            )}
            °
          </strong>
          <small>Map-frame orientation</small>
        </article>

        <article className="telemetry-stat">
          <span>Actual speed</span>
          <strong>
            {formatNumber(
              telemetry.robot.linear_speed_mps,
              3,
            )}
            {" m/s"}
          </strong>
          <small>
            Angular{" "}
            {formatNumber(
              telemetry.robot.angular_speed_rps,
              3,
            )}{" "}
            rad/s
          </small>
        </article>

        <article className="telemetry-stat">
          <span>Nearest obstacle</span>
          <strong>
            {formatNumber(
              telemetry.sensors
                .minimum_obstacle_distance_m,
              2,
            )}
            {" m"}
          </strong>
          <small>
            {telemetry.sensors.valid_laser_points}
            {" valid laser points"}
          </small>
        </article>

        <article className="telemetry-stat">
          <span>Distance remaining</span>
          <strong>
            {formatNumber(
              telemetry.navigation
                .distance_remaining_m,
              2,
            )}
            {" m"}
          </strong>
          <small>
            {telemetry.navigation.status}
          </small>
        </article>

        <article className="telemetry-stat">
          <span>Simulation time</span>
          <strong>
            {formatTime(
              telemetry.simulation.sim_time_s,
            )}
          </strong>
          <small>
            Map{" "}
            {telemetry.map.available
              ? `${telemetry.map.width} × ${telemetry.map.height}`
              : "not received"}
          </small>
        </article>
      </div>

      <div className="telemetry-main-grid">
        <article className="navigation-map-card">
          <div className="telemetry-card-heading">
            <div>
              <span>LIVE NAVIGATION MAP</span>
              <h3>Robot route and destination</h3>
            </div>

            <div className="map-legend">
              <span>
                <i className="legend-dot robot" />
                Robot
              </span>
              <span>
                <i className="legend-dot route" />
                Route
              </span>
              <span>
                <i className="legend-dot goal" />
                Goal
              </span>
            </div>
          </div>

          <div className="navigation-map">
            <svg
              viewBox={`0 0 ${width} ${height}`}
              role="img"
              aria-label="Live robot navigation map"
            >
              <defs>
                <pattern
                  id="telemetry-grid"
                  width="38"
                  height="38"
                  patternUnits="userSpaceOnUse"
                >
                  <path
                    d="M 38 0 L 0 0 0 38"
                    className="telemetry-grid-line"
                  />
                </pattern>

                <filter id="robot-glow">
                  <feGaussianBlur
                    stdDeviation="5"
                    result="blur"
                  />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>

              <rect
                width={width}
                height={height}
                className="telemetry-map-background"
              />

              <rect
                width={width}
                height={height}
                fill="url(#telemetry-grid)"
              />

              {telemetry.navigation.path.length >
                1 && (
                <polyline
                  points={telemetry.navigation.path
                    .map(
                      (point) =>
                        `${convertX(point.x)},${convertY(point.y)}`,
                    )
                    .join(" ")}
                  className="navigation-route"
                />
              )}

              <g>
                <circle
                  cx={convertX(home.x)}
                  cy={convertY(home.y)}
                  r="8"
                  className="location-marker home"
                />
                <text
                  x={convertX(home.x) + 13}
                  y={convertY(home.y) - 13}
                  className="location-label"
                >
                  Home
                </text>
              </g>

              <g>
                <circle
                  cx={convertX(roomA.x)}
                  cy={convertY(roomA.y)}
                  r="8"
                  className="location-marker room"
                />
                <text
                  x={convertX(roomA.x) + 13}
                  y={convertY(roomA.y) - 13}
                  className="location-label"
                >
                  Room A
                </text>
              </g>

              {goal && (
                <g>
                  <circle
                    cx={convertX(goal.x)}
                    cy={convertY(goal.y)}
                    r="15"
                    className="goal-ring"
                  />
                  <circle
                    cx={convertX(goal.x)}
                    cy={convertY(goal.y)}
                    r="5"
                    className="goal-centre"
                  />
                </g>
              )}

              <line
                x1={robotScreenX}
                y1={robotScreenY}
                x2={headingX}
                y2={headingY}
                className="robot-heading"
              />

              <circle
                cx={robotScreenX}
                cy={robotScreenY}
                r="13"
                className="robot-marker"
                filter="url(#robot-glow)"
              />

              <circle
                cx={robotScreenX}
                cy={robotScreenY}
                r="4"
                className="robot-centre"
              />
            </svg>
          </div>

          <div className="map-footer">
            <span>
              Goal:{" "}
              {goal
                ? `${formatNumber(
                    goal.x,
                  )}, ${formatNumber(goal.y)}`
                : "No active goal"}
            </span>

            <span>
              Route points:{" "}
              {telemetry.navigation
                .path_point_count}
            </span>

            <span>
              Frame: {telemetry.map.frame_id}
            </span>
          </div>
        </article>

        <article className="mission-live-card">
          <div className="telemetry-card-heading">
            <div>
              <span>MISSION EXECUTION</span>
              <h3>Current mission</h3>
            </div>

            <span
              className={`mission-state ${telemetry.mission.status}`}
            >
              {telemetry.mission.status}
            </span>
          </div>

          <div className="mission-progress-row">
            <div>
              <strong>{progress}%</strong>
              <span>Mission progress</span>
            </div>

            <span>
              Step{" "}
              {telemetry.mission.current_step ??
                "—"}
              {" / "}
              {telemetry.mission.total_steps ||
                "—"}
            </span>
          </div>

          <div className="mission-progress-track">
            <div
              className="mission-progress-fill"
              style={{
                width: `${progress}%`,
              }}
            />
          </div>

          <dl className="mission-live-details">
            <div>
              <dt>Action</dt>
              <dd>
                {telemetry.mission.action ??
                  "Waiting"}
              </dd>
            </div>

            <div>
              <dt>Target</dt>
              <dd>
                {telemetry.mission.target ??
                  "—"}
              </dd>
            </div>

            <div>
              <dt>Step status</dt>
              <dd>
                {telemetry.mission.step_status ??
                  "—"}
              </dd>
            </div>

            <div>
              <dt>Navigation</dt>
              <dd>
                {telemetry.navigation.status}
              </dd>
            </div>

            <div>
              <dt>Elapsed</dt>
              <dd>
                {telemetry.navigation.elapsed_s !==
                null
                  ? `${formatNumber(
                      telemetry.navigation
                        .elapsed_s,
                      1,
                    )} s`
                  : "—"}
              </dd>
            </div>

            <div>
              <dt>Mission ID</dt>
              <dd className="mission-id">
                {telemetry.mission.mission_id ??
                  "—"}
              </dd>
            </div>
          </dl>

          {telemetry.mission.description && (
            <div className="mission-description">
              {
                telemetry.mission
                  .description
              }
            </div>
          )}

          {telemetry.mission.error && (
            <div className="mission-error">
              {telemetry.mission.error}
            </div>
          )}
        </article>
      </div>
    </section>
  );
}
