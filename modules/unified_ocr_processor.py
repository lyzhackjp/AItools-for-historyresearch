from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class OCRModelType(Enum):
    TESSERACT = "tesseract"
    LLM_OCR = "llm_ocr"
    NDLOCR_LITE = "ndlocr_lite"
    NDLKOTENOCR_LITE = "ndlkotenocr_lite"


MODEL_ALIASES = {
    "ndlocr-lite": OCRModelType.NDLOCR_LITE.value,
    "ndlkotenocr-lite": OCRModelType.NDLKOTENOCR_LITE.value,
    "qwen-vl-ocr": OCRModelType.LLM_OCR.value,
    "qwen_vl_ocr": OCRModelType.LLM_OCR.value,
    "llm": OCRModelType.LLM_OCR.value,
}


@dataclass
class UnifiedOCRConfig:
    ndlocr_path: Optional[str] = None
    ndlkoten_path: Optional[str] = None
    tesseract_path: Optional[str] = None
    llm_provider: str = "qwen"
    llm_model: Optional[str] = None
    use_gpu: bool = False
    enable_visualization: bool = False
    timeout: int = 300
    default_model: str = OCRModelType.NDLOCR_LITE.value
    fallback_models: List[str] = field(default_factory=list)


@dataclass
class OCREngineSpec:
    name: str
    kind: str
    label: str
    description: str
    use_case: str
    handler_name: str
    requires_external_dependency: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class UnifiedOCRResult:
    def __init__(self):
        self.success: bool = False
        self.text: str = ""
        self.xml_content: str = ""
        self.pages: List[Dict[str, Any]] = []
        self.structures: List[Dict[str, Any]] = []
        self.error: Optional[str] = None
        self.processing_time: float = 0.0
        self.output_dir: Optional[str] = None
        self.visualization_paths: List[str] = []
        self.model_type: str = ""
        self.model_description: str = ""
        self.backend_kind: str = ""
        self.provider: Optional[str] = None
        self.needs_review: bool = False
        self.metadata: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "text": self.text,
            "xml_content": self.xml_content,
            "pages": self.pages,
            "structures": self.structures,
            "error": self.error,
            "processing_time": self.processing_time,
            "output_dir": self.output_dir,
            "visualization_paths": self.visualization_paths,
            "model_type": self.model_type,
            "model_description": self.model_description,
            "backend_kind": self.backend_kind,
            "provider": self.provider,
            "needs_review": self.needs_review,
            "metadata": self.metadata,
        }

    def merge_all_text(self) -> str:
        if self.pages:
            parts = [page.get("text", "") for page in self.pages if page.get("text")]
            if parts:
                return "\n\n".join(parts)
        return self.text

    def to_package(self, source_path: Optional[str] = None) -> Dict[str, Any]:
        """Return a workflow-ready OCR result envelope."""
        text = self.merge_all_text()
        quality_flags: List[str] = []
        if not self.success:
            quality_flags.append("ocr_failed")
        if not text.strip():
            quality_flags.append("no_text")
        if not self.pages:
            quality_flags.append("no_pages")
        if self.error:
            quality_flags.append("has_error")

        page_confidences = [
            float(page.get("confidence"))
            for page in self.pages
            if page.get("confidence") is not None
        ]
        if page_confidences:
            confidence = sum(page_confidences) / len(page_confidences)
        elif self.success and text.strip():
            confidence = 0.72
        else:
            confidence = 0.2
        if quality_flags:
            confidence = min(confidence, 0.68)

        return {
            "type": "ocr_result",
            "source_path": source_path,
            "success": self.success,
            "text": text,
            "pages": self.pages,
            "structures": self.structures,
            "artifacts": [
                {"type": "visualization", "path": path}
                for path in self.visualization_paths
            ],
            "output_dir": self.output_dir,
            "backend": self.backend_kind or self.metadata.get("kind") or "unknown",
            "provider": self.provider or self.metadata.get("provider") or self.model_type,
            "model": self.model_type or self.metadata.get("selected_model"),
            "model_description": self.model_description,
            "processing_time": self.processing_time,
            "confidence": round(max(0.1, min(confidence, 0.95)), 2),
            "needs_review": self.needs_review or bool(quality_flags),
            "quality_flags": quality_flags,
            "error": self.error,
            "metadata": self.metadata,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }


