import asyncio
import shutil
from pathlib import Path
from typing import BinaryIO
import logging
import os
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TesseractCliOcrOptions,
    AcceleratorOptions,
)
from docling.datamodel.accelerator_options import AcceleratorDevice as DoclingAcceleratorDevice
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling_core.types.doc import ImageRefMode
from config import settings, AcceleratorDevice

logger = logging.getLogger(__name__)


class DocumentProcessor:
    def __init__(self):
        logger.info("🔧 Initializing DocumentProcessor with Tesseract CLI OCR")

        # Map config accelerator device to Docling's enum
        device_map = {
            AcceleratorDevice.CPU: DoclingAcceleratorDevice.CPU,
            AcceleratorDevice.CUDA: DoclingAcceleratorDevice.CUDA,
            AcceleratorDevice.MPS: DoclingAcceleratorDevice.MPS,
        }
        docling_device = device_map[settings.accelerator_device]

        logger.info(f"⚙️  Accelerator: {settings.accelerator_device.value.upper()}, Threads: {settings.num_threads}")

        # Configure Tesseract CLI OCR with Russian and English languages
        # Using TesseractCliOcrOptions which uses tesseract command-line tool
        ocr_options = TesseractCliOcrOptions(
            lang=["rus", "eng"]
        )

        # Configure accelerator options for CPU/GPU processing
        accelerator_options = AcceleratorOptions(
            num_threads=settings.num_threads,
            device=docling_device
        )

        # Configure pipeline with OCR and image extraction options
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.ocr_options = ocr_options
        pipeline_options.accelerator_options = accelerator_options

        # Enable image generation for export
        pipeline_options.generate_picture_images = True
        pipeline_options.images_scale = 2.0  # Higher resolution images

        # Initialize DocumentConverter with configuration
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options,
                    backend=PyPdfiumDocumentBackend
                )
            }
        )

        logger.info(f"✅ DocumentProcessor initialized with Tesseract CLI (rus+eng), {settings.accelerator_device.value.upper()}, and image extraction")

    async def process_document(
        self,
        file_path: Path,
        output_dir: Path
    ) -> tuple[Path, Path]:
        """
        Process document and return paths to markdown and images directory

        Args:
            file_path: Path to input document
            output_dir: Directory for output files

        Returns:
            Tuple of (markdown_path, images_dir_path)
        """
        try:
            logger.info(f"📄 Starting document processing: {file_path.name}")
            logger.info(f"📊 File size: {file_path.stat().st_size / 1024 / 1024:.2f} MB")

            # Run conversion in thread pool to avoid blocking
            logger.info("🔄 Running Docling converter with Tesseract OCR (rus+eng)...")
            result = await asyncio.to_thread(
                self.converter.convert,
                str(file_path)
            )

            # Log document info
            page_count = len(result.document.pages) if hasattr(result.document, 'pages') else 'unknown'
            logger.info(f"✅ Document converted successfully! Pages: {page_count}")

            # Export to markdown with images
            markdown_path = output_dir / "document.md"
            images_dir = output_dir / "images"

            # Export markdown with images using save_as_markdown with ImageRefMode.REFERENCED
            # This will create document_artifacts folder by default
            logger.info("📝 Exporting to Markdown format with images...")

            await asyncio.to_thread(
                result.document.save_as_markdown,
                str(markdown_path),
                image_mode=ImageRefMode.REFERENCED
            )

            logger.info(f"💾 Markdown saved: {markdown_path.name}")

            # Rename document_artifacts to images and fix paths in markdown
            artifacts_dir = output_dir / "document_artifacts"
            if artifacts_dir.exists():
                logger.info("🔄 Renaming document_artifacts to images...")

                # Create images directory if it doesn't exist
                images_dir.mkdir(exist_ok=True)

                # Move all files from document_artifacts to images
                for file in artifacts_dir.iterdir():
                    if file.is_file():
                        shutil.move(str(file), str(images_dir / file.name))

                # Remove empty document_artifacts directory
                artifacts_dir.rmdir()

                # Fix paths in markdown file
                logger.info("🔧 Fixing image paths in markdown...")
                markdown_content = markdown_path.read_text(encoding="utf-8")

                # Replace absolute paths and document_artifacts with relative images/
                import re
                # Pattern to match image paths with absolute paths or document_artifacts
                markdown_content = re.sub(
                    r'!\[(.*?)\]\(.*/document_artifacts/(.*?)\)',
                    r'![\1](images/\2)',
                    markdown_content
                )
                # Also replace any remaining absolute paths
                markdown_content = re.sub(
                    r'!\[(.*?)\]\(/[^)]*?/images/(.*?)\)',
                    r'![\1](images/\2)',
                    markdown_content
                )

                markdown_path.write_text(markdown_content, encoding="utf-8")
                logger.info("✅ Image paths fixed in markdown")

            # Count images that were saved
            image_count = 0
            if images_dir.exists():
                image_count = len(list(images_dir.glob("*")))
                logger.info(f"🖼️  Total images extracted: {image_count}")
            else:
                logger.info("ℹ️  No images found in document")

            logger.info(f"✨ Document processing completed successfully!")
            return markdown_path, images_dir

        except Exception as e:
            logger.error(f"❌ Error processing document: {e}", exc_info=True)
            raise

    async def _extract_images(self, result, images_dir: Path) -> int:
        """Extract and save images from document"""
        image_count = 0
        try:
            # Get pictures from the document
            if hasattr(result.document, 'pictures') and result.document.pictures:
                total_images = len(result.document.pictures)
                logger.info(f"🖼️  Found {total_images} images in document, extracting...")

                for idx, picture in enumerate(result.document.pictures, start=1):
                    # Determine file extension
                    ext = "png"  # Default extension
                    if hasattr(picture, 'format'):
                        ext = picture.format.lower()
                    elif hasattr(picture, 'image') and hasattr(picture.image, 'format'):
                        ext = picture.image.format.lower()

                    image_path = images_dir / f"image_{idx}.{ext}"

                    # Save image
                    if hasattr(picture, 'get_image'):
                        img = picture.get_image()
                        if img:
                            await asyncio.to_thread(img.save, str(image_path))
                            image_count += 1
                    elif hasattr(picture, 'image'):
                        await asyncio.to_thread(
                            picture.image.save,
                            str(image_path)
                        )
                        image_count += 1

                    logger.info(f"  💾 Saved image {idx}/{total_images}: {image_path.name}")
            else:
                logger.info("ℹ️  No images found in document")
        except Exception as e:
            logger.warning(f"⚠️  Error extracting images: {e}")

        return image_count


processor = DocumentProcessor()
