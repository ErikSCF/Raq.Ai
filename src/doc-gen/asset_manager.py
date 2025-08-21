"""
Asset Manager for RAQ Document Generation

Provides the AssetManager class for handling document processing, asset movement,
and vector database creation for RAG-enabled document generation workflows.
"""

import os
import shutil
import glob
import json
from typing import List, Dict, Optional
from pathlib import Path

# Document processing imports
try:
    from pypdf import PdfReader
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

# AutoGen memory imports
try:
    from autogen_core.memory import MemoryContent, MemoryMimeType
    from autogen_ext.memory.chromadb import (
        ChromaDBVectorMemory,
        PersistentChromaDBVectorMemoryConfig,
        SentenceTransformerEmbeddingFunctionConfig,
    )
    HAS_AUTOGEN_MEMORY = True
except ImportError:
    HAS_AUTOGEN_MEMORY = False


class AssetManager:
    """Manages project assets and creates vector databases for RAG."""
    
    def __init__(self, job_id: str, job_folder: str, document_type: str, assets: List[str] = None):
        # Require PDF and DOCX processing libraries to be present.
        if not HAS_PDF or not HAS_DOCX:
            missing = []
            if not HAS_PDF:
                missing.append('pypdf')
            if not HAS_DOCX:
                missing.append('python-docx')
            raise ImportError(f"Missing required libraries for AssetManager: {', '.join(missing)}")

        self.job_id = job_id
        self.job_folder = Path(job_folder)
        self.document_type = document_type
        self.assets_dir = self.job_folder / "assets"
        self.memory = None
        self.moved_files = []
        
        # Create assets directory
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy document type template files first
        self._copy_document_template_files()
        
        # Move provided assets if any
        if assets:
            self._move_assets(assets)
    
    def _copy_document_template_files(self):
        """Copy document template files from documents/{document_type}/ to job assets folder"""
        import shutil
        
        # Check if we're in a test environment by looking for tests/documents first
        current_file = Path(__file__).resolve()
        test_source_dir = current_file.parent / "tests" / "documents" / self.document_type
        prod_source_dir = current_file.parent / "documents" / self.document_type
        
        if test_source_dir.exists():
            documents_dir = test_source_dir
        elif prod_source_dir.exists():
            documents_dir = prod_source_dir
        else:
            print(f"Warning: Document type '{self.document_type}' not found in documents/ or tests/documents/")
            return
        
        print(f"Copying document template files from {documents_dir} to {self.assets_dir}")
        
        # Copy all non-workflow files to assets (workflow.yaml should be handled by WorkflowManager)
        # Also exclude brand_content_brief.md as it should be in the main job folder, not assets
        for item in documents_dir.iterdir():
            if item.is_file() and item.suffix not in ['.yaml', '.yml'] and item.name != 'brand_content_brief.md':
                destination = self.assets_dir / item.name
                shutil.copy2(item, destination)
                self.moved_files.append(str(destination))
                print(f"Copied template asset: {item.name}")
            elif item.is_dir():
                # Copy subdirectories recursively to assets
                destination = self.assets_dir / item.name
                shutil.copytree(item, destination, exist_ok=True)
                # Add all files in the copied directory to moved_files
                for copied_file in destination.rglob("*"):
                    if copied_file.is_file():
                        self.moved_files.append(str(copied_file))
                print(f"Copied template directory: {item.name}")
    
    def _move_assets(self, assets: List[str]) -> List[str]:
        """Move provided assets to the job folder."""
        for asset_path in assets:
            if os.path.exists(asset_path):
                filename = os.path.basename(asset_path)
                destination = self.assets_dir / filename
                
                try:
                    shutil.copy2(asset_path, destination)
                    self.moved_files.append(str(destination))
                    print(f"Moved asset: {filename} -> {destination}")
                except Exception as e:
                    print(f"Error moving asset {asset_path}: {e}")
            else:
                print(f"Asset not found: {asset_path}")
        
        return self.moved_files
        
    async def create_vector_memory(self) -> Optional[ChromaDBVectorMemory]:
        """Create ChromaDB vector memory from all assets in the directory."""
        if not HAS_AUTOGEN_MEMORY:
            print("Warning: AutoGen memory not available, skipping vector memory creation")
            return None
            
        try:
            # Create vector memory with job-specific persistence
            chroma_path = self.assets_dir / f".chroma_raq_{self.job_id}"
            
            self.memory = ChromaDBVectorMemory(
                config=PersistentChromaDBVectorMemoryConfig(
                    collection_name=f"raq_docs_{self.job_id}",
                    persistence_path=str(chroma_path),
                    k=6,
                    score_threshold=0.25,
                    embedding_function_config=SentenceTransformerEmbeddingFunctionConfig(
                        model_name="all-MiniLM-L6-v2"
                    ),
                )
            )
            
            # Process all document types
            await self._process_pdf_files()
            await self._process_docx_files()
            await self._process_text_files()
            await self._process_conversation_files()
            
            print(f"Created vector memory for job {self.job_id}")
            return self.memory
            
        except Exception as e:
            print(f"Error creating vector memory: {e}")
            return None
    
    async def _add_content(self, text: str, metadata: dict):
        """Add text content to vector memory."""
        if text and text.strip() and self.memory:
            await self.memory.add(MemoryContent(
                content=text,
                mime_type=MemoryMimeType.TEXT,
                metadata=metadata
            ))
    
    async def _process_pdf_files(self):
        """Process PDF files and add to memory."""
        if not HAS_PDF:
            print("Warning: pypdf not available, skipping PDF processing")
            return
            
        pdf_files = list(self.assets_dir.glob("**/*.pdf"))
        for pdf_path in pdf_files:
            try:
                with open(pdf_path, "rb") as f:
                    reader = PdfReader(f)
                    for i, page in enumerate(reader.pages):
                        text = page.extract_text() or ""
                        if text.strip():
                            await self._add_content(text, {
                                "source": pdf_path.name,
                                "page": i + 1,
                                "type": "pdf",
                                "path": str(pdf_path.relative_to(self.assets_dir))
                            })
                print(f"Processed PDF: {pdf_path.name}")
            except Exception as e:
                print(f"Error processing PDF {pdf_path.name}: {e}")
    
    async def _process_docx_files(self):
        """Process DOCX files and add to memory."""
        if not HAS_DOCX:
            print("Warning: python-docx not available, skipping DOCX processing")
            return
            
        docx_files = list(self.assets_dir.glob("**/*.docx"))
        for docx_path in docx_files:
            try:
                doc = Document(docx_path)
                chunk = []
                chunk_num = 1
                
                for para in doc.paragraphs:
                    if para.text.strip():
                        chunk.append(para.text.strip())
                    
                    # Create chunks of ~1200 characters
                    if sum(len(x) for x in chunk) > 1200:
                        await self._add_content("\n".join(chunk), {
                            "source": docx_path.name,
                            "chunk": chunk_num,
                            "type": "docx",
                            "path": str(docx_path.relative_to(self.assets_dir))
                        })
                        chunk = []
                        chunk_num += 1
                
                # Add remaining content
                if chunk:
                    await self._add_content("\n".join(chunk), {
                        "source": docx_path.name,
                        "chunk": chunk_num,
                        "type": "docx",
                        "path": str(docx_path.relative_to(self.assets_dir))
                    })
                    
                print(f"Processed DOCX: {docx_path.name}")
            except Exception as e:
                print(f"Error processing DOCX {docx_path.name}: {e}")
    
    async def _process_text_files(self):
        """Process markdown and text files."""
        text_files = list(self.assets_dir.glob("**/*.md")) + list(self.assets_dir.glob("**/*.txt"))
        
        for text_path in text_files:
            try:
                with open(text_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                
                # Split on headers for markdown, or by paragraphs for txt
                if text_path.suffix == ".md":
                    parts = text.split("\n\n## ")
                    for i, part in enumerate(parts):
                        if part.strip():
                            await self._add_content(part, {
                                "source": text_path.name,
                                "section": i + 1,
                                "type": "markdown",
                                "path": str(text_path.relative_to(self.assets_dir))
                            })
                else:
                    # For txt files, split by double newlines
                    parts = text.split("\n\n")
                    for i, part in enumerate(parts):
                        if part.strip():
                            await self._add_content(part, {
                                "source": text_path.name,
                                "paragraph": i + 1,
                                "type": "text",
                                "path": str(text_path.relative_to(self.assets_dir))
                            })
                            
                print(f"Processed text file: {text_path.name}")
            except Exception as e:
                print(f"Error processing text file {text_path.name}: {e}")
    
    async def _process_conversation_files(self):
        """Process conversation transcript JSON files."""
        conv_files = list(self.assets_dir.glob("**/conversations/**/*.json"))
        
        for conv_path in conv_files:
            try:
                with open(conv_path, "r", encoding="utf-8") as f:
                    conv = json.load(f)
                
                # Expect format: [{"speaker":"client","ts":"2025-05-21","text":"..."}, ...]
                for i, turn in enumerate(conv):
                    if isinstance(turn, dict) and turn.get('text'):
                        speaker = turn.get('speaker', 'unknown')
                        timestamp = turn.get('ts', '')
                        text = turn.get('text', '')
                        
                        formatted_text = f"[{timestamp}][{speaker}] {text}"
                        await self._add_content(formatted_text, {
                            "source": conv_path.name,
                            "turn": i + 1,
                            "type": "conversation",
                            "path": str(conv_path.relative_to(self.assets_dir))
                        })
                print(f"Processed conversation: {conv_path.name}")
            except Exception as e:
                print(f"Error processing conversation {conv_path.name}: {e}")

    def get_asset_summary(self) -> Dict:
        """Get a summary of assets in the directory."""
        if not self.assets_dir.exists():
            return {"total_files": 0, "types": {}, "moved_files": self.moved_files}
        
        file_types = {}
        total_files = 0
        
        for file_path in self.assets_dir.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith('.'):
                suffix = file_path.suffix.lower()
                file_types[suffix] = file_types.get(suffix, 0) + 1
                total_files += 1
        
        return {
            "total_files": total_files,
            "types": file_types,
            "assets_dir": str(self.assets_dir),
            "moved_files": self.moved_files
        }
    
    def list_asset_files(self) -> List[str]:
        """List all asset files in the directory."""
        if not self.assets_dir.exists():
            return []
        
        asset_files = []
        for file_path in self.assets_dir.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith('.'):
                asset_files.append(str(file_path))
        
        return asset_files
    
    def format_assets_for_agent(self) -> str:
        """Format asset content for agent consumption."""
        summary = self.get_asset_summary()
        
        if summary["total_files"] == 0:
            return ""
        
        return f"""
ASSET SUMMARY:
Total files: {summary['total_files']}
File types: {', '.join(f"{ext}({count})" for ext, count in summary['types'].items())}
Moved files: {len(summary['moved_files'])}

Note: These assets have been automatically ingested into agent memory via ChromaDB.
Agents can directly query and reference this content during planning.
"""
