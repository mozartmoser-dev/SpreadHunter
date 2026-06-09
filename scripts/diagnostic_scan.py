"""Diagnóstico de performance das varreduras.

Uso:
    python scripts/diagnostic_scan.py                    # Analisa logs existentes
    python scripts/diagnostic_scan.py --watch            # Monitora o log em tempo real
"""
import re
import sys
import time
from pathlib import Path
from collections import defaultdict

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_PATTERN = re.compile(
    r"Varredura \((Global|Fast)\): (\d+) monitored, (\d+) with book in ([\d.]+)s"
)


def analisar_logs():
    arquivos = sorted(LOG_DIR.glob("spreadhunter.log*"))
    
    if not arquivos:
        print("Nenhum arquivo de log encontrado em", LOG_DIR)
        return
    
    for arq in arquivos:
        print(f"\n{'='*60}")
        print(f"Arquivo: {arq.name} ({(arq.stat().st_size/1024):.0f} KB)")
        print(f"{'='*60}")
        
        global_tempos = []
        fast_tempos = []
        total_linhas = 0
        
        with open(arq, "r", encoding="utf-8", errors="ignore") as f:
            for linha in f:
                m = LOG_PATTERN.search(linha)
                if m:
                    tipo = m.group(1)
                    segs = float(m.group(4))
                    if tipo == "Global":
                        global_tempos.append(segs)
                    else:
                        fast_tempos.append(segs)
                    total_linhas += 1
        
        if not global_tempos and not fast_tempos:
            print("  Nenhuma varredura encontrada.")
            continue
        
        if global_tempos:
            print(f"\n  Global ({len(global_tempos)} scans):")
            print(f"    Média: {sum(global_tempos)/len(global_tempos):.2f}s")
            print(f"    Mín:   {min(global_tempos):.2f}s")
            print(f"    Máx:   {max(global_tempos):.2f}s")
            gargalos = [t for t in global_tempos if t > 1.0]
            if gargalos:
                print(f"    Gargalos (>1s): {len(gargalos)} ({len(gargalos)/len(global_tempos)*100:.0f}%)")
        
        if fast_tempos:
            print(f"\n  Fast ({len(fast_tempos)} scans):")
            print(f"    Média: {sum(fast_tempos)/len(fast_tempos):.3f}s")
            print(f"    Mín:   {min(fast_tempos):.3f}s")
            print(f"    Máx:   {max(fast_tempos):.3f}s")


def monitorar():
    import subprocess
    log_atual = LOG_DIR / "spreadhunter.log"
    if not log_atual.exists():
        print("spreadhunter.log não encontrado.")
        return
    
    print("Monitorando tempo de varredura (Ctrl+C para parar)...")
    print(f"{'Tipo':<8} {'Monit':>6} {'Book':>6} {'Tempo':>8}")
    print("-"*30)
    
    try:
        with open(log_atual, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, 2)
            while True:
                linha = f.readline()
                if not linha:
                    time.sleep(1)
                    continue
                m = LOG_PATTERN.search(linha)
                if m:
                    tipo = m.group(1)
                    monitored = m.group(2)
                    book = m.group(3)
                    segs = m.group(4)
                    alerta = " ⚠" if float(segs) > 1.0 else ""
                    print(f"{tipo:<8} {monitored:>6} {book:>6} {segs:>7}s{alerta}")
    except KeyboardInterrupt:
        print("\nMonitoramento encerrado.")


if __name__ == "__main__":
    if "--watch" in sys.argv:
        monitorar()
    else:
        analisar_logs()
