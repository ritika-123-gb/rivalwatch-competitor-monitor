import base64,hashlib,json,os,re,sqlite3,threading,urllib.parse,urllib.request,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).parent; DB=Path(os.getenv('MONITOR_DB',ROOT/'monitor.db')); PORT=int(os.getenv('PORT','8080')); LOCK=threading.Lock()
def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def connect():
 c=sqlite3.connect(DB,timeout=30); c.row_factory=sqlite3.Row; return c
def init():
 with connect() as d: d.executescript('''CREATE TABLE IF NOT EXISTS competitors(id INTEGER PRIMARY KEY,domain TEXT UNIQUE,created_at TEXT,last_checked TEXT,blog_url TEXT,pricing_url TEXT,pricing_hash TEXT,pricing_summary TEXT,check_count INTEGER DEFAULT 0);CREATE TABLE IF NOT EXISTS articles(id INTEGER PRIMARY KEY,competitor_id INTEGER,url TEXT,title TEXT,published TEXT,description TEXT,first_seen TEXT,keyword TEXT,volume INTEGER,enrichment_status TEXT,UNIQUE(competitor_id,url));CREATE TABLE IF NOT EXISTS checks(id INTEGER PRIMARY KEY,competitor_id INTEGER,checked_at TEXT,new_count INTEGER,status TEXT,message TEXT,pricing_changed INTEGER DEFAULT 0);''')
def canon(u):
 p=urllib.parse.urlsplit(u); return urllib.parse.urlunsplit((p.scheme.lower(),p.netloc.lower(),re.sub('/{2,}','/',p.path or '/').rstrip('/') or '/', '', ''))
def fetch(url,timeout=14,limit=1200000):
 q=urllib.request.Request(url,headers={'User-Agent':'CompetitorMonitor/1.0','Accept':'text/html,application/xml,text/xml,*/*'})
 with urllib.request.urlopen(q,timeout=timeout) as r:return r.read(limit+1).decode(r.headers.get_content_charset() or 'utf-8','replace'),r.geturl(),r.headers.get('Content-Type','')
class P(HTMLParser):
 def __init__(self,u):
  super().__init__(convert_charrefs=True);self.u=u;self.links=[];self.meta={};self.dates=[];self.title='';self.it=False;self.ib=False;self.skip=0;self.txt=[]
 def handle_starttag(self,t,attrs):
  a=dict(attrs)
  if t=='title':self.it=True
  if t in ('script','style','noscript','svg'):self.skip+=1
  if t=='body':self.ib=True
  if t in ('a','link') and a.get('href'):self.links.append({'url':urllib.parse.urljoin(self.u,a['href']),'text':a.get('aria-label',a.get('title','')),'rel':a.get('rel',''),'type':a.get('type','')})
  if t=='meta':
   k=(a.get('property') or a.get('name') or a.get('itemprop') or '').lower()
   if k and a.get('content'):self.meta[k]=a['content'].strip()
  if t=='time' and a.get('datetime'):self.dates.append(a['datetime'])
  if t=='meta' and a.get('content') and re.search(r'date|published|pubdate|timestamp',a.get('property','')+' '+a.get('name','')+' '+a.get('itemprop',''),re.I):self.dates.append(a['content'])
 def handle_endtag(self,t):
  if t=='title':self.it=False
  if t=='body':self.ib=False
  if t in ('script','style','noscript','svg'):self.skip=max(0,self.skip-1)
 def handle_data(self,s):
  s=s.strip()
  if self.it and s:self.title+=' '+s
  if self.ib and not self.skip and s:self.txt.append(s)
def parse(b,u):
 p=P(u)
 try:p.feed(b)
 except Exception:pass
 m=p.meta;date=next((m[k] for k in ('article:published_time','datepublished','date','pubdate','publish_date') if m.get(k)),None) or next((x for x in p.dates if re.search(r'\d{4}',x)),None)
 return {'title':(m.get('og:title') or m.get('twitter:title') or p.title).strip(),'description':m.get('description') or m.get('og:description') or m.get('twitter:description') or '','published':date,'links':p.links,'text':re.sub(r'\s+',' ',' '.join(p.txt))}
def same(u,h):
 try:
  target=(urllib.parse.urlsplit(u).hostname or '').lower().removeprefix('www.');base=h.lower().removeprefix('www.');return target==base or target.endswith('.'+base)
 except Exception:return False
ART=re.compile(r'blog|insight|resource|article|news|story|journal|learn|press|update',re.I); SKIP_PATH=re.compile(r'/(?:login|sign[-_]?in|signup|register|developers?|community|trust|about|contact|careers?|legal|privacy|terms|authors?|category|categories|tag|page|search|feed|wp-json|wp-admin)(?:/|$)',re.I); LISTING_PATH=re.compile(r'/(?:blog|resources?|insights?|news|newsroom|articles?|stories|press(?:-releases)?|learn|content|updates?)(?:/|$)',re.I); article_path=lambda p: bool(p and not SKIP_PATH.search(p) and not re.search(r'\.(?:xml|rss|jpe?g|png|gif|svg|pdf|css|js|zip)$',p) and not re.search(r'pricing|plans|price',p) and ((bool(LISTING_PATH.search(p)) and bool(p[LISTING_PATH.search(p).end():].strip('/')) and len(p[LISTING_PATH.search(p).end():].strip('/').split('/'))<=4) or (len([x for x in p.split('/') if x])>=2 and bool(re.search(r'20\d{2}|[-_]',p.rstrip('/').split('/')[-1])))))
def xml_urls(xml):
 try:
  urls=[]
  for e in ET.fromstring(xml).iter():
   if e.tag.split('}')[-1].lower() in ('loc','link'):
    u=(e.text or e.attrib.get('href','')).strip()
    if u.startswith('http'):urls.append(u)
  return urls
 except Exception:return []
def discover(domain):
 domain=domain.strip().lower();domain=domain if re.match(r'^https?://',domain) else 'https://'+domain;s=urllib.parse.urlsplit(domain)
 if not s.hostname or '.' not in s.hostname:raise ValueError('Enter a valid domain, such as example.com')
 host=s.hostname;origin=f'{s.scheme}://{s.netloc}'
 try:b,home,_=fetch(origin)
 except Exception:
  try:origin=('http' if s.scheme=='https' else 'https')+'://'+s.netloc;b,home,_=fetch(origin)
  except Exception as e:raise RuntimeError(f'Could not fetch homepage ({type(e).__name__}). The site may be offline or blocking this server.')
 pages={canon(home):parse(b,home)}; cand=[];feeds=[];maps=[]
 for x in pages[canon(home)]['links']:
  u=x['url'];path=urllib.parse.urlsplit(u).path.lower()
  if not same(u,host):continue
  if 'alternate' in x['rel'].lower() and ('rss' in x['type'].lower() or 'atom' in x['type'].lower() or path.endswith(('.xml','.rss'))):feeds.append(u)
  if 'sitemap' in path:maps.append(u)
  if ART.search(x['text']+' '+path):cand.append(u)
 try:
  robots,_,_=fetch(origin+'/robots.txt',7,100000);maps += [urllib.parse.urljoin(origin,x.group(1)) for x in re.finditer(r'^\s*Sitemap:\s*(\S+)',robots,re.I|re.M)]
 except Exception:pass
 if not maps:maps=[origin+'/sitemap.xml']
 q=maps[:3];seen=set()
 while q and len(seen)<10:
  sm=q.pop(0)
  if sm in seen:continue
  seen.add(sm)
  try:
   xml,_,_=fetch(sm,8,800000);urls=xml_urls(xml)
   if 'sitemapindex' in xml[:1200].lower():q+=urls[:8]
   else:
    for u in urls:
     path=urllib.parse.urlsplit(u).path.lower()
     if same(u,host) and (article_path(path) or re.search(r'pricing|plans|price',path)):cand.append(u)
  except Exception:pass
 listings=list(dict.fromkeys(u for u in cand if same(u,host) and LISTING_PATH.search(urllib.parse.urlsplit(u).path) and not article_path(urllib.parse.urlsplit(u).path)))[:12]
 for f in feeds[:4]:
  try:xml,_,_=fetch(f,8,800000);cand += [u for u in xml_urls(xml)[:40] if same(u,host)]
  except Exception:pass
 urls=[];errors=[]
 for u in listings:
  try:
   b,final,ct=fetch(u,10)
   if 'html' not in ct and not b.lstrip().startswith('<'):continue
   pages[canon(final)]=parse(b,final);urls += [x['url'] for x in pages[canon(final)]['links'] if same(x['url'],host) and article_path(urllib.parse.urlsplit(x['url']).path)]
  except Exception as e:errors.append(f"Listing {urllib.parse.urlsplit(u).path}: {type(e).__name__}")
 urls+=cand;articles=[]
 for u in dict.fromkeys(urls):
  path=urllib.parse.urlsplit(u).path.lower()
  if not same(u,host) or not article_path(path):continue
  
  try:
   b,final,ct=fetch(u,9,900000)
   if 'html' not in ct and not b.lstrip().startswith('<'):continue
   d=parse(b,final)
   if len(d['title'])>=8 and (d['published'] or d['description'] or LISTING_PATH.search(path)):articles.append({'url':canon(final),'title':d['title'],'published':d['published'],'description':d['description']})
  except Exception:pass
  if len(articles)>=30:break
 priceurls=[]
 for page in pages.values():priceurls += [x['url'] for x in page['links'] if same(x['url'],host) and re.search(r'pricing|plans|price',urllib.parse.urlsplit(x['url']).path.lower())]
 priceurls += [u for u in cand if re.search(r'pricing|plans|price',urllib.parse.urlsplit(u).path.lower())];price=None
 if priceurls:
  try:b,final,_=fetch(next(iter(dict.fromkeys(priceurls))));summary=parse(b,final)['text'][:80000];price={'url':canon(final),'hash':hashlib.sha256(summary.encode()).hexdigest(),'summary':summary}
  except Exception as e:errors.append('Pricing page: '+type(e).__name__)
 return {'domain':urllib.parse.urlsplit(home).netloc,'articles':articles,'blog_url':listings[0] if listings else None,'pricing':price,'errors':errors,'page_count':len(pages)}
STOP=set('the a an and or for to of in on with from by how what when why our your their this that new best top guide using use into vs is are be can may will about complete ultimate'.split())
def enrich(title):
 words=re.findall(r'[A-Za-z0-9][A-Za-z0-9+#.-]*',title.lower());kw=' '.join([w for w in words if w not in STOP and len(w)>2][:4]) or title.lower()[:80];login=os.getenv('DATAFORSEO_LOGIN');pw=os.getenv('DATAFORSEO_PASSWORD')
 if not login or not pw:return kw,None,'keyword extracted · add DataForSEO credentials for volume'
 data=json.dumps([{'keywords':[kw],'location_code':int(os.getenv('DATAFORSEO_LOCATION','2840')),'language_code':os.getenv('DATAFORSEO_LANGUAGE','en')}]).encode();auth=base64.b64encode(f'{login}:{pw}'.encode()).decode();req=urllib.request.Request('https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live',data=data,headers={'Authorization':'Basic '+auth,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=12) as r:resp=json.loads(r.read().decode())
  for task in resp.get('tasks',[]):
   for result in task.get('result',[]) or []:
    for item in result.get('items',[]) or []:return item.get('keyword',kw),item.get('search_volume'),'DataForSEO search volume'
  return kw,None,'No volume returned by DataForSEO'
 except Exception as e:return kw,None,f'Volume unavailable · {type(e).__name__}; check credentials'
def send_slack(url,msg):
 req=urllib.request.Request(url,data=json.dumps({'text':msg}).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=10) as r:return r.status
def check(domain,webhook=''):
 found=discover(domain)
 with LOCK:
  with connect() as d:
   row=d.execute('SELECT * FROM competitors WHERE domain=?',(found['domain'],)).fetchone()
   if not row:
    cid=d.execute('INSERT INTO competitors(domain,created_at) VALUES(?,?)',(found['domain'],now())).lastrowid;row=d.execute('SELECT * FROM competitors WHERE id=?',(cid,)).fetchone()
   cid=row['id'];old={x[0] for x in d.execute('SELECT url FROM articles WHERE competitor_id=?',(cid,))};new=[a for a in found['articles'] if a['url'] not in old]
   for a in new:
    kw,vol,status=enrich(a['title']);d.execute('INSERT OR IGNORE INTO articles(competitor_id,url,title,published,description,first_seen,keyword,volume,enrichment_status) VALUES(?,?,?,?,?,?,?,?,?)',(cid,a['url'],a['title'],a['published'],a['description'],now(),kw,vol,status))
   price=found['pricing'];changed=bool(price and row['pricing_hash'] and row['pricing_hash']!=price['hash'])
   if price:d.execute('UPDATE competitors SET pricing_url=?,pricing_hash=?,pricing_summary=? WHERE id=?',(price['url'],price['hash'],price['summary'],cid))
   d.execute('UPDATE competitors SET last_checked=?,blog_url=COALESCE(?,blog_url),check_count=check_count+1 WHERE id=?',(now(),found['blog_url'],cid))
   d.execute('INSERT INTO checks(competitor_id,checked_at,new_count,status,message,pricing_changed) VALUES(?,?,?,?,?,?)',(cid,now(),len(new),'ok' if found['articles'] or found['page_count'] else 'limited','; '.join(found['errors'][:3]),int(changed)))
   out={'competitor':dict(d.execute('SELECT * FROM competitors WHERE id=?',(cid,)).fetchone()),'new_articles':[dict(d.execute('SELECT * FROM articles WHERE competitor_id=? AND url=?',(cid,a['url'])).fetchone()) for a in new],'articles':[dict(x) for x in d.execute('SELECT * FROM articles WHERE competitor_id=? ORDER BY first_seen DESC LIMIT 100',(cid,))],'pricing_changed':changed,'pricing':price or ({'url':row['pricing_url']} if row['pricing_url'] else None),'discovery':{'page_count':found['page_count'],'errors':found['errors'],'article_count':len(found['articles']),'blog_url':found['blog_url']}}
 if webhook and (new or changed):
  lines=[f"*{found['domain']}* — {len(new)} new posts"+('; pricing page changed' if changed else '')]
  for a in new[:10]:
   vol=f"{a['volume']:,} searches/mo" if a['volume'] is not None else 'volume unavailable';lines.append(f"• <{a['url']}|{a['title']}> — keyword: {a['keyword']} · {vol}")
  if changed and price:lines.append('Pricing page: '+price['url'])
  try:send_slack(webhook,'\n'.join(lines));out['alert']='sent'
  except Exception as e:out['alert']='failed: '+type(e).__name__
 elif webhook:out['alert']='no changes to notify'
 return out
class Handler(BaseHTTPRequestHandler):
 def log_message(self,fmt,*args):print(fmt%args)
 def jsonout(self,code,obj):
  b=json.dumps(obj).encode();self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  path=urllib.parse.urlsplit(self.path).path
  if path=='/api/state':
   with LOCK,connect() as d:
    cs=[dict(x) for x in d.execute('SELECT * FROM competitors ORDER BY last_checked DESC,created_at DESC')]
    for c in cs:c['articles']=[dict(a) for a in d.execute('SELECT * FROM articles WHERE competitor_id=? ORDER BY first_seen DESC LIMIT 30',(c['id'],))];c['checks']=[dict(h) for h in d.execute('SELECT * FROM checks WHERE competitor_id=? ORDER BY checked_at DESC LIMIT 10',(c['id'],))]
   return self.jsonout(200,{'competitors':cs})
  if path=='/api/config':return self.jsonout(200,{'keyword_api_configured':bool(os.getenv('DATAFORSEO_LOGIN') and os.getenv('DATAFORSEO_PASSWORD')),'alert_configured':bool(os.getenv('SLACK_WEBHOOK_URL'))})
  names={'/':'index.html','/app.js':'app.js','/styles.css':'styles.css'}
  if path in names:
   b=(ROOT/names[path]).read_bytes();typ='text/html; charset=utf-8' if path=='/' else 'text/javascript; charset=utf-8' if path.endswith('.js') else 'text/css; charset=utf-8';self.send_response(200);self.send_header('Content-Type',typ);self.send_header('Content-Length',str(len(b)));self.end_headers();return self.wfile.write(b)
  self.jsonout(404,{'error':'Not found'})
 def do_POST(self):
  try:b=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or b'{}')
  except Exception:return self.jsonout(400,{'error':'Invalid JSON'})
  path=urllib.parse.urlsplit(self.path).path
  if path=='/api/check':
   if not b.get('domain','').strip():return self.jsonout(400,{'error':'Enter a competitor domain first.'})
   try:return self.jsonout(200,check(b['domain'],b.get('webhook','').strip() or os.getenv('SLACK_WEBHOOK_URL','')))
   except ValueError as e:return self.jsonout(400,{'error':str(e)})
   except Exception as e:return self.jsonout(502,{'error':str(e),'kind':type(e).__name__})
  if path=='/api/check-all':
   with LOCK,connect() as d:domains=[x[0] for x in d.execute('SELECT domain FROM competitors')]
   results=[]
   for x in domains:
    try:results.append(check(x,b.get('webhook','').strip() or os.getenv('SLACK_WEBHOOK_URL','')))
    except Exception as e:results.append({'domain':x,'error':str(e)})
   return self.jsonout(200,{'results':results})
  self.jsonout(404,{'error':'Not found'})
 def do_DELETE(self):
  m=re.fullmatch(r'/api/competitors/(\d+)',urllib.parse.urlsplit(self.path).path)
  if not m:return self.jsonout(404,{'error':'Not found'})
  cid=int(m.group(1))
  with LOCK,connect() as d:d.execute('DELETE FROM articles WHERE competitor_id=?',(cid,));d.execute('DELETE FROM checks WHERE competitor_id=?',(cid,));d.execute('DELETE FROM competitors WHERE id=?',(cid,))
  self.jsonout(200,{'ok':True})
if __name__=='__main__':
 init();print(f'Competitor monitor at http://localhost:{PORT}');ThreadingHTTPServer(('0.0.0.0',PORT),Handler).serve_forever()







