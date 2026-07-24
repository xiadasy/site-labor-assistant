#!/usr/bin/env python3
"""
东方枢纽项目人员总管 — 增量同步脚本
用法：
  . /var/minis/offloads/env_cookies_scg_cn_XXXX.sh && python3 sync_incremental.py

功能：
  1. 拉主接口全量人员，逐人比对 modifiedOn/status/entryDate/exitDate
  2. 只对新增或变化的人拉4个明细接口（详情/合同/证书/服务进退场）
  3. 拉日考勤（当月1日至今）和月度考勤（当前月）全量分页
  4. 归档到每人，合并写入 project-encrypted-data.json
  5. 校验通过后推送 GitHub
  6. 接口401/code≠00000/total不一致 → 终止，不覆盖旧数据
"""
import os,json,time,base64,requests,concurrent.futures,pickle,sys
from urllib.parse import unquote
from datetime import datetime,timezone,timedelta

# ── 配置 ──
ROOT='/var/minis/workspace/site-labor-assistant'
OUT=f'{ROOT}/project-encrypted-data.json'
CKPT=f'{ROOT}/.private-ckpt.pkl'
LOG=f'{ROOT}/.private-sync.log'
BASE='https://ics.scg.cn'
PID='bd89507c-490e-4395-b2d8-3459959a49a8'
NAME='东方枢纽上海东站站场区地下工程机电安装及装饰装修工程1标段'
MANAGED=['黄卫华_2414班组','上海东站九分弱电班组','(有登高车操作证)上海东站九分弱电班组','(有登高车操作证)上海东站九分弱电黄卫华班组']
WORKERS=3
RETRY=3
TIMEOUT=60

# ── 认证 ──
T=unquote(os.environ.get('COOKIE_ICS_SESSION_BRIDGE',''))
if not T: print('❌ 缺少 COOKIE_ICS_SESSION_BRIDGE，请先在浏览器登录智慧工地并桥接会话'); sys.exit(1)
H={'Authorization':T if T.startswith('Bearer ') else 'Bearer '+T,'Accept':'application/json'}

def log(msg):
    line=f'[{datetime.now():%H:%M:%S}] {msg}'
    print(line,flush=True)
    with open(LOG,'a') as f: f.write(line+'\n')

def call(path,p):
    err=None
    for n in range(RETRY):
        try:
            r=requests.get(BASE+path,params=p,headers=H,timeout=TIMEOUT)
            if r.status_code==401: raise RuntimeError('401 未授权')
            if r.status_code!=200: raise RuntimeError(f'HTTP {r.status_code}')
            x=r.json()
            if x.get('code')!='00000': raise RuntimeError(f'{x.get("code")} {x.get("msg")}')
            return x['data']
        except Exception as e:
            err=e
            if '401' in str(e): raise  # 401 直接终止
            time.sleep(1+n*2)
    raise RuntimeError(f'{path}: {err}')

def pages(path,p,size=5000):
    p={**p,'pageIndex':1,'pageSize':size,'total':0}
    first=call(path,p)
    total=first.get('total'); rows=first.get('rows',[])
    if not isinstance(total,int) or total<0: raise RuntimeError(f'{path} total invalid: {total}')
    for i in range(2,(total+size-1)//size+1):
        rows+=call(path,{**p,'pageIndex':i}).get('rows',[])
    if len(rows)!=total: raise RuntimeError(f'{path} total mismatch: {total}/{len(rows)}')
    return rows

def date(x):
    if not x or str(x).startswith('0001') or str(x).startswith('9999'): return ''
    return str(x)[:10]

def load_ckpt():
    if os.path.exists(CKPT):
        with open(CKPT,'rb') as f: return pickle.load(f)
    return {}

def save_ckpt(d):
    with open(CKPT,'wb') as f: pickle.dump(d,f)

# ── 增量判断 ──
def needs_sync(row, old_result):
    """判断是否需要重新拉明细：新增/modifiedOn变/status变/entryDate变/exitDate变"""
    if not old_result: return True  # 新人
    old_detail=old_result[0]  # getProjectWorkerDetail 返回
    if row.get('modifiedOn')!=old_detail.get('modifiedOn'): return True
    if row.get('status')!=old_detail.get('status'): return True
    if date(row.get('entryDate'))!=date(old_detail.get('entryDate')): return True
    if date(row.get('exitDate'))!=date(old_detail.get('exitDate')): return True
    return False

# ── 单人4接口 ──
def fetch_detail(row):
    w=row['workerId']; p=row['id']
    d=call('/api/v1.0/projectWorker/getProjectWorkerDetail',{'id':p})
    c=pages('/api/v1.0/workerContract/queryProjectWorkerContractPaging',{'ProjectId':PID,'WorkerId':w},100)
    ce=pages('/api/v1.0/workerCertificate/extpaging',{'WorkerId':w},100)
    s=pages('/api/v1.0/projectWorkerEntryExit/queryProjectWorkerEntryExitPaging',{'WorkerId':w},100)
    return p,d,c,ce,s

# ── 格式化 ──
def fmt_contracts(c):
    return [{'type':x.get('periodType') or '','startDate':date(x.get('startDate')),'endDate':date(x.get('endDate')),'teamName':x.get('teamName') or ''} for x in c]
def fmt_certs(ce):
    return [{'name':x.get('certificateName') or '','className':x.get('className') or '','typeName':x.get('typeName') or '','code':x.get('code') or '','startDate':date(x.get('startDate')),'endDate':date(x.get('endDate'))} for x in ce]
def fmt_services(s):
    return [{'projectName':x.get('projectName') or '','corpName':x.get('corpName') or '','teamName':x.get('teamName') or '','trade':x.get('workerTypeName') or '','entryDate':date(x.get('entryDate')),'exitDate':date(x.get('exitDate'))} for x in s]
def fmt_daily(records):
    return [{'time':x.get('time') or '','laborHour':x.get('laborHour') or 0,'inTime':x.get('inTime') or '','outTime':x.get('outTime') or '','status':x.get('status') or ''} for x in records]
def fmt_monthly(records):
    return [{'attendanceDate':x.get('attendanceDate') or '','laborHour':x.get('workerLaborHour') or 0,'totalLaborHour':x.get('totalWorkerLaborHour') or 0} for x in records]

def build_person(r,d,c,ce,s,old_map,da_list,mo_list):
    bd=str(d.get('birthday') or '')
    old=old_map.get(d.get('idNumber') or r.get('idNumber'),{})
    age=datetime.now().year-int(bd[:4]) if bd[:4].isdigit() and int(bd[:4])>1900 else old.get('age','')
    return {
        'projectWorkerId':r['id'],'workerId':r['workerId'],
        'name':d.get('workerName') or r.get('workerName'),
        'idCard':d.get('idNumber') or r.get('idNumber'),
        'age':age,'sex':'男' if d.get('gender')==1 else ('女' if d.get('gender')==2 else ''),
        'phone':d.get('phone') or '','address':d.get('address') or '','grantOrg':d.get('grantOrg') or '',
        'nation':d.get('nationName') or '','birthday':date(d.get('birthday')),
        'bankName':d.get('payRollBankName') or '','bankBranch':d.get('payRollBrunchName') or '',
        'bankCard':d.get('payRollBankCardNumber') or '','cardNumber':d.get('cardNumber') or '',
        'hasContract':bool(c),'hasInsurance':bool(d.get('hasBuyInsurance')),'hasQualification':bool(ce),
        'unit':d.get('corpName') or r.get('corpName') or '未录入',
        'team':d.get('teamName') or r.get('teamName') or '',
        'role':'作业人员' if d.get('role')==1 else str(d.get('role') or ''),
        'trade':d.get('workTypeName') or r.get('workTypeName') or '',
        'entryDate':date(d.get('entryDate')),'exitDate':date(d.get('exitDate')),
        'healthCode':str(d.get('healthCode') or '未知'),
        'status':'已进场' if d.get('status')==1 else '已退场',
        'access':d.get('workerOperationMsg') or '接口尚未同步',
        'dispatchStatus':str(d.get('workerOperationStatus') or ''),
        'medical':old.get('medical'),'sourceModifiedAt':str(d.get('modifiedOn') or ''),
        'serviceCreatedAt':str(d.get('createdOn') or ''),'entryDays':d.get('entryDays') or 0,
        'contractStatus':'已登记' if c else '无记录',
        'qualificationStatus':'已登记' if ce else '无记录',
        'accessStatus':d.get('workerOperationMsg') or '接口尚未同步',
        'accessCard':d.get('cardNumber') or '',
        'contracts':fmt_contracts(c),'certificates':fmt_certs(ce),'services':fmt_services(s),
        'dailyAttendance':da_list,'monthlyAttendance':mo_list,
        'detailSyncStatus':'已同步','attendanceMode':'synced'
    }

def main():
    log('═══ 增量同步开始 ═══')
    ckpt=load_ckpt()

    # ── Step 1: 拉主接口 ──
    log('拉主接口人员列表...')
    rows=pages('/api/v1.0/projectWorker/queryProjectWorkerPaging',{'projectId':PID},5000)
    if len(rows)<100 or any(x.get('projectId')!=PID for x in rows):
        raise RuntimeError(f'主接口校验失败: {len(rows)}人')
    ids=[x.get('idNumber') for x in rows]
    if len(ids)!=len(set(ids)) or any(not x for x in ids):
        raise RuntimeError('身份证重复或缺失')
    log(f'主接口: {len(rows)} 人')
    ckpt['rows']=rows

    # ── Step 2: 增量比对 ──
    if 'results' not in ckpt: ckpt['results']={}
    results=ckpt['results']
    todo=[]
    skipped=0
    for r in rows:
        old=results.get(r['id'])
        if needs_sync(r, old):
            todo.append(r)
        else:
            skipped+=1
    log(f'增量比对: 已有{len(results)}人, 需更新{len(todo)}人, 跳过{skipped}人')
    if not todo:
        log('✅ 无变化，人员明细全部复用旧数据')

    # ── Step 3: 拉变化人员的4个明细接口 ──
    if todo:
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
            fs={ex.submit(fetch_detail,r):r['id'] for r in todo}
            done=0; fail=0
            for f in concurrent.futures.as_completed(fs):
                try:
                    k,d,c,ce,s=f.result()
                    results[k]=(d,c,ce,s)
                    done+=1
                except Exception as e:
                    log(f'❌ FAIL {fs[f]}: {e}')
                    fail+=1
                if (done+fail)%50==0:
                    save_ckpt(ckpt)
                    log(f'明细进度: {done+fail}/{len(todo)} (成功{done} 失败{fail})')
        save_ckpt(ckpt)
        if fail>0:
            raise RuntimeError(f'明细同步失败{fail}人，终止不覆盖')
        log(f'✅ 明细同步完成: {done}人更新')

    # ── Step 4: 拉考勤全量 ──
    now=datetime.now()
    month_start=now.strftime('%Y-%m-01')
    today=now.strftime('%Y-%m-%d')
    month_str=now.strftime('%Y-%m')
    log(f'拉日考勤 {month_start}~{today}...')
    daily=pages('/api/v1.0/ProjectWorkerAttendance/Paging',{'projectId':PID,'startTime':month_start,'endTime':today},5000)
    log(f'日考勤: {len(daily)} 条')
    log(f'拉月度考勤 {month_str}...')
    monthly=pages('/api/v1.0/projectTeamAttendance/ProjectCorpTeamWorkerLobarHourPaging',{'projectId':PID,'attendanceDate':month_str},5000)
    log(f'月度考勤: {len(monthly)} 条')
    ckpt['daily']=daily; ckpt['monthly']=monthly
    save_ckpt(ckpt)

    # ── Step 5: 考勤按 projectWorkerId 归档 ──
    by_pw={r['id']:r for r in rows}
    da_map={}; mo_map={}
    for x in daily:
        k=None
        for r in rows:
            if r.get('workerName')==x.get('workerName') and r.get('corpName')==x.get('corpName'):
                k=r['id']; break
        if k: da_map.setdefault(k,[]).append(x)
    for x in monthly:
        k=x.get('projectWorkerId')
        if k: mo_map.setdefault(k,[]).append(x)
    log(f'考勤归档: 日考勤{len(da_map)}人/{len(daily)}条, 月考勤{len(mo_map)}人/{len(monthly)}条')

    # ── Step 6: 合并写入 ──
    log('合并写入 project-encrypted-data.json...')
    old_data=json.loads(base64.b64decode(json.load(open(OUT))['payload'])) if os.path.exists(OUT) else {'project':{},'people':[]}
    old_map={p.get('idCard'):p for p in old_data.get('people',[])}
    people=[]
    for r in rows:
        res=results.get(r['id'])
        if not res:
            raise RuntimeError(f'缺少 {r["id"]} 的明细数据')
        d,c,ce,s=res
        pwid=r['id']
        da=fmt_daily(da_map.get(pwid,[]))
        mo=fmt_monthly(mo_map.get(pwid,[]))
        people.append(build_person(r,d,c,ce,s,old_map,da,mo))

    # 校验
    if len(people)!=len(rows):
        raise RuntimeError(f'人数不一致: {len(people)}/{len(rows)}')
    summary={
        'records':len(people),'units':len(set(x['unit'] for x in people)),
        'active':sum(x['status']=='已进场' for x in people),
        'managed':sum(x['team'] in MANAGED for x in people),
        'managedActive':sum(x['team'] in MANAGED and x['status']=='已进场' for x in people),
        'medicalMatched':0,'medicalWarnings':0,
        'detailSynced':len(people),'detailPending':0,
        'dailyAttendanceRecords':len(daily),'monthlyAttendanceRecords':len(monthly)
    }
    old_data['project'].update({
        'updatedAt':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'dataSource':'智慧工地实时接口（增量同步·真实档案+日/月考勤）',
        'summary':summary,'managedTeams':MANAGED,
        'syncStatus':{
            'details':'已同步 全部','dailyAttendance':'已同步','monthlyAttendance':'已同步',
            'dateRange':f'{month_start}~{today}','attendanceMonth':month_str,
            'attendanceMode':'synced','syncType':'incremental',
            'incrementalUpdated':len(todo),'incrementalSkipped':skipped
        }
    })
    old_data['people']=people
    raw=json.dumps(old_data,ensure_ascii=False,separators=(',',':')).encode()
    tmp=OUT+'.new'
    json.dump({'payload':base64.b64encode(raw).decode()},open(tmp,'w'),ensure_ascii=False)
    os.replace(tmp,OUT)
    log(f'✅ 写入完成: {json.dumps(summary,ensure_ascii=False)}')

    # ── Step 7: 推送 GitHub ──
    log('推送 GitHub...')
    import subprocess
    gitdir=f'cd {ROOT}'
    subprocess.run(f'{gitdir} && git add project-encrypted-data.json',shell=True,check=True)
    r=subprocess.run(f'{gitdir} && git diff --cached --quiet',shell=True)
    if r.returncode==0:
        log('⚠️ 无变化，跳过提交')
    else:
        msg=f'data: incremental sync {len(todo)} updated, {skipped} skipped, {len(daily)} daily, {len(monthly)} monthly'
        subprocess.run(f'{gitdir} && git commit -m "{msg}"',shell=True,check=True)
        token=os.environ.get('GITHUB_TOKEN','')
        if token:
            subprocess.run(f'{gitdir} && git push "https://x-access-token:{token}@github.com/xiadasy/site-labor-assistant.git" main',shell=True,check=True)
            log('✅ 已推送 GitHub')
        else:
            log('⚠️ 无 GITHUB_TOKEN，请手动 git push')
    log('═══ 增量同步完成 ═══')

if __name__=='__main__':
    try:
        main()
    except Exception as e:
        log(f'❌ 终止: {e}')
        print(f'\n❌ 同步失败，旧数据未被覆盖: {e}')
        sys.exit(1)
