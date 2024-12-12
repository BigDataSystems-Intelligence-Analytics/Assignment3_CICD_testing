import os 
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, constr, EmailStr, validator

class RegisterUser(BaseModel):
    first_name: str
    last_name: str
    phone: constr(pattern=r'^\d{10}$')
    email: EmailStr
    password: constr(min_length=8)

    @validator('password')
    def validate_password(cls, value):
        if not any(char.islower() for char in value):
            raise ValueError('Password must contain at least one lowercase letter.')
        if not any(char.isupper() for char in value):
            raise ValueError('Password must contain at least one uppercase letter.')
        if not any(char.isdigit() for char in value):
            raise ValueError('Password must contain atleast one digit.')
        if not any(char in '!@#$%^&*()-_=+[]{}|;:,.<>?/' for char in value):
            raise ValueError('Password must contain at least one special character.')
        return value

class LoginUser(BaseModel):
    email: EmailStr
    password: constr(max_length=8)

    @validator('password')
    def validate_password(cls, value):
        if not any(char.islower() for char in value):
            raise ValueError('Password must contain at least one lowercase letter.')
        if not any(char.isupper() for char in value):
            raise ValueError('Password must contain at least one uppercase letter.')
        if not any(char.isdigit() for char in value):
            raise ValueError('Password must contain atleast one digit.')
        if not any(char in '!@#$%^&*()-_=+[]{}|;:,.<>?/' for char in value):
            raise ValueError('Password must contain at least one special character.')
        return value
    
class ExploreDocs(BaseModel):
    count: Optional[int] = None

class LoadDocument(BaseModel):
    document_id: str

class SourceType(str, Enum):
    full_text = "full_text"
    report = "report"

class PromptType(str, Enum):
    report = "report"
    default = "default"

class UserPrompts(BaseModel):
    question: str
    prompt_type: PromptType
    source : SourceType