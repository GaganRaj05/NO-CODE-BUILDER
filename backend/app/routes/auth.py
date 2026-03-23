from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import JSONResponse
from app.models.User import Users
from app.core.config import ALGORITHM, SECRET_KEY
from app.schemas.auth import UserSignUp, UserSignIn
import logging
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/sign-in")
async def login(data: UserSignIn, response:Response):
    try:
        user = await Users.find_one({"email":data.email})
        if not user:
            raise HTTPException(status_code = 400, detail = {"success":False, "msg":"No users found"})
        
        verify = pwd_context.verify(data.password, user.password)
        if not verify:
            raise HTTPException(status_code = 401, detail = {"success":False, "msg":"Incorrect password"})
        
        token = jwt.encode({"id":str(user.id), "email":user.email,"exp":datetime.utcnow()+timedelta(minutes=60)},SECRET_KEY, algorithm=ALGORITHM)
        
        response.set_cookie(
            key = "auth_token",
            value = token,
            secure = True,
            httpOnly = True,
            sameSite = "none",
            path = "/",
            max_age = 3600,
        )
        return {
            "success": True,
            "msg": "Login Successful"
        }        
    except Exception as e:
        logger.error(f"Signup route ran into an error:\n{str(e)}")
        raise HTTPException(status_code = 500, detail = {"success":False, "msg":"Some error occured, Please try again later"}) 
    
    