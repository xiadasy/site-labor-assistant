#!/usr/bin/env python3
"""把管理人员名册合并到本单位花名册"""
import os,json,base64,openpyxl
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT='/var/minis/workspace/site-labor-assistant'
COMPANY=f'{ROOT}/company-encrypted-data.json'
ROSTER='/var/minis/attachments/uploads/shared-5A8B2B42_管理人员名册（安装九分3.26）.xlsx'

def decrypt(path, password):
    e=json.load(open(path))
    salt=base64.b64decode(e['salt']); iv=base64.b64decode(e['iv']); ct=base64.b64decode(e['ciphertext'])
    kdf=PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=int(e.get('iterations',210000)))
    key=kdf.derive(password.encode())
    plain=AESGCM(key).decrypt(iv, ct, None)
    return json.loads(plain.decode())

def encrypt(data, password):
    salt=os.urandom(16); iv=os.urandom(12)
    kdf=PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=210000)
    key=kdf.derive(password.encode())
    ct=AESGCM(key).encrypt(iv, json.dumps(data,ensure_ascii=False,separators=(',',':')).encode(), None)
    return {'version':1,'algorithm':'AES-GCM-256','kdf':'PBKDF2-SHA256','iterations':210000,
            'salt':base64.b64encode(salt).decode(),'iv':base64.b64encode(iv).decode(),
            'ciphertext':base64.b64encode(ct).decode()}

pw=os.environ['COMPANY_QUERY_PASSWORD']
data=decrypt(COMPANY, pw)
print(f'本单位人员: {len(data["people"])}')

# read management roster
wb=openpyxl.load_workbook(ROSTER, data_only=True)
ws=wb.active
mgmt=[]
for row in ws.iter_rows(min_row=3, max_row=ws.max_row, values_only=True):
    if not row[2]: continue
    mgmt.append({
        'name':str(row[2] or '').strip(),
        'idCard':str(row[4] or '').strip().upper(),
        'phone':str(row[5] or '').strip(),
        'position':str(row[1] or '').strip(),
        'plate':str(row[9] or '').strip(),
        'mgmtUnit':str(row[3] or '').strip(),
    })
print(f'管理人员: {len(mgmt)}')

# match and merge
matched=0; new=0
for m in mgmt:
    hit=None
    for p in data['people']:
        if m['idCard'] and (p.get('idCard','').upper()==m['idCard']):
            hit=p; break
        if m['name'] and (p.get('name','')==m['name']):
            hit=p; break
    if hit:
        matched+=1
        # fill missing fields
        if not hit.get('idCard') and m['idCard']: hit['idCard']=m['idCard']
        if not hit.get('phone') and m['phone']: hit['phone']=m['phone']
        if not hit.get('position') and m['position']: hit['position']=m['position']
        if not hit.get('department') and m['position']: hit['department']=m['position']
        # always update position from mgmt roster (more authoritative)
        if m['position']:
            hit['mgmtPosition']=m['position']
            if not hit.get('position'): hit['position']=m['position']
        if m['plate']: hit['plate']=m['plate']
        if m['mgmtUnit']: hit['mgmtUnit']=m['mgmtUnit']
    else:
        # add as new person
        new+=1
        data['people'].append({
            'id':m['idCard'] or m['name'],
            'name':m['name'],
            'department':m['position'] or '管理人员',
            'position':m['position'] or '',
            'phone':m['phone'],
            'idCard':m['idCard'],
            'sex':'',
            'mgmtPosition':m['position'],
            'mgmtUnit':m['mgmtUnit'],
            'plate':m['plate'],
            'employmentStatus':'在职',
            'remark':'管理人员名册（3.26）导入',
            'certificates':[],
            'employmentHistory':[]
        })
        print(f'  新增管理人员: {m["name"]} ({m["position"]})')

print(f'匹配: {matched}, 新增: {new}, 总计: {len(data["people"])}')
data['project']['updatedAt']='2026-07-20 10:30:00'
data['project']['mgmtRosterImported']='2026-07-20'

# encrypt and save
enc=encrypt(data, pw)
tmp=COMPANY+'.new'; json.dump(enc, open(tmp,'w'), ensure_ascii=False); os.replace(tmp, COMPANY)
print('已加密保存 company-encrypted-data.json')
