import cloudinary
import cloudinary.uploader
from config import CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET, CLOUDINARY_CLOUD_NAME


cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET
)

def upload_image(image_bytes: bytes, folder: str = "dermaassess") -> str:
    """Uploads an image to Cloudinary and returns the secure URL."""
    try:
        result = cloudinary.uploader.upload(
            image_bytes,
            folder=folder,
            resource_type="image"
        )
        return result.get("secure_url")
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        return ""
