#!/usr/bin/env python3
"""Run the report's 40 case IDs against ephemeral Docker Compose services.

This extends the earlier 16 API cases with browser, SQLite, HTTP, concurrency,
service-failure, and Socket.IO tests. An observed prerequisite gap is Blocked,
not a fabricated Pass. The four known defects are expected to be reported Fail.
Only run on isolated CI demo data. Never use against production systems.
"""
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time
import uuid

from run_integration import Runner, NotReady, CheckFailed


class FullRunner(Runner):
    def __init__(self, base, out, project):
        super().__init__(base, out)
        self.project = Path(project)
        self.browser = None
        self.context = None
        self.pw = None
        self.admin_token = None
        self.other_token = None
        self.expected_browser_cases = {2,3,4,5,6,18,19,21,22,23,24,40}

    def extra(self):
        self.test_catalog_db()
        self.test_accounts()
        self.test_order_flow()
        self.test_chat()
        self.test_browser()
        self.test_concurrency()
        self.test_catalog_failure()
        # Ensure all test IDs were attempted (even if prerequisites failed)
        missed=[row['id'] for row in self.rows if row['status']=='Not Run']
        if missed:
            print('WARNING: Cases not attempted: '+', '.join(missed), flush=True)

    def token_b(self):
        if self.other_token: return self.other_token
        code, data = self.req('POST','/users/users/login',{'email':self.other_email, 'password':self.test_password})
        if code != 200:
            code,_ = self.req('POST','/users/users/register',{'name':'CI Test B','email':self.other_email,'password':self.test_password})
            self.check(code==201, f'Cannot prepare synthetic B (HTTP {code})')
            code,data=self.req('POST','/users/users/login',{'email':self.other_email,'password':self.test_password})
        self.check(code==200 and 'access_token' in data, f'Cannot login B: HTTP {code}')
        self.other_token=data['access_token']
        return self.other_token

    def new_order(self,token=None,car=None,quantity=1):
        token=token or self.require(self.auth_a,'synthetic A JWT')
        car=car or self.require(self.car,'Catalog seed data')
        code, data=self.req('POST','/orders/orders', {'items':[{'car_id':car['id'],'quantity':quantity}]},token=token)
        self.check(code==201 and 'id' in data, f'Cannot prepare synthetic order: HTTP {code} {data}')
        return data

    def orders(self,token):
        code,data=self.req('GET','/orders/orders',token=token)
        self.check(code==200 and isinstance(data,list),f'Cannot read orders: HTTP {code}')
        return data

    def one_order(self, token, oid):
        return next((o for o in self.orders(token) if o['id']==oid),None)

    def test_catalog_db(self):
        def tc07():
            c=self.require(self.car,'Catalog list')
            path=self.project/'catalog-service'/'instance'/'catalog_service_v3.db'
            if not path.exists():
                raise NotReady(f'SQLite database unavailable at {path}')
            with sqlite3.connect(f'file:{path}?mode=ro',uri=True,timeout=5) as db:
                total=db.execute('select coalesce(sum(stock_quantity),0) from inventory where car_model_id=?',(c['id'],)).fetchone()[0]
            code,data=self.req('GET',f'/catalog/catalog/cars/{c["id"]}')
            self.check(code==200,f'Catalog detail HTTP {code}')
            self.check(data.get('stock_quantity')==total,f'API stock {data.get("stock_quantity")}, SQLite sum {total}')
            return f'Car {c["id"]}, DB sum {total}, API {data["stock_quantity"]}'
        self.run(7,'Catalog stock_quantity equals sum of SQLite inventory rows',tc07)

    def test_accounts(self):
        def tc10():
            self.require(self.auth_a,'A login')
            code, account=self.req('POST','/users/users/login', {'email':self.user_email,'password':self.test_password})
            self.check(code==200 and account.get('user_id'),f'Cannot get user_id from login HTTP {code}')
            uid=account['user_id']; name='CI QA name '+uuid.uuid4().hex[:6]
            code,data=self.req('PUT','/users/users/update',{'name':name},token=self.auth_a)
            self.check(code==200,f'Profile update HTTP {code}')
            code,data=self.req('GET',f'/users/users/{uid}',token=self.auth_a)
            self.check(code==200 and data.get('name')==name,f'Profile read-back mismatch: {data}')
            return f'User {uid}, new name persisted'
        self.run(10,'Authenticated user can update own name and read it back',tc10)

        def tc11():
            self.require(self.auth_a,'A JWT')
            wrong,new_pwd='DefinitelyWrong123!', 'CI-Changed-Password-'+uuid.uuid4().hex[:12]
            code,_=self.req('PUT','/users/users/change-password',{'old_password':wrong,'new_password':new_pwd},token=self.auth_a)
            self.check(code==401,f'Wrong old password expected 401, got {code}')
            code,_=self.req('PUT','/users/users/change-password',{'old_password':self.test_password,'new_password':new_pwd},token=self.auth_a)
            self.check(code==200,f'Correct old password expected 200, got {code}')
            old_code,_=self.req('POST','/users/users/login',{'email':self.user_email,'password':self.test_password})
            new_code,body=self.req('POST','/users/users/login',{'email':self.user_email,'password':new_pwd})
            self.check(old_code==401 and new_code==200 and 'access_token' in body,f'Old/new login HTTP {old_code}/{new_code}')
            self.auth_a=body['access_token']
            return 'Wrong old rejected, correct changed, old login 401/new login 200'
        self.run(11,'Old incorrect password fails; new password replaces previous password',tc11)

    def test_order_flow(self):
        def tc14():
            a=self.require(self.auth_a,'A JWT');o=self.new_order(a);before=o['total_amount']
            code,_=self.req('PUT',f'/orders/orders/{o["id"]}/pay',{'method':'demo'},token=a)
            after=self.one_order(a,o['id'])
            self.check(code==200 and after is not None and after['status']=='Paid',f'Pay HTTP {code}, after {after}')
            self.check(after['total_amount']==before,'Order amount changed during mock payment')
            return f'Order {o["id"]}: Pending -> Paid, amount unchanged (simulation only)'
        self.run(14,'Own demo order changes to Paid; amount unchanged',tc14)

        def tc15():
            a=self.require(self.auth_a,'A JWT');b=self.token_b()
            ob=self.new_order(b)
            oa=self.new_order(a)
            la=self.orders(a); lb=self.orders(b)
            self.check(ob['id'] not in {o['id'] for o in la},'A sees B order')
            self.check(oa['id'] not in {o['id'] for o in lb},'B sees A order')
            self.check(all(o.get('user_id')==oa['user_id'] for o in la),'A order user_id mismatch')
            self.check(all(o.get('user_id')==ob['user_id'] for o in lb),'B order user_id mismatch')
            return f'A orders {len(la)}; B orders {len(lb)}; no cross-visible orders'
        self.run(15,'Account A/B order lists are separated',tc15)

        def tc16():
            a=self.require(self.auth_a,'A JWT')
            code,admin=self.req('POST','/users/users/login',{'email':'admin@vinfast.com','password':'admin123'})
            if code!=200 or 'access_token' not in admin:
                raise NotReady('Demo admin fixture unavailable; provide CI-only admin credentials')
            self.admin_token=admin['access_token']
            o=self.new_order(a)
            code,_=self.req('PUT',f'/orders/orders/{o["id"]}/confirm',token=self.admin_token)
            after=self.one_order(a,o['id'])
            self.check(code==200 and after and after['status']=='Scheduled',f'Confirm HTTP {code}, order {after}')
            histcode,hist=self.req('GET',f'/chat/chat/{o["id"]}',token=a)
            self.check(histcode==200 and isinstance(hist,list) and any('THÔNG BÁO' in x.get('content','') for x in hist),f'No expected chat notification (HTTP {histcode})')
            return f'Admin confirmed order {o["id"]} and chat notification persisted'
        self.run(16,'Demo admin can confirm order; system chat notification persisted',tc16)

        def tc37():
            a=self.require(self.auth_a,'A JWT');o=self.new_order(a)
            x,_=self.req('PUT',f'/orders/orders/{o["id"]}/pay',{'method':'demo'},token=a)
            after1=self.one_order(a,o['id'])
            y,_=self.req('PUT',f'/orders/orders/{o["id"]}/pay',{'method':'demo'},token=a)
            after2=self.one_order(a,o['id'])
            self.check(x==200 and y==200 and after1 and after2,'Demo repeat pay endpoint unavailable')
            self.check(after1['status']==after2['status']=='Paid','Repeated request changed status incorrectly')
            self.check(after1['total_amount']==after2['total_amount'],'Repeated request changed total')
            return 'Repeated mock pay kept Paid and amount unchanged; no real transaction ledger exists'
        self.run(37,'Repeated mock payment does not change amount or leave Paid state',tc37)

        def tc38():
            a=self.require(self.auth_a,'Customer JWT');o=self.new_order(a)
            before=self.one_order(a,o['id'])
            code,_=self.req('PUT',f'/orders/orders/{o["id"]}/confirm',token=a)
            after=self.one_order(a,o['id'])
            self.check(code==403,f'Expected 403, got {code}')
            self.check(after and before and after['status']==before['status'],'Unauthorized confirm changed order')
            return f'HTTP 403; order {o["id"]} remained {after["status"]}'
        self.run(38,'Customer cannot confirm appointment as admin',tc38)

    def test_chat(self):
        def client(self,url):
            try:
                import socketio
            except ImportError as e:raise NotReady('python-socketio[client] not installed') from e
            return socketio.Client(reconnection=False,logger=False,engineio_logger=False,request_timeout=6)

        def tc17():
            oid=self.order_id or self.new_order()['id']
            a=self.client(self.base);b=self.client(self.base)
            messages=[];ev=threading.Event();marker='CI_CHAT_'+uuid.uuid4().hex[:10]
            @b.on('receive_message')
            def collect(msg):
                if marker in str(msg):messages.append(msg);ev.set()
            try:
                a.connect(self.base,transports=['websocket'],wait_timeout=8)
                b.connect(self.base,transports=['websocket'],wait_timeout=8)
                a.emit('join',{'order_id':oid}); b.emit('join',{'order_id':oid});time.sleep(0.7)
                a.emit('send_message',{'order_id':oid,'role':'customer','name':'CI A','content':marker})
                ev.wait(5)
            finally:
                for cl in (a,b):
                    try:cl.disconnect()
                    except Exception:pass
            histcode,hist=self.req('GET',f'/chat/chat/{oid}',token=self.require(self.auth_a,'A JWT'))
            self.check(histcode==200 and any(marker in x.get('content','') for x in hist),f'Message was not persisted (HTTP {histcode})')
            self.check(bool(messages),'Message stored but client B did not receive via Gateway room')
            return f'Gateway Socket.IO delivered message for order {oid}; history persisted'
        self.run(17,'Two gateway Socket.IO clients in same test order receive message; history persisted',tc17)

        def tc39():
            # Deliberately use isolated Chat container on localhost:5005 to test
            # the SERVICE authorization boundary, not production/private rooms.
            try:
                import socketio
            except ImportError as e:raise NotReady('python-socketio[client] unavailable') from e
            oid=self.order_id or self.new_order()['id']
            url='http://127.0.0.1:5005'
            unauthorized=self.client(url);sender=self.client(url)
            marker='CI_UNAUTHORIZED_'+uuid.uuid4().hex[:10]
            received=[];ev=threading.Event()
            @unauthorized.on('receive_message')
            def callback(data):
                if marker in str(data):received.append(data);ev.set()
            try:
                unauthorized.connect(url,wait_timeout=8)
                sender.connect(url,wait_timeout=8)
                unauthorized.emit('join',{'order_id':oid})
                sender.emit('join',{'order_id':oid})
                time.sleep(0.6)
                sender.emit('send_message',{'order_id':oid,'role':'customer','name':'CI legit','content':marker})
                ev.wait(5)
            finally:
                for cl in (unauthorized,sender):
                    try:cl.disconnect()
                    except Exception:pass
            self.check(not received,f'Unauthenticated socket joined test room {oid} and received message')
            return 'Unauthenticated socket did not receive private message in isolated Chat service'
        self.run(39,'Unauthenticated socket must not receive another test order chat (Chat service boundary)',tc39)

    def test_browser(self):
        try:
            from playwright.sync_api import sync_playwright
            self.pw=sync_playwright().start()
            self.browser=self.pw.chromium.launch(headless=True,args=['--no-sandbox'])
            self.context=self.browser.new_context(viewport={'width':1365,'height':850},ignore_https_errors=True)
            self.context.route('**/*',lambda route: route.abort() if route.request.resource_type=='image' and route.request.url.startswith('https://') else route.continue_())
            page=self.context.new_page()
            page.goto('http://127.0.0.1/',wait_until='domcontentloaded',timeout=18000)
            page.locator('#car-list .car-card').first.wait_for(timeout=15000)
        except Exception as e:
            reason=f'Chromium/frontend not ready: {type(e).__name__}: {str(e)[:180]}'
            for tc in sorted(self.expected_browser_cases):
                self.run(tc,'Browser prerequisite available',lambda reason=reason: (_ for _ in ()).throw(NotReady(reason)))
            self._browser_cleanup()
            return
        try:
            self._browser_checks(page)
        finally:
            self._browser_cleanup()

    def screenshot(self,page,tc):
        try:
            p=self.out/'screenshots';p.mkdir(exist_ok=True)
            f=p/f'TC-{tc:02d}.png';page.screenshot(path=str(f),full_page=True,timeout=8000)
            self.rows[tc-1]['evidence']=f'screenshots/{f.name}; http_trace.jsonl'
        except Exception:pass

    def _browser_checks(self,page):
        def names():return sorted([x.strip() for x in page.locator('#car-list .car-card h2').all_text_contents()])
        def set_search(value):
            page.locator('#search-input').fill(value)
            page.wait_for_timeout(300)
            return names()
        def tc02():
            wanted=set_search('VF 8');self.screenshot(page,2)
            self.check(wanted==['VinFast VF 8'],f'Expected VF 8 only, got {wanted}')
            return f'Names after VF 8 search: {wanted}'
        self.run(2,'Search VF 8 shows only the matching model',tc02)

        def tc03():
            found=set_search('Flagship');self.screenshot(page,3)
            self.check(found==['VinFast VF 9'],f'Expected description match VF 9, got {found}')
            return 'Description keyword Flagship matched VF 9'
        self.run(3,'A description-only keyword matches model via OR search',tc03)

        def absent_filter(tc,label):
            # A prerequisite observation, not an executed filter test.
            controls=page.locator('input,select,button').evaluate_all('(els) => els.map(e => ({id:e.id,txt:(e.textContent||""),placeholder:e.placeholder||""}))')
            relevant=[v for v in controls if any(w in str(v).lower() for w in ('minprice','maxprice','pricefilter','giá từ','dòng xe','loaixe'))]
            self.screenshot(page,tc)
            if not relevant: raise NotReady(f'{label} UI/control not implemented; cannot execute a valid boundary assertion')
            raise NotReady(f'{label} control may exist but test fixture/acceptance criterion needs review: {relevant[:2]}')
        for tc,label in [(4,'Price range'),(5,'Car category'),(23,'Lower price boundary'),(24,'Upper price boundary')]:
            self.run(tc,f'{label} filter is implemented with testable controls',lambda tc=tc,label=label: absent_filter(tc,label))

        def tc06():
            c=self.require(self.car,'Catalog list'); pid=c['id']
            p=self.context.new_page()
            try:
                p.goto(f'http://127.0.0.1/car_detail.html?car_id={pid}',wait_until='domcontentloaded',timeout=15000)
                p.locator('#car-name').filter(has_text=c['model_name']).wait_for(timeout=12000)
                nm=p.locator('#car-name').inner_text(); price=p.locator('#car-price').inner_text()
                desc=p.locator('#car-desc').inner_text(); spec=p.locator('#car-specs li').count()
                self.screenshot(p,6)
                self.check(c['model_name'] in nm, 'Wrong car name')
                self.check(c['description'] in desc,f'Description mismatch: {desc[:80]}')
                self.check(spec>0,'Car technical specifications missing')
                self.check(''.join(ch for ch in price if ch.isdigit()) == str(c['base_price']), f'Price mismatch: UI {price}, API {c["base_price"]}')
                self.check(p.locator('#car-image-box img').count() == 1, 'Car image element missing')
                return f'Car ID {pid}: name/price/description/specs and image element match Catalog; external image download not asserted'
            finally:p.close()
        self.run(6,'Car detail UI matches Catalog and renders specs',tc06)

        def tc19():
            set_search('vf 8'); restored=set_search('');self.screenshot(page,19)
            code,allcars=self.req('GET','/catalog/catalog/cars')
            self.check(code==200 and len(restored)==len(allcars),f'Clear search restored {len(restored)} / {len(allcars)}')
            return f'{len(restored)} cards restored'
        self.run(19,'Clearing search restores all cards',tc19)

        def tc21():
            a=set_search('vf 8');b=set_search('VF 8')
            c=set_search('hạng');d=set_search('HẠNG')
            self.screenshot(page,21)
            self.check(a==b and c==d,f'Case-insensitive mismatch: {a}/{b}; {c}/{d}')
            return 'Case insensitive search verified for ASCII and accented Vietnamese; accent removal not specified'
        self.run(21,'Case-insensitive matching for ASCII/Vietnamese characters',tc21)

        def tc22():
            a=set_search('VF 8');b=set_search('  VF 8  ')
            self.screenshot(page,22)
            if a!=b:raise NotReady(f'Observed difference (normal {a}; padded {b}); SRS does not define trim requirement')
            return 'Padded and unpadded queries returned same list'
        self.run(22,'Document behavior for padded spaces; require SRS oracle for failure classification',tc22)

        def tc18():
            admin=self.require(self.admin_token,'admin login fixture')
            context=self.browser.new_context(viewport={'width':1365,'height':850},ignore_https_errors=True)
            try:
                context.add_init_script(f'localStorage.setItem("jwt_token", {json.dumps(admin)});localStorage.setItem("user_role", "admin");')
                p=context.new_page();p.goto('http://127.0.0.1/admin.html',wait_until='domcontentloaded',timeout=18000)
                p.wait_for_timeout(5000)
                self.screenshot(p,18)
                has_chart=p.evaluate('typeof Chart !== "undefined" && !!Chart.getChart("orderStatusChart") && !!Chart.getChart("inventoryChart")')
                if not has_chart:raise NotReady('Chart.js CDN unavailable or charts not initialized; API/UI needs separate investigation')
                n=p.locator('#orders-table-body tr').count()
                self.check(n>0,'Order table empty')
                return f'Charts initialized; {n} dashboard table rows'
            finally:context.close()
        self.run(18,'Admin status and inventory charts render on Chromium',tc18)

        def tc40():
            # Safe canary HTML only; API is intercepted at the browser boundary.
            marker='<em data-sqa-canary="true">CANARY</em>'
            code,cars=self.req('GET','/catalog/catalog/cars')
            self.check(code==200 and cars,'No test cars')
            fixture=json.loads(json.dumps(cars));fixture[0]['description']=marker
            p=self.context.new_page()
            def mock_catalog(route):route.fulfill(status=200,content_type='application/json',body=json.dumps(fixture,ensure_ascii=False))
            p.route('**/catalog/catalog/cars',mock_catalog)
            try:
                p.goto('http://127.0.0.1/index.html',wait_until='domcontentloaded',timeout=15000)
                p.locator('.car-card').first.wait_for(timeout=12000)
                list_em=p.locator('.car-card .desc em[data-sqa-canary]').count()
                # Exercise the existing chat renderer only with a benign fixture.
                chat_result=p.evaluate('''(s) => {
                  const c=document.getElementById('chatMessages');
                  if(!c || typeof appendMessageToUI !== 'function') return 'not-renderable';
                  c.innerHTML='';
                  appendMessageToUI({content:s,role:'customer',name:'CI',time:'00:00',order_id:1});
                  return c.querySelector('em[data-sqa-canary]')?'html-created':'plain-text';
                }''',marker)
                self.screenshot(p,40)
                if chat_result=='not-renderable':raise NotReady(f'Catalog list HTML created={bool(list_em)}, chat renderer missing; cannot complete both variants')
                self.check(list_em==0 and chat_result=='plain-text',f'HTML created unexpectedly: catalog={bool(list_em)}, chat={chat_result}')
                return 'Benign HTML marker remained text in list and chat'
            finally:p.close()
        self.run(40,'Harmless HTML marker must be escaped in list and chat renderers',tc40)

    def _browser_cleanup(self):
        for obj in (self.context,self.browser,self.pw):
            try:
                if obj:
                    if obj is self.pw:obj.stop()
                    else:obj.close()
            except Exception:pass

    def test_concurrency(self):
        def tc34():
            cars_code,cars=self.req('GET','/catalog/catalog/cars')
            self.check(cars_code==200 and cars,'No Catalog data')
            car=cars[-1];a=self.require(self.auth_a,'A JWT');b=self.token_b()
            stock=self.car_snapshot(car['id'])
            self.check(stock>=2,'Need at least two test cars in stock to set one unit')
            code,_=self.req('POST','/catalog/inventory/reduce',{'car_id':car['id'],'quantity':stock-1},token=a)
            self.check(code==200 and self.car_snapshot(car['id'])==1,'Could not set CI-only stock to 1')
            def make(token):return self.req('POST','/orders/orders',{'items':[{'car_id':car['id'],'quantity':1}]},token=token)
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                fa=pool.submit(make,a);fb=pool.submit(make,b)
                x,y=fa.result(),fb.result()
            final=self.car_snapshot(car['id'])
            successes=sum(z[0]==201 for z in (x,y))
            self.check(successes==1 and final==0,f'Concurrency anomaly: responses {x[0]}/{y[0]}, succeeded={successes}, final stock={final}')
            return f'One successful order, stock 1->0; second rejected (HTTP {x[0]}/{y[0]})'
        self.run(34,'Two parallel orders for last CI-only unit must not oversell',tc34)

    def test_catalog_failure(self):
        def compose(*args):
            return subprocess.run(['docker','compose','-f',str(self.project/'docker-compose.yml'),*args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=35)
        def tc35():
            token=self.require(self.auth_a,'A JWT');car=self.require(self.car,'Catalog data')
            before=len(self.orders(token))
            stopped=False
            try:
                res=compose('stop','catalog');stopped=res.returncode==0
                if not stopped:raise NotReady('Cannot stop isolated Catalog service: '+res.stdout[-200:])
                code,data=self.req('POST','/orders/orders',{'items':[{'car_id':car['id'],'quantity':1}]},token=token)
                after=len(self.orders(token))
                self.check(code==503,f'Expected 503 dependency failure, got HTTP {code}')
                self.check(after==before,f'Order count {before}->{after} after Catalog outage')
                return f'Catalog stopped: HTTP {code}, order count {before}->{after}'
            finally:
                if stopped:
                    try:compose('start','catalog')
                    except Exception:pass
        self.run(35,'Catalog outage causes dependency failure without successful new order',tc35)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--base-url',default='http://127.0.0.1:8000')
    ap.add_argument('--output',default='qa-evidence')
    ap.add_argument('--project-dir',default='VinFast-SOA-Project-master')
    args=ap.parse_args()
    r=FullRunner(args.base_url,args.output,args.project_dir)
    try:
        r.suite()   # The original 16 CI API checks, unchanged
        r.extra()   # The remaining 24 cases
    finally:
        totals=r.write()
        path=Path(args.output)/'summary.json'
        v=json.loads(path.read_text(encoding='utf-8'))
        v['source']='GitHub Actions: Docker Compose API / Chromium UI / Socket.IO / SQLite (40 attempted case IDs)'
        v['scope_note']='Blocked means prerequisite/acceptance criterion missing; Pass is only for assertions actually performed.'
        path.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
        with open(Path(args.output)/'README_results.md','a',encoding='utf-8') as f:
            f.write('\n**Detailed coverage:** API + Chromium browser + SQLite DB + concurrent HTTP + isolated Socket.IO. Some test cases are Blocked when features/criteria are missing. Check notes and screenshots.\n')
        print('FINAL SUMMARY',totals,flush=True)
    raise SystemExit(1 if totals.get('Fail',0)>0 or totals.get('Blocked',0)>0 else 0)


if __name__=='__main__':main()
