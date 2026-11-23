import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from database.models.user import User
from dto.request.create_user import CreateUserRequest
from dto.request.update_user import UpdateUserRequest
from dto.response.create_user import CreateUserResponse
from dto.response.get_users import GetAllUsersResponse, UserResponse
from dto.response.delete_response import DeleteResponse


def create_user_handler(db: Session, request: CreateUserRequest) -> CreateUserResponse:
    user = User(**request.model_dump())
    db.add(user)
    db.commit()
    db.refresh(user)
    response = CreateUserResponse.model_validate(user)
    response.message = "User created successfully"
    return response


def get_user_handler(db: Session, user_id: uuid.UUID) -> UserResponse:
    user = db.get(User, user_id)
    if user is None:
        raise ValueError("User not found")
    response = UserResponse.model_validate(user)
    response.message = "User fetched successfully"
    return response


def get_all_users_handler(db: Session) -> GetAllUsersResponse:
    users = db.scalars(select(User)).all()
    response = GetAllUsersResponse(users=users)
    response.message = "Users fetched successfully"
    return response


def update_user_handler(db: Session, user_id: uuid.UUID, request: UpdateUserRequest) -> UserResponse:
    user = db.get(User, user_id)
    if user is None:
        raise ValueError("User not found")
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    response = UserResponse.model_validate(user)
    response.message = "User updated successfully"
    return response


def delete_user_handler(db: Session, user_id: uuid.UUID) -> DeleteResponse:
    user = db.get(User, user_id)
    if user is None:
        raise ValueError("User not found")
    db.delete(user)
    db.commit()
    return DeleteResponse(message="User deleted successfully")
