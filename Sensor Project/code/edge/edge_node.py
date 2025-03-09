#!/usr/bin/env python3
"""
Edge Node Processing Module

This module implements the edge computing functionality for processing
UWB and RFID sensor data locally before sending to the central server.
"""

import os
import sys
import time
import json
import logging
import numpy as np
import threading
import paho.mqtt.client as mqtt
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import yaml

# Add parent directory to path to import from other modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uwb.uwb_interface import UWBSensor
from uwb.trilateration import Trilateration
from rfid.rfid_interface import RFIDReader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("edge_node.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('edge_node')

class EdgeNode:
    """
    Edge computing node for processing UWB and RFID sensor data.
    """
    
    def __init__(self, config_file: str, node_id: str = None):
        """
        Initialize edge node with configuration.
        
        Args:
            config_file: Path to YAML configuration file
            node_id: Unique identifier for this edge node
        """
        self.config_file = config_file
        self.node_id = node_id or f"edge_{os.getpid()}"
        self.config = None
        self.uwb_sensors = {}
        self.rfid_readers = {}
        self.mqtt_client = None
        self.running = False
        self.data_lock = threading.Lock()
        self.latest_positions = {}  # Dictionary mapping tag IDs to positions
        
        # Load configuration
        self._load_config()
        
        logger.info(f"Edge node {self.node_id} initialized")
    
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
                'uwb': {
                    'sensors': [
                        {'id': 'uwb_1', 'position': [0.0, 0.0, 2.5], 'spi_bus': 0, 'spi_device': 0},
                        {'id': 'uwb_2', 'position': [5.0, 0.0, 2.5], 'spi_bus': 0, 'spi_device': 1},
                        {'id': 'uwb_3', 'position': [5.0, 5.0, 2.5], 'spi_bus': 0, 'spi_device': 2},
                        {'id': 'uwb_4', 'position': [0.0, 5.0, 2.5], 'spi_bus': 1, 'spi_device': 0}
                    ],
                    'update_interval': 1.0  # seconds
                },
                'rfid': {
                    'readers': [
                        {'id': 'rfid_1', 'port': '/dev/ttyUSB0', 'simulate': True},
                        {'id': 'rfid_2', 'port': '/dev/ttyUSB1', 'simulate': True}
                    ],
                    'tag_database': 'config/tags.json',
                    'update_interval': 0.5  # seconds
                },
                'processing': {
                    'position_buffer_size': 5,
                    'trilateration_method': 'multi',
                    'filter_outliers': True
                }
            }
            logger.warning("Using default configuration")
    
    def setup(self):
        """Initialize sensors, RFID readers, and MQTT client."""
        # Initialize UWB sensors
        for sensor_config in self.config['uwb']['sensors']:
            try:
                sensor_id = sensor_config['id']
                position = tuple(sensor_config['position'])
                spi_bus = sensor_config.get('spi_bus', 0)
                spi_device = sensor_config.get('spi_device', 0)
                
                # Create UWB sensor
                sensor = UWBSensor(spi_bus=spi_bus, spi_device=spi_device)
                sensor.set_sensor_position(position, sensor_id)
                
                # Store sensor
                self.uwb_sensors[sensor_id] = sensor
                logger.info(f"Initialized UWB sensor {sensor_id} at position {position}")
            except Exception as e:
                logger.error(f"Failed to initialize UWB sensor {sensor_config.get('id')}: {e}")
        
        # Initialize RFID readers
        for reader_config in self.config['rfid']['readers']:
            try:
                reader_id = reader_config['id']
                port = reader_config.get('port')
                simulate = reader_config.get('simulate', False)
                
                # Create RFID reader
                reader = RFIDReader(port=port, reader_id=reader_id, simulate=simulate)
                reader.connect()
                
                # Load tag database if available
                if 'tag_database' in self.config['rfid'] and os.path.exists(self.config['rfid']['tag_database']):
                    reader.load_tag_database(self.config['rfid']['tag_database'])
                
                # Store reader
                self.rfid_readers[reader_id] = reader
                logger.info(f"Initialized RFID reader {reader_id}")
            except Exception as e:
                logger.error(f"Failed to initialize RFID reader {reader_config.get('id')}: {e}")
        
        # Setup MQTT client
        try:
            self.mqtt_client = mqtt.Client(client_id=f"edge_node_{self.node_id}")
            self.mqtt_client.on_connect = self._on_mqtt_connect
            
            # Connect to broker
            broker = self.config['mqtt']['broker']
            port = self.config['mqtt']['port']
            self.mqtt_client.connect(broker, port, 60)
            self.mqtt_client.loop_start()
            
            logger.info(f"Connected to MQTT broker at {broker}:{port}")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback for when MQTT client connects to broker."""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            # Subscribe to command topic
            command_topic = f"{self.config['mqtt']['topic_prefix']}/commands/{self.node_id}"
            client.subscribe(command_topic)
            logger.info(f"Subscribed to command topic: {command_topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code: {rc}")
    
    def start(self):
        """Start processing sensor data."""
        if self.running:
            logger.warning("Edge node is already running")
            return
        
        self.running = True
        
        # Start UWB sensor thread
        uwb_thread = threading.Thread(target=self._uwb_processing_loop)
        uwb_thread.daemon = True
        uwb_thread.start()
        
        # Start RFID reader thread
        rfid_thread = threading.Thread(target=self._rfid_processing_loop)
        rfid_thread.daemon = True
        rfid_thread.start()
        
        logger.info("Edge node processing started")
    
    def stop(self):
        """Stop processing sensor data and clean up."""
        self.running = False
        
        # Give threads time to stop
        time.sleep(1)
        
        # Disconnect MQTT client
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        
        # Close UWB sensors
        for sensor in self.uwb_sensors.values():
            sensor.close()
        
        # Disconnect RFID readers
        for reader in self.rfid_readers.values():
            reader.disconnect()
        
        logger.info("Edge node stopped")
    
    def _uwb_processing_loop(self):
        """Background thread for processing UWB sensor data."""
        update_interval = self.config['uwb']['update_interval']
        
        # Get anchor positions for trilateration
        anchor_positions = []
        for sensor_id, sensor in self.uwb_sensors.items():
            anchor_positions.append(sensor.sensor_position)
        
        # Create trilateration object
        trilat = Trilateration(anchor_positions)
        
        while self.running:
            try:
                # Get distances from all UWB sensors to tags
                tag_distances = {}
                
                # In a real implementation, you would have UWB tags on pallets
                # For simulation, we'll use the RFID tag IDs as if they also had UWB
                with self.data_lock:
                    # Use the tag IDs from latest_positions or create some demo ones
                    if not self.latest_positions:
                        tag_ids = ['tag_1', 'tag_2', 'tag_3']
                    else:
                        tag_ids = list(self.latest_positions.keys())
                
                # Simulate measuring distances to each tag
                for tag_id in tag_ids:
                    distances = []
                    for sensor_id, sensor in self.uwb_sensors.items():
                        # In real implementation, each sensor would measure distance to the tag
                        # Here we simulate with random distances
                        distance = sensor.measure_distance(tag_id)
                        distances.append(distance)
                    
                    tag_distances[tag_id] = distances
                
                # Calculate position for each tag
                for tag_id, distances in tag_distances.items():
                    method = self.config['processing']['trilateration_method']
                    position = trilat.estimate_position(distances, method=method)
                    
                    if position:
                        with self.data_lock:
                            # Store position
                            self.latest_positions[tag_id] = {
                                'position': position,
                                'timestamp': time.time()
                            }
                        
                        # Publish position to MQTT
                        self._publish_position(tag_id, position)
                        
                        logger.debug(f"Calculated position for {tag_id}: {position}")
            
            except Exception as e:
                logger.error(f"Error in UWB processing loop: {e}")
            
            # Sleep until next update
            time.sleep(update_interval)
    
    def _rfid_processing_loop(self):
        """Background thread for processing RFID reader data."""
        update_interval = self.config['rfid']['update_interval']
        
        while self.running:
            try:
                all_tags = {}
                
                # Read tags from all readers
                for reader_id, reader in self.rfid_readers.items():
                    tags = reader.read_tags()
                    
                    for tag in tags:
                        tag_id = tag['tag_id']
                        
                        # Store or update tag information
                        all_tags[tag_id] = tag
                        
                        # Publish tag detection to MQTT
                        self._publish_tag_detection(tag)
                
                # Update latest tags
                with self.data_lock:
                    for tag_id, tag_info in all_tags.items():
                        # If this tag doesn't have a position yet, give it a dummy position
                        if tag_id not in self.latest_positions:
                            self.latest_positions[tag_id] = {
                                'position': (0.0, 0.0, 0.0),  # Will be updated by UWB
                                'timestamp': time.time()
                            }
                        
                        # Add tag info to the position data
                        self.latest_positions[tag_id].update({
                            'pallet_id': tag_info.get('pallet_id', 'unknown'),
                            'content_type': tag_info.get('content_type', 'unknown'),
                            'last_seen': time.time()
                        })
            
            except Exception as e:
                logger.error(f"Error in RFID processing loop: {e}")
            
            # Sleep until next update
            time.sleep(update_interval)
    
    def _publish_position(self, tag_id: str, position: Tuple[float, float, float]):
        """Publish tag position to MQTT broker."""
        if not self.mqtt_client:
            return
        
        try:
            topic = f"{self.config['mqtt']['topic_prefix']}/positions/{tag_id}"
            
            payload = {
                'tag_id': tag_id,
                'position': {
                    'x': position[0],
                    'y': position[1],
                    'z': position[2]
                },
                'timestamp': time.time(),
                'edge_node': self.node_id
            }
            
            # Add additional tag information if available
            with self.data_lock:
                if tag_id in self.latest_positions:
                    tag_info = self.latest_positions[tag_id]
                    if 'pallet_id' in tag_info:
                        payload['pallet_id'] = tag_info['pallet_id']
                    if 'content_type' in tag_info:
                        payload['content_type'] = tag_info['content_type']
            
            # Publish message
            self.mqtt_client.publish(topic, json.dumps(payload), qos=1)
            
            logger.debug(f"Published position for {tag_id} to {topic}")
        except Exception as e:
            logger.error(f"Error publishing position: {e}")
    
    def _publish_tag_detection(self, tag_info: Dict):
        """Publish tag detection to MQTT broker."""
        if not self.mqtt_client:
            return
        
        try:
            tag_id = tag_info['tag_id']
            topic = f"{self.config['mqtt']['topic_prefix']}/tags/{tag_id}"
            
            payload = {
                'tag_id': tag_id,
                'timestamp': time.time(),
                'reader_id': tag_info.get('reader_id'),
                'edge_node': self.node_id
            }
            
            # Add additional tag information
            for key in ['pallet_id', 'content_type', 'weight_kg', 'destination']:
                if key in tag_info:
                    payload[key] = tag_info[key]
            
            # Publish message
            self.mqtt_client.publish(topic, json.dumps(payload), qos=1)
            
            logger.debug(f"Published tag detection for {tag_id} to {topic}")
        except Exception as e:
            logger.error(f"Error publishing tag detection: {e}")
    
    def get_status(self) -> Dict:
        """
        Get current status of the edge node.
        
        Returns:
            Dictionary with status information
        """
        status = {
            'node_id': self.node_id,
            'timestamp': time.time(),
            'uwb_sensors': len(self.uwb_sensors),
            'rfid_readers': len(self.rfid_readers),
            'running': self.running
        }
        
        # Add currently tracked tags and positions
        with self.data_lock:
            status['tracked_tags'] = len(self.latest_positions)
            status['tags'] = []
            
            for tag_id, data in self.latest_positions.items():
                tag_data = {
                    'tag_id': tag_id,
                    'position': data.get('position'),
                }
                
                # Add additional info if available
                for key in ['pallet_id', 'content_type', 'last_seen']:
                    if key in data:
                        tag_data[key] = data[key]
                
                status['tags'].append(tag_data)
        
        return status


# Example usage
if __name__ == "__main__":
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Edge Node for UWB-RFID Positioning System')
    parser.add_argument('--config', type=str, default='config/edge_config.yaml', help='Path to configuration file')
    parser.add_argument('--node-id', type=str, help='Unique identifier for this edge node')
    args = parser.parse_args()
    
    # Create edge node
    edge_node = EdgeNode(config_file=args.config, node_id=args.node_id)
    
    try:
        # Setup node
        edge_node.setup()
        
        # Start processing
        edge_node.start()
        
        # Run until interrupted
        print("Edge node running. Press Ctrl+C to stop.")
        while True:
            time.sleep(10)
            status = edge_node.get_status()
            print(f"Status: {len(status['tags'])} tags tracked")
    
    except KeyboardInterrupt:
        print("Stopping edge node...")
    
    finally:
        # Clean up
        edge_node.stop()
