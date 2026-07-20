#!/usr/bin/env python3
import os,json,base64,pickle
from datetime import datetime
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT='/var/minis/workspace/site-labor-assistant'
OUT=f'{ROOT}/project-encrypted-data.json'
CKPT=f'{ROOT}/.private-ckpt.pkl'
MANAGED=['黄卫华_2414班组','上海东站九分弱电班组','(有登高车操作证)上海东站九分弱电班组','(有登高车操作证)上海东站九分弱电黄卫华班组']

def date(x):
    if not x or str(x).startswith('0001') or str(x).startswith('9999'): return ''
    return str(x)[:10]

def decrypt(path, password):
    e=json.load(open(path))
    salt=base64.b64decode(e['salt']); iv=base64.b64decode(e['iv']); ct=base64.b64decode(e['ciphertext'])
    kdf=PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=int(e.get('iterations',210000)))
    key=kdf.derive(password.encode())
    plain=AESGCM(key).decrypt(iv, ct, None)
    return json.loads(plain.decode())

# 1) rebuild services with projectName from checkpoint when available
old=json.loads(base64.b64decode(json.load(open(OUT))['payload']))
fixed=0
if os.path.exists(CKPT):
    ck=pickle.load(open(CKPT,'rb'))
    results=ck['results']
    for p in old['people']:
        pwid=p.get('projectWorkerId')
        if not pwid or pwid not in results: continue
        d,c,ce,s=results[pwid]
        p['services']=[{
            'projectName':x.get('projectName') or '',
            'corpName':x.get('corpName') or '',
            'teamName':x.get('teamName') or '',
            'trade':x.get('workerTypeName') or '',
            'entryDate':date(x.get('entryDate')),
            'exitDate':date(x.get('exitDate'))
        } for x in s]
        fixed+=1
    old['project']['updatedAt']=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    raw=json.dumps(old,ensure_ascii=False,separators=(',',':')).encode()
    tmp=OUT+'.new'; json.dump({'payload':base64.b64encode(raw).decode()},open(tmp,'w'),ensure_ascii=False); os.replace(tmp,OUT)
print('services rebuilt for',fixed,'people')

# 2) decrypt labor + company for search packages
labor=decrypt(f'{ROOT}/encrypted-data.json', os.environ['LABOR_QUERY_PASSWORD'])
company=decrypt(f'{ROOT}/company-encrypted-data.json', os.environ['COMPANY_QUERY_PASSWORD'])

labor_people=[]
for u in labor.get('units',[]):
    for p in u.get('people',[]):
        labor_people.append({
            'id':p.get('idCard') or f"{u.get('id')}|{p.get('name')}",
            'n':p.get('name') or '',
            'idc':p.get('idCard') or '',
            'ph':p.get('phone') or '',
            'u':u.get('name') or '',
            'uid':u.get('id') or '',
            'w':p.get('trade') or '',
            'x':p.get('sex') or '',
            's':p.get('status') or '',
            'e':p.get('entryDate') or '',
            'ex':p.get('exitDate') or '',
            'addr':p.get('address') or '',
            'bank':p.get('bank') or '',
            'bc':p.get('bankCard') or '',
            'rate':p.get('dailyRate') or '',
            'med':p.get('medicalDate') or '',
            'pay':p.get('payrollHistory') or [],
            'att':p.get('attendanceHistory') or [],
            'cert':p.get('certificates') or [],
            'hist':p.get('statusHistory') or [],
            'avatar':p.get('avatar') or p.get('avatarData') or ''
        })

company_people=[]
for p in company.get('people',[]):
    company_people.append({
        'id':p.get('id') or p.get('name'),
        'n':p.get('name') or '',
        'dep':p.get('department') or '',
        'pos':p.get('position') or '',
        'ph':p.get('phone') or '',
        'x':p.get('sex') or '',
        'age':p.get('age') or '',
        'edu':p.get('education') or p.get('highestEducation') or '',
        'school':p.get('school') or '',
        'major':p.get('major') or '',
        'native':p.get('nativePlace') or '',
        'status':p.get('employmentStatus') or '',
        'years':p.get('yearsInCompany') or '',
        'exp':p.get('experienceYears') or '',
        'certs':p.get('certificates') or [],
        'remark':p.get('remark') or '',
        'retire':p.get('retirementCategory') or '',
        'hist':p.get('employmentHistory') or []
    })

# 3) project search indexes
people=[]
for p in old['people']:
    people.append({
        'id':p.get('projectWorkerId') or p.get('idCard') or '',
        'n':p.get('name') or '',
        'idc':p.get('idCard') or '',
        'ph':p.get('phone') or '',
        'u':p.get('unit') or '',
        't':p.get('team') or '',
        'w':p.get('trade') or '',
        's':p.get('status') or '',
        'a':p.get('age') or '',
        'x':p.get('sex') or '',
        'e':p.get('entryDate') or '',
        'ex':p.get('exitDate') or '',
        'b':p.get('bankName') or '',
        'bc':p.get('bankCard') or '',
        'cs':p.get('contractStatus') or '',
        'qs':p.get('qualificationStatus') or '',
        'ac':p.get('accessCard') or '',
        'addr':p.get('address') or '',
        'nation':p.get('nation') or '',
        'bd':p.get('birthday') or '',
        'grant':p.get('grantOrg') or '',
        'role':p.get('role') or '',
        'managed': 1 if p.get('team') in MANAGED else 0,
        'c':[{'type':x.get('type') or '','start':x.get('startDate') or '','end':x.get('endDate') or '','team':x.get('teamName') or ''} for x in (p.get('contracts') or [])],
        'q':[{'name':x.get('name') or '','code':x.get('code') or '','type':x.get('typeName') or '','start':x.get('startDate') or '','end':x.get('endDate') or ''} for x in (p.get('certificates') or [])],
        'svc':[{'project':x.get('projectName') or '','corp':x.get('corpName') or '','team':x.get('teamName') or '','trade':x.get('trade') or '','entry':x.get('entryDate') or '','exit':x.get('exitDate') or ''} for x in (p.get('services') or [])],
        'da':[{'time':x.get('time') or '','h':x.get('laborHour') or 0,'in':x.get('inTime') or '','out':x.get('outTime') or ''} for x in (p.get('dailyAttendance') or [])[-8:]],
        'ma':[{'m':x.get('attendanceDate') or '','h':x.get('laborHour') or 0} for x in (p.get('monthlyAttendance') or [])]
    })
summary={
 'records':len(people),
 'active':sum(1 for p in people if p['s']=='已进场'),
 'managed':sum(1 for p in people if p['managed']),
 'managedActive':sum(1 for p in people if p['managed'] and p['s']=='已进场'),
 'withCert':sum(1 for p in people if p['q']),
 'units':len(set(p['u'] for p in people if p['u'])),
 'labor':len(labor_people),
 'company':len(company_people),
 'updatedAt':old['project'].get('updatedAt')
}
lite=[{'id':p['id'],'n':p['n'],'idc':p['idc'],'ph':p['ph'],'u':p['u'],'t':p['t'],'w':p['w'],'s':p['s'],'a':p['a'],'x':p['x'],'e':p['e'],'managed':p['managed']} for p in people]
open(f'{ROOT}/search-lite.json','w').write(json.dumps({'version':2,'summary':summary,'people':lite},ensure_ascii=False,separators=(',',':')))
open(f'{ROOT}/search-index.json','w').write(json.dumps({'version':2,'summary':summary,'people':people},ensure_ascii=False,separators=(',',':')))
open(f'{ROOT}/project-widget-summary.json','w').write(json.dumps(summary,ensure_ascii=False,separators=(',',':')))

# labor/company search packages stay encrypted by reusing existing files; export plaintext private packages for local password unlock via existing encrypted files
# For search page convenience we export public lite names only? No - keep decrypt from existing encrypted-data.json / company-encrypted-data.json in browser.
# Also export managed overlay map source as part of labor package already.

open(f'{ROOT}/search-meta.json','w').write(json.dumps({
  'version':2,
  'tabs':[
    {'id':'project','name':'项目总管','count':summary['records']},
    {'id':'managed','name':'我管班组','count':summary['managed']},
    {'id':'labor','name':'劳务助手','count':summary['labor'],'needPassword':'labor'},
    {'id':'company','name':'本单位','count':summary['company'],'needPassword':'company'}
  ],
  'summary':summary
},ensure_ascii=False,separators=(',',':')))

print('search-lite',round(os.path.getsize(f'{ROOT}/search-lite.json')/1024,1),'KB')
print('search-index',round(os.path.getsize(f'{ROOT}/search-index.json')/1024,1),'KB')
print('labor people',len(labor_people),'company people',len(company_people))
print(summary)
# verify projectName present
has=sum(1 for p in people if any(x.get('project') for x in p['svc']))
print('people with projectName in services',has)
