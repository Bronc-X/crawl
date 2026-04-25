from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class MaterialNotFoundError(FileNotFoundError):
    """Raised when a requested material cannot be resolved."""


@dataclass
class MaterialService:
    materials_dir: Path
    material_map: dict[str, str]

    def resolve(self, material_id: str) -> Path:
        relative_path = self.material_map.get(material_id)
        if not relative_path:
            raise MaterialNotFoundError(f"unknown material id: {material_id}")

        candidate = self.materials_dir / relative_path
        if not candidate.exists():
            raise MaterialNotFoundError(f"material does not exist: {candidate}")
        return candidate

    def has_material(self, material_id: str) -> bool:
        try:
            self.resolve(material_id)
        except MaterialNotFoundError:
            return False
        return True
