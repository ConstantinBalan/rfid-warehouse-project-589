# Sprint 3: Software Infrastructure Setup (2 weeks)

## Sprint Goal
Set up the core data storage, messaging, and visualization infrastructure required for the indoor positioning system.

## User Stories and Tasks

### User Story 1: As a developer, I need to set up the data storage infrastructure

**Acceptance Criteria:**
- InfluxDB is properly installed and configured
- Database schema is well-defined and documented
- Test data can be generated and stored
- Query performance is acceptable for real-time visualization
- Backup procedures are established

#### Tasks:
1. **Set up InfluxDB**
   - File: `scripts/setup_influxdb.sh`
   - Implementation details:
     - Create installation script for InfluxDB 2.x
     - Add configuration steps:
       - Create admin user
       - Set up organization
       - Create initial bucket with retention policy
       - Configure API access tokens
     - Implement health check verification
     - Add backup configuration
     - Create documentation on port configuration (default: 8086)
     - Include instructions for Docker-based installation option
   - Estimated effort: 1 day
   - Dependencies: None

2. **Create database schema**
   - File: `docs/influxdb_schema.md`
   - Implementation details:
     - Define measurement schema for position data:
       - Tags: `pallet_id`, `tag_id`, `edge_node_id`
       - Fields: `x`, `y`, `z`, `accuracy`, `algorithm`
       - Timestamp handling
     - Define measurement schema for tag detection events:
       - Tags: `tag_id`, `reader_id`, `edge_node_id`
       - Fields: `rssi`, `phase`, `doppler`, `read_count`
       - Timestamp handling
     - Create metadata structure:
       - Pallet metadata measurement
       - Tag metadata measurement
       - Sensor location measurement
     - Define downsampling with continuous queries:
       - 1s raw data
       - 1m aggregated averages
       - 1h statistical rollups
     - Create `scripts/create_influxdb_schema.py` for schema setup
   - Estimated effort: 2 days
   - Dependencies: InfluxDB setup

3. **Implement data generator**
   - File: `tools/data_generator.py`
   - Implementation details:
     - Create `InfluxDataGenerator` class
     - Implement CLI with argparse:
       - Time range parameters
       - Data density options
       - Noise level configuration
     - Add positioning data generation methods:
       - `generate_pallet_movements(num_pallets, duration)`
       - `generate_position_readings(movements, frequency)`
     - Create tag detection generation:
       - `generate_tag_detections(movements, readers, probability)`
     - Implement database write methods:
       - `write_batch(data_points, batch_size=1000)`
       - `write_stream(data_generator, frequency)`
     - Add progress reporting
     - Create unit tests in `tests/test_data_generator.py`
   - Estimated effort: 2 days
   - Dependencies: InfluxDB setup, Database schema

4. **Create database performance tests**
   - File: `tools/db_performance_test.py`
   - Implementation details:
     - Create test suite for query performance
     - Implement write performance tests:
       - Single point write latency
       - Batch write throughput (points/second)
       - Concurrent writer performance
     - Add read performance tests:
       - Point query latency
       - Range query performance
       - Aggregation query performance
       - Concurrent reader performance
     - Create visualization of performance results
     - Generate performance report
     - Add command line options for test configuration
   - Estimated effort: 1 day
   - Dependencies: InfluxDB setup, Data generator

### User Story 2: As a developer, I need to set up the messaging infrastructure

**Acceptance Criteria:**
- MQTT broker is properly installed and configured
- Message protocol is well-defined and documented
- Performance testing shows adequate throughput and latency
- Security measures are implemented
- Client libraries are selected and tested

#### Tasks:
1. **Install and configure MQTT broker**
   - File: `scripts/setup_mqtt.sh`
   - Implementation details:
     - Create installation script for Mosquitto broker
     - Configure security settings:
       - Create passwords file
       - Set up SSL/TLS with self-signed certificates
       - Configure ACLs for topic access control
     - Set up topics structure:
       - `uwb/+/distance` for UWB distance readings
       - `rfid/+/detection` for RFID detection events
       - `nodes/+/status` for edge node status updates
       - `server/commands` for control messages
     - Implement broker monitoring with metrics
     - Add systemd service configuration
     - Include instructions for Docker-based installation option
   - Estimated effort: 1 day
   - Dependencies: None

2. **Create MQTT client benchmarking tools**
   - File: `tools/mqtt_benchmark.py`
   - Implementation details:
     - Create `MQTTPublisher` class for load testing:
       - Configurable message size
       - Adjustable publishing rate
       - Multiple concurrent connections
     - Implement `MQTTSubscriber` class:
       - Support for wildcard subscriptions
       - Message reception timing
       - Multiple concurrent connections
     - Add benchmarking methods:
       - `measure_throughput(msg_size, msg_count, pub_count)`
       - `measure_latency(msg_size, round_trip=True)`
       - `test_qos_levels(qos_values=[0, 1, 2])`
     - Create visualization of benchmark results
     - Generate performance report with recommendations
   - Estimated effort: 2 days
   - Dependencies: MQTT broker

3. **Implement message protocol**
   - File: `docs/mqtt_protocol.md`
   - Implementation details:
     - Define message formats in JSON:
       - Position data message structure
       - Tag detection message structure
       - Edge node status message structure
       - Command message structure
     - Implement serialization/deserialization in `common/mqtt_protocol.py`:
       - `serialize_uwb_data(sensor_id, tag_id, distance, timestamp)`
       - `serialize_rfid_data(reader_id, tag_id, rssi, timestamp)`
       - `serialize_position_data(tag_id, position, accuracy, timestamp)`
       - `deserialize_message(topic, payload)`
     - Add validation with JSON schema
     - Implement error handling for invalid messages
     - Create unit tests in `tests/test_mqtt_protocol.py`
     - Add example messages for each message type
   - Estimated effort: 2 days
   - Dependencies: MQTT broker

### User Story 3: As a developer, I need to set up the visualization infrastructure

**Acceptance Criteria:**
- Grafana is properly installed and configured
- Dashboards are automatically provisioned
- InfluxDB data source is correctly set up
- Visualization is responsive and user-friendly
- Custom components are developed for warehouse-specific visualization

#### Tasks:
1. **Install and configure Grafana**
   - File: `scripts/setup_grafana.sh`
   - Implementation details:
     - Create installation script for Grafana
     - Configure security settings:
       - Create admin user
       - Set up HTTPS with self-signed certificates
       - Configure anonymous access (if required)
     - Set up InfluxDB data source:
       - Create connection parameters
       - Test connection verification
       - Set up authentication
     - Configure basic settings:
       - Default home dashboard
       - Timezone handling
       - Organization name
     - Add systemd service configuration
     - Include instructions for Docker-based installation option
   - Estimated effort: 1 day
   - Dependencies: InfluxDB setup

2. **Implement dashboard provisioning**
   - File: `visualization/dashboard_provisioning.py`
   - Implementation details:
     - Create dashboard JSON definitions:
       - Main overview dashboard
       - Pallet tracking dashboard
       - Edge node performance dashboard
       - System health dashboard
     - Implement automatic dashboard deployment:
       - `upload_dashboard(dashboard_json, overwrite=True)`
       - `create_folder(folder_name)`
       - `set_dashboard_permissions(dashboard_id, permissions)`
     - Set up variables for filtering:
       - Pallet ID selector
       - Time range picker
       - Edge node selector
     - Configure auto-refresh settings for real-time data
     - Create documentation on how to modify dashboards
   - Estimated effort: 2 days
   - Dependencies: Grafana setup

3. **Develop custom Grafana plugins (if needed)**
   - File: `visualization/warehouse_map_plugin/`
   - Implementation details:
     - Create plugin structure following Grafana guidelines
     - Implement warehouse floor plan visualization:
       - `WarehouseMapPanel.tsx` React component
       - SVG rendering of warehouse layout
       - Dynamic positioning of pallet markers
     - Add interactive features:
       - Zoom and pan controls
       - Pallet selection with tooltip
       - Historical path display
     - Create heat map visualization:
       - Position accuracy overlay
       - Coverage map for readers
       - Dwell time visualization
     - Implement build process with webpack
     - Create installation and usage documentation
   - Estimated effort: 4 days
   - Dependencies: Grafana setup

## Sprint Deliverables
1. Fully configured InfluxDB instance with optimized schema
2. Operational MQTT broker with defined message protocol
3. Grafana installation with provisioned dashboards
4. Data generation tools for testing
5. Performance benchmark results for all components
6. Custom visualization components (if implemented)

## Demonstration
At the end of the sprint, a demonstration will show:
- Data flowing from generators to InfluxDB
- MQTT message passing with the defined protocol
- Grafana dashboards displaying real-time and historical data
- Performance metrics for all infrastructure components
- Simulated warehouse visualization with pallet tracking
