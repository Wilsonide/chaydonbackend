import cloudinary
import cloudinary.uploader
from fastapi import UploadFile

from app.core.config import settings

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True,
)


class CloudinaryService:
    async def upload(
        self,
        file: UploadFile,
        folder: str,
    ):
        file.file.seek(0)

        result = cloudinary.uploader.upload(
            file.file,
            folder=folder,
            resource_type="auto",
        )

        return {
            "url": result["secure_url"],
            "public_id": result["public_id"],
            "resource_type": result["resource_type"],
            "file_name": file.filename,
            "file_type": file.content_type,
        }

    async def delete(
        self,
        public_id: str,
        resource_type: str,
    ):
        cloudinary.uploader.destroy(
            public_id,
            resource_type=resource_type,
        )
