"""
Warehouse Model for UWB-RFID Indoor Positioning System.

This module provides the WarehouseModel class for creating and managing a virtual
warehouse environment, including obstacles and coordinate conversions for visualization.
"""

import numpy as np
import json
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class Obstacle:
    position: Tuple[float, float, float]  # (x, y, z) coordinates
    dimensions: Tuple[float, float, float]  # (width, length, height)
    obstacle_type: str  # 'shelf', 'wall', 'column', etc.
    id: str  # Unique identifier

class WarehouseModel:
    def __init__(self, width: float, length: float, height: float, 
                 origin: Tuple[float, float, float] = (0, 0, 0),
                 name: str = "Warehouse"):
        """
        Initialize warehouse with dimensions and origin point.
        
        Args:
            width: Width of warehouse (X dimension) in meters
            length: Length of warehouse (Y dimension) in meters
            height: Height of warehouse (Z dimension) in meters
            origin: Coordinates of the warehouse origin point
            name: Name of the warehouse
        """
        self.width = width
        self.length = length
        self.height = height
        self.origin = origin
        self.name = name
        self.obstacles: List[Obstacle] = []
        
        # For Grafana geomap visualization, we'll store GPS reference coordinates
        self.reference_lat = 0.0  # Reference latitude for (0,0) point
        self.reference_lon = 0.0  # Reference longitude for (0,0) point
        self.meters_per_lat = 111320.0  # Approximate meters per degree latitude
        self.meters_per_lon = 111320.0  # Will be adjusted based on latitude
    
    def set_gps_reference(self, lat: float, lon: float):
        """
        Set the GPS reference coordinates for geomap visualization.
        
        Args:
            lat: Latitude coordinate for warehouse origin
            lon: Longitude coordinate for warehouse origin
        """
        self.reference_lat = lat
        self.reference_lon = lon
        # Adjust meters per longitude degree based on latitude
        self.meters_per_lon = 111320.0 * np.cos(np.radians(lat))
    
    def xy_to_latlon(self, x: float, y: float) -> Tuple[float, float]:
        """
        Convert warehouse coordinates to GPS coordinates for visualization.
        
        Args:
            x: X coordinate in warehouse space (meters)
            y: Y coordinate in warehouse space (meters)
            
        Returns:
            Tuple of (latitude, longitude) corresponding to the warehouse position
        """
        lat = self.reference_lat + (y / self.meters_per_lat)
        lon = self.reference_lon + (x / self.meters_per_lon)
        return (lat, lon)
    
    def latlon_to_xy(self, lat: float, lon: float) -> Tuple[float, float]:
        """
        Convert GPS coordinates to warehouse coordinates.
        
        Args:
            lat: Latitude coordinate
            lon: Longitude coordinate
            
        Returns:
            Tuple of (x, y) in warehouse space (meters)
        """
        y = (lat - self.reference_lat) * self.meters_per_lat
        x = (lon - self.reference_lon) * self.meters_per_lon
        return (x, y)
    
    def add_obstacle(self, position: Tuple[float, float, float], 
                     dimensions: Tuple[float, float, float], 
                     obstacle_type: str, 
                     obstacle_id: Optional[str] = None) -> str:
        """
        Add an obstacle to the warehouse.
        
        Args:
            position: Position (x, y, z) in meters
            dimensions: Dimensions (width, length, height) in meters
            obstacle_type: Type of obstacle (e.g., "shelf", "wall")
            obstacle_id: Optional ID for the obstacle
            
        Returns:
            ID of the created obstacle
        """
        if obstacle_id is None:
            obstacle_id = f"obstacle_{len(self.obstacles)}"
            
        obstacle = Obstacle(position, dimensions, obstacle_type, obstacle_id)
        self.obstacles.append(obstacle)
        return obstacle_id
    
    def remove_obstacle(self, obstacle_id: str) -> bool:
        """
        Remove an obstacle by ID.
        
        Args:
            obstacle_id: ID of the obstacle to remove
            
        Returns:
            True if obstacle was removed, False if not found
        """
        for i, obstacle in enumerate(self.obstacles):
            if obstacle.id == obstacle_id:
                self.obstacles.pop(i)
                return True
        return False
    
    def get_floor_plan(self) -> Dict:
        """
        Return a 2D representation of the warehouse floor plan.
        
        Returns:
            Dictionary with warehouse dimensions and obstacles
        """
        floor_plan = {
            "dimensions": {"width": self.width, "length": self.length},
            "obstacles": []
        }
        
        for obstacle in self.obstacles:
            if obstacle.position[2] < 0.5:  # Only include ground-level obstacles
                floor_plan["obstacles"].append({
                    "id": obstacle.id,
                    "position": obstacle.position[:2],  # Only x,y
                    "dimensions": obstacle.dimensions[:2],  # Only width,length
                    "type": obstacle.obstacle_type
                })
                
        return floor_plan
    
    def check_collision(self, position: Tuple[float, float, float], 
                        dimensions: Tuple[float, float, float]) -> bool:
        """
        Check if there would be a collision at the given position.
        
        Args:
            position: Position to check (x, y, z)
            dimensions: Dimensions of object to check (width, length, height)
            
        Returns:
            True if a collision would occur, False otherwise
        """
        # Check if position is outside warehouse boundaries
        x, y, z = position
        w, l, h = dimensions
        
        # Check warehouse boundaries
        if (x < 0 or x + w > self.width or 
            y < 0 or y + l > self.length or 
            z < 0 or z + h > self.height):
            return True
        
        # Check collision with obstacles
        for obstacle in self.obstacles:
            ox, oy, oz = obstacle.position
            ow, ol, oh = obstacle.dimensions
            
            # Simple box collision check
            if (x < ox + ow and x + w > ox and
                y < oy + ol and y + l > oy and
                z < oz + oh and z + h > oz):
                return True
        
        return False
    
    def visualize(self, show_3d: bool = False, 
                  show_obstacles: bool = True,
                  save_path: Optional[str] = None):
        """
        Visualize the warehouse.
        
        Args:
            show_3d: If True, show 3D visualization, otherwise 2D
            show_obstacles: If True, show obstacles in visualization
            save_path: Optional path to save visualization image
        """
        if show_3d:
            # Create 3D visualization
            fig = plt.figure(figsize=(10, 8))
            ax = fig.add_subplot(111, projection='3d')
            
            # Plot warehouse boundaries as a wireframe box
            x = [0, self.width, self.width, 0, 0]
            y = [0, 0, self.length, self.length, 0]
            z = [0, 0, 0, 0, 0]
            ax.plot(x, y, z, 'k-')
            
            x = [0, self.width, self.width, 0, 0]
            y = [0, 0, self.length, self.length, 0]
            z = [self.height, self.height, self.height, self.height, self.height]
            ax.plot(x, y, z, 'k-')
            
            # Connect bottom to top
            for i in range(4):
                ax.plot([x[i], x[i]], [y[i], y[i]], [0, self.height], 'k-')
            
            if show_obstacles:
                for obstacle in self.obstacles:
                    ox, oy, oz = obstacle.position
                    ow, ol, oh = obstacle.dimensions
                    
                    # Plot obstacle as a box
                    x = [ox, ox+ow, ox+ow, ox, ox]
                    y = [oy, oy, oy+ol, oy+ol, oy]
                    z = [oz, oz, oz, oz, oz]
                    ax.plot(x, y, z, 'b-')
                    
                    x = [ox, ox+ow, ox+ow, ox, ox]
                    y = [oy, oy, oy+ol, oy+ol, oy]
                    z = [oz+oh, oz+oh, oz+oh, oz+oh, oz+oh]
                    ax.plot(x, y, z, 'b-')
                    
                    # Connect bottom to top
                    for i in range(4):
                        ax.plot([x[i], x[i]], [y[i], y[i]], [oz, oz+oh], 'b-')
            
            ax.set_xlabel('X (meters)')
            ax.set_ylabel('Y (meters)')
            ax.set_zlabel('Z (meters)')
            ax.set_title(f"{self.name} - 3D View")
            
        else:
            # Create 2D visualization
            fig, ax = plt.subplots(figsize=(10, 8))
            
            # Plot warehouse boundaries
            ax.add_patch(plt.Rectangle(self.origin[:2], self.width, self.length, 
                                       fill=False, edgecolor='black', linewidth=2))
            
            if show_obstacles:
                for obstacle in self.obstacles:
                    # Draw each obstacle
                    x, y, _ = obstacle.position
                    w, l, _ = obstacle.dimensions
                    
                    # Different colors based on obstacle type
                    if obstacle.obstacle_type == 'shelf':
                        color = 'blue'
                    elif obstacle.obstacle_type == 'wall':
                        color = 'red'
                    else:
                        color = 'green'
                        
                    ax.add_patch(plt.Rectangle((x, y), w, l, fill=True, 
                                             color=color, alpha=0.5))
                    # Add label
                    ax.text(x + w/2, y + l/2, obstacle.id, 
                            horizontalalignment='center',
                            verticalalignment='center',
                            fontsize=8, color='black')
        
            plt.axis('equal')
            plt.xlim(0, self.width)
            plt.ylim(0, self.length)
            plt.title(f"{self.name} Floor Plan")
            plt.xlabel("X (meters)")
            plt.ylabel("Y (meters)")
            
            # Add a grid
            plt.grid(True, linestyle='--', alpha=0.7)
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()
    
    def save_layout(self, filename: str):
        """
        Save warehouse layout to a JSON file.
        
        Args:
            filename: Path to save the layout file
        """
        data = {
            "name": self.name,
            "dimensions": {
                "width": self.width,
                "length": self.length,
                "height": self.height
            },
            "origin": self.origin,
            "obstacles": [
                {
                    "id": o.id,
                    "position": o.position,
                    "dimensions": o.dimensions,
                    "type": o.obstacle_type
                } for o in self.obstacles
            ],
            "geomap": {
                "reference_lat": self.reference_lat,
                "reference_lon": self.reference_lon
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load_layout(cls, filename: str) -> 'WarehouseModel':
        """
        Load warehouse layout from a JSON file.
        
        Args:
            filename: Path to the layout file
            
        Returns:
            WarehouseModel instance with the loaded layout
        """
        with open(filename, 'r') as f:
            data = json.load(f)
        
        model = cls(
            width=data["dimensions"]["width"],
            length=data["dimensions"]["length"],
            height=data["dimensions"]["height"],
            origin=tuple(data["origin"]),
            name=data["name"]
        )
        
        # Load geomap reference if available
        if "geomap" in data:
            model.reference_lat = data["geomap"]["reference_lat"]
            model.reference_lon = data["geomap"]["reference_lon"]
            # Update meters per lon
            model.meters_per_lon = 111320.0 * np.cos(np.radians(model.reference_lat))
        
        # Load obstacles
        for obstacle_data in data["obstacles"]:
            model.add_obstacle(
                position=tuple(obstacle_data["position"]),
                dimensions=tuple(obstacle_data["dimensions"]),
                obstacle_type=obstacle_data["type"],
                obstacle_id=obstacle_data["id"]
            )
        
        return model
