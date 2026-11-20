#!/usr/bin/env python3
"""Integration-check prototype for an ISOLATED VinFast SOA GitHub runner.

No edits to the repository or the original DB. HTTP requests are made only to
local CI containers. Results are observed, not prefilled. Tests not covered by
this HTTP harness retain Not Run. Do not use against production.
"""
import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid
import xml.etree.ElementTree as ET

CASE_NAMES = [
    'Danh sách xe', 'Tìm theo tên', 'Tìm theo mô tả', 'Lọc khoảng giá',
    'Lọc dòng xe', 'Chi tiết xe', 'Tồn kho xe', 'Đăng ký', 'Đăng nhập',
    'Cập nhật hồ sơ', 'Đổi mật khẩu', 'Tạo đơn', 'Hết hàng',
    'Thanh toán', 'Theo dõi đơn', 'Xác nhận admin', 'Chat', 'Biểu đồ',
    'Tìm kiếm rỗng', 'Xe không tồn tại', 'Tìm không dấu', 'Từ khóa khoảng trắng',
    'Giá biên dưới', 'Giá biên trên', 'Thiếu trường đăng ký', 'Trùng email',
    'Đăng nhập sai', 'Không có token', 'JWT giả', 'Quantity = 0',
    'Quantity âm', 'Quantity quá tồn', 'Đơn nhiều mặt hàng',
    'Hai yêu cầu đồng thời', 'Trả lỗi Catalog', 'Thanh toán không sở hữu',
    'Thanh toán lặp', 'Admin giả', 'Chat trái phép', 'XSS mô tả xe',
]
assert len(CASE_NAMES) == 40
REDACTED = {'password', 'old_password', 'new_password', 'access_token', 'token', 'jwt', 'authorization', 'password_hash', 'secret', 'jwt_secret_key'}


def clean(value):
    if isinstance(value, dict):
        return {k: ('[REDACTED]' if k.lower() in REDACTED else clean(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(x) for x in value[:40]]
    if isinstance(value, str):
        return value[:500]
    return value


class CheckFailed(Exception):
    pass


class NotReady(Exception):
    pass


class Runner:
    def __init__(self, base, out):
        self.base = base.rstrip('/')
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.log = open(self.out / 'http_trace.jsonl', 'w', encoding='utf-8')
        self.rows = [dict(id=f'TC-{i:02}', name=name, status='Not Run', expected='', actual='', notes='', duration_ms='', evidence='') for i, name in enumerate(CASE_NAMES, 1)]
        self.car = None
        self.auth_a = None
        self.auth_b = None
        self.user_email = f'qa-{uuid.uuid4().hex[:16]}@example.test'
        self.other_email = f'qa-{uuid.uuid4().hex[:16]}@example.test'
        self.test_password = 'Temporary-CI-Only-Strong-2026!'  # not production
        self.order_id = None
        self.registered_a = False

    def req(self, method, route, data=None, token=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        encoded = None if data is None else json.dumps(data, ensure_ascii=False).encode('utf-8')
        request = urllib.request.Request(self.base + route, method=method, data=encoded, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                code, body = response.status, response.read(65536).decode('utf-8', 'replace')
        except urllib.error.HTTPError as err:
            code, body = err.code, err.read(65536).decode('utf-8', 'replace')
        except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
            raise NotReady('HTTP unavailable: ' + str(err)) from err
        try:
            parsed = json.loads(body)
        except ValueError:
            parsed = {'raw': body[:400]}
        record = dict(time=datetime.now(timezone.utc).isoformat(), method=method, route=route, status=code, request=clean(data), response=clean(parsed))
        self.log.write(json.dumps(record, ensure_ascii=False) + '\n')
        self.log.flush()
        return code, parsed

    @staticmethod
    def check(cond, msg):
        if not cond:
            raise CheckFailed(msg)

    def car_snapshot(self, car_id):
        status, obj = self.req('GET', f'/catalog/catalog/cars/{car_id}')
        self.check(status == 200 and isinstance(obj, dict), f'Cannot get car stock: HTTP {status}')
        self.check(isinstance(obj.get('stock_quantity'), int), 'Missing integer stock_quantity')
        return obj['stock_quantity']

    def run(self, idn, expected, fn):
        row = self.rows[idn - 1]
        row['expected'] = expected
        start = time.monotonic()
        try:
            actual = fn()
            row['status'] = 'Pass'
            row['actual'] = str(actual or 'Meets assertion')[:250]
        except CheckFailed as e:
            row['status'] = 'Fail'
            row['actual'] = str(e)[:350]
        except NotReady as e:
            row['status'] = 'Blocked'
            row['actual'] = str(e)[:350]
        except Exception as e:
            row['status'] = 'Blocked'
            row['actual'] = f'Test harness or prerequisite error ({type(e).__name__}): {str(e)}'[:350]
        row['duration_ms'] = round((time.monotonic() - start) * 1000)
        row['evidence'] = 'http_trace.jsonl'
        print(f"{row['id']}  {row['status']:<7}  {row['name']}: {row['actual']}", flush=True)

    def require(self, value, label):
        if value is None:
            raise NotReady(f'Prerequisite unavailable: {label}')
        return value

    def suite(self):
        def list_cars():
            status, cars = self.req('GET', '/catalog/catalog/cars')
            self.check(status == 200, f'Expected 200, got {status}')
            self.check(isinstance(cars, list) and bool(cars), 'Expected a non-empty array')
            self.check(all('id' in c and 'model_name' in c and 'base_price' in c for c in cars), 'Missing car fields')
            self.car = cars[0]
            return f'{len(cars)} cars, first ID {self.car["id"]}'
        self.run(1, 'GET 200 and a nonempty car list', list_cars)

        def nonexistent():
            status, _ = self.req('GET', '/catalog/catalog/cars/999999')
            self.check(status == 404, f'Expected 404, got {status}')
            return 'HTTP 404'
        self.run(20, 'Unknown car ID returns 404', nonexistent)

        def missing_registration():
            code, _ = self.req('POST', '/users/users/register', {'name': 'CI User', 'password': self.test_password})
            self.check(code == 400, f'Expected 400, got {code}')
            return 'HTTP 400'
        self.run(25, 'Missing email is rejected with HTTP 400', missing_registration)

        def signup():
            code, data = self.req('POST', '/users/users/register', {'name': 'CI User A', 'email': self.user_email, 'password': self.test_password})
            self.check(code == 201 and isinstance(data.get('user_id'), int), f'Expected 201/new user, got {code}: {clean(data)}')
            self.registered_a = True
            return 'Created synthetic CI account A'
        self.run(8, 'Register returns HTTP 201 and user_id', signup)

        def duplicate():
            self.require(self.registered_a or None, 'successful registration A')
            code, _ = self.req('POST', '/users/users/register', {'name': 'Dup', 'email': self.user_email, 'password': self.test_password})
            self.check(code == 409, f'Expected 409, got {code}')
            return 'HTTP 409'
        self.run(26, 'Duplicate email is rejected HTTP 409', duplicate)

        def invalid_login():
            self.require(self.registered_a or None, 'successful registration A')
            code, _ = self.req('POST', '/users/users/login', {'email': self.user_email, 'password': 'NotThePassword'})
            self.check(code == 401, f'Expected 401, got {code}')
            return 'HTTP 401'
        self.run(27, 'Wrong password is rejected HTTP 401', invalid_login)

        def login():
            code, obj = self.req('POST', '/users/users/login', {'email': self.user_email, 'password': self.test_password})
            self.check(code == 200 and isinstance(obj.get('access_token'), str), f'Expected 200/JWT, got {code}')
            self.auth_a = obj['access_token']
            return 'HTTP 200 and JWT returned (JWT not saved)'
        self.run(9, 'Correct credentials return a JWT', login)

        def no_token():
            code, _ = self.req('GET', '/orders/orders')
            self.check(code == 401, f'Expected 401, got {code}')
            return 'HTTP 401'
        self.run(28, 'Orders endpoint rejects missing JWT', no_token)

        def fake_token():
            code, _ = self.req('GET', '/orders/orders', token='definitely.invalid.signature')
            self.check(code == 401, f'Expected 401, got {code}')
            return 'HTTP 401'
        self.run(29, 'Orders endpoint rejects fake JWT', fake_token)

        def catalog_reduce(quantity, idn):
            car = self.require(self.car, 'catalog list')
            token = self.require(self.auth_a, 'login A')
            before = self.car_snapshot(car['id'])
            code, _ = self.req('POST', '/catalog/inventory/reduce', {'car_id': car['id'], 'quantity': quantity}, token=token)
            after = self.car_snapshot(car['id'])
            self.check(code == 400, f'Expected HTTP 400 for quantity={quantity}, got {code}')
            self.check(before == after, f'Stock changed: {before} -> {after}')
            return f'HTTP {code}, stock unchanged {before}'
        self.run(30, 'quantity=0 must be rejected and stock unchanged', lambda: catalog_reduce(0, 30))
        self.run(31, 'quantity=-1 must be rejected and stock unchanged', lambda: catalog_reduce(-1, 31))

        def too_many_inventory():
            car = self.require(self.car, 'catalog list')
            token = self.require(self.auth_a, 'login A')
            before = self.car_snapshot(car['id'])
            return catalog_reduce(before+1, 32)
        self.run(32, 'quantity above stock is rejected and stock unchanged', too_many_inventory)

        def too_many_order():
            car = self.require(self.car, 'catalog list')
            token = self.require(self.auth_a, 'login A')
            before = self.car_snapshot(car['id'])
            _, orders_before = self.req('GET', '/orders/orders', token=token)
            code, _ = self.req('POST', '/orders/orders', {'items':[{'car_id': car['id'], 'quantity': before+1}]}, token=token)
            after = self.car_snapshot(car['id'])
            _, orders_after = self.req('GET', '/orders/orders', token=token)
            self.check(code == 400, f'Expected HTTP 400, got {code}')
            self.check(after == before, f'Stock changed: {before} -> {after}')
            self.check(len(orders_after) == len(orders_before), 'Rejected order left a new order record')
            return f'HTTP 400, stock unchanged ({after}), no new order'
        self.run(13, 'Order quantity above stock rejected without stock change', too_many_order)

        def create_order():
            car = self.require(self.car, 'catalog list')
            token = self.require(self.auth_a, 'login A')
            before = self.car_snapshot(car['id'])
            self.check(before >= 1, 'No test stock remaining')
            code, obj = self.req('POST', '/orders/orders', {'items':[{'car_id': car['id'], 'quantity':1}]}, token=token)
            after = self.car_snapshot(car['id'])
            self.check(code == 201, f'Expected 201, got {code}')
            self.check(obj.get('total_amount') == car['base_price'], 'Total amount differs from unit price')
            self.check(obj.get('status') == 'Pending' and len(obj.get('items', [])) == 1, 'Expected Pending with one item')
            self.check(after == before-1, f'Expected stock {before-1}, got {after}')
            self.order_id = obj.get('id')
            return f'Order ID={self.order_id}, 1 item, stock {before}->{after}'
        self.run(12, 'One available car creates Pending order and reduces stock by 1', create_order)

        def multi_failure():
            car = self.require(self.car, 'catalog list')
            token = self.require(self.auth_a, 'login A')
            cars_code, cars = self.req('GET', '/catalog/catalog/cars')
            self.check(cars_code == 200 and len(cars) > 1, 'Need two models')
            second = next(c for c in cars if c['id'] != car['id'])
            before1, before2 = self.car_snapshot(car['id']), self.car_snapshot(second['id'])
            self.check(before1 > 0, 'No stock for first model')
            _, orders_before = self.req('GET', '/orders/orders', token=token)
            code, obj = self.req('POST', '/orders/orders', {'items':[
                {'car_id': car['id'], 'quantity':1},
                {'car_id':second['id'],'quantity':before2+1},
            ]}, token=token)
            after1, after2 = self.car_snapshot(car['id']), self.car_snapshot(second['id'])
            _, orders_after = self.req('GET', '/orders/orders', token=token)
            self.check(code >= 400, f'Expected rejected order, got HTTP {code}')
            self.check(after1 == before1 and after2 == before2,
                       f'Rollback missing: A {before1}->{after1}; B {before2}->{after2}; order HTTP {code}')
            self.check(len(orders_after) == len(orders_before), 'Rejected order left a new order record')
            return 'Rejected both items, both inventories unchanged and no new order'
        self.run(33, 'Failed 2-item order must preserve both inventories', multi_failure)

        def idor_payment():
            car = self.require(self.car, 'catalog list')
            a = self.require(self.auth_a, 'login A')
            if not self.order_id:
                raise NotReady('Need an order created by user A')
            code, obj = self.req('POST', '/users/users/register', {'name':'CI User B', 'email': self.other_email, 'password':self.test_password})
            self.check(code == 201, f'Cannot register B: HTTP {code}')
            code, data = self.req('POST', '/users/users/login', {'email':self.other_email,'password':self.test_password})
            self.check(code == 200 and 'access_token' in data, 'Cannot login as B')
            b = data['access_token']
            code, orderlist = self.req('GET', '/orders/orders', token=a)
            self.check(code == 200 and isinstance(orderlist,list), 'Cannot check order status before')
            initial = next((x['status'] for x in orderlist if x.get('id')==self.order_id), None)
            self.check(initial == 'Pending', f'Order is not Pending: {initial}')
            pay_code, _ = self.req('PUT', f'/orders/orders/{self.order_id}/pay', {'method':'demo'}, token=b)
            code, orderlist = self.req('GET', '/orders/orders', token=a)
            after = next((x['status'] for x in orderlist if x.get('id')==self.order_id), None)
            self.check(pay_code in (403,404), f'Expected 403/404 for another user, got HTTP {pay_code}')
            self.check(after == initial, f'Order status changed {initial}->{after} after foreign-user payment')
            return f'Pay status HTTP {pay_code}; order stayed {after}'
        self.run(36, 'User B cannot pay or modify User A order', idor_payment)

    def write(self):
        self.log.close()
        with open(self.out / 'test_results.csv', 'w', newline='', encoding='utf-8-sig') as f:
            fieldnames = ['id','name','status','expected','actual','notes','duration_ms','evidence']
            w=csv.DictWriter(f,fieldnames=fieldnames)
            w.writeheader()
            w.writerows(self.rows)
        totals = {k: sum(row['status']==k for row in self.rows) for k in ('Pass','Fail','Blocked','Not Run')}
        payload = dict(source='GitHub Actions container integration tests (not browser E2E)', repo=os.getenv('GITHUB_REPOSITORY'), sha=os.getenv('GITHUB_SHA'), run_id=os.getenv('GITHUB_RUN_ID'), run_at=datetime.now(timezone.utc).isoformat(), total=40, **totals, results=self.rows)
        (self.out / 'summary.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
        testsuite=ET.Element('testsuite',name='VinFast API integration (selected cases)',tests=str(40-totals['Not Run']),failures=str(totals['Fail']),skipped=str(totals['Blocked']))
        for row in self.rows:
            if row['status']=='Not Run':continue
            elem=ET.SubElement(testsuite,'testcase',classname='VinFast.API',name=row['id']+' '+row['name'],time=str((row['duration_ms'] or 0)/1000))
            if row['status']=='Fail':ET.SubElement(elem,'failure',message=row['actual']).text=row['expected']
            if row['status']=='Blocked':ET.SubElement(elem,'skipped',message=row['actual'])
        ET.ElementTree(testsuite).write(self.out/'junit.xml',encoding='utf-8',xml_declaration=True)
        summary = f"# VinFast SQA integration run\n\nCommit: `{os.getenv('GITHUB_SHA','local')}`\n\n" + '\n'.join(f'- {k}: **{v}**' for k,v in totals.items()) + '\n\nSelected checks only: browser/WebSocket/concurrency cases remain Not Run unless separately tested.\n'
        (self.out/'README_results.md').write_text(summary,encoding='utf-8')
        ghsummary=os.getenv('GITHUB_STEP_SUMMARY')
        if ghsummary:
            with open(ghsummary,'a',encoding='utf-8') as f:f.write(summary)
        return totals


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base-url',default='http://127.0.0.1:8000')
    parser.add_argument('--output',default='qa-evidence')
    args=parser.parse_args()
    runner=Runner(args.base_url,args.output)
    runner.suite()
    totals=runner.write()
    # A Failed test is an observed product deviation, not a fabricated success.
    # Exit 1 makes the workflow visibly fail while `if: always()` still uploads evidence.
    raise SystemExit(1 if totals['Fail'] or totals['Blocked'] else 0)


if __name__=='__main__':
    main()