class UnifiedOCRProcessor:
    ENGINE_SPECS: Dict[str, OCREngineSpec] = {
        OCRModelType.TESSERACT.value: OCREngineSpec(
            name=OCRModelType.TESSERACT.value,
            kind="local_engine",
            label="Tesseract OCR",
            description="Generic local OCR using the installed Tesseract runtime.",
            use_case="Printed pages, general fallback OCR, lightweight local processing.",
            handler_name="_run_tesseract",
            metadata={"language_options": ["en", "ja", "zh", "zh-tw", "ko"]},
        ),
        OCRModelType.LLM_OCR.value: OCREngineSpec(
            name=OCRModelType.LLM_OCR.value,
            kind="remote_llm",
            label="LLM OCR",
            description="Vision-language OCR via an LLM client.",
            use_case="Messy scans, mixed layouts, OCR rescue and post-correction.",
            handler_name="_run_llm_ocr",
            requires_external_dependency=True,
        ),
        OCRModelType.NDLOCR_LITE.value: OCREngineSpec(
            name=OCRModelType.NDLOCR_LITE.value,
            kind="local_engine",
            label="NDL OCR-Lite",
            description="OCR for modern printed Japanese materials.",
            use_case="Modern Japanese books, magazines, newspapers, printed documents.",
            handler_name="_run_ndlocr_lite",
            requires_external_dependency=True,
            metadata={"family": "ndl"},
        ),
        OCRModelType.NDLKOTENOCR_LITE.value: OCREngineSpec(
            name=OCRModelType.NDLKOTENOCR_LITE.value,
            kind="local_engine",
            label="NDL Koten OCR-Lite",
            description="OCR for classical Japanese texts and kuzushiji-like materials.",
            use_case="Classical books, premodern materials, cursive historical documents.",
            handler_name="_run_ndlkotenocr_lite",
            requires_external_dependency=True,
            metadata={"family": "ndl"},
        ),
    }

    def __init__(self, config: Optional[UnifiedOCRConfig] = None):
        self.config = config or UnifiedOCRConfig()
        self._ocr_processor = None
        self._ndlocr_processor = None
        self._ndlkoten_processor = None

    def _normalize_model_type(self, model_type: Optional[str]) -> str:
        value = (model_type or self.config.default_model).strip().lower()
        return MODEL_ALIASES.get(value, value)

    def _get_ocr_processor(self):
        if self._ocr_processor is None:
            from modules.ocr_processor import OCRProcessor

            self._ocr_processor = OCRProcessor(tesseract_path=self.config.tesseract_path)
        return self._ocr_processor

    def _get_ndlocr_processor(self):
        if self._ndlocr_processor is None:
            from modules.ndlocr_lite import NDLOCRLiteConfig, NDLOCRLiteProcessor

            ndlocr_config = NDLOCRLiteConfig(
                ndlocr_path=self.config.ndlocr_path,
                use_gpu=self.config.use_gpu,
                enable_visualization=self.config.enable_visualization,
                timeout=self.config.timeout,
            )
            self._ndlocr_processor = NDLOCRLiteProcessor(ndlocr_config)
        return self._ndlocr_processor

    def _get_ndlkoten_processor(self):
        if self._ndlkoten_processor is None:
            from modules.ndlkotenocr_lite import NDLKotenOCRLiteConfig, NDLKotenOCRLiteProcessor

            ndlkoten_config = NDLKotenOCRLiteConfig(
                ndlkoten_path=self.config.ndlkoten_path,
                use_gpu=self.config.use_gpu,
                enable_visualization=self.config.enable_visualization,
                timeout=self.config.timeout,
            )
            self._ndlkoten_processor = NDLKotenOCRLiteProcessor(ndlkoten_config)
        return self._ndlkoten_processor

    def _engine_available(self, model_type: str) -> bool:
        normalized = self._normalize_model_type(model_type)
        try:
            if normalized == OCRModelType.TESSERACT.value:
                return True
            if normalized == OCRModelType.LLM_OCR.value:
                return True
            if normalized == OCRModelType.NDLOCR_LITE.value:
                return self._get_ndlocr_processor().is_installed()
            if normalized == OCRModelType.NDLKOTENOCR_LITE.value:
                return self._get_ndlkoten_processor().is_installed()
        except Exception:
            return False
        return False

    def is_model_available(self, model_type: str = OCRModelType.NDLOCR_LITE.value) -> bool:
        return self._engine_available(model_type)

    def get_available_models(self) -> List[Dict[str, Any]]:
        models: List[Dict[str, Any]] = []
        for name, spec in self.ENGINE_SPECS.items():
            models.append(
                {
                    "type": name,
                    "name": spec.label,
                    "name_cn": spec.label,
                    "description": spec.description,
                    "use_case": spec.use_case,
                    "available": self._engine_available(name),
                    "kind": spec.kind,
                    "metadata": spec.metadata,
                }
            )
        return models

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "default_model": self._normalize_model_type(self.config.default_model),
            "fallback_models": [self._normalize_model_type(item) for item in self.config.fallback_models],
            "models": self.get_available_models(),
        }

    def get_model_info(self, model_type: str) -> Optional[Dict[str, Any]]:
        normalized = self._normalize_model_type(model_type)
        spec = self.ENGINE_SPECS.get(normalized)
        if spec is None:
            return None
        return {
            "type": normalized,
            "name": spec.label,
            "name_cn": spec.label,
            "description": spec.description,
            "use_case": spec.use_case,
            "available": self._engine_available(normalized),
            "kind": spec.kind,
            "metadata": spec.metadata,
        }

    def _result_from_mapping(
        self,
        payload: Dict[str, Any],
        model_type: str,
        output_dir: Optional[str],
    ) -> UnifiedOCRResult:
        spec = self.ENGINE_SPECS[model_type]
        result = UnifiedOCRResult()
        result.success = bool(payload.get("success"))
        result.text = payload.get("text", "") or ""
        result.xml_content = payload.get("xml_content", "") or ""
        result.pages = payload.get("pages", []) or []
        result.structures = payload.get("structures", []) or []
        result.error = payload.get("error")
        result.processing_time = float(payload.get("processing_time", 0.0) or 0.0)
        result.output_dir = payload.get("output_dir") or output_dir
        result.visualization_paths = payload.get("visualization_paths", []) or []
        result.model_type = model_type
        result.model_description = spec.label
        result.backend_kind = spec.kind
        result.provider = payload.get("provider")
        result.metadata = {
            "method": payload.get("method", model_type),
            "engine": model_type,
            "kind": spec.kind,
            **payload.get("metadata", {}),
        }
        if not result.pages and result.text:
            result.pages = [
                {
                    "page": 1,
                    "text": result.text,
                    "confidence": payload.get("confidence"),
                }
            ]
        if payload.get("words"):
            result.structures = result.structures or [{"type": "words", "items": payload["words"]}]
        result.needs_review = not result.success or bool(payload.get("needs_review"))
        return result

    def _run_tesseract(
        self,
        image_path: str,
        output_dir: Optional[str],
        language: str,
        llm_client: Any = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        processor = self._get_ocr_processor()
        start = time.perf_counter()
        payload = processor.extract_text_from_image(image_path, language=language, config=kwargs.get("config"))
        payload.setdefault("processing_time", time.perf_counter() - start)
        payload.setdefault("provider", "tesseract")
        return payload

    def _run_llm_ocr(
        self,
        image_path: str,
        output_dir: Optional[str],
        language: str,
        llm_client: Any = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if llm_client is None:
            raise RuntimeError("llm_client is required for llm_ocr backend.")
        processor = self._get_ocr_processor()
        start = time.perf_counter()
        payload = processor.llm_ocr(image_path, llm_client=llm_client, language=language, prompt_template=kwargs.get("prompt_template"))
        payload.setdefault("processing_time", time.perf_counter() - start)
        payload.setdefault("provider", getattr(llm_client, "provider", self.config.llm_provider))
        return payload

    def _run_ndlocr_lite(
        self,
        image_path: str,
        output_dir: Optional[str],
        language: str,
        llm_client: Any = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        processor = self._get_ndlocr_processor()
        start = time.perf_counter()
        result = processor.process_image(image_path, output_dir)
        return {
            "success": result.success,
            "text": result.text,
            "xml_content": result.xml_content,
            "pages": result.pages,
            "structures": result.structures,
            "error": result.error,
            "processing_time": result.processing_time or (time.perf_counter() - start),
            "output_dir": result.output_dir,
            "visualization_paths": result.visualization_paths,
            "provider": "ndlocr_lite",
            "method": "ndlocr_lite",
        }

    def _run_ndlkotenocr_lite(
        self,
        image_path: str,
        output_dir: Optional[str],
        language: str,
        llm_client: Any = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        processor = self._get_ndlkoten_processor()
        start = time.perf_counter()
        result = processor.process_image(image_path, output_dir)
        return {
            "success": result.success,
            "text": result.text,
            "xml_content": result.xml_content,
            "pages": result.pages,
            "structures": result.structures,
            "error": result.error,
            "processing_time": result.processing_time or (time.perf_counter() - start),
            "output_dir": result.output_dir,
            "visualization_paths": result.visualization_paths,
            "provider": "ndlkotenocr_lite",
            "method": "ndlkotenocr_lite",
        }

    def process_image(
        self,
        image_path: str,
        model_type: Optional[str] = None,
        output_dir: Optional[str] = None,
        *,
        language: str = "ja",
        llm_client: Any = None,
        fallback_models: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> UnifiedOCRResult:
        normalized = self._normalize_model_type(model_type)
        chain = [normalized]
        for item in fallback_models or self.config.fallback_models:
            resolved = self._normalize_model_type(item)
            if resolved not in chain:
                chain.append(resolved)

        last_error: Optional[str] = None
        for candidate in chain:
            if candidate not in self.ENGINE_SPECS:
                last_error = f"Unsupported OCR model type: {candidate}"
                continue
            if not self._engine_available(candidate):
                last_error = f"OCR model '{candidate}' is not currently available."
                continue

            spec = self.ENGINE_SPECS[candidate]
            runner: Callable[..., Dict[str, Any]] = getattr(self, spec.handler_name)
            try:
                payload = runner(
                    image_path=image_path,
                    output_dir=output_dir,
                    language=language,
                    llm_client=llm_client,
                    **kwargs,
                )
                result = self._result_from_mapping(payload, candidate, output_dir)
                result.metadata["attempted_models"] = chain
                result.metadata["selected_model"] = candidate
                if result.success:
                    return result
                last_error = result.error
            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}: {exc}"

        failed = UnifiedOCRResult()
        failed.model_type = normalized
        failed.model_description = self.ENGINE_SPECS.get(normalized, OCREngineSpec(normalized, "", normalized, "", "", "")).label
        failed.error = last_error or "No OCR backend could process the image."
        failed.needs_review = True
        failed.metadata = {"attempted_models": chain}
        return failed

    def process_image_package(
        self,
        image_path: str,
        model_type: Optional[str] = None,
        output_dir: Optional[str] = None,
        *,
        language: str = "ja",
        llm_client: Any = None,
        fallback_models: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Process one image and return a workflow-ready OCR envelope."""
        result = self.process_image(
            image_path=image_path,
            model_type=model_type,
            output_dir=output_dir,
            language=language,
            llm_client=llm_client,
            fallback_models=fallback_models,
            **kwargs,
        )
        package = result.to_package(source_path=image_path)
        package["capabilities"] = self.get_capabilities()
        return package

    def process_directory(
        self,
        directory_path: str,
        model_type: Optional[str] = None,
        output_dir: Optional[str] = None,
        *,
        language: str = "ja",
        llm_client: Any = None,
        **kwargs: Any,
    ) -> UnifiedOCRResult:
        normalized = self._normalize_model_type(model_type)
        if normalized == OCRModelType.NDLOCR_LITE.value and self._engine_available(normalized):
            processor = self._get_ndlocr_processor()
            result = processor.process_directory(directory_path, output_dir)
            return self._result_from_mapping(
                {
                    "success": result.success,
                    "text": result.text,
                    "xml_content": result.xml_content,
                    "pages": result.pages,
                    "structures": result.structures,
                    "error": result.error,
                    "processing_time": result.processing_time,
                    "output_dir": result.output_dir,
                    "visualization_paths": result.visualization_paths,
                    "provider": "ndlocr_lite",
                    "method": "ndlocr_lite",
                },
                normalized,
                output_dir,
            )
        if normalized == OCRModelType.NDLKOTENOCR_LITE.value and self._engine_available(normalized):
            processor = self._get_ndlkoten_processor()
            result = processor.process_directory(directory_path, output_dir)
            return self._result_from_mapping(
                {
                    "success": result.success,
                    "text": result.text,
                    "xml_content": result.xml_content,
                    "pages": result.pages,
                    "structures": result.structures,
                    "error": result.error,
                    "processing_time": result.processing_time,
                    "output_dir": result.output_dir,
                    "visualization_paths": result.visualization_paths,
                    "provider": "ndlkotenocr_lite",
                    "method": "ndlkotenocr_lite",
                },
                normalized,
                output_dir,
            )

        image_files: List[Path] = []
        for pattern in ("*.png", "*.jpg", "*.jpeg", "*.tif", "*.tiff", "*.bmp"):
            image_files.extend(sorted(Path(directory_path).glob(pattern)))

        combined = UnifiedOCRResult()
        combined.model_type = normalized
        combined.model_description = self.ENGINE_SPECS.get(normalized, self.ENGINE_SPECS[OCRModelType.TESSERACT.value]).label
        combined.backend_kind = self.ENGINE_SPECS.get(normalized, self.ENGINE_SPECS[OCRModelType.TESSERACT.value]).kind
        combined.output_dir = output_dir
        combined.metadata = {"file_count": len(image_files), "directory_path": str(directory_path)}

        texts: List[str] = []
        page_results: List[Dict[str, Any]] = []
        total_time = 0.0
        errors: List[str] = []
        for index, image_file in enumerate(image_files, start=1):
            result = self.process_image(
                str(image_file),
                model_type=normalized,
                output_dir=output_dir,
                language=language,
                llm_client=llm_client,
                **kwargs,
            )
            total_time += result.processing_time
            if result.success:
                texts.append(result.text)
                page_results.append({"page": index, "image_path": str(image_file), "text": result.text})
            else:
                errors.append(f"{image_file.name}: {result.error}")

        combined.success = len(errors) == 0 and len(image_files) > 0
        combined.text = "\n\n".join(texts)
        combined.pages = page_results
        combined.processing_time = total_time
        combined.error = "; ".join(errors) if errors else None
        combined.needs_review = bool(errors)
        return combined

    def process_directory_package(
        self,
        directory_path: str,
        model_type: Optional[str] = None,
        output_dir: Optional[str] = None,
        *,
        language: str = "ja",
        llm_client: Any = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Process a directory and return a workflow-ready OCR envelope."""
        result = self.process_directory(
            directory_path=directory_path,
            model_type=model_type,
            output_dir=output_dir,
            language=language,
            llm_client=llm_client,
            **kwargs,
        )
        package = result.to_package(source_path=directory_path)
        package["type"] = "ocr_batch"
        package["capabilities"] = self.get_capabilities()
        package["page_count"] = len(result.pages)
        return package

    def compare_models(
        self,
        image_path: str,
        output_dir: Optional[str] = None,
        *,
        language: str = "ja",
        llm_client: Any = None,
    ) -> Dict[str, UnifiedOCRResult]:
        results: Dict[str, UnifiedOCRResult] = {}
        for model_name in self.ENGINE_SPECS:
            if not self._engine_available(model_name):
                continue
            if model_name == OCRModelType.LLM_OCR.value and llm_client is None:
                continue
            results[model_name] = self.process_image(
                image_path,
                model_type=model_name,
                output_dir=output_dir,
                language=language,
                llm_client=llm_client,
            )
        return results
