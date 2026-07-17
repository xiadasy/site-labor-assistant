#!/usr/bin/env python3
import os,json,time,base64,requests,concurrent.futures,pickle,sys
from urllib.parse import unquote
from datetime import datetime
ROOT='/var/minis/workspace/site-labor-assistant'
BASE='https://ics.scg.cn'
PID='2622d8fe-8250-4742-bb59-8f2ed935bc9a'
NAME='承德斐讯大数据（一期）项目工程总承包'
OUT=ROOT+'/chengde-project-data.json'
CKPT=ROOT+'/.private-chengde-ckpt.pkl'
T=unquote(os.environ.get('COOKIE_ICS_SESSION_BRIDGE',''))
if not T: raise SystemExit('missing COOKIE_ICS_SESSION_BRIDGE')
H={'Authorization':T if T.startswith('Bearer ') else 'Bearer '+T,'Accept':'application/json'}
def call(path,p,retry=3):
    err=None
    for n in range(retry):
        try:
            r=requests.get(BASE+path,params=p,headers=H,timeout=60)
            if r.status_code!=200: raise RuntimeError('HTTP '+str(r.status_code))
            x=r.json()
            if x.get('code')!='00000': raise RuntimeError(str(x.get('code'))+' '+str(x.get('msg')))
            return x['data']
        except Exception as e:
            err=e; time.sleep(1+n*2)
    raise RuntimeError(path+': '+str(err))
def pages(path,p,size=5000):
    q={**p,'pageIndex':1,'pageSize':size,'total':0}; first=call(path,q)
    total=first.get('total'); rows=first.get('rows',[])
    if not isinstance(total,int): raise RuntimeError(path+' invalid total')
    for i in range(2,(total+size-1)//size+1): rows+=call(path,{**q,'pageIndex':i}).get('rows',[])
    if len(rows)!=total: raise RuntimeError(f'{path} mismatch {len(rows)}/{total}')
    return rows
def date(x):
    if not x or str(x).startswith('0001') or str(x).startswith('9999'): return ''
    return str(x)[:10]
def save(d):
    with open(CKPT,'wb') as f: pickle.dump(d,f)
def detail(r):
    w=r['workerId']; p=r['id']
    d=call('/api/v1.0/projectWorker/getProjectWorkerDetail',{'id':p})
    c=pages('/api/v1.0/workerContract/queryProjectWorkerContractPaging',{'ProjectId':PID,'WorkerId':w},100)
    ce=pages('/api/v1.0/workerCertificate/extpaging',{'WorkerId':w},100)
    s=pages('/api/v1.0/projectWorkerEntryExit/queryProjectWorkerEntryExitPaging',{'WorkerId':w},100)
    return p,d,c,ce,s
print('拉取承德项目主人员...'); rows=pages('/api/v1.0/projectWorker/queryProjectWorkerPaging',{'projectId':PID},5000)
if len(rows)!=994 or any(x.get('projectId')!=PID for x in rows): raise SystemExit('主人员校验失败 '+str(len(rows)))
ck={'rows':rows,'results':{}}
if os.path.exists(CKPT):
    try:
        old=pickle.load(open(CKPT,'rb'))
        if len(old.get('rows',[]))==len(rows): ck=old; ck['rows']=rows
    except: pass
results=ck.setdefault('results',{})
todo=[r for r in rows if r['id'] not in results]
print(f'承德项目 {len(rows)}人，已缓存{len(results)}，待抓{len(todo)}')
fail=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    fs={ex.submit(detail,r):r['id'] for r in todo}
    for i,f in enumerate(concurrent.futures.as_completed(fs),1):
        try:
            k,d,c,ce,s=f.result(); results[k]=(d,c,ce,s)
        except Exception as e: fail.append((fs[f],str(e)))
        if i%50==0: save(ck); print('进度',len(results),'/',len(rows),'失败',len(fail),flush=True)
save(ck)
if fail or len(results)!=len(rows): raise SystemExit('明细失败 '+str(fail[:3]))
people=[]
for r in rows:
    d,c,ce,s=results[r['id']]
    bd=str(d.get('birthday') or '')
    age=datetime.now().year-int(bd[:4]) if bd[:4].isdigit() else ''
    people.append({
      'projectWorkerId':r['id'],'workerId':r['workerId'],'name':d.get('workerName') or r.get('workerName') or '',
      'idCard':d.get('idNumber') or r.get('idNumber') or '','phone':d.get('phone') or '',
      'sex':'男' if d.get('gender')==1 else ('女' if d.get('gender')==2 else ''),'age':age,'birthday':date(d.get('birthday')),
      'nation':d.get('nationName') or '','address':d.get('address') or '','grantOrg':d.get('grantOrg') or '',
      'unit':d.get('corpName') or r.get('corpName') or '','team':d.get('teamName') or r.get('teamName') or '',
      'trade':d.get('workTypeName') or r.get('workTypeName') or '','role':'作业人员' if d.get('role')==1 else str(d.get('role') or ''),
      'status':'已进场' if d.get('status')==1 else '已退场','entryDate':date(d.get('entryDate')),'exitDate':date(d.get('exitDate')),
      'bankName':d.get('payRollBankName') or '','bankCard':d.get('payRollBankCardNumber') or '','accessCard':d.get('cardNumber') or '',
      'contracts':[{'type':x.get('periodType') or '','startDate':date(x.get('startDate')),'endDate':date(x.get('endDate')),'teamName':x.get('teamName') or ''} for x in c],
      'certificates':[{'name':x.get('certificateName') or '','typeName':x.get('typeName') or '','code':x.get('code') or '','startDate':date(x.get('startDate')),'endDate':date(x.get('endDate'))} for x in ce],
      'services':[{'projectName':x.get('projectName') or '','corpName':x.get('corpName') or '','teamName':x.get('teamName') or '','trade':x.get('workerTypeName') or '','entryDate':date(x.get('entryDate')),'exitDate':date(x.get('exitDate'))} for x in s]
    })
summary={'records':len(people),'active':sum(p['status']=='已进场' for p in people),'exited':sum(p['status']=='已退场' for p in people),'units':len(set(p['unit'] for p in people)),'teams':len(set(p['team'] for p in people)),'withCertificate':sum(bool(p['certificates']) for p in people),'updatedAt':datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
raw=json.dumps({'project':{'id':PID,'name':NAME,'status':'已结束','summary':summary},'people':people},ensure_ascii=False,separators=(',',':')).encode()
json.dump({'payload':base64.b64encode(raw).decode()},open(OUT,'w'),ensure_ascii=False)
print('完成',summary)
