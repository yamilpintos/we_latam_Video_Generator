#!/usr/bin/env bash
# Guardia nocturna (15/9): cada 10 min baja lo terminado (bajar_paralelo.sh) y
# mira el crédito de Vast; si baja de $1,50 destruye la instancia para no quedar
# en negativo (lo bajado ya está a salvo). Termina cuando hay 94 clips locales
# o la instancia ya no existe.
cd "$(dirname "$0")"
PY=/c/Python314/python
IID=$(python -c "import json;print(json.load(open('corrida.json'))['instancia'])")
while true; do
  bash bajar_paralelo.sh 2>&1 | grep -E "locales|!!" | tail -2
  n=$(ls clips/T*_00001_.mp4 2>/dev/null | wc -l)
  cred=$(cd ../.. && python -X utf8 -c "
import sys; sys.path.insert(0,'.')
from h3pipeline import vast
u=vast._pedir('/users/current/'); print(round(u.get('credit') or 0,2))
vivas=[i['id'] for i in vast.instancias()]
print('viva' if $IID in vivas else 'muerta')" 2>/dev/null | tr '\n' ' ')
  echo "$(date +%H:%M) clips locales: $n/71 · crédito: $cred"
  case "$cred" in *muerta*) echo "instancia ya no existe; fin"; break;; esac
  c=${cred%% *}
  if awk "BEGIN{exit !($c < 1.5)}"; then
    echo "CRÉDITO BAJO ($c): destruyo la instancia $IID"
    (cd ../.. && python -X utf8 -c "
import sys; sys.path.insert(0,'.')
from h3pipeline import vast; print(vast.destruir($IID, confirmar=True))")
    break
  fi
  [ "$n" -ge 71 ] && { echo "los 71 están; fin"; break; }
  sleep 600
done
