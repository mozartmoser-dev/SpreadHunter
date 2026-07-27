import pyautogui
import time
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.infrastructure.integrations.pnt import _focar_janela_pnt, _localizar_imagem

images_dir = Path("src/infrastructure/integrations/pnt_images")
_focar_janela_pnt()
time.sleep(1.0)

pos = _localizar_imagem(str(images_dir), "ferramentas.png")
if pos:
    x, y = pyautogui.center(pos)
    print(f"Found Ferramentas at {x}, {y}. Clicking...")
    pyautogui.moveTo(x, y, duration=0.3)
    time.sleep(0.2)
    pyautogui.click()
    time.sleep(1.0)
    
    # 4 down presses
    for i in range(1, 5):
        pyautogui.press("down")
        time.sleep(0.3)
        pyautogui.screenshot(str(images_dir / f"debug_run2_down{i}.png"))
        print(f"Pressed down {i}")
        
    pyautogui.press("enter")
    time.sleep(2.0)
    pyautogui.screenshot(str(images_dir / "debug_run2_enter.png"))
    print("Pressed enter and captured screen.")
else:
    print("Ferramentas not found")
