"""Offline preview smoke tests; run: python preview_regression.py path/to/index.html"""
import sys,json
from pathlib import Path
from playwright.sync_api import sync_playwright
src=Path(sys.argv[1]).read_text(encoding='utf-8')
results=[]
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
 for mode in ['light','dark']:
  page=browser.new_page(viewport={'width':390,'height':844},color_scheme=mode)
  errors=[]; requests=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('request',lambda r:requests.append(r.url))
  page.set_content(src,wait_until='domcontentloaded',timeout=20000)
  page.locator('details.review-controls').evaluate('(e)=>e.open=true')
  scenarios=page.locator('#integrated-scenario option').count()
  groups=page.locator('#integrated-topic option').all_text_contents()
  ids=[];fail=[]
  for group in groups:
   page.locator('#integrated-topic').select_option(label=group)
   choices=page.locator('#integrated-scenario option').evaluate_all('(xs)=>xs.map(x=>x.value)')
   for sid in choices:
    ids.append(sid)
    try:
     page.locator('#integrated-scenario').select_option(value=sid)
     page.wait_for_function('document.querySelector("#padel-integrated-review").dataset.scenario === '+json.dumps(sid),timeout=2500)
     content=page.locator('#integrated-mount #content').inner_text(timeout=2500)
     if not content.strip() or 'Aanmelden\nAccount' in content:fail.append((sid,'blank or login screen'))
     if sid.startswith('rcr001-') and 'Kas & Voorraad' not in content:fail.append((sid,'missing finance screen'))
    except Exception as e:fail.append((sid,str(e)[:150]))
  fg=page.locator('#integrated-reference').evaluate('(e)=>getComputedStyle(e).color')
  results.append({'mode':mode,'scenario_count':len(ids),'unique':len(set(ids)),'fail':fail[:30],'fail_count':len(fail),'errors':errors[:10],'requests':requests,'description_color':fg})
  page.close()
 browser.close()
print(json.dumps(results,ensure_ascii=False,indent=2))
if any(r['fail_count'] or r['errors'] or r['requests'] or r['scenario_count']!=62 for r in results):sys.exit(1)