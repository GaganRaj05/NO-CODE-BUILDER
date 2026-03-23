from pydantic import BaseModel, Field, EmailStr, model_validator, field_validator
from datetime import datetime
from typing import Optional
from enum import Enum

class AuthProvider(str, Enum):
    email = "email"
    google = "google"

class UserSignUp(BaseModel):
    name: str = Field(..., min_length=5, description="Name Text")
    email: EmailStr
    authProvider: AuthProvider
    google_token: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)
    

    @model_validator(mode="after")
    def validate_auth(self):
        if self.authProvider == "google" and not self.google_token :
            raise ValueError("google_id is required for Google auth")

        if self.authProvider == "email" and not self.password:
            raise ValueError("password is required for email auth")

        return self
    
class UserSignIn(BaseModel):
    email:EmailStr 
    password:str = Field(..., min_length = 8)
    
