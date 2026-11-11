"""Preview preservation gate: run with local accepted R4a3 HTML and preview HTML.
No production/network calls. Includes browser menu/finance/RCR checks and scenario sweeps.
"""
import sys,re,json,hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright
base=Path(sys.argv[1]).read_text(encoding='utf-8');current=Path(sys.argv[2]).read_text(encoding='utf-8')

def ids(s,name):
 start=s.index('const '+name+'=[')+len('const '+name+'=[');i=start;depth=1;quote=None;esc=False
 while depth:
  c=s[i]
  if quote:
   if esc:esc=False
   elif c=='\\':esc=True
   elif c==quote:quote=None
  elif c in "'\"`":quote=c
  elif c=='[':depth+=1
  elif c==']':depth-=1
  i+=1
 return re.findall(r"\{id:'([^']+)'",s[start:i-1])

fail=[];info={}
for key in ['SCENARIOS','SESSION_SCENARIOS','INTEGRATED_SCENARIOS']:
 old=ids(base,key);new=ids(current,key);missing=sorted(set(old)-set(new));dupes=[x for x in set(new) if new.count(x)>1]
 if missing or dupes:fail.append(f'{key}: missing {missing}, duplicate {dupes}')
 info[key]={'base':len(old),'preview':len(new),'missing':missing,'extra':sorted(set(new)-set(old))}
if set(ids(current,'INTEGRATED_SCENARIOS'))-set(ids(base,'INTEGRATED_SCENARIOS'))!= {'rcr001-running','rcr001-new','rcr001-unavailable'}:fail.append('Unexpected integrated scenario additions')
if 'Ballen:()=>scene.cashStock?cashStockMockup():reviewFinance()' not in current:fail.append('Ballen finance route missing function invocation')
if "connect-src 'none'" not in current or "form-action 'none'" not in current:fail.append('CSP not retained')
if 'fetch(' in current or 'XMLHttpRequest' in current:fail.append('Unexpected browser network API')

with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
 for mode,width in [('light',390),('dark',390),('light',1280)]:
  page=b.new_page(viewport={'width':width,'height':844},color_scheme=mode);errors=[];requests=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('request',lambda r:requests.append(r.url))
  page.set_content(current,wait_until='domcontentloaded',timeout=20000)
  page.locator('details.review-controls').evaluate('(e)=>e.open=true')
  seen=[]
  for group in page.locator('#integrated-topic option').all_text_contents():
   page.locator('#integrated-topic').select_option(label=group)
   for sid in page.locator('#integrated-scenario option').evaluate_all('(xs)=>xs.map(x=>x.value)'):
    seen.append(sid)
    page.locator('#integrated-scenario').select_option(value=sid)
    try:page.wait_for_function('document.querySelector("#padel-integrated-review").dataset.scenario === '+json.dumps(sid),timeout=3000)
    except Exception:fail.append(f'{mode}/{width}/{sid}: scenario not loaded');continue
    body=page.locator('#integrated-mount #content').inner_text(timeout=3000)
    if not body.strip() or 'function reviewFinance' in body:fail.append(f'{mode}/{width}/{sid}: blank/source code')
    if sid.startswith('rcr001-'):
     if 'Kas & Voorraad' not in body:fail.append(f'{mode}/{width}/{sid}: missing Kas & Voorraad')
    elif 'Read-only mockup ·' in body and 'Kas & Voorraad' in body:fail.append(f'{mode}/{width}/{sid}: leaked RCR screen')
  if set(seen)!=set(ids(current,'INTEGRATED_SCENARIOS')):fail.append(f'{mode}/{width}: selector mismatch')
  # Verify old finance admin view and player advance, not only scenario startup.
  page.locator('#integrated-topic').select_option(label='Start en openen')
  page.locator('#integrated-scenario').select_option(value='initial')
  page.wait_for_function('document.querySelector("#padel-integrated-review").dataset.scenario === "initial"',timeout=3000)
  nav=page.locator('#integrated-mount #nav [data-tab]').evaluate_all('(xs)=>xs.map(x=>x.dataset.tab)')
  if nav!=['Home','Inschrijving','Pleinen','Voorschot','Beheer']:fail.append(f'{mode}/{width}: admin nav changed {nav}')
  page.locator('#integrated-mount [data-tab="Voorschot"]').first.click()
  if 'Ballenvoorschot' not in page.locator('#integrated-mount #content').inner_text():fail.append(f'{mode}/{width}: player finance view missing')
  page.locator('#integrated-mount [data-tab="Beheer"]').first.click()
  utility=page.locator('#integrated-mount .utility-tabs [data-tab]').evaluate_all('(xs)=>xs.map(x=>x.dataset.tab)')
  if utility!=['Beheer','Spelers','Ballen']:fail.append(f'{mode}/{width}: admin utility changed {utility}')
  page.locator('#integrated-mount [data-tab="Ballen"]').first.click()
  oldfin=page.locator('#integrated-mount #content').inner_text()
  if 'Ballen en voorschotten' not in oldfin or 'function reviewFinance' in oldfin:fail.append(f'{mode}/{width}: legacy Ballen missing/source')
  page.locator('#integrated-mount [data-tab="Spelers"]').first.click()
  if 'Spelersbestand' not in page.locator('#integrated-mount #content').inner_text():fail.append(f'{mode}/{width}: players admin missing')
  page.locator('#integrated-role').select_option(value='p2')
  roleNav=page.locator('#integrated-mount #nav [data-tab]').evaluate_all('(xs)=>xs.map(x=>x.dataset.tab)')
  if 'Beheer' in roleNav:fail.append(f'{mode}/{width}: player has admin nav')
  if errors:fail.append(f'{mode}/{width}: errors {errors[:3]}')
  if requests:fail.append(f'{mode}/{width}: requests {requests[:3]}')
  info[f'browser-{mode}-{width}']={'scenarios':len(seen),'nav':nav,'utility':utility,'playerNav':roleNav,'errors':errors,'requests':requests}
  page.close()
 b.close()
report={'result':'PASS' if not fail else 'FAIL','failures':fail,'evidence':info,'sourceSHA256':hashlib.sha256(current.encode()).hexdigest()}
print(json.dumps(report,ensure_ascii=False,indent=2));sys.exit(bool(fail))