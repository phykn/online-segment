from io import BytesIO

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from PIL import Image

from src.data.image import read_bytes

router = APIRouter(prefix='/images', tags=['images'])


@router.post('/crop')
def crop_image(file: UploadFile = File(), x: int = Form(ge=0), y: int = Form(ge=0),
               width: int = Form(gt=0), height: int = Form(gt=0)) -> Response:
    image = read_bytes(file.file.read())
    if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > image.shape[1] or y + height > image.shape[0]:
        raise HTTPException(422, 'Crop must be inside the image.')
    output = BytesIO()
    Image.fromarray(image[y:y + height, x:x + width]).save(output, format='PNG')
    return Response(content=output.getvalue(), media_type='image/png')
