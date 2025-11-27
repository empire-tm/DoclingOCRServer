import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import BinaryIO
import logging
import os
import re
import uuid
from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
    WordFormatOption,
    PowerpointFormatOption,
    ExcelFormatOption,
    ImageFormatOption,
)
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    PaginatedPipelineOptions,
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
        ocr_options = TesseractCliOcrOptions(
            lang=["rus", "eng"]
        )

        # Configure accelerator options for CPU/GPU processing
        accelerator_options = AcceleratorOptions(
            num_threads=settings.num_threads,
            device=docling_device
        )

        # Configure PDF pipeline with OCR and image extraction options
        # do_ocr=True enables OCR for text extraction when needed
        # generate_picture_images=True extracts embedded images from document
        # generate_page_images=False prevents converting entire pages to images
        pdf_pipeline_options = PdfPipelineOptions()
        pdf_pipeline_options.do_ocr = True
        pdf_pipeline_options.ocr_options = ocr_options
        pdf_pipeline_options.accelerator_options = accelerator_options
        pdf_pipeline_options.generate_picture_images = True  # Extract embedded images
        pdf_pipeline_options.images_scale = 2.0

        # Configure pipeline for Office documents
        office_pipeline_options = PaginatedPipelineOptions()
        office_pipeline_options.generate_picture_images = True  # Extract embedded images
        office_pipeline_options.images_scale = 2.0

        # Initialize DocumentConverter with configuration for all formats
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pdf_pipeline_options,
                    backend=PyPdfiumDocumentBackend
                ),
                InputFormat.DOCX: WordFormatOption(
                    pipeline_options=office_pipeline_options
                ),
                InputFormat.PPTX: PowerpointFormatOption(
                    pipeline_options=office_pipeline_options
                ),
                InputFormat.XLSX: ExcelFormatOption(
                    pipeline_options=office_pipeline_options
                ),
                InputFormat.IMAGE: ImageFormatOption(
                    pipeline_options=pdf_pipeline_options
                ),
            }
        )

        # Create force_ocr converter for when needed (scanned documents)
        # force_full_page_ocr=True forces OCR on entire page even if text is detected
        force_ocr_options = TesseractCliOcrOptions(
            lang=["rus", "eng"],
            force_full_page_ocr=True
        )

        force_pdf_pipeline_options = PdfPipelineOptions()
        force_pdf_pipeline_options.do_ocr = True
        force_pdf_pipeline_options.ocr_options = force_ocr_options
        force_pdf_pipeline_options.accelerator_options = accelerator_options
        force_pdf_pipeline_options.generate_picture_images = True  # Extract embedded images
        force_pdf_pipeline_options.images_scale = 2.0

        force_office_pipeline_options = PaginatedPipelineOptions()
        force_office_pipeline_options.generate_picture_images = True  # Extract embedded images
        force_office_pipeline_options.images_scale = 2.0

        self.force_ocr_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=force_pdf_pipeline_options,
                    backend=PyPdfiumDocumentBackend
                ),
                InputFormat.DOCX: WordFormatOption(
                    pipeline_options=force_office_pipeline_options
                ),
                InputFormat.PPTX: PowerpointFormatOption(
                    pipeline_options=force_office_pipeline_options
                ),
                InputFormat.XLSX: ExcelFormatOption(
                    pipeline_options=force_office_pipeline_options
                ),
                InputFormat.IMAGE: ImageFormatOption(
                    pipeline_options=force_pdf_pipeline_options
                ),
            }
        )

        logger.info("✅ DocumentProcessor initialized for all formats (PDF, DOCX, PPTX, XLSX, Images)")

    async def _convert_legacy_office_format(self, file_path: Path, target_format: str) -> Path:
        """
        Convert legacy Office formats (.doc, .xls) to modern formats using LibreOffice

        Args:
            file_path: Path to legacy office file (.doc or .xls)
            target_format: Target format ('docx' or 'xlsx')

        Returns:
            Path to converted file
        """
        try:
            source_ext = file_path.suffix.lower()
            logger.info(f"🔄 Converting {file_path.name} from {source_ext} to .{target_format}...")

            # Output directory for converted file
            output_dir = file_path.parent

            # Run LibreOffice in headless mode to convert
            cmd = [
                "libreoffice",
                "--headless",
                "--convert-to", target_format,
                "--outdir", str(output_dir),
                str(file_path)
            ]

            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # 60 seconds timeout
            )

            if result.returncode != 0:
                logger.error(f"LibreOffice conversion failed: {result.stderr}")
                raise RuntimeError(f"Failed to convert {source_ext} to .{target_format}: {result.stderr}")

            # Determine output file path
            converted_path = file_path.with_suffix(f".{target_format}")

            if not converted_path.exists():
                raise RuntimeError(f"Converted file not found: {converted_path}")

            logger.info(f"✅ Successfully converted to {converted_path.name}")
            return converted_path

        except subprocess.TimeoutExpired:
            logger.error("LibreOffice conversion timed out")
            raise RuntimeError("Document conversion timed out (60s limit)")
        except Exception as e:
            logger.error(f"Error converting legacy Office format: {e}")
            raise

    async def process_document(
        self,
        file_path: Path,
        output_dir: Path,
        force_ocr: bool = False
    ) -> tuple[Path, Path]:
        """
        Process document and return paths to markdown and images directory

        Args:
            file_path: Path to input document
            output_dir: Directory for output files
            force_ocr: If True, forces OCR on entire page/document

        Returns:
            Tuple of (markdown_path, images_dir_path)
        """
        converted_file = None
        try:
            logger.info(f"📄 Starting document processing: {file_path.name}")
            logger.info(f"📊 File size: {file_path.stat().st_size / 1024 / 1024:.2f} MB")

            # Check if file is legacy Office format and needs conversion
            file_suffix = file_path.suffix.lower()
            if file_suffix == ".doc":
                converted_file = await self._convert_legacy_office_format(file_path, "docx")
                file_path = converted_file
            elif file_suffix == ".xls":
                converted_file = await self._convert_legacy_office_format(file_path, "xlsx")
                file_path = converted_file

            if force_ocr:
                logger.info("🔍 Force OCR enabled for this document")
                converter = self.force_ocr_converter
            else:
                converter = self.converter

            # Run conversion in thread pool to avoid blocking
            logger.info("🔄 Running Docling converter with Tesseract OCR (rus+eng)...")
            result = await asyncio.to_thread(
                converter.convert,
                str(file_path)
            )

            # Log document info
            page_count = len(result.document.pages) if hasattr(result.document, 'pages') else 'unknown'
            logger.info(f"✅ Document converted successfully! Pages: {page_count}")

            # Debug: Check document content
            logger.info("🔍 Checking document content...")
            try:
                # Try to get text from document
                doc_text = result.document.export_to_markdown()
                text_length = len(doc_text)
                logger.info(f"📊 Document text length: {text_length} characters")
                if text_length > 0:
                    preview = doc_text[:200].replace('\n', ' ')
                    logger.info(f"📄 Text preview: {preview}...")
                else:
                    logger.warning("⚠️  Document appears to have no text content!")
            except Exception as e:
                logger.warning(f"⚠️  Could not preview document content: {e}")

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

                # Create mapping of old filenames to new GUID-based filenames
                filename_mapping = {}

                # Move all files from document_artifacts to images with new GUID names
                for file in artifacts_dir.iterdir():
                    if file.is_file():
                        # Generate new GUID-based filename
                        new_name = f"{uuid.uuid4()}{file.suffix}"
                        old_name = file.name
                        filename_mapping[old_name] = new_name

                        # Move file with new name
                        shutil.move(str(file), str(images_dir / new_name))
                        logger.info(f"  📷 Renamed: {old_name} -> {new_name}")

                # Remove empty document_artifacts directory
                artifacts_dir.rmdir()

                # Fix paths in markdown file
                logger.info("🔧 Fixing image paths in markdown...")
                markdown_content = markdown_path.read_text(encoding="utf-8")

                # Replace image references with new filenames
                for old_name, new_name in filename_mapping.items():
                    # Replace paths with document_artifacts
                    markdown_content = re.sub(
                        rf'!\[(.*?)\]\(.*/document_artifacts/{re.escape(old_name)}\)',
                        rf'![\1](images/{new_name})',
                        markdown_content
                    )
                    # Replace paths with just images/
                    markdown_content = re.sub(
                        rf'!\[(.*?)\]\(/[^)]*?/images/{re.escape(old_name)}\)',
                        rf'![\1](images/{new_name})',
                        markdown_content
                    )
                    # Replace relative paths
                    markdown_content = re.sub(
                        rf'!\[(.*?)\]\(images/{re.escape(old_name)}\)',
                        rf'![\1](images/{new_name})',
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
        finally:
            # Clean up converted file if it was created
            if converted_file and converted_file.exists():
                try:
                    converted_file.unlink()
                    logger.info(f"🧹 Cleaned up temporary converted file: {converted_file.name}")
                except Exception as e:
                    logger.warning(f"⚠️  Could not delete temporary converted file: {e}")

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
