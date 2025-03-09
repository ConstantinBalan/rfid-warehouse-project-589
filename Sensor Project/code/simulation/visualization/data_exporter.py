"""
Data Exporter for UWB-RFID Indoor Positioning System.

This module provides classes for exporting simulation data to InfluxDB
for visualization in Grafana.
"""

import time
import json
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import numpy as np
from datetime import datetime

# Import simulation components
from ..warehouse_model import WarehouseModel
from ..virtual_pallet import VirtualPallet
from ..uwb_sensor_model import UWBSensorNetwork
from ..rfid_reader_model import RFIDReader


class InfluxDBExporter:
    """
    Exports warehouse and pallet data to InfluxDB for visualization in Grafana.
    """
    
    def __init__(self, 
                 url: str = "http://localhost:8086",
                 token: str = "",
                 org: str = "warehouse",
                 bucket: str = "warehouse_simulation",
                 batch_size: int = 100):
        """
        Initialize InfluxDB connection.
        
        Args:
            url: InfluxDB server URL
            token: InfluxDB authentication token
            org: InfluxDB organization
            bucket: InfluxDB bucket name
            batch_size: Number of points to batch write
        """
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        self.batch_size = batch_size
        
        # Connect to InfluxDB
        self.client = InfluxDBClient(url=url, token=token, org=org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        
        # Cache for batch writing
        self.point_cache = []
    
    def close(self):
        """Close the InfluxDB connection."""
        self._flush_cache()  # Flush any remaining points
        self.client.close()
    
    def _flush_cache(self):
        """Flush the point cache to InfluxDB."""
        if self.point_cache:
            self.write_api.write(bucket=self.bucket, record=self.point_cache)
            self.point_cache = []
    
    def _add_point(self, point: Point):
        """
        Add a point to the cache and flush if batch size is reached.
        
        Args:
            point: InfluxDB Point to add
        """
        self.point_cache.append(point)
        
        if len(self.point_cache) >= self.batch_size:
            self._flush_cache()
    
    def create_bucket(self, reset_bucket: bool = False):
        """
        Create the InfluxDB bucket for warehouse data.
        
        Args:
            reset_bucket: If True, delete and recreate the bucket
        """
        buckets_api = self.client.buckets_api()
        bucket_list = buckets_api.find_buckets().buckets
        bucket_names = [bucket.name for bucket in bucket_list]
        
        if reset_bucket and self.bucket in bucket_names:
            # Delete existing bucket
            bucket = next(bucket for bucket in bucket_list if bucket.name == self.bucket)
            buckets_api.delete_bucket(bucket)
            print(f"Deleted bucket: {self.bucket}")
            
        if reset_bucket or self.bucket not in bucket_names:
            # Create new bucket
            organization_api = self.client.organizations_api()
            org_id = organization_api.find_organizations(org=self.org)[0].id
            buckets_api.create_bucket(bucket_name=self.bucket, org_id=org_id)
            print(f"Created bucket: {self.bucket}")
    
    def export_warehouse_layout(self, warehouse_model: WarehouseModel, reset_bucket: bool = False):
        """
        Export warehouse layout to InfluxDB.
        
        Args:
            warehouse_model: WarehouseModel instance
            reset_bucket: If True, delete and recreate the bucket
        """
        # Create/reset bucket if needed
        if reset_bucket:
            self.create_bucket(reset_bucket=True)
        
        # Export warehouse boundaries as geodata points
        # We'll create points at the corners of the warehouse
        corners = [
            (0, 0),  # Bottom-left
            (warehouse_model.width, 0),  # Bottom-right
            (warehouse_model.width, warehouse_model.length),  # Top-right
            (0, warehouse_model.length),  # Top-left
            (0, 0)  # Back to start to close polygon
        ]
        
        # Convert corners to lat/lon for Grafana geomap
        boundary_points = []
        for x, y in corners:
            lat, lon = warehouse_model.xy_to_latlon(x, y)
            
            # Create point for boundary
            point = Point("warehouse_boundary") \
                .tag("warehouse_id", warehouse_model.name) \
                .tag("point_type", "boundary") \
                .field("position", f"POINT({lon} {lat})") \
                .field("x", x) \
                .field("y", y) \
                .field("order", len(boundary_points)) \
                .time(datetime.utcnow(), WritePrecision.NS)
                
            boundary_points.append(point)
        
        # Write boundary points
        self.write_api.write(bucket=self.bucket, record=boundary_points)
        
        # Export obstacles
        obstacle_points = []
        for obstacle in warehouse_model.obstacles:
            # For each obstacle, we create a point at each corner
            x, y, z = obstacle.position
            w, l, h = obstacle.dimensions
            
            # Create center point with metadata
            lat, lon = warehouse_model.xy_to_latlon(x + w/2, y + l/2)
            
            point = Point("warehouse_obstacle") \
                .tag("warehouse_id", warehouse_model.name) \
                .tag("obstacle_id", obstacle.id) \
                .tag("obstacle_type", obstacle.obstacle_type) \
                .field("position", f"POINT({lon} {lat})") \
                .field("x", x + w/2) \
                .field("y", y + l/2) \
                .field("z", z + h/2) \
                .field("width", w) \
                .field("length", l) \
                .field("height", h) \
                .time(datetime.utcnow(), WritePrecision.NS)
                
            obstacle_points.append(point)
            
            # Create corners for polygon representation
            corners = [
                (x, y),  # Bottom-left
                (x + w, y),  # Bottom-right
                (x + w, y + l),  # Top-right
                (x, y + l),  # Top-left
                (x, y)  # Back to start to close polygon
            ]
            
            for i, (corner_x, corner_y) in enumerate(corners):
                lat, lon = warehouse_model.xy_to_latlon(corner_x, corner_y)
                
                point = Point("warehouse_obstacle_boundary") \
                    .tag("warehouse_id", warehouse_model.name) \
                    .tag("obstacle_id", obstacle.id) \
                    .tag("obstacle_type", obstacle.obstacle_type) \
                    .field("position", f"POINT({lon} {lat})") \
                    .field("x", corner_x) \
                    .field("y", corner_y) \
                    .field("order", i) \
                    .time(datetime.utcnow(), WritePrecision.NS)
                    
                obstacle_points.append(point)
        
        # Write obstacle points
        self.write_api.write(bucket=self.bucket, record=obstacle_points)
        
        print(f"Exported warehouse layout: {warehouse_model.name}")
    
    def export_sensors(self, uwb_network: UWBSensorNetwork, warehouse_model: WarehouseModel):
        """
        Export UWB sensor network to InfluxDB.
        
        Args:
            uwb_network: UWBSensorNetwork instance
            warehouse_model: WarehouseModel for coordinate conversion
        """
        sensor_points = []
        
        for sensor_id, sensor in uwb_network.sensors.items():
            x, y, z = sensor.position
            lat, lon = warehouse_model.xy_to_latlon(x, y)
            
            point = Point("uwb_sensor") \
                .tag("sensor_id", sensor_id) \
                .field("position", f"POINT({lon} {lat})") \
                .field("x", x) \
                .field("y", y) \
                .field("z", z) \
                .field("range", sensor.max_range) \
                .time(datetime.utcnow(), WritePrecision.NS)
                
            sensor_points.append(point)
        
        # Write sensor points
        self.write_api.write(bucket=self.bucket, record=sensor_points)
        
        print(f"Exported {len(uwb_network.sensors)} UWB sensors")
    
    def export_rfid_readers(self, readers: List[RFIDReader], warehouse_model: WarehouseModel):
        """
        Export RFID readers to InfluxDB.
        
        Args:
            readers: List of RFIDReader instances
            warehouse_model: WarehouseModel for coordinate conversion
        """
        reader_points = []
        
        for reader in readers:
            x, y, z = reader.position
            lat, lon = warehouse_model.xy_to_latlon(x, y)
            
            point = Point("rfid_reader") \
                .tag("reader_id", reader.reader_id) \
                .field("position", f"POINT({lon} {lat})") \
                .field("x", x) \
                .field("y", y) \
                .field("z", z) \
                .field("range", reader.read_range) \
                .time(datetime.utcnow(), WritePrecision.NS)
                
            reader_points.append(point)
        
        # Write reader points
        self.write_api.write(bucket=self.bucket, record=reader_points)
        
        print(f"Exported {len(readers)} RFID readers")
    
    def export_pallet_position(self, pallet: VirtualPallet, warehouse_model: WarehouseModel,
                             timestamp: Optional[float] = None):
        """
        Export a single pallet position to InfluxDB.
        
        Args:
            pallet: VirtualPallet instance
            warehouse_model: WarehouseModel for coordinate conversion
            timestamp: Optional timestamp, defaults to current time
        """
        if timestamp is None:
            timestamp = time.time()
        
        # Convert to nanosecond timestamp for InfluxDB
        ns_timestamp = int(timestamp * 1e9)
        
        x, y, z = pallet.position
        lat, lon = warehouse_model.xy_to_latlon(x, y)
        
        # Get velocity if available
        vx, vy, vz = pallet.get_velocity()
        speed = np.sqrt(vx**2 + vy**2 + vz**2)
        
        point = Point("pallet_position") \
            .tag("pallet_id", pallet.pallet_id) \
            .tag("content_type", pallet.content_type) \
            .field("position", f"POINT({lon} {lat})") \
            .field("x", x) \
            .field("y", y) \
            .field("z", z) \
            .field("vx", vx) \
            .field("vy", vy) \
            .field("vz", vz) \
            .field("speed", speed) \
            .field("weight", pallet.weight) \
            .field("tag_count", len(pallet.tag_ids)) \
            .time(ns_timestamp, WritePrecision.NS)
            
        self._add_point(point)
    
    def export_pallet_batch(self, pallets: List[VirtualPallet], warehouse_model: WarehouseModel):
        """
        Export multiple pallets in a single batch.
        
        Args:
            pallets: List of VirtualPallet instances
            warehouse_model: WarehouseModel for coordinate conversion
        """
        timestamp = time.time()
        
        for pallet in pallets:
            self.export_pallet_position(pallet, warehouse_model, timestamp)
        
        # Flush the cache to ensure all points are written
        self._flush_cache()
        
        print(f"Exported batch of {len(pallets)} pallets")
    
    def export_uwb_measurements(self, tag_id: str, measurements: Dict[str, float],
                               tag_position: Tuple[float, float, float],
                               warehouse_model: WarehouseModel,
                               timestamp: Optional[float] = None):
        """
        Export UWB distance measurements for a tag.
        
        Args:
            tag_id: ID of the UWB tag
            measurements: Dictionary mapping sensor IDs to measured distances
            tag_position: True position of the tag
            warehouse_model: WarehouseModel for coordinate conversion
            timestamp: Optional timestamp, defaults to current time
        """
        if timestamp is None:
            timestamp = time.time()
        
        # Convert to nanosecond timestamp for InfluxDB
        ns_timestamp = int(timestamp * 1e9)
        
        # Create a point for the true position
        x, y, z = tag_position
        lat, lon = warehouse_model.xy_to_latlon(x, y)
        
        true_pos_point = Point("uwb_tag_true_position") \
            .tag("tag_id", tag_id) \
            .field("position", f"POINT({lon} {lat})") \
            .field("x", x) \
            .field("y", y) \
            .field("z", z) \
            .time(ns_timestamp, WritePrecision.NS)
            
        self._add_point(true_pos_point)
        
        # Create points for each measurement
        for sensor_id, distance in measurements.items():
            measurement_point = Point("uwb_measurement") \
                .tag("tag_id", tag_id) \
                .tag("sensor_id", sensor_id) \
                .field("distance", distance) \
                .time(ns_timestamp, WritePrecision.NS)
                
            self._add_point(measurement_point)
    
    def export_rfid_detection(self, reader_id: str, tag_id: str, 
                             rssi: float, 
                             tag_position: Tuple[float, float, float],
                             warehouse_model: WarehouseModel,
                             timestamp: Optional[float] = None):
        """
        Export RFID tag detection.
        
        Args:
            reader_id: ID of the RFID reader
            tag_id: ID of the detected tag
            rssi: Received signal strength indicator
            tag_position: True position of the tag
            warehouse_model: WarehouseModel for coordinate conversion
            timestamp: Optional timestamp, defaults to current time
        """
        if timestamp is None:
            timestamp = time.time()
        
        # Convert to nanosecond timestamp for InfluxDB
        ns_timestamp = int(timestamp * 1e9)
        
        # Position data
        x, y, z = tag_position
        lat, lon = warehouse_model.xy_to_latlon(x, y)
        
        point = Point("rfid_detection") \
            .tag("reader_id", reader_id) \
            .tag("tag_id", tag_id) \
            .field("position", f"POINT({lon} {lat})") \
            .field("x", x) \
            .field("y", y) \
            .field("z", z) \
            .field("rssi", rssi) \
            .time(ns_timestamp, WritePrecision.NS)
            
        self._add_point(point)


class CSVExporter:
    """
    Exports simulation data to CSV files for analysis or importing to other tools.
    """
    
    def __init__(self, output_dir: str = "./data"):
        """
        Initialize CSV exporter.
        
        Args:
            output_dir: Directory to save CSV files
        """
        self.output_dir = output_dir
        
        # Ensure output directory exists
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        # File handles for different data types
        self.files = {}
        self.writers = {}
    
    def open_file(self, data_type: str, headers: List[str]):
        """
        Open a CSV file for a specific data type.
        
        Args:
            data_type: Type of data being exported
            headers: CSV headers
        """
        import csv
        import os
        
        # Close if already open
        self.close_file(data_type)
        
        # Open new file
        filename = os.path.join(self.output_dir, f"{data_type}.csv")
        self.files[data_type] = open(filename, 'w', newline='')
        
        # Create CSV writer
        writer = csv.writer(self.files[data_type])
        writer.writerow(headers)
        
        self.writers[data_type] = writer
    
    def close_file(self, data_type: str):
        """
        Close a CSV file.
        
        Args:
            data_type: Type of data file to close
        """
        if data_type in self.files:
            self.files[data_type].close()
            del self.files[data_type]
            del self.writers[data_type]
    
    def close_all(self):
        """Close all open CSV files."""
        for data_type in list(self.files.keys()):
            self.close_file(data_type)
    
    def export_pallet_position(self, pallet: VirtualPallet, 
                              timestamp: Optional[float] = None):
        """
        Export pallet position to CSV.
        
        Args:
            pallet: VirtualPallet instance
            timestamp: Optional timestamp, defaults to current time
        """
        if timestamp is None:
            timestamp = time.time()
        
        # Ensure file is open
        if "pallet_positions" not in self.writers:
            headers = ["timestamp", "pallet_id", "x", "y", "z", "vx", "vy", "vz", "content_type", "weight"]
            self.open_file("pallet_positions", headers)
        
        # Get position and velocity
        x, y, z = pallet.position
        vx, vy, vz = pallet.get_velocity()
        
        # Write row
        self.writers["pallet_positions"].writerow([
            timestamp, pallet.pallet_id, x, y, z, vx, vy, vz, 
            pallet.content_type, pallet.weight
        ])
    
    def export_uwb_measurement(self, tag_id: str, sensor_id: str, 
                              distance: float, 
                              true_position: Tuple[float, float, float],
                              sensor_position: Tuple[float, float, float],
                              timestamp: Optional[float] = None):
        """
        Export UWB measurement to CSV.
        
        Args:
            tag_id: ID of the UWB tag
            sensor_id: ID of the UWB sensor
            distance: Measured distance
            true_position: True position of the tag (x, y, z)
            sensor_position: Position of the sensor (x, y, z)
            timestamp: Optional timestamp, defaults to current time
        """
        if timestamp is None:
            timestamp = time.time()
        
        # Ensure file is open
        if "uwb_measurements" not in self.writers:
            headers = ["timestamp", "tag_id", "sensor_id", "distance", 
                      "tag_x", "tag_y", "tag_z", 
                      "sensor_x", "sensor_y", "sensor_z"]
            self.open_file("uwb_measurements", headers)
        
        # Write row
        self.writers["uwb_measurements"].writerow([
            timestamp, tag_id, sensor_id, distance,
            true_position[0], true_position[1], true_position[2],
            sensor_position[0], sensor_position[1], sensor_position[2]
        ])
    
    def export_rfid_detection(self, reader_id: str, tag_id: str, 
                             rssi: float, 
                             tag_position: Tuple[float, float, float],
                             reader_position: Tuple[float, float, float],
                             timestamp: Optional[float] = None):
        """
        Export RFID detection to CSV.
        
        Args:
            reader_id: ID of the RFID reader
            tag_id: ID of the detected tag
            rssi: Received signal strength indicator
            tag_position: True position of the tag (x, y, z)
            reader_position: Position of the reader (x, y, z)
            timestamp: Optional timestamp, defaults to current time
        """
        if timestamp is None:
            timestamp = time.time()
        
        # Ensure file is open
        if "rfid_detections" not in self.writers:
            headers = ["timestamp", "reader_id", "tag_id", "rssi",
                      "tag_x", "tag_y", "tag_z",
                      "reader_x", "reader_y", "reader_z"]
            self.open_file("rfid_detections", headers)
        
        # Write row
        self.writers["rfid_detections"].writerow([
            timestamp, reader_id, tag_id, rssi,
            tag_position[0], tag_position[1], tag_position[2],
            reader_position[0], reader_position[1], reader_position[2]
        ])