from fastapi import APIRouter,status, Response
import boto3

router = APIRouter(prefix="/document",tags=["Document"])

@router.get("/register")
def register_document():
    