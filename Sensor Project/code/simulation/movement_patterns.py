"""
Movement Patterns for UWB-RFID Indoor Positioning System.

This module provides generators for different movement patterns used to
simulate pallet movements in the warehouse environment.
"""

import numpy as np
import math
import time
from typing import Tuple, List, Generator, Optional, Dict, Callable
from .warehouse_model import WarehouseModel
from .virtual_pallet import VirtualPallet


class MovementPattern:
    """Base class for movement pattern generators."""
    
    def __init__(self, warehouse_model: WarehouseModel):
        """
        Initialize with warehouse model for collision avoidance.
        
        Args:
            warehouse_model: WarehouseModel instance for collision checking
        """
        self.warehouse_model = warehouse_model
        
    def generate_path(self, 
                      start_position: Tuple[float, float, float],
                      end_position: Tuple[float, float, float], 
                      speed: float = 1.0,
                      time_step: float = 0.1) -> Generator[Tuple[Tuple[float, float, float], float], None, None]:
        """
        Generate movement path from start to end position.
        
        Args:
            start_position: Starting (x, y, z) position
            end_position: Ending (x, y, z) position
            speed: Movement speed in m/s
            time_step: Time step between positions in seconds
            
        Yields:
            Tuples of ((x, y, z), timestamp)
        """
        raise NotImplementedError("Subclasses must implement this method")


class LinearMovement(MovementPattern):
    """Generate linear movement between two points."""
    
    def generate_path(self, 
                      start_position: Tuple[float, float, float],
                      end_position: Tuple[float, float, float], 
                      speed: float = 1.0,
                      time_step: float = 0.1) -> Generator[Tuple[Tuple[float, float, float], float], None, None]:
        """
        Generate straight-line movement path from start to end position.
        
        Args:
            start_position: Starting (x, y, z) position
            end_position: Ending (x, y, z) position
            speed: Movement speed in m/s
            time_step: Time step between positions in seconds
            
        Yields:
            Tuples of ((x, y, z), timestamp)
        """
        # Calculate distance between points
        dx = end_position[0] - start_position[0]
        dy = end_position[1] - start_position[1]
        dz = end_position[2] - start_position[2]
        
        distance = math.sqrt(dx**2 + dy**2 + dz**2)
        
        # Calculate total time needed
        total_time = distance / speed
        
        # Calculate step size
        num_steps = max(2, int(total_time / time_step))
        
        # Generate path points
        current_time = time.time()
        
        for i in range(num_steps + 1):
            t = i / num_steps  # Interpolation factor [0..1]
            
            # Linear interpolation
            x = start_position[0] + t * dx
            y = start_position[1] + t * dy
            z = start_position[2] + t * dz
            
            position = (x, y, z)
            timestamp = current_time + i * time_step
            
            yield (position, timestamp)


class PathMovement(MovementPattern):
    """Generate movement along a predefined path."""
    
    def __init__(self, warehouse_model: WarehouseModel, waypoints: List[Tuple[float, float, float]]):
        """
        Initialize with warehouse model and waypoints.
        
        Args:
            warehouse_model: WarehouseModel instance
            waypoints: List of (x, y, z) positions to visit
        """
        super().__init__(warehouse_model)
        self.waypoints = waypoints
    
    def generate_path(self, 
                      start_position: Optional[Tuple[float, float, float]] = None,
                      end_position: Optional[Tuple[float, float, float]] = None, 
                      speed: float = 1.0,
                      time_step: float = 0.1) -> Generator[Tuple[Tuple[float, float, float], float], None, None]:
        """
        Generate movement path along waypoints.
        
        Args:
            start_position: Optional starting position, defaults to first waypoint
            end_position: Optional ending position, defaults to last waypoint
            speed: Movement speed in m/s
            time_step: Time step between positions in seconds
            
        Yields:
            Tuples of ((x, y, z), timestamp)
        """
        # Use provided waypoints
        path = list(self.waypoints)
        
        # Override start/end if provided
        if start_position:
            path = [start_position] + path[1:]
            
        if end_position:
            path = path[:-1] + [end_position]
        
        # Generate movement between consecutive waypoints
        linear_movement = LinearMovement(self.warehouse_model)
        current_time = time.time()
        
        for i in range(len(path) - 1):
            segment_start = path[i]
            segment_end = path[i+1]
            
            # Generate segment
            for position, timestamp in linear_movement.generate_path(
                segment_start, segment_end, speed, time_step
            ):
                if i == 0 or position != segment_start:  # Avoid yielding the same point twice
                    yield (position, current_time + (timestamp - current_time))


class RandomMovement(MovementPattern):
    """Generate random movement within a defined area."""
    
    def __init__(self, warehouse_model: WarehouseModel, 
                 area_min: Tuple[float, float, float], 
                 area_max: Tuple[float, float, float],
                 randomness: float = 0.5,
                 avoid_obstacles: bool = True):
        """
        Initialize with area bounds and randomness factor.
        
        Args:
            warehouse_model: WarehouseModel instance
            area_min: Minimum (x, y, z) bounds
            area_max: Maximum (x, y, z) bounds
            randomness: Factor controlling randomness (0.0-1.0)
            avoid_obstacles: Whether to check for obstacle collisions
        """
        super().__init__(warehouse_model)
        self.area_min = area_min
        self.area_max = area_max
        self.randomness = max(0.0, min(1.0, randomness))  # Clamp to [0, 1]
        self.avoid_obstacles = avoid_obstacles
    
    def _random_point(self) -> Tuple[float, float, float]:
        """Generate a random point within the defined area."""
        x = np.random.uniform(self.area_min[0], self.area_max[0])
        y = np.random.uniform(self.area_min[1], self.area_max[1])
        z = np.random.uniform(self.area_min[2], self.area_max[2])
        return (x, y, z)
    
    def _check_valid_point(self, position: Tuple[float, float, float], 
                           dimensions: Tuple[float, float, float] = (1.0, 1.0, 1.0)) -> bool:
        """Check if a point is valid (within bounds and not colliding)."""
        # Check if within bounds
        for i in range(3):
            if position[i] < self.area_min[i] or position[i] > self.area_max[i]:
                return False
        
        # Check for obstacle collision if enabled
        if self.avoid_obstacles:
            return not self.warehouse_model.check_collision(position, dimensions)
        
        return True
    
    def generate_path(self, 
                      start_position: Tuple[float, float, float],
                      end_position: Optional[Tuple[float, float, float]] = None, 
                      speed: float = 1.0,
                      time_step: float = 0.1,
                      num_waypoints: int = 5,
                      max_duration: float = 60.0) -> Generator[Tuple[Tuple[float, float, float], float], None, None]:
        """
        Generate random movement path starting from start_position.
        
        Args:
            start_position: Starting (x, y, z) position
            end_position: Optional ending position
            speed: Movement speed in m/s
            time_step: Time step between positions in seconds
            num_waypoints: Number of random waypoints to generate
            max_duration: Maximum duration of movement in seconds
            
        Yields:
            Tuples of ((x, y, z), timestamp)
        """
        # Generate random waypoints
        waypoints = [start_position]
        
        for _ in range(num_waypoints):
            # For each waypoint, either go toward end or random
            if end_position and np.random.random() > self.randomness:
                # Move toward end position
                next_point = (
                    waypoints[-1][0] + (end_position[0] - waypoints[-1][0]) * 0.5,
                    waypoints[-1][1] + (end_position[1] - waypoints[-1][1]) * 0.5,
                    waypoints[-1][2] + (end_position[2] - waypoints[-1][2]) * 0.5
                )
            else:
                # Generate a random direction
                angle = np.random.uniform(0, 2 * np.pi)
                distance = np.random.uniform(1.0, 5.0)  # Random distance
                
                next_point = (
                    waypoints[-1][0] + distance * np.cos(angle),
                    waypoints[-1][1] + distance * np.sin(angle),
                    waypoints[-1][2]  # Typically keep z constant for ground movement
                )
            
            # Ensure point is valid
            attempts = 0
            while not self._check_valid_point(next_point) and attempts < 10:
                # Try a different random point
                next_point = self._random_point()
                attempts += 1
            
            if attempts < 10:  # Only add if we found a valid point
                waypoints.append(next_point)
        
        # Add end position if specified
        if end_position:
            waypoints.append(end_position)
        
        # Generate movement between consecutive waypoints
        path_movement = PathMovement(self.warehouse_model, waypoints)
        total_duration = 0.0
        
        for position, timestamp in path_movement.generate_path(
            None, None, speed, time_step
        ):
            # Check if we've exceeded maximum duration
            elapsed = timestamp - time.time()
            if elapsed > max_duration:
                break
                
            yield (position, timestamp)
            total_duration = elapsed


# Factory for creating movement patterns
def create_movement_pattern(pattern_type: str, warehouse_model: WarehouseModel, **kwargs) -> MovementPattern:
    """
    Factory function for creating movement patterns.
    
    Args:
        pattern_type: Type of movement pattern ("linear", "path", "random")
        warehouse_model: WarehouseModel instance
        **kwargs: Additional arguments for specific pattern types
        
    Returns:
        MovementPattern instance
    """
    if pattern_type == "linear":
        return LinearMovement(warehouse_model)
    
    elif pattern_type == "path":
        waypoints = kwargs.get("waypoints", [])
        return PathMovement(warehouse_model, waypoints)
    
    elif pattern_type == "random":
        area_min = kwargs.get("area_min", (0, 0, 0))
        area_max = kwargs.get("area_max", (warehouse_model.width, warehouse_model.length, warehouse_model.height))
        randomness = kwargs.get("randomness", 0.5)
        avoid_obstacles = kwargs.get("avoid_obstacles", True)
        return RandomMovement(warehouse_model, area_min, area_max, randomness, avoid_obstacles)
    
    else:
        raise ValueError(f"Unknown movement pattern type: {pattern_type}")


# Common warehouse movement scenarios
def create_pickup_dropoff_pattern(warehouse_model: WarehouseModel,
                                  pickup_point: Tuple[float, float, float],
                                  dropoff_point: Tuple[float, float, float],
                                  intermediate_points: Optional[List[Tuple[float, float, float]]] = None,
                                  speed: float = 1.0) -> PathMovement:
    """
    Create a pattern for pickup and dropoff operations.
    
    Args:
        warehouse_model: WarehouseModel instance
        pickup_point: Coordinates of pickup location
        dropoff_point: Coordinates of dropoff location
        intermediate_points: Optional waypoints between pickup and dropoff
        speed: Movement speed in m/s
        
    Returns:
        PathMovement instance
    """
    # Build waypoints list
    waypoints = [pickup_point]
    
    if intermediate_points:
        waypoints.extend(intermediate_points)
        
    waypoints.append(dropoff_point)
    
    return PathMovement(warehouse_model, waypoints)


def create_aisle_patrol_pattern(warehouse_model: WarehouseModel, 
                                aisle_start: Tuple[float, float],
                                aisle_end: Tuple[float, float],
                                aisle_width: float = 3.0,
                                z_height: float = 0.2,
                                speed: float = 0.8) -> PathMovement:
    """
    Create a back-and-forth patrol pattern along a warehouse aisle.
    
    Args:
        warehouse_model: WarehouseModel instance
        aisle_start: (x, y) start of the aisle
        aisle_end: (x, y) end of the aisle
        aisle_width: Width of the aisle
        z_height: Z-coordinate height
        speed: Movement speed in m/s
        
    Returns:
        PathMovement instance
    """
    # Calculate perpendicular direction for aisle width
    dx = aisle_end[0] - aisle_start[0]
    dy = aisle_end[1] - aisle_start[1]
    length = math.sqrt(dx**2 + dy**2)
    
    # Normalized perpendicular vector
    if length > 0:
        perpx = -dy / length
        perpy = dx / length
    else:
        perpx, perpy = 1.0, 0.0
    
    # Create zigzag pattern
    waypoints = []
    
    # Start at one corner
    waypoints.append((aisle_start[0], aisle_start[1], z_height))
    
    # Go to opposite corner
    waypoints.append((aisle_end[0], aisle_end[1], z_height))
    
    # Move to side
    waypoints.append((
        aisle_end[0] + perpx * aisle_width,
        aisle_end[1] + perpy * aisle_width,
        z_height
    ))
    
    # Go back to start side
    waypoints.append((
        aisle_start[0] + perpx * aisle_width,
        aisle_start[1] + perpy * aisle_width,
        z_height
    ))
    
    # Close the loop
    waypoints.append((aisle_start[0], aisle_start[1], z_height))
    
    return PathMovement(warehouse_model, waypoints)