import os
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from google.genai import types
from ..services.cloudinary_service import upload_to_cloudinary, delete_from_cloudinary
from ..services.ocr import process_document_gemini
from ..services.validation_service import validate_documents, DocumentValidationResult

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
IMAGE_MIME_TYPES = {"image/jpeg", "image/png"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "application/pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024   # 10 MB per file
MAX_MULTI_UPLOAD = 5


@router.post("/upload")
async def upload_document(files: List[UploadFile] = File(...)):
    # ------------------------------------------------------------------ #
    # STEP 1 — Count and coarse-type validation
    # ------------------------------------------------------------------ #
    if len(files) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided.")

    if len(files) > MAX_MULTI_UPLOAD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many files. You may upload at most {MAX_MULTI_UPLOAD} images of the same receipt at once."
        )

    # PDFs are only accepted as a single file upload
    if len(files) > 1:
        for f in files:
            _, ext = os.path.splitext((f.filename or "").lower())
            if ext not in IMAGE_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="When uploading multiple files, all files must be images (JPG/JPEG/PNG). PDF is only accepted as a single upload."
                )

    # ------------------------------------------------------------------ #
    # STEP 2 — Per-file validation: extension, MIME type, size
    # ------------------------------------------------------------------ #
    validated_files: list[dict] = []

    for f in files:
        filename = f.filename or "unknown"
        _, ext = os.path.splitext(filename.lower())
        mime_type = f.content_type or ""

        if ext not in ALLOWED_EXTENSIONS or mime_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{filename}': unsupported file type. Allowed: JPG, JPEG, PNG, PDF."
            )

        try:
            file_bytes = await f.read()
            if len(file_bytes) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"'{filename}' exceeds the 10 MB size limit."
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to read '{filename}': {str(e)}"
            )
        finally:
            await f.close()

        validated_files.append({
            "filename": filename,
            "ext": ext,
            "mime_type": mime_type,
            "bytes": file_bytes,
            "file_type": "pdf" if ext == ".pdf" else "image",
        })

    # ------------------------------------------------------------------ #
    # STEP 3 — Build typed Parts list (reused for both validation + extraction)
    # ------------------------------------------------------------------ #
    parts = [
        types.Part.from_bytes(data=vf["bytes"], mime_type=vf["mime_type"])
        for vf in validated_files
    ]

    # ------------------------------------------------------------------ #
    # STEP 4 — Document validation (single Gemini call)
    # ------------------------------------------------------------------ #
    try:
        validation: DocumentValidationResult = validate_documents(parts)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document validation failed: {str(e)}"
        )

    validation_payload = {
        "is_valid_purchase_document": validation.is_valid_purchase_document,
        "is_single_document": validation.is_single_document,
        "is_native_digital": validation.is_native_digital,
        "rejection_reason": validation.rejection_reason,
        "confidence": validation.confidence,
    }

    if not validation.is_valid_purchase_document:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "NOT_PURCHASE_DOCUMENT",
                "message": validation.rejection_reason or "This does not appear to be a purchase-related document.",
                "validation": validation_payload,
            }
        )

    if len(files) > 1 and not validation.is_single_document:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "DIFFERENT_RECEIPTS",
                "message": validation.rejection_reason or "The uploaded images appear to belong to different receipts.",
                "validation": validation_payload,
            }
        )

    is_pdf_upload = any(vf["file_type"] == "pdf" for vf in validated_files)
    if is_pdf_upload and not validation.is_native_digital:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "NOT_NATIVE_DIGITAL",
                "message": validation.rejection_reason or "Please use the Physical Receipt upload flow for photos or scans of physical receipts.",
                "validation": validation_payload,
            }
        )

    # ------------------------------------------------------------------ #
    # STEP 5 — Upload all files to Cloudinary
    # ------------------------------------------------------------------ #
    cloudinary_assets: list[dict] = []
    for vf in validated_files:
        try:
            asset = upload_to_cloudinary(vf["bytes"], vf["file_type"], vf["filename"])
            asset["filename"] = vf["filename"]
            cloudinary_assets.append(asset)
        except Exception as e:
            # Clean up any already-uploaded assets on failure
            for uploaded in cloudinary_assets:
                try:
                    delete_from_cloudinary(uploaded["public_id"], vf["file_type"])
                except Exception:
                    pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Cloudinary upload failed for '{vf['filename']}': {str(e)}"
            )

    # ------------------------------------------------------------------ #
    # STEP 6 — Structured extraction (existing logic, unchanged prompt)
    # ------------------------------------------------------------------ #
    try:
        extracted_data = process_document_gemini(parts)
    except Exception as e:
        # Clean up all Cloudinary assets on extraction failure
        for asset in cloudinary_assets:
            first_type = validated_files[0]["file_type"]
            try:
                delete_from_cloudinary(asset["public_id"], first_type)
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gemini structured extraction failed: {str(e)}"
        )

    # ------------------------------------------------------------------ #
    # STEP 7 — Return enriched response
    # ------------------------------------------------------------------ #
    primary = validated_files[0]
    return {
        "success": True,
        "message": f"{'1 file' if len(files) == 1 else f'{len(files)} images'} uploaded and processed successfully.",
        "validation": validation_payload,
        "cloudinary_assets": cloudinary_assets,
        # Convenience top-level fields (primary file) kept for backwards compat
        "cloudinary_url": cloudinary_assets[0]["secure_url"],
        "cloudinary_public_id": cloudinary_assets[0]["public_id"],
        "document": {
            "original_filename": primary["filename"],
            "file_type": primary["file_type"],
            "mime_type": primary["mime_type"],
            "image_count": len(files),
            "extracted_data": extracted_data,
        }
    }
