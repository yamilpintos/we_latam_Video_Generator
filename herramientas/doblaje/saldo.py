# -*- coding: utf-8 -*-
"""El estado de la plata, para leer ANTES de gastar desde un chat o la PC.

    python saldo.py              # saldo de cada clave de ElevenLabs, gasto de hoy, topes, pausa, GPU de vast
    python saldo.py --reanudar   # levanta la pausa automática de gasto
    python saldo.py --json
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from doblaje.creditos import main  # noqa: E402

main()
