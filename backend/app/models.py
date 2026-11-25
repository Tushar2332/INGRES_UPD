from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from datetime import datetime
from .database import Base

class GroundwaterData(Base):
    __tablename__ = "groundwater_data"
    
    id = Column(Integer, primary_key=True, index=True)
    s_no = Column(String, index=True)
    state = Column(String, index=True)
    district = Column(String, index=True)
    assessment_unit = Column(String)
    rainfall_mm = Column(Float)
    total_geographical_area = Column(Float)
    ground_water_recharge = Column(Float)
    annual_extractable_gw_resource = Column(Float)
    gw_extraction = Column(Float)
    stage_of_gw_extraction = Column(Float)
    net_gw_availability = Column(Float)

    # Verified area, recharge-source, sectoral-extraction, environmental-flow & aquifer fields
    recharge_worthy_area_ha = Column(Float)
    hilly_area_ha = Column(Float)
    recharge_rainfall_ham = Column(Float)
    recharge_canals_ham = Column(Float)
    recharge_sw_irrigation_ham = Column(Float)
    recharge_gw_irrigation_ham = Column(Float)
    recharge_tanks_ponds_ham = Column(Float)
    recharge_wcs_ham = Column(Float)
    recharge_pipelines_ham = Column(Float)
    recharge_sewages_flash_flood_ham = Column(Float)
    env_flows_ham = Column(Float)
    extraction_domestic_ham = Column(Float)
    extraction_industrial_ham = Column(Float)
    extraction_irrigation_ham = Column(Float)
    domestic_alloc_2025_ham = Column(Float)
    potential_waterlogged_ham = Column(Float)
    potential_flood_prone_ham = Column(Float)
    potential_spring_discharge_ham = Column(Float)
    in_storage_unconfined_fresh_ham = Column(Float)
    in_storage_unconfined_saline_ham = Column(Float)
    total_unconfined_fresh_ham = Column(Float)
    total_unconfined_saline_ham = Column(Float)
    dynamic_confined_fresh_ham = Column(Float)
    in_storage_confined_fresh_ham = Column(Float)
    total_confined_fresh_ham = Column(Float)
    total_gw_availability_fresh_ham = Column(Float)
    total_gw_availability_saline_ham = Column(Float)

    # Official CGWB C (Command) / NC (Non-Command) / PQ (Poor Quality) breakdown
    extractable_c_ham = Column(Float)
    extractable_nc_ham = Column(Float)
    extractable_pq_ham = Column(Float)
    extraction_c_ham = Column(Float)
    extraction_nc_ham = Column(Float)
    extraction_pq_ham = Column(Float)
    stage_c_pct = Column(Float)
    stage_nc_pct = Column(Float)
    stage_pq_pct = Column(Float)
    net_availability_c_ham = Column(Float)
    net_availability_nc_ham = Column(Float)
    net_availability_pq_ham = Column(Float)
    extraction_domestic_c_ham = Column(Float)
    extraction_domestic_nc_ham = Column(Float)
    extraction_industrial_c_ham = Column(Float)
    extraction_industrial_nc_ham = Column(Float)
    extraction_irrigation_c_ham = Column(Float)
    extraction_irrigation_nc_ham = Column(Float)
    
class ChatHistory(Base):
    __tablename__ = "chat_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_message = Column(Text)
    bot_response = Column(Text)
    language = Column(String, default="en")
    timestamp = Column(DateTime, default=datetime.utcnow)
