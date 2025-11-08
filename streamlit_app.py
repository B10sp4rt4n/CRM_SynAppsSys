import sys
import os
from pathlib import Path

# Cambiar al directorio correcto
aup_dir = Path(__file__).parent / "aup_crm_core"
os.chdir(str(aup_dir))
sys.path.insert(0, str(aup_dir))

# Ejecutar la app
exec(open("ui/main_app.py").read())
