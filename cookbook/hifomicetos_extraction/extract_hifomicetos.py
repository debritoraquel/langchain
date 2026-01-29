"""
Pipeline de extração de conhecimento para hifomicetos aquáticos.

- Extrai texto e descrições taxonômicas.
- Extrai figuras/imagens de PDFs.
- Gera metadados estruturados para integração em grafo de conhecimento.

Requisitos (instale no seu ambiente):
  pip install pymupdf pillow
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import fitz  # PyMuPDF
from PIL import Image
import io


@dataclass
class MorphometricData:
    """Dados morfométricos extraídos."""

    parameter: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean_value: Optional[float] = None
    unit: Optional[str] = None
    raw_text: str = ""


@dataclass
class ConidiumDescription:
    """Descrição detalhada do conídio."""

    shape: List[str] = field(default_factory=list)
    color: List[str] = field(default_factory=list)
    surface: str = ""
    length: Optional[MorphometricData] = None
    width: Optional[MorphometricData] = None
    septa_count: Optional[MorphometricData] = None
    septa_type: str = ""
    branching: str = ""
    apex: str = ""
    base: str = ""
    basal_extension: bool = False
    mucilaginous_sheath: bool = False
    raw_description: str = ""


@dataclass
class ConidiophoreDescription:
    """Descrição do conidióforo."""

    type: str = ""
    branching: str = ""
    septation: str = ""
    length: Optional[MorphometricData] = None
    width: Optional[MorphometricData] = None
    color: List[str] = field(default_factory=list)
    surface: str = ""
    raw_description: str = ""


@dataclass
class ConidiogenousCellDescription:
    """Descrição das células conidiogênicas."""

    type: str = ""
    position: str = ""
    proliferation: str = ""
    length: Optional[MorphometricData] = None
    width: Optional[MorphometricData] = None
    raw_description: str = ""


@dataclass
class TaxonomicDescription:
    """Descrição taxonômica completa."""

    species_name: str
    genus: str
    specific_epithet: str
    authority: str = ""
    order: Optional[str] = None
    family: Optional[str] = None
    conidium: Optional[ConidiumDescription] = None
    conidiophore: Optional[ConidiophoreDescription] = None
    conidiogenous_cell: Optional[ConidiogenousCellDescription] = None
    substrate: List[str] = field(default_factory=list)
    habitat: List[str] = field(default_factory=list)
    geographic_distribution: List[str] = field(default_factory=list)
    holotype: str = ""
    isotype: str = ""
    original_description: str = ""
    references: List[str] = field(default_factory=list)


class TaxonomicDescriptionExtractor:
    """Extrator de descrições taxonômicas."""

    SHAPE_TERMS = {
        "conidium": [
            "sigmoid",
            "filiform",
            "fusiform",
            "clavate",
            "obclavate",
            "navicular",
            "tetraradiate",
            "triradiate",
            "multiradiate",
            "curved",
            "straight",
            "lunate",
            "arcuate",
            "helicoid",
            "acerose",
            "cylindrical",
            "ellipsoid",
            "spherical",
            "reniform",
            "pyriform",
            "obpyriform",
            "scolecoid",
            "vermiform",
        ],
        "apex": ["rounded", "acute", "obtuse", "truncate", "attenuate"],
        "base": ["rounded", "truncate", "tapered", "swollen", "constricted"],
    }

    COLOR_TERMS = [
        "hyaline",
        "pale brown",
        "brown",
        "dark brown",
        "olivaceous",
        "golden",
        "fuscous",
        "subhyaline",
        "pallide brunnea",
        "atro-brunnea",
        "subfuscous",
    ]

    SURFACE_TERMS = [
        "smooth",
        "rough",
        "verrucose",
        "echinulate",
        "warted",
        "tuberculate",
        "spinulose",
        "laevis",
        "laevia",
    ]

    def extract_description(self, text: str, species_name: str) -> Optional[TaxonomicDescription]:
        description_section = self._find_species_section(text, species_name)
        if not description_section:
            return None

        genus, epithet, authority = self._parse_scientific_name(species_name, description_section)

        description = TaxonomicDescription(
            species_name=species_name,
            genus=genus,
            specific_epithet=epithet,
            authority=authority,
        )

        description.conidium = self._extract_conidium_description(description_section)
        description.conidiophore = self._extract_conidiophore_description(description_section)
        description.conidiogenous_cell = self._extract_conidiogenous_cell(description_section)
        description.substrate = self._extract_substrate_info(description_section)
        description.habitat = self._extract_habitat_info(description_section)
        description.geographic_distribution = self._extract_distribution(description_section)
        description.holotype = self._extract_holotype(description_section)
        description.original_description = description_section

        return description

    def _find_species_section(self, text: str, species_name: str) -> Optional[str]:
        escaped_name = re.escape(species_name)
        patterns = [
            rf"{escaped_name}\s+[A-Z][^,\n]*(?:,\s*sp\.\s*nov\.)?[^\n]*\n+(.*?)(?=\n\n[A-Z][a-z]+\s+[a-z]+|$)",
            rf"{escaped_name}\s+\([^)]+\)[^\n]*\n+(.*?)(?=\n\n[A-Z][a-z]+\s+[a-z]+|$)",
            rf"{escaped_name}[^\n]*\n+(.*?)(?=\n\n|Material examined|Known distribution)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()

        return None

    def _parse_scientific_name(self, species_name: str, text: str) -> Tuple[str, str, str]:
        parts = species_name.split()
        genus = parts[0] if parts else ""
        epithet = parts[1] if len(parts) > 1 else ""

        authority = ""
        auth_pattern = rf"{re.escape(species_name)}\s+([A-Z][^,\n{{]+)"
        match = re.search(auth_pattern, text)
        if match:
            authority = match.group(1).strip()

        return genus, epithet, authority

    def _extract_conidium_description(self, text: str) -> ConidiumDescription:
        conidium = ConidiumDescription()
        conidium_section = self._find_section(text, ["Conidia", "Conidio"])
        if not conidium_section:
            conidium_section = text

        conidium.raw_description = conidium_section
        conidium.shape = self._extract_terms(conidium_section, self.SHAPE_TERMS["conidium"])
        conidium.color = self._extract_terms(conidium_section, self.COLOR_TERMS)

        surface_terms = self._extract_terms(conidium_section, self.SURFACE_TERMS)
        conidium.surface = ", ".join(surface_terms) if surface_terms else ""

        conidium.length, conidium.width = self._extract_dimensions(conidium_section)
        conidium.septa_count = self._extract_septa_count(conidium_section)

        if re.search(r"basal\s+extension|excentric|percurrent", conidium_section, re.I):
            conidium.basal_extension = True

        if re.search(r"mucilaginous|mucilage|sheath", conidium_section, re.I):
            conidium.mucilaginous_sheath = True

        apex_terms = self._extract_terms(conidium_section, self.SHAPE_TERMS["apex"])
        conidium.apex = apex_terms[0] if apex_terms else ""

        base_terms = self._extract_terms(conidium_section, self.SHAPE_TERMS["base"])
        conidium.base = base_terms[0] if base_terms else ""

        return conidium

    def _extract_conidiophore_description(self, text: str) -> ConidiophoreDescription:
        conidiophore = ConidiophoreDescription()
        section = self._find_section(text, ["Conidiophore", "Conidiophora"])
        if not section:
            section = text

        conidiophore.raw_description = section

        if re.search(r"macronematous", section, re.I):
            conidiophore.type = "macronematous"
        elif re.search(r"micronematous", section, re.I):
            conidiophore.type = "micronematous"
        elif re.search(r"semimacronematous", section, re.I):
            conidiophore.type = "semimacronematous"

        if re.search(r"unbranched|simple", section, re.I):
            conidiophore.branching = "unbranched"
        elif re.search(r"branched", section, re.I):
            conidiophore.branching = "branched"

        conidiophore.color = self._extract_terms(section, self.COLOR_TERMS)

        surface_terms = self._extract_terms(section, self.SURFACE_TERMS)
        conidiophore.surface = ", ".join(surface_terms) if surface_terms else ""

        conidiophore.length, conidiophore.width = self._extract_dimensions(section)

        return conidiophore

    def _extract_conidiogenous_cell(self, text: str) -> ConidiogenousCellDescription:
        cell = ConidiogenousCellDescription()
        section = self._find_section(text, ["Conidiogenous cell", "Cellulae conidiogenae"])
        if not section:
            section = text

        cell.raw_description = section

        type_terms = ["phialidic", "blastic", "holoblastic", "enteroblastic", "thallic"]
        extracted_types = self._extract_terms(section, type_terms)
        cell.type = ", ".join(extracted_types) if extracted_types else ""

        if re.search(r"\bterminal\b", section, re.I):
            cell.position = "terminal"
        elif re.search(r"\bintercalary\b", section, re.I):
            cell.position = "intercalary"

        if re.search(r"sympodial", section, re.I):
            cell.proliferation = "sympodial"
        elif re.search(r"percurrent", section, re.I):
            cell.proliferation = "percurrent"

        cell.length, cell.width = self._extract_dimensions(section)

        return cell

    def _extract_dimensions(
        self, text: str
    ) -> Tuple[Optional[MorphometricData], Optional[MorphometricData]]:
        pattern = r"(\d+(?:\.\d+)?)[–—-](\d+(?:\.\d+)?)\s*[×x]\s*(\d+(?:\.\d+)?)[–—-](\d+(?:\.\d+)?)\s*([µμ]m)"

        match = re.search(pattern, text)
        if match:
            length = MorphometricData(
                parameter="length",
                min_value=float(match.group(1)),
                max_value=float(match.group(2)),
                unit="µm",
                raw_text=match.group(0),
            )

            width = MorphometricData(
                parameter="width",
                min_value=float(match.group(3)),
                max_value=float(match.group(4)),
                unit="µm",
                raw_text=match.group(0),
            )

            return length, width

        return None, None

    def _extract_septa_count(self, text: str) -> Optional[MorphometricData]:
        patterns = [r"(\d+)[–—-](\d+)[-\s]septa(?:te)?", r"(\d+)[-\s]septa(?:te)?"]

        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                if len(match.groups()) == 2:
                    return MorphometricData(
                        parameter="septa_count",
                        min_value=float(match.group(1)),
                        max_value=float(match.group(2)),
                        raw_text=match.group(0),
                    )
                return MorphometricData(
                    parameter="septa_count",
                    mean_value=float(match.group(1)),
                    raw_text=match.group(0),
                )

        return None

    def _extract_terms(self, text: str, term_list: List[str]) -> List[str]:
        found_terms = []
        for term in term_list:
            pattern = rf"\b{re.escape(term)}\b"
            if re.search(pattern, text, re.I):
                found_terms.append(term)

        return found_terms

    def _find_section(self, text: str, headers: List[str]) -> Optional[str]:
        for header in headers:
            pattern = rf"{header}[^\n]*\n+(.*?)(?=\n[A-Z][a-z]+[^\n]*:|$)"
            match = re.search(pattern, text, re.I | re.DOTALL)
            if match:
                return match.group(1).strip()

        return None

    def _extract_substrate_info(self, text: str) -> List[str]:
        substrates = []
        substrate_terms = [
            "submerged leaves",
            "decomposing leaves",
            "leaf litter",
            "submerged wood",
            "decomposing wood",
            "twigs",
            "bark",
            "foam",
            "water",
            "debris",
        ]

        for term in substrate_terms:
            if re.search(rf"\b{term}\b", text, re.I):
                substrates.append(term)

        return substrates

    def _extract_habitat_info(self, text: str) -> List[str]:
        habitats = []
        habitat_terms = [
            "stream",
            "river",
            "brook",
            "creek",
            "pond",
            "lake",
            "wetland",
            "marsh",
            "swamp",
            "spring",
            "waterfall",
            "lotic",
            "lentic",
            "freshwater",
            "aquatic",
        ]

        for term in habitat_terms:
            if re.search(rf"\b{term}\b", text, re.I):
                habitats.append(term)

        return habitats

    def _extract_distribution(self, text: str) -> List[str]:
        distribution = []
        dist_pattern = (
            r"(?:Geographical distribution|Known distribution|Distribution)[:\s]+(.*?)(?=\n[A-Z]|Material examined|$)"
        )
        match = re.search(dist_pattern, text, re.I | re.DOTALL)

        if match:
            dist_text = match.group(1)
            place_pattern = r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
            places = re.findall(place_pattern, dist_text)
            distribution.extend(places)

        geographic_terms = [
            "Cosmopolitan",
            "Africa",
            "Asia",
            "Europe",
            "North America",
            "South America",
            "Oceania",
            "Antarctica",
            "tropical",
            "temperate",
        ]

        for term in geographic_terms:
            if re.search(rf"\b{term}\b", text, re.I):
                distribution.append(term)

        return list(set(distribution))

    def _extract_holotype(self, text: str) -> str:
        pattern = r"(?:Holotype|Holotypus|Type)[:\s]+([^\n]+)"
        match = re.search(pattern, text, re.I)

        return match.group(1).strip() if match else ""


class FigureExtractor:
    """Extrator especializado de figuras de hifomicetos."""

    def __init__(self, output_dir: str) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.conidia_dir = self.output_dir / "conidia"
        self.conidiophores_dir = self.output_dir / "conidiophores"
        self.keys_dir = self.output_dir / "dichotomous_keys"
        self.composite_dir = self.output_dir / "composite_figures"

        for dir_path in [
            self.conidia_dir,
            self.conidiophores_dir,
            self.keys_dir,
            self.composite_dir,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def extract_all_figures(self, pdf_path: str) -> List[Dict]:
        doc = fitz.open(pdf_path)
        pdf_name = Path(pdf_path).stem

        all_figures = []

        for page_num in range(len(doc)):
            page_figures = self._extract_page_figures(doc, page_num, pdf_name)
            all_figures.extend(page_figures)

        doc.close()

        metadata_file = self.output_dir / f"{pdf_name}_figures_metadata.json"
        metadata_file.write_text(json.dumps(all_figures, indent=2, ensure_ascii=False), encoding="utf-8")

        return all_figures

    def _extract_page_figures(self, doc: fitz.Document, page_num: int, pdf_name: str) -> List[Dict]:
        page = doc[page_num]
        page_text = page.get_text()

        figures = []
        image_list = page.get_images(full=True)

        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]

            img_rects = page.get_image_rects(xref)
            if not img_rects:
                continue

            bbox = img_rects[0]

            img_pil = Image.open(io.BytesIO(image_bytes))
            img_width, img_height = img_pil.size

            figure_type = self._classify_figure_type(page_text, bbox, img_width, img_height)
            caption = self._extract_figure_caption(page_text, bbox, page_num)
            species_list = self._extract_species_from_caption(caption)
            scale_info = self._extract_scale_bar_info(caption, page_text)
            subfigures = self._detect_subfigures(caption)

            figure_data = {
                "pdf_source": pdf_name,
                "page_number": page_num + 1,
                "figure_index": img_index + 1,
                "figure_type": figure_type,
                "caption": caption,
                "species_mentioned": species_list,
                "scale_bar_info": scale_info,
                "subfigures": subfigures,
                "dimensions": {
                    "width_px": img_width,
                    "height_px": img_height,
                    "aspect_ratio": img_width / img_height if img_height > 0 else 0,
                },
                "bounding_box": {
                    "x0": bbox.x0,
                    "y0": bbox.y0,
                    "x1": bbox.x1,
                    "y1": bbox.y1,
                },
                "image_format": image_ext,
            }

            saved_path = self._save_figure(
                image_bytes,
                pdf_name,
                page_num + 1,
                img_index + 1,
                figure_type,
                image_ext,
            )

            figure_data["saved_path"] = str(saved_path)
            figures.append(figure_data)

        return figures

    def _classify_figure_type(self, page_text: str, bbox: fitz.Rect, width: int, height: int) -> str:
        nearby_text = self._get_nearby_text(page_text, bbox)

        if re.search(r"(?:key|clave|chave)\s+to", nearby_text, re.I):
            return "dichotomous_key"

        conidia_terms = ["conidia", "conidio", "spore", "esporo"]
        if any(re.search(rf"\b{term}\b", nearby_text, re.I) for term in conidia_terms):
            if width > height * 1.5 or height > width * 1.5:
                return "conidia_composite"
            return "conidia_drawing"

        if re.search(r"conidiophore|conidioforo", nearby_text, re.I):
            return "conidiophore_drawing"

        if 0.7 < (width / height) < 1.3:
            if "bar" in nearby_text.lower() or "scale" in nearby_text.lower():
                return "microscopy_photo"

        if re.search(r"Fig(?:ure)?s?\.\s*\d+[A-Z]?[–—-]\d+[A-Z]?", nearby_text):
            return "composite_figure"

        return "general_illustration"

    def _extract_figure_caption(self, page_text: str, bbox: fitz.Rect, page_num: int) -> str:
        patterns = [
            r"Fig(?:ure)?s?\.?\s*(\d+[A-Z]?)\.?\s*([^\n]+(?:\n(?!\n|Fig)[^\n]+)*)",
            r"Figs?\.?\s*(\d+[–—-]\d+[A-Z]?)\.?\s*([^\n]+(?:\n(?!\n|Fig)[^\n]+)*)",
            r"Figure\s+(\d+[A-Z]?)[\.:]\s*([^\n]+(?:\n(?!\n|Figure)[^\n]+)*)",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, page_text, re.IGNORECASE)
            for match in matches:
                fig_id = match.group(1)
                caption_text = match.group(2).strip()
                caption_text = re.sub(r"\s+", " ", caption_text)
                return f"Fig. {fig_id}. {caption_text}"

        return ""

    def _get_nearby_text(self, page_text: str, bbox: fitz.Rect, proximity: int = 200) -> str:
        return page_text

    def _extract_species_from_caption(self, caption: str) -> List[str]:
        species_list = []
        pattern = r"\b([A-Z][a-z]+(?:ella|spora|phora|myces|cladium)?)\s+([a-z]+(?:ii|ae|is|um|a)?)\b"

        matches = re.finditer(pattern, caption)
        for match in matches:
            genus = match.group(1)
            epithet = match.group(2)

            if genus not in ["Figure", "Scale", "Bar"]:
                species_list.append(f"{genus} {epithet}")

        return species_list

    def _extract_scale_bar_info(self, caption: str, page_text: str) -> Dict:
        scale_info = {"has_scale_bar": False, "value": None, "unit": None, "applies_to": []}

        patterns = [
            r"[Ss]cale\s+bar[s]?\s*[=:]\s*(\d+(?:\.\d+)?)\s*([µμ]m)",
            r"[Bb]ar[s]?\s*[=:]\s*(\d+(?:\.\d+)?)\s*([µμ]m)",
            r"\([Bb]ar:\s*(\d+(?:\.\d+)?)\s*([µμ]m)\)",
        ]

        text_to_search = caption + " " + page_text

        for pattern in patterns:
            match = re.search(pattern, text_to_search)
            if match:
                scale_info["has_scale_bar"] = True
                scale_info["value"] = float(match.group(1))
                scale_info["unit"] = match.group(2).replace("μ", "µ")
                break

        if "Figs" in caption or re.search(r"Fig\.\s*\d+[A-Z–—-]+", caption):
            subfig_pattern = r"Fig\.\s*(\d+[A-Z](?:[,\s]+[A-Z])*)"
            match = re.search(subfig_pattern, caption)
            if match:
                scale_info["applies_to"] = re.findall(r"[A-Z]", match.group(1))

        return scale_info

    def _detect_subfigures(self, caption: str) -> List[str]:
        subfigures = []

        patterns = [
            r"Fig\.\s*\d+([A-Z])[–—-]([A-Z])",
            r"Fig\.\s*\d+([A-Z](?:,\s*[A-Z])*)",
        ]

        for pattern in patterns:
            match = re.search(pattern, caption)
            if match:
                if "–" in match.group(0) or "—" in match.group(0) or "-" in match.group(0):
                    start = match.group(1)
                    end = match.group(2)
                    subfigures = [chr(i) for i in range(ord(start), ord(end) + 1)]
                else:
                    subfigures = re.findall(r"[A-Z]", match.group(1))
                break

        return subfigures

    def _save_figure(
        self,
        image_bytes: bytes,
        pdf_name: str,
        page_num: int,
        img_index: int,
        figure_type: str,
        image_ext: str,
    ) -> Path:
        if "conidia" in figure_type:
            target_dir = self.conidia_dir
        elif "conidiophore" in figure_type:
            target_dir = self.conidiophores_dir
        elif "key" in figure_type:
            target_dir = self.keys_dir
        elif "composite" in figure_type:
            target_dir = self.composite_dir
        else:
            target_dir = self.output_dir / "other"
            target_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{pdf_name}_p{page_num}_fig{img_index}.{image_ext}"
        filepath = target_dir / filename

        filepath.write_bytes(image_bytes)

        return filepath


class ImageAnnotator:
    """Anotador de imagens com informações taxonômicas."""

    def create_annotated_dataset(self, figures_metadata: List[Dict], output_file: str) -> Dict:
        dataset = {
            "images": [],
            "categories": self._get_morphological_categories(),
            "annotations": [],
        }

        annotation_id = 1

        for idx, fig_meta in enumerate(figures_metadata):
            image_entry = {
                "id": idx + 1,
                "file_name": Path(fig_meta["saved_path"]).name,
                "width": fig_meta["dimensions"]["width_px"],
                "height": fig_meta["dimensions"]["height_px"],
                "species": fig_meta["species_mentioned"],
                "scale_bar": fig_meta["scale_bar_info"],
            }

            dataset["images"].append(image_entry)

            for species in fig_meta["species_mentioned"]:
                annotation = {
                    "id": annotation_id,
                    "image_id": idx + 1,
                    "species_name": species,
                    "figure_type": fig_meta["figure_type"],
                    "caption": fig_meta["caption"],
                }
                dataset["annotations"].append(annotation)
                annotation_id += 1

        Path(output_file).write_text(json.dumps(dataset, indent=2, ensure_ascii=False), encoding="utf-8")

        return dataset

    def _get_morphological_categories(self) -> List[Dict]:
        return [
            {
                "id": 1,
                "name": "tetraradiate",
                "supercategory": "branched_conidia",
                "description": "Conidia with 4 radiating arms",
            },
            {
                "id": 2,
                "name": "sigmoid",
                "supercategory": "scolecoid_conidia",
                "description": "S-shaped conidia",
            },
            {
                "id": 3,
                "name": "filiform",
                "supercategory": "scolecoid_conidia",
                "description": "Thread-like conidia",
            },
            {
                "id": 4,
                "name": "clavate",
                "supercategory": "simple_conidia",
                "description": "Club-shaped conidia",
            },
            {
                "id": 5,
                "name": "triradiate",
                "supercategory": "branched_conidia",
                "description": "Conidia with 3 radiating arms",
            },
            {
                "id": 6,
                "name": "multiradiate",
                "supercategory": "branched_conidia",
                "description": "Conidia with more than 4 arms",
            },
        ]


def iter_pdf_paths(input_dir: Path) -> Iterable[Path]:
    for path in input_dir.rglob("*.pdf"):
        if path.is_file():
            yield path


def extract_text_from_pdf(pdf_path: Path) -> str:
    doc = fitz.open(pdf_path)
    full_text = []
    for page in doc:
        full_text.append(page.get_text())
    doc.close()
    return "\n".join(full_text)


def detect_species_candidates(text: str) -> List[str]:
    pattern = r"\b([A-Z][a-z]+(?:ella|spora|phora|myces|cladium)?)\s+([a-z]+(?:ii|ae|is|um|a)?)\b"
    species = set()
    for match in re.finditer(pattern, text):
        genus = match.group(1)
        epithet = match.group(2)
        if genus not in {"Figure", "Scale", "Bar"}:
            species.add(f"{genus} {epithet}")
    return sorted(species)


def normalize_windows_path(path_str: str) -> Path:
    normalized = Path(path_str)
    return normalized.expanduser().resolve()


def run_pipeline(input_dir: Path, output_dir: Path, species_list: Optional[List[str]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    figure_extractor = FigureExtractor(output_dir=str(figures_dir))
    annotator = ImageAnnotator()
    tax_extractor = TaxonomicDescriptionExtractor()

    taxonomic_records: List[Dict] = []
    figures_records: List[Dict] = []

    for pdf_path in iter_pdf_paths(input_dir):
        text = extract_text_from_pdf(pdf_path)

        if species_list:
            candidates = species_list
        else:
            candidates = detect_species_candidates(text)

        for species_name in candidates:
            description = tax_extractor.extract_description(text, species_name)
            if description:
                record = asdict(description)
                record["source_pdf"] = pdf_path.name
                taxonomic_records.append(record)

        figures_metadata = figure_extractor.extract_all_figures(str(pdf_path))
        figures_records.extend(figures_metadata)

    (output_dir / "taxonomic_descriptions.json").write_text(
        json.dumps(taxonomic_records, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    annotator.create_annotated_dataset(figures_records, str(output_dir / "image_annotations.json"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extração de descrições taxonômicas e figuras de PDFs de hifomicetos.")
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Diretório com artigos em PDF (ex.: D:/MBA/tcc/REFERENCIAS/CHAVES HIFOMICETOS)",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Diretório para salvar imagens e JSONs estruturados",
    )
    parser.add_argument(
        "--species",
        nargs="*",
        default=None,
        help="Lista de espécies para priorizar (opcional)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dir = normalize_windows_path(args.input_dir)
    output_dir = normalize_windows_path(args.output_dir)
    run_pipeline(input_dir=input_dir, output_dir=output_dir, species_list=args.species)


if __name__ == "__main__":
    main()
