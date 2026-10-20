"""Export current storyboard HUD frames, not stale screenshots or sensor logs."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path.home() / 'AppData/Local/Temp/foothold-mvp-render-deps'))
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=True)
    page = browser.new_page(viewport={'width': 1600, 'height': 1000}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto((root / 'output/FOOTHOLD-film-storyboard.html').as_uri())
    page.evaluate('document.fonts.ready')
    for shot, name, done in [('O4','mission',False),('O5','observe',False),('O6','scan',False),('E6','record',False),('E7','transfer',False),('E7','complete',True)]:
        page.evaluate('''([id, done]) => {
          document.querySelector('#hud-export')?.remove();
          const item = all.find(x => x.d[0] === id);
          const node = item.fig.querySelector('.frame').cloneNode(true);
          node.id = 'hud-export';
          node.style.cssText = 'position:fixed;left:0;top:0;width:1600px;height:900px;z-index:99999';
          if (id === 'E7') {
            completed = done;
            node.querySelectorAll('.hud').forEach(x => x.remove());
            // Transfer and completion refer to the same captured target as E6.
            node.querySelector('.photo').setAttribute('style', all.find(x => x.d[0] === 'E6').fig.querySelector('.photo').getAttribute('style'));
            node.insertAdjacentHTML('beforeend', hud('transfer'));
          }
          document.body.append(node);
        }''', [shot, done])
        page.locator('#hud-export').screenshot(path=str(root / f'output/FOOTHOLD-film-hud-v4-{name}.png'))
    browser.close()
    if errors:
        raise RuntimeError(errors)
    print('Exported six current HUD/scan reference frames; no JavaScript errors.')
