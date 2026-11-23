from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database.db_engine import get_db
from dto.request.create_user import CreateUserRequest
from dto.response.create_user import CreateUserResponse
from services.user_service import create_user_handler

router = APIRouter(prefix="/user", tags=["User"])


@router.post("/create", response_model=CreateUserResponse)
def create_user(request: CreateUserRequest, db: Session = Depends(get_db)):
    return create_user_handler(db, request)
