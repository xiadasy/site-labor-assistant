import json,base64
from datetime import datetime
d=json.loads(base64.b64decode(json.load(open('project-encrypted-data.json'))['payload']))
managed=d['project'].get('managedTeams',[])
try:
    tabs={x['id']:x.get('count',0) for x in json.load(open('search-meta.json')).get('tabs',[])}
except Exception:
    tabs={}
people=[]
for p in d['people']:
    people.append({
        'id':p.get('projectWorkerId') or p.get('idCard') or '',
        'n':p.get('name') or '',
        'photo':p.get('photo') or '',
        'idc':p.get('idCard') or '',
        'ph':p.get('phone') or '',
        'u':p.get('unit') or '',
        't':p.get('team') or '',
        'w':p.get('trade') or '',
        's':p.get('status') or '',
        'a':p.get('age') or '',
        'x':p.get('sex') or '',
        'e':p.get('entryDate') or '',
        'managed':(p.get('team') or '') in managed,
        'grant':p.get('grantOrg') or '',
        'role':p.get('role') or '',
        'b':p.get('bankName') or '',
        'bc':p.get('bankCard') or '',
        'cs':p.get('contractStatus') or '',
        'qs':p.get('qualificationStatus') or '',
        'ac':p.get('accessCard') or '',
        'addr':p.get('address') or '',
        'nation':p.get('nation') or '',
        'bd':p.get('birthday') or '',
        'c':[{'type':x.get('type') or '','team':x.get('teamName') or '','start':x.get('startDate') or '','end':x.get('endDate') or ''} for x in (p.get('contracts') or [])],
        'q':[{'name':x.get('name') or '','type':x.get('typeName') or '','code':x.get('code') or '','start':x.get('startDate') or '','end':x.get('endDate') or ''} for x in (p.get('certificates') or [])],
        'svc':[{'project':x.get('projectName') or '','corp':x.get('corpName') or '','team':x.get('teamName') or '','trade':x.get('trade') or '','entry':x.get('entryDate') or '','exit':x.get('exitDate') or ''} for x in (p.get('services') or [])],
        'da':[{'time':x.get('time') or '','h':x.get('laborHour') or 0,'in':x.get('inTime') or '','out':x.get('outTime') or ''} for x in (p.get('dailyAttendance') or [])[-5:]],
        'ma':[{'m':x.get('attendanceDate') or '','h':x.get('laborHour') or 0} for x in (p.get('monthlyAttendance') or [])]
    })
summary={
 'records':len(people),
 'active':sum(1 for p in people if p['s']=='已进场'),
 'managed':sum(1 for p in people if p['t'] in managed),
 'managedActive':sum(1 for p in people if p['t'] in managed and p['s']=='已进场'),
 'withCert':sum(1 for p in people if p['q']),
 'withPhoto':sum(1 for p in people if p.get('photo')),
 'units':len(set(p['u'] for p in people if p['u'])),
 'labor':tabs.get('labor',0),
 'company':tabs.get('company',0),
 'updatedAt':d['project'].get('updatedAt') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
}
source_services=sum(len(p.get('services') or []) for p in d['people'])
index_services=[s for p in people for s in p['svc']]
if len(people)!=summary['records'] or len(index_services)!=source_services:
    raise RuntimeError('search index count mismatch')
if any(not s.get('project') for s in index_services):
    raise RuntimeError('search index missing project service name')
if sum(bool(p.get('photo')) for p in people)!=summary['withPhoto']:
    raise RuntimeError('search index photo count mismatch')
if sum(bool(p.get('managed')) for p in people)!=summary['managed']:
    raise RuntimeError('search index managed count mismatch')
# lite index for first paint
lite=[{'id':p['id'],'n':p['n'],'photo':p['photo'],'idc':p['idc'],'ph':p['ph'],'u':p['u'],'t':p['t'],'w':p['w'],'s':p['s'],'a':p['a'],'x':p['x'],'e':p['e'],'managed':p['managed']} for p in people]
open('search-lite.json','w').write(json.dumps({'version':1,'summary':summary,'people':lite},ensure_ascii=False,separators=(',',':')))
# full detail index for expand
open('search-index.json','w').write(json.dumps({'version':1,'summary':summary,'people':people},ensure_ascii=False,separators=(',',':')))
open('project-widget-summary.json','w').write(json.dumps(summary,ensure_ascii=False,separators=(',',':')))
try:
    meta=json.load(open('search-meta.json'))
    meta.setdefault('summary',{}).update(summary)
    for tab in meta.get('tabs',[]):
        if tab.get('id')=='project': tab['count']=summary['records']
        elif tab.get('id')=='managed': tab['count']=summary['managed']
    open('search-meta.json','w').write(json.dumps(meta,ensure_ascii=False,separators=(',',':')))
except Exception:
    pass
print('search-lite.json',round(len(open('search-lite.json','rb').read())/1024,1),'KB')
print('search-index.json',round(len(open('search-index.json','rb').read())/1024,1),'KB')
print('project-widget-summary.json',round(len(open('project-widget-summary.json','rb').read())/1024,1),'KB')
print(summary)
