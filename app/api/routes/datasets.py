from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user, get_dataset_service, require_admin
from app.schemas.auth import UserRead
from app.schemas.common import MessageResponse
from app.schemas.dataset import DatasetCreate, DatasetRead, DatasetUpdate
from app.services.dataset_service import DatasetService

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("", response_model=dict)
def list_datasets(
    page: int = 1,
    size: int = 50,
    _: UserRead = Depends(get_current_user),
    service: DatasetService = Depends(get_dataset_service),
):
    items, total = service.list_datasets(page, size)
    return {"items": [i.model_dump() for i in items], "total": total, "page": page, "size": size}


@router.get("/{dataset_id}", response_model=DatasetRead)
def get_dataset(
    dataset_id: int,
    _: UserRead = Depends(get_current_user),
    service: DatasetService = Depends(get_dataset_service),
):
    try:
        return service.get_dataset(dataset_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("", response_model=DatasetRead)
def create_dataset(
    body: DatasetCreate,
    user: UserRead = Depends(get_current_user),
    service: DatasetService = Depends(get_dataset_service),
):
    return service.create_dataset(body, user.username)


@router.put("/{dataset_id}", response_model=DatasetRead)
def update_dataset(
    dataset_id: int,
    body: DatasetUpdate,
    user: UserRead = Depends(get_current_user),
    service: DatasetService = Depends(get_dataset_service),
):
    try:
        return service.update_dataset(dataset_id, body, user.username)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@router.delete("/{dataset_id}", response_model=MessageResponse)
def delete_dataset(
    dataset_id: int,
    _: UserRead = Depends(require_admin),
    service: DatasetService = Depends(get_dataset_service),
):
    try:
        service.delete_dataset(dataset_id)
        return MessageResponse(message="삭제되었습니다.")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
