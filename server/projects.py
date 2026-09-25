from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    path: str


def parse_projects(raw: str) -> dict[str, Project]:
    """Parsea "id:ruta;id:ruta" en {id: Project}.

    El nombre visible sale del ultimo segmento de la ruta, asi que la
    configuracion no tiene que repetirlo. Las entradas mal formadas se
    ignoran en silencio: una linea rota en la config no debe impedir
    que arranque el servidor. Solo se aceptan rutas absolutas para evitar
    que paths relativos se resuelvan contra el working directory del
    servidor en tiempo de ejecucion. Cuando un id se repite, se mantiene
    la ultima entrada.
    """
    projects: dict[str, Project] = {}
    for entry in raw.split(";"):
        project_id, _, path = entry.partition(":")
        project_id = project_id.strip()
        path = path.strip()
        if not project_id or not path:
            continue
        if not Path(path).is_absolute():
            continue
        projects[project_id] = Project(
            id=project_id,
            name=Path(path).name,
            path=path,
        )
    return projects
