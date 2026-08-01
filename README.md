# RoboOps AI

RoboOps AI is a full-stack autonomous robot operations platform combining local large-language-model planning, ROS2 navigation, Gazebo simulation, computer vision, workflow automation, mission reporting, and a live React dashboard.

## Main capabilities

- Natural-language mission generation using a local Ollama model
- Human approval before mission execution
- Real ROS2 Humble and Nav2 navigation
- TurtleBot3 Waffle simulation in Gazebo
- Live robot position, speed, heading, laser, route, and mission telemetry
- Simulated RGB camera streaming
- OpenCV object detection
- Automatic inspection-image capture
- PostgreSQL mission and report storage
- n8n completed/failed mission automation
- Automatic PDF mission reports
- Production startup using systemd
- Complete system health checking

## Architecture

```mermaid
flowchart LR
    U[React Dashboard] --> A[FastAPI Backend]
    U --> T[Telemetry WebSocket]
    U --> V[Vision Service]
    U --> R[Report Service]

    A --> L[Local Ollama LLM]
    A --> P[(PostgreSQL)]
    A --> B[ROS2 Mission Bridge]

    B --> W[Mission Worker]
    W --> N[Nav2]
    N --> G[Gazebo TurtleBot3]

    G --> T
    G --> V

    V --> C[OpenCV Detection]
    V --> E[Inspection Captures]

    W --> X[ROS2 Mission Status]
    X --> M[n8n Automation Bridge]
    X --> R

    M --> N8N[n8n Workflow]
    R --> PDF[PDF Mission Reports]
Technology stack
Frontend
React
TypeScript
Vite
WebSockets
SVG navigation visualization
Backend
FastAPI
SQLAlchemy
PostgreSQL
Redis
ReportLab
OpenCV
cv_bridge
Robotics
ROS2 Humble
Nav2
Gazebo Classic
TurtleBot3 Waffle
AMCL
LaserScan and odometry
RealSense simulated camera
AI and automation
Ollama
Qwen2
n8n
Structured mission-plan generation
Human approval workflow
Deployment
Docker Compose
systemd
SSH port forwarding
Automated health checks
Project structure
roboops-ai/
├── backend/                 FastAPI and ROS2 bridge services
├── frontend/                React dashboard
├── ros2_ws/                 ROS2 mission-worker workspace
├── infrastructure/          PostgreSQL, Redis and n8n
├── automation/              Exported n8n workflows
├── deployment/systemd/      Production systemd units
├── scripts/                 Simulation and health scripts
├── data/
│   ├── captures/            Runtime inspection images
│   └── reports/             Runtime PDF reports
└── docs/                    Project documentation and screenshots
Mission workflow
Natural-language command
→ Local LLM mission plan
→ Human approval
→ FastAPI publishes ROS2 command
→ Mission worker executes Nav2 and vision actions
→ Gazebo robot navigates
→ Camera detects objects and saves evidence
→ Mission result is stored in PostgreSQL
→ n8n receives completed or failed event
→ PDF report is generated
→ Dashboard displays report and evidence
Supported mission actions
Action	Execution
navigate	Real Nav2 movement
return_home	Real Nav2 movement to the home pose
detect_object	Live OpenCV inspection
capture_image	Saves annotated inspection evidence
inspect_path	Software inspection step
Named navigation locations
Location	X	Y
Home	-2.0	-0.5
Room A	-1.0	-0.5
Environment configuration

Copy the example:

cp backend/.env.example backend/.env

Set a secure PostgreSQL password and update DATABASE_URL.

Never commit the real .env file.

Build the ROS2 package
cd /srv/roboops-ai/ros2_ws

source /opt/ros/humble/setup.bash

colcon build --symlink-install
Build the frontend
cd /srv/roboops-ai/frontend

npm install
npm run build
Start the infrastructure
cd /srv/roboops-ai/infrastructure

docker compose \
  -f compose.yaml \
  -f compose.override.yaml \
  up -d
Install production services
sudo /srv/roboops-ai/deployment/install-systemd.sh

Start the platform:

sudo systemctl start roboops.target

Stop the platform:

sudo systemctl stop roboops.target
Health check
/srv/roboops-ai/scripts/roboops-health.sh
Local access through SSH
ssh.exe -N -L 5173:127.0.0.1:5173 -L 5678:127.0.0.1:5678 -L 8000:127.0.0.1:8000 -L 8001:127.0.0.1:8001 -L 8002:127.0.0.1:8002 -L 8003:127.0.0.1:8003 -L 8004:127.0.0.1:8004 titans@SERVER_ADDRESS

Services:

Service	URL
Dashboard	http://localhost:5173
Main API	http://localhost:8000/docs
Telemetry	http://localhost:8001/api/telemetry/health
Vision	http://localhost:8002/api/vision/health
Automation	http://localhost:8003/api/automation/health
Reports	http://localhost:8004/api/reports/health
n8n	http://localhost:5678
Example mission
Go to Room A, detect any visible object, capture an inspection image, and return home.
Security notes
All application ports bind to 127.0.0.1.
Access is provided through an encrypted SSH tunnel.
Environment files, captures, reports, models, build outputs, and database data are excluded from Git.
The local LLM runs without sending mission data to a paid cloud API.
Current status

The complete portfolio workflow has been implemented:

AI planning
→ Approval
→ Real Nav2 navigation
→ Vision inspection
→ n8n automation
→ PostgreSQL storage
→ PDF evidence report
→ React dashboard

