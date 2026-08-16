import logging
import uuid
import cloudinary
import cloudinary.uploader
from ..config import settings

logger = logging.getLogger(__name__)

# Configure Cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True,
)

def upload_to_cloudinary(file_bytes: bytes, file_type: str, original_filename: str) -> dict:
    """Uploads document to Cloudinary and returns secure URL and public ID."""
    try:
        unique_id = str(uuid.uuid4())
        # Use raw for PDF, image for receipts
        resource_type = "raw" if file_type == "pdf" else "image"
        
        upload_result = cloudinary.uploader.upload(
            file_bytes,
            public_id=unique_id,
            resource_type=resource_type,
            overwrite=True,
        )
        return {
            "secure_url": upload_result.get("secure_url"),
            "public_id": upload_result.get("public_id")
        }
    except Exception as e:
        logger.error(f"Cloudinary upload failed: {e}")
        raise RuntimeError(f"Cloudinary upload failed: {str(e)}")

def delete_from_cloudinary(public_id: str, file_type: str):
    """Deletes an asset from Cloudinary."""
    try:
        resource_type = "raw" if file_type == "pdf" else "image"
        cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        logger.info(f"Deleted {public_id} from Cloudinary.")
    except Exception as e:
        logger.error(f"Failed to delete {public_id} from Cloudinary: {e}")
