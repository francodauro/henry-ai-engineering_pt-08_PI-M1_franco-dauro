"""Prompts del triage versionados en YAML (``prompts/triage_vN.yaml``), fuera del código.

Cada archivo es una **plantilla**: se versiona y nunca se edita (un cambio es siempre una versión nueva).
Las **variables** se completan en cada request y no se versionan (M1L2 · Plantillas y variables):
- en el system: ``{empresa}``, ``{categorias}`` y ``{acciones}`` (salen de src/contract.py);
- en el mensaje del usuario: ``{consulta}``.
"""

from __future__ import annotations

import string
from dataclasses import dataclass
from pathlib import Path

import yaml

from .contract import ACTIONS, CATEGORIES

COMPANY = "Nubbix"
SYSTEM_VARIABLES = {"empresa", "categorias", "acciones"}
USER_VARIABLES = {"consulta"}
REQUIRED_FIELDS = ("version", "fecha", "tecnica", "descripcion", "system", "user")
PREFIX = "triage_"


class PromptError(Exception):
    """El archivo del prompt no existe o está mal formado."""


@dataclass(frozen=True)
class PromptTemplate:
    version: str
    tecnica: str
    system: str
    user: str


def normalize_version(version: str) -> str:
    """Acepta ``v1`` o ``triage_v1`` y devuelve ``triage_v1``."""
    version = version.strip()
    return version if version.startswith(PREFIX) else PREFIX + version


def list_versions(prompts_dir: Path) -> list[str]:
    return sorted(p.stem for p in prompts_dir.glob(f"{PREFIX}v*.yaml"))


def _fields(template: str) -> set[str]:
    """Variables ``{asi}`` que usa una plantilla."""
    try:
        return {name for _, name, _, _ in string.Formatter().parse(template) if name is not None}
    except ValueError as exc:  # por ejemplo, una llave sin cerrar
        raise PromptError(f"Plantilla mal formada: {exc}") from exc


def load_prompt(version: str, prompts_dir: Path) -> PromptTemplate:
    """Lee y valida ``prompts/<version>.yaml``.

    :raises PromptError: si no existe, si falta un campo o si usa variables desconocidas.
    """
    version = normalize_version(version)
    path = prompts_dir / f"{version}.yaml"
    if not path.exists():
        raise PromptError(f"No existe {path.name}. Versiones disponibles: {list_versions(prompts_dir)}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)  # safe_load: solo datos, nunca construye objetos de Python
    if not isinstance(data, dict):
        raise PromptError(f"{path.name} debe ser un mapa YAML con los campos {REQUIRED_FIELDS}")
    missing = [k for k in REQUIRED_FIELDS if not str(data.get(k) or "").strip()]
    if missing:
        raise PromptError(f"A {path.name} le faltan campos: {missing}")
    if data["version"] != version:
        raise PromptError(f"{path.name} dice version={data['version']!r}; debe coincidir con el nombre del archivo")

    system, user = str(data["system"]), str(data["user"])
    if _fields(system) != SYSTEM_VARIABLES:
        raise PromptError(f"{path.name}: el system debe usar exactamente {sorted(SYSTEM_VARIABLES)}; usa {sorted(_fields(system))}")
    if _fields(user) != USER_VARIABLES:
        raise PromptError(f"{path.name}: el user debe usar exactamente {{consulta}}; usa {sorted(_fields(user))}")
    return PromptTemplate(version=version, tecnica=str(data["tecnica"]), system=system, user=user)


def _bullets(items: dict[str, str]) -> str:
    return "\n".join(f"- {name}: {description}" for name, description in items.items())


def render_system(template: PromptTemplate) -> str:
    return template.system.format(empresa=COMPANY, categorias=_bullets(CATEGORIES), acciones=_bullets(ACTIONS))


def render_user(template: PromptTemplate, query: str) -> str:
    return template.user.format(consulta=query)
