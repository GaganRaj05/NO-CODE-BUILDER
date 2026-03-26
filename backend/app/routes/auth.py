from fastapi import APIRouter, HTTPException, Response, Query, Depends
from fastapi.responses import JSONResponse
from app.models.User import Users
from app.core.config import ALGORITHM, SECRET_KEY
from app.schemas.auth import UserSignUp, UserSignIn, EmailVerification, GoogleAuth
from app.services.redis import get_redis
from app.services.oauth import verify_google_token
from pydantic import EmailStr
import logging
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
import redis.asyncio as redis
import random
from app.models.Tenants import Tenants, TenantType
from app.models.Membership import Membership, Role


pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/sign-in")
async def signIn(data: UserSignIn, response:Response):
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
            httponly = True,
            samesite = "none",
            path = "/",
            max_age = 3600,
        )
        return {
            "success": True,
            "msg": "Login Successful"
        }   
    except HTTPException:
        raise      
    except Exception as e:
        logger.error(f"Signup route ran into an error:\n{str(e)}")
        raise HTTPException(status_code = 500, detail = {"success":False, "msg":"Some error occured, Please try again later"}) 
    

@router.get("/generate-otp")
async def generate_otp(email:EmailStr = Query(...), redis: redis.Redis = Depends(get_redis)):
    try:
        user = await Users.find_one({"email":email})
        if user:
            raise HTTPException(status_code = 400, detail={"success":False, "msg":"Email already taken"})
        otp = str(random.randint(100000, 999999))
        print(otp)
        #render emailing service to be added here
        
        await redis.set(f"otp:email:{email}", otp, ex=500)
        return {"success":True, "msg":"Otp generated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Otp generating route ran into an error:\n{str(e)}')
        raise HTTPException(status_code = 500, detail= {"success":False, "msg":"Some error occured please try again later"})
    
@router.post("/verify-email" )
async def verify_email(data:EmailVerification, redis: redis.Redis = Depends(get_redis)):
    try:
        otpStored = await redis.get(f"otp:email:{data.email}")
        if not otpStored:
            raise HTTPException(status_code = 410, detail = {"success":False, "msg":"Otp Expired"})
        
        if otpStored != data.otp:
            raise HTTPException(status_code = 401, detail = {"success":False, "msg":"Incorrect Otp"})
        
        return {"success":True, "msg":"Email verified successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Email Verification ran into an error:\n{str(e)}')
        raise HTTPException(status_code = 500, detail = {"success":False, "msg":"Some error occured, Please try again later"})
    
@router.post("/sign-up")
async def sign_up(data: UserSignUp):
    try:
        user = await Users.find_one({"email":data.email})
        if user:
            raise HTTPException(status_code=401, detail = {"success":False, "msg":"Email already taken"})
        hashed_pw =  pwd_context.hash(data.password)
        
        user = Users(
            name=data.name,
            email=data.email,
            auth_provider="email",
            google_id=None,
            subscription_tiers="free",
            password=hashed_pw
        )

        await user.insert()  
        
        tenant =  Tenants(
            type = TenantType.PERSONAL,
            name = data.name,
            created_by = str(user.id)
        )    
        
        await tenant.insert()
        
        membership =  Membership(
            user_id = str(user.id),
            tenant_id = str(tenant.id),
            role = Role.OWNER
        )
     
        await membership.insert()
        return {"success":True, "msg":"Account created successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"The signup route ran into an error:\n{str(e)}")
        raise HTTPException(status_code = 500, detail={"success":False, "msg":"Some error occured, Please try again later"})
    
    
@router.post("/google-auth")
async def google_auth(data: GoogleAuth, response:Response):
    try:
        payload = verify_google_token(data.google_token)
        if not payload:
            raise HTTPException(status_code=400, detail ={"success":False, "msg":"Invalid Google Token"})
        if not payload.get("email_verified"):
            raise HTTPException(400, detail={"success":False, "msg":"Email not verified"})
        email = payload["email"]
        google_id = payload["sub"]
        name = payload.get("name")
        
        user = await Users.find_one({"email":email})
        if user:    
            if user.authProvider == "email":
                raise HTTPException(status_code=403, detail={"success":False, "msg":"Use email login"})          
        else:
            user = Users(
                name=name,
                email=email,
                authProvider="google",
                google_id=google_id,
                password=None,
                subscriptionTier="free"
            )
            await user.insert()
            
            tenant =  Tenants(
                type = TenantType.PERSONAL,
                name = name,
                created_by = str(user.id),
            )

            await tenant.insert()
            
            membership =  Membership(
                user_id = str(user.id),
                tenant_id = str(tenant.id),
                role = Role.OWNER
            )
            await membership.insert()
        token = jwt.encode({"id":user.id, "email":user.email, "exp":datetime.utcnow()+timedelta(minutes=60)}, SECRET_KEY, algorithm=ALGORITHM)
        response.set_cookie(
            key="auth_token",
            value=token,
            samesite="none",
            secure=True,
            httponly=True,
            path="/",
            max_age = 3600,
        )        
        return {"success":True, "msg":"Account created successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code = 500, detail = {"success":False, "msg":"Some error occured, Please try again later"})