from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from database import Base

class Vehicle(Base):
    __tablename__ = "vehicles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, default="Toyota Etios")
    plate_number = Column(String, unique=True)
    current_odometer = Column(Float, default=125430.0)
    last_oil_change = Column(Float, default=125000.0)

class Trip(Base):
    __tablename__ = "trips"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String)
    customer_phone = Column(String, nullable=True) # New field
    
    # Split Route into From and To
    from_location = Column(String, nullable=True) # New field
    to_location = Column(String, nullable=True)   # New field
    pickup_location = Column(String, nullable=True) # New field
    
    driver_name = Column(String, default="Ravi")
    
    # KM Tracking
    start_km = Column(Float)
    end_km = Column(Float, nullable=True)
    
    # Financials
    total_fare = Column(Float, default=0.0)
    diesel_litres = Column(Float, default=0.0)
    diesel_cost = Column(Float, default=0.0)
    toll_cost = Column(Float, default=0.0)
    driver_commission = Column(Float, default=0.0)
    other_expenses = Column(Float, default=0.0)
    
    status = Column(String, default="Active") # Active or Completed
    created_at = Column(DateTime, default=datetime.utcnow)