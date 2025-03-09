#!/usr/bin/env python3
"""
Central Server Module

This module implements the central server functionality for aggregating
data from edge nodes and storing it for visualization in Grafana.
"""

import os
import sys
import time
import json
import logging
import threading
import paho.mqtt.client as mqtt
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import yaml
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from flask import Flask, jsonify, request, send_from_directory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("central_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('central_server')

# Flask app for API
app = Flask(__name__)

class CentralServer:
    """
    Central server for aggregating and visualizing UWB-RFID positioning data.
    """
    
    def __init__(self, config_file: str):
        """
        Initialize central server with configuration.
        
        Args:
            config_file: Path to YAML configuration file
        """
        self.config_file = config_file
        self.config = None
        self.mqtt_client = None
        self.influxdb_client = None
        self.write_api = None
        self.running = False
        self.data_lock = threading.Lock()
        self.latest_positions = {}  # Dictionary mapping tag IDs to positions
        self.edge_nodes = {}  # Dictionary mapping edge node IDs to status
        
        # Load configuration
        self._load_config()
        
        # Set Flask app reference to this server instance
        app.central_server = self
        
        logger.info("Central server initialized")
    
    def _load_config(self):
        """Load configuration from YAML file."""
        try:
            with open(self.config_file, 'r') as f:
                self.config = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {self.config_file}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            # Set default configuration
            self.config = {
                'mqtt': {
                    'broker': 'localhost',
                    'port': 1883,
                    'topic_prefix': 'warehouse/tracking'
                },
                'influxdb': {
                    'url': 'http://localhost:8086',
                    'token': 'my-token',
                    'org': 'my-org',
                    'bucket': 'warehouse_tracking'
                },
                'api': {
                    'host': '0.0.0.0',
                    'port': 5000
                },
                'processing': {
                    'position_history_length': 100,
                    'data_retention_days': 30
                }
            }
            logger.warning("Using default configuration")
    
    def setup(self):
        """Initialize MQTT client and InfluxDB connection."""
        # Setup MQTT client
        try:
            self.mqtt_client = mqtt.Client(client_id="central_server")
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_message = self._on_mqtt_message
            
            # Connect to broker
            broker = self.config['mqtt']['broker']
            port = self.config['mqtt']['port']
            self.mqtt_client.connect(broker, port, 60)
            
            logger.info(f"Connected to MQTT broker at {broker}:{port}")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
        
        # Setup InfluxDB client
        try:
            url = self.config['influxdb']['url']
            token = self.config['influxdb']['token']
            org = self.config['influxdb']['org']
            
            self.influxdb_client = InfluxDBClient(url=url, token=token, org=org)
            self.write_api = self.influxdb_client.write_api(write_options=SYNCHRONOUS)
            
            logger.info(f"Connected to InfluxDB at {url}")
        except Exception as e:
            logger.error(f"Failed to connect to InfluxDB: {e}")
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback for when MQTT client connects to broker."""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            
            # Subscribe to position and tag topics
            topic_prefix = self.config['mqtt']['topic_prefix']
            client.subscribe(f"{topic_prefix}/positions/#")
            client.subscribe(f"{topic_prefix}/tags/#")
            
            logger.info(f"Subscribed to topics: {topic_prefix}/positions/# and {topic_prefix}/tags/#")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code: {rc}")
    
    def _on_mqtt_message(self, client, userdata, msg):
        """Callback for when a message is received from the broker."""
        try:
            # Parse topic parts
            topic_parts = msg.topic.split('/')
            topic_prefix = self.config['mqtt']['topic_prefix']
            
            # Ensure it's our topic prefix
            if not msg.topic.startswith(f"{topic_prefix}/"):
                return
            
            # Parse payload
            payload = json.loads(msg.payload.decode('utf-8'))
            
            # Process based on topic type
            if 'positions' in topic_parts:
                self._process_position_message(payload)
            elif 'tags' in topic_parts:
                self._process_tag_message(payload)
            
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def _process_position_message(self, payload):
        """Process position message from edge node."""
        try:
            tag_id = payload.get('tag_id')
            position = (
                payload.get('position', {}).get('x', 0.0),
                payload.get('position', {}).get('y', 0.0),
                payload.get('position', {}).get('z', 0.0)
            )
            timestamp = payload.get('timestamp', time.time())
            edge_node = payload.get('edge_node', 'unknown')
            
            # Store position in memory
            with self.data_lock:
                if tag_id not in self.latest_positions:
                    self.latest_positions[tag_id] = {
                        'positions': [],
                        'last_update': timestamp
                    }
                
                # Add position to history
                position_data = {
                    'position': position,
                    'timestamp': timestamp,
                    'edge_node': edge_node
                }
                
                # Add pallet information if available
                if 'pallet_id' in payload:
                    position_data['pallet_id'] = payload['pallet_id']
                if 'content_type' in payload:
                    position_data['content_type'] = payload['content_type']
                
                # Add to position history
                history_length = self.config['processing']['position_history_length']
                self.latest_positions[tag_id]['positions'].append(position_data)
                
                # Trim history if needed
                if len(self.latest_positions[tag_id]['positions']) > history_length:
                    self.latest_positions[tag_id]['positions'] = self.latest_positions[tag_id]['positions'][-history_length:]
                
                # Update last update time
                self.latest_positions[tag_id]['last_update'] = timestamp
            
            # Store in InfluxDB
            self._store_position_in_influxdb(tag_id, position, payload)
            
            logger.debug(f"Processed position for tag {tag_id} at {position}")
        except Exception as e:
            logger.error(f"Error processing position message: {e}")
    
    def _process_tag_message(self, payload):
        """Process tag detection message from edge node."""
        try:
            tag_id = payload.get('tag_id')
            timestamp = payload.get('timestamp', time.time())
            reader_id = payload.get('reader_id', 'unknown')
            edge_node = payload.get('edge_node', 'unknown')
            
            # Update edge node status
            with self.data_lock:
                if edge_node not in self.edge_nodes:
                    self.edge_nodes[edge_node] = {
                        'last_update': timestamp,
                        'readers': set()
                    }
                
                self.edge_nodes[edge_node]['last_update'] = timestamp
                if reader_id != 'unknown':
                    self.edge_nodes[edge_node]['readers'].add(reader_id)
            
            # Store in InfluxDB
            self._store_tag_in_influxdb(tag_id, reader_id, payload)
            
            logger.debug(f"Processed tag detection for {tag_id} from reader {reader_id}")
        except Exception as e:
            logger.error(f"Error processing tag message: {e}")
    
    def _store_position_in_influxdb(self, tag_id, position, payload):
        """Store position data in InfluxDB."""
        if not self.write_api:
            return
        
        try:
            bucket = self.config['influxdb']['bucket']
            x, y, z = position
            
            # Create data point
            point = Point("position") \
                .tag("tag_id", tag_id) \
                .field("x", float(x)) \
                .field("y", float(y)) \
                .field("z", float(z))
            
            # Add additional fields if available
            if 'pallet_id' in payload:
                point = point.tag("pallet_id", payload['pallet_id'])
            if 'content_type' in payload:
                point = point.tag("content_type", payload['content_type'])
            if 'edge_node' in payload:
                point = point.tag("edge_node", payload['edge_node'])
            
            # Add timestamp if available (convert to nanoseconds)
            if 'timestamp' in payload:
                ns_timestamp = int(payload['timestamp'] * 1_000_000_000)
                point = point.time(ns_timestamp)
            
            # Write to InfluxDB
            self.write_api.write(bucket=bucket, record=point)
            
        except Exception as e:
            logger.error(f"Error storing position in InfluxDB: {e}")
    
    def _store_tag_in_influxdb(self, tag_id, reader_id, payload):
        """Store tag detection data in InfluxDB."""
        if not self.write_api:
            return
        
        try:
            bucket = self.config['influxdb']['bucket']
            
            # Create data point
            point = Point("tag_detection") \
                .tag("tag_id", tag_id) \
                .tag("reader_id", reader_id) \
                .field("detected", 1)
            
            # Add additional fields if available
            if 'pallet_id' in payload:
                point = point.tag("pallet_id", payload['pallet_id'])
            if 'content_type' in payload:
                point = point.tag("content_type", payload['content_type'])
            if 'edge_node' in payload:
                point = point.tag("edge_node", payload['edge_node'])
            if 'weight_kg' in payload:
                point = point.field("weight_kg", float(payload['weight_kg']))
            
            # Add timestamp if available (convert to nanoseconds)
            if 'timestamp' in payload:
                ns_timestamp = int(payload['timestamp'] * 1_000_000_000)
                point = point.time(ns_timestamp)
            
            # Write to InfluxDB
            self.write_api.write(bucket=bucket, record=point)
            
        except Exception as e:
            logger.error(f"Error storing tag detection in InfluxDB: {e}")
    
    def start(self):
        """Start the central server."""
        if self.running:
            logger.warning("Central server is already running")
            return
        
        self.running = True
        
        # Start MQTT client loop
        self.mqtt_client.loop_start()
        
        # Start API server in a separate thread
        api_thread = threading.Thread(target=self._start_api_server)
        api_thread.daemon = True
        api_thread.start()
        
        logger.info("Central server started")
    
    def stop(self):
        """Stop the central server and clean up."""
        self.running = False
        
        # Stop MQTT client
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        
        # Close InfluxDB client
        if self.influxdb_client:
            self.influxdb_client.close()
        
        logger.info("Central server stopped")
    
    def _start_api_server(self):
        """Start the REST API server."""
        try:
            host = self.config['api']['host']
            port = self.config['api']['port']
            app.run(host=host, port=port, debug=False, use_reloader=False)
        except Exception as e:
            logger.error(f"Error starting API server: {e}")
    
    def get_all_positions(self) -> Dict:
        """
        Get all current positions of tags.
        
        Returns:
            Dictionary with tag positions
        """
        result = {
            'timestamp': time.time(),
            'tags': []
        }
        
        with self.data_lock:
            for tag_id, data in self.latest_positions.items():
                if data['positions']:
                    # Get latest position
                    latest = data['positions'][-1]
                    
                    tag_data = {
                        'tag_id': tag_id,
                        'position': latest['position'],
                        'timestamp': latest['timestamp']
                    }
                    
                    # Add additional info if available
                    for key in ['pallet_id', 'content_type', 'edge_node']:
                        if key in latest:
                            tag_data[key] = latest[key]
                    
                    result['tags'].append(tag_data)
        
        return result
    
    def get_tag_history(self, tag_id: str) -> Dict:
        """
        Get position history for a specific tag.
        
        Args:
            tag_id: ID of the tag to get history for
            
        Returns:
            Dictionary with tag position history
        """
        result = {
            'tag_id': tag_id,
            'positions': []
        }
        
        with self.data_lock:
            if tag_id in self.latest_positions:
                result['positions'] = self.latest_positions[tag_id]['positions']
        
        return result
    
    def get_system_status(self) -> Dict:
        """
        Get current system status.
        
        Returns:
            Dictionary with system status information
        """
        status = {
            'timestamp': time.time(),
            'edge_nodes': {},
            'total_tracked_tags': len(self.latest_positions)
        }
        
        # Add edge node information
        with self.data_lock:
            for node_id, node_data in self.edge_nodes.items():
                status['edge_nodes'][node_id] = {
                    'last_update': node_data['last_update'],
                    'readers': list(node_data['readers']),
                    'online': (time.time() - node_data['last_update']) < 60  # Consider node online if updated in last minute
                }
        
        return status


# Flask API routes
@app.route('/api/positions', methods=['GET'])
def api_get_positions():
    """API endpoint to get all current positions."""
    positions = app.central_server.get_all_positions()
    return jsonify(positions)

@app.route('/api/tags/<tag_id>', methods=['GET'])
def api_get_tag_history(tag_id):
    """API endpoint to get history for a specific tag."""
    history = app.central_server.get_tag_history(tag_id)
    return jsonify(history)

@app.route('/api/status', methods=['GET'])
def api_get_status():
    """API endpoint to get system status."""
    status = app.central_server.get_system_status()
    return jsonify(status)

@app.route('/')
def index():
    """Serve the static dashboard page."""
    return send_from_directory('static', 'index.html')


# Example usage
if __name__ == "__main__":
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Central Server for UWB-RFID Positioning System')
    parser.add_argument('--config', type=str, default='config/server_config.yaml', help='Path to configuration file')
    args = parser.parse_args()
    
    # Create central server
    server = CentralServer(config_file=args.config)
    
    try:
        # Setup server
        server.setup()
        
        # Start server
        server.start()
        
        # Run until interrupted
        print("Central server running. Press Ctrl+C to stop.")
        while True:
            time.sleep(10)
            status = server.get_system_status()
            print(f"Status: {status['total_tracked_tags']} tags tracked, {len(status['edge_nodes'])} edge nodes")
    
    except KeyboardInterrupt:
        print("Stopping central server...")
    
    finally:
        # Clean up
        server.stop()
