"""Optional browser checks against a locally running, signed-out development workspace."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
parser=argparse.ArgumentParser()
parser.add_argument('--base-url', default='http://127.0.0.1:8011')
parser.add_argument('--screenshots', type=Path, default=Path('/tmp/preparationpal-app-ui'))
parser.add_argument('--capture-preview', action='store_true')
args=parser.parse_args()
base=args.base_url.rstrip('/')
out=args.screenshots;out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
 browser=p.chromium.launch(channel='chrome')
 page=browser.new_page(viewport={'width':1440,'height':960})
 errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(base+'/prepare')
 expect(page.get_by_role('heading',name='What would you like to practise?')).to_be_visible()
 page.evaluate('document.fonts.ready')
 expect(page.get_by_role('button',name='Model',exact=True)).to_contain_text('qwen2.5:7b')
 page.screenshot(path=str(out/'workspace-desktop.png'))
 if args.capture_preview:
  page.screenshot(path=str(Path(__file__).resolve().parents[1]/'frontend/public/workspace-preview.png'))
 before=page.locator('header').last.bounding_box()['height']
 page.get_by_role('button',name='Model info',exact=True).click()
 expect(page.get_by_role('dialog')).to_be_visible()
 assert page.locator('header').last.bounding_box()['height']==before
 page.screenshot(path=str(out/'model-info.png'))
 page.keyboard.press('Escape')
 expect(page.get_by_role('dialog')).not_to_be_visible()
 expect(page.get_by_role('button',name='Model info',exact=True)).to_be_focused()
 for name in ['Question format','Difficulty','Questions']:
  page.get_by_role('button',name=name,exact=True).click()
  expect(page.get_by_role('listbox',name=name)).to_be_visible()
  page.keyboard.press('End');page.keyboard.press('Enter')
 expect(page.locator('select')).to_have_count(0)
 for width in [320,375,768,1440]:
  page.set_viewport_size({'width':width,'height':960})
  page.goto(base+'/prepare')
  expect(page.get_by_role('button',name='Model info',exact=True)).to_be_visible()
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),width
  page.get_by_role('button',name='Model info',exact=True).click()
  box=page.get_by_role('dialog').bounding_box()
  assert box['x']>=0 and box['x']+box['width']<=width,width
  page.keyboard.press('Escape')
  page.get_by_role('button',name='Questions',exact=True).click()
  expect(page.get_by_role('option',name='20',exact=True)).to_be_visible()
  page.screenshot(path=str(out/f'controls-{width}.png'))
  page.keyboard.press('Escape')
 page.set_viewport_size({'width':1440,'height':960})
 for route in ['quiz','agent','code','chat','flashcards','guide']:
  page.goto(base+'/'+route)
  expect(page.get_by_role('button',name='Model',exact=True)).to_be_visible()
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),route
 page.set_viewport_size({'width':1440,'height':1000})
 for width in [1440,375,320]:
  page.set_viewport_size({'width':width,'height':1000})
  page.goto(base+'/')
  page.evaluate('document.fonts.ready')
  expect(page.get_by_role('heading',level=1)).to_contain_text('Practise the questions')
  assert page.locator('.workspace img').evaluate('(img) => img.complete && img.naturalWidth > 0')
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),width
  page.screenshot(path=str(out/f'landing-{width}.png'),full_page=True)
 assert not errors,errors
 browser.close()
print('Workspace, all routes, custom lists, model dialog and responsive checks passed.')
