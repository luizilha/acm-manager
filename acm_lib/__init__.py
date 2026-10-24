"""Núcleo do AC Manager separado por responsabilidade.

Os módulos internos podem ser importados diretamente; ``acm.py`` reexporta a
API pública antiga para manter compatibilidade com a GUI e scripts.
"""

from .base import *
from .downloads import *
from .catalog import *
from .content import *
from .servers import *
from .installer import *
from .setup import *
from .cli import main
