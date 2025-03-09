# Installation Guide

This document provides detailed instructions for setting up the UWB-RFID indoor positioning system.

## Hardware Requirements

### UWB Sensor Setup
1. **Components needed**:
   - 4× DWM1000 or DWM3000 UWB modules
   - 4× Raspberry Pi (minimum 3B+ recommended) for corner nodes
   - Power supplies for each Raspberry Pi
   - Ethernet cables or Wi-Fi capability for network communication

2. **Physical Installation**:
   - Mount each UWB sensor in a corner of the room
   - Ensure line-of-sight between sensors when possible
   - Measure and record the exact coordinates of each sensor for calibration
   - Connect each UWB sensor to its Raspberry Pi via GPIO pins

### RFID System Setup
1. **Components needed**:
   - RFID readers (compatible with ISO/IEC 15693 or similar standard)
   - RFID tags (passive, to be attached to pallets)
   - Connection cables (typically USB or GPIO)

2. **Physical Installation**:
   - Attach RFID tags to each pallet
   - Position RFID readers at strategic locations for optimal coverage
   - Connect RFID readers to the edge computing nodes

### Central Server
1. **Hardware requirements**:
   - Raspberry Pi 4 (8GB RAM recommended) or small form-factor PC
   - Minimum 64GB storage
   - Ethernet connectivity
   - UPS for power stability (optional but recommended)

## Software Installation

### Edge Nodes (Raspberry Pi)

1. **Operating System**:
   ```bash
   # Download and flash Raspberry Pi OS Lite to SD card
   # Boot the Raspberry Pi and perform initial setup
   
   # Update the system
   sudo apt update
   sudo apt upgrade -y
   
   # Install required packages
   sudo apt install -y python3-pip git screen
   ```

2. **Python Dependencies**:
   ```bash
   # Install required Python packages
   pip3 install pyserial numpy paho-mqtt influxdb-client
   
   # Install UWB library dependencies
   sudo apt install -y build-essential python3-dev
   pip3 install spidev RPi.GPIO
   ```

3. **Clone Repository**:
   ```bash
   git clone https://github.com/yourusername/uwb-rfid-positioning.git
   cd uwb-rfid-positioning
   ```

### Central Server

1. **InfluxDB Installation**:
   ```bash
   # Add InfluxDB repository
   wget -q https://repos.influxdata.com/influxdb.key
   echo '23a1c8836f0afc5ed24e0486339d7cc8f6790b83886c4c96995b88a061c5bb5d influxdb.key' | sha256sum -c && cat influxdb.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/influxdb.gpg > /dev/null
   echo 'deb [signed-by=/etc/apt/trusted.gpg.d/influxdb.gpg] https://repos.influxdata.com/debian stable main' | sudo tee /etc/apt/sources.list.d/influxdata.list
   
   # Install InfluxDB
   sudo apt update
   sudo apt install -y influxdb
   
   # Start InfluxDB service
   sudo systemctl enable influxdb
   sudo systemctl start influxdb
   ```

2. **Grafana Installation**:
   ```bash
   # Add Grafana repository
   wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
   echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
   
   # Install Grafana
   sudo apt update
   sudo apt install -y grafana
   
   # Start Grafana service
   sudo systemctl enable grafana-server
   sudo systemctl start grafana-server
   ```

3. **Setup Python Environment**:
   ```bash
   # Install required Python packages
   pip3 install flask influxdb-client paho-mqtt numpy pandas
   ```

## Configuration

### UWB Sensor Calibration

1. Place all four UWB sensors at their designated corner positions
2. Measure the exact coordinates (x, y, z) of each sensor
3. Update the configuration in `config/uwb_config.json`
4. Run the calibration script:
   ```bash
   python3 scripts/calibrate_uwb.py
   ```

### RFID Setup

1. Configure each RFID reader by editing `config/rfid_config.json`
2. Register the RFID tags in the system:
   ```bash
   python3 scripts/register_rfid_tags.py
   ```

### Network Configuration

1. Configure the MQTT broker on the central server:
   ```bash
   sudo apt install -y mosquitto mosquitto-clients
   sudo systemctl enable mosquitto
   sudo systemctl start mosquitto
   ```

2. Update the network configuration in `config/network_config.json` with:
   - MQTT broker address
   - InfluxDB connection details
   - Edge node addresses

## Starting the System

1. **Start Edge Nodes**:
   On each edge node, run:
   ```bash
   cd uwb-rfid-positioning
   python3 edge/main.py --node-id <NODE_ID>
   ```

2. **Start Central Server**:
   ```bash
   cd uwb-rfid-positioning
   python3 server/main.py
   ```

3. **Access Grafana Dashboard**:
   Open a web browser and navigate to:
   ```
   http://<server-ip>:3000
   ```
   Default login: admin/admin

## Troubleshooting

See [troubleshooting.md](troubleshooting.md) for common issues and their solutions.
