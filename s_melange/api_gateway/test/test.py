from fastapi import APIRouter

router = APIRouter(prefix="/test1")


@router.get("/")
def read_root():
    return {"message": "Test"}

@router.get("/check/")
def test_check():
    return {"message": "checked"}