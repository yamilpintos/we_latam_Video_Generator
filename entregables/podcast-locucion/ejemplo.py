"""Un episodio de punta a punta, sin la API.

    export ELEVENLABS_API_KEY=...
    python ejemplo.py
"""
from pathlib import Path

from locucion import Ajustes, audio, guion, narrar, voces

TEXTO = """Hay una foto que mi padre guardó durante treinta años en la guantera de un camión.
Está gastada en los bordes y tiene una mancha de aceite que le tapa media cara.

Durante mucho tiempo pensé que era un descuido. [sighs] No lo era.

La verdad la supe el día que vendimos el camión, y no fue él quien me la contó."""

AJUSTES = Ajustes(voz_id=voces.MEDIDAS["pablo"]["voz_id"])

# 1 · estimar antes de gastar un solo crédito
cps = voces.cps_de(AJUSTES.voz_id)
seg = guion.estimar(TEXTO, cps, AJUSTES.pausa_oracion, AJUSTES.pausa_parrafo, AJUSTES.arranque)
print(f"estimado: {seg:.1f} s · {len(TEXTO)} caracteres · {len(guion.partir(TEXTO))} líneas")

# 2 · locutar
salida = Path("episodio.mp3")
ep = narrar(TEXTO, AJUSTES, salida, cache=Path("cache"),
            progreso=lambda i, n, t: print(f"  [{i}/{n}] {t[:60]}"))
print(f"real: {ep.total:.1f} s → {salida} ({salida.stat().st_size / 1e6:.1f} MB)")

# 3 · los subtítulos salen con los tiempos REALES, no estimados
Path("episodio.srt").write_text(ep.srt(), encoding="utf-8")
print("subtítulos en episodio.srt")

# 4 · verificar el máster: tiene que dar -14 ± 0,5
lufs = audio.medir_lufs(salida)
print(f"volumen integrado: {lufs} LUFS" if lufs is not None else "no pude medir el volumen")
