"""
run.py - Lanzador institucional INEI SMART-CORE
I.E. INEI N.º 34 de Chancay

Perfiles de Ejecución:
1. Desarrollo (Local Dev): host 127.0.0.1, reload=True, DEMO_MODE configurable.
2. Demostración (Local Demo): host 127.0.0.1, reload=False, DEMO_MODE=True.
3. Producción (Oficial): host 127.0.0.1 (bajo Proxy Reverso Nginx/Caddy), reload=False, DEMO_MODE=False.

Seguridad de Interfaces y Recarga en Caliente:
- host="0.0.0.0": Expone el servidor a todas las interfaces de red físicas y virtuales de la máquina.
  En redes abiertas o no confiables permite acceso directo a clientes no autorizados sin pasar por proxy.
  En producción DEBE escuchar en "127.0.0.1" o en la interfaz interna aislada.
- reload=True: Monitorea activamente el sistema de archivos (inotify/StatReload).
  En producción consume ciclos de CPU innecesarios, reevalúa módulos dinámicamente y puede causar
  inconsistencias en transacciones concurrentes de SQLite. DEBE permanecer reload=False en producción.
"""

import sys
import os
import argparse
import uvicorn

if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath("."))
    
    parser = argparse.ArgumentParser(description="Lanzador institucional INEI SMART-CORE")
    parser.add_argument("--mode", choices=["dev", "demo", "prod"], default=os.getenv("APP_ENV", "dev"),
                        help="Perfil de ejecución: dev (desarrollo), demo (demostración local), prod (producción)")
    parser.add_argument("--host", default=None, help="Host/IP de escucha")
    parser.add_argument("--port", type=int, default=None, help="Puerto TCP")
    args = parser.parse_args()

    from app.config import SERVER_HOST, SERVER_PORT, SERVER_RELOAD, DEMO_MODE

    # Configuración por perfil
    if args.mode == "prod":
        os.environ["DEMO_MODE"] = "false"
        os.environ["SERVER_RELOAD"] = "false"
        host = args.host or "127.0.0.1"
        port = args.port or SERVER_PORT
        reload_flag = False
        print("=" * 70)
        print("  MODO PRODUCCIÓN INEI SMART-CORE - I.E. INEI N° 34")
        print(f"  Escuchando en: http://{host}:{port} (Reload: Desactivado | Demo: Bloqueado)")
        print("=" * 70)
    elif args.mode == "demo":
        os.environ["DEMO_MODE"] = "true"
        os.environ["SERVER_RELOAD"] = "false"
        host = args.host or SERVER_HOST
        port = args.port or SERVER_PORT
        reload_flag = False
        print("=" * 70)
        print("  MODO DEMOSTRACIÓN INSTITUCIONAL - I.E. INEI N° 34")
        print(f"  Escuchando en: http://{host}:{port} (Demo: Habilitado | Reload: Desactivado)")
        print("=" * 70)
    else:
        # Modo Desarrollo (por defecto)
        host = args.host or SERVER_HOST
        port = args.port or SERVER_PORT
        reload_flag = SERVER_RELOAD
        print("=" * 70)
        print("  MODO DESARROLLO / PRUEBAS LOCALES - INEI SMART-CORE")
        print(f"  Escuchando en: http://{host}:{port} (Reload: {reload_flag} | Demo: {DEMO_MODE})")
        print("=" * 70)

    uvicorn.run("app.main:app", host=host, port=port, reload=reload_flag)
