from datetime import date
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class UserSignup(BaseModel):
    username: str
    first_name: str
    last_name: str
    email: str
    password: str
    location: str
    title: str 
    speciality: str 
    department: str 
