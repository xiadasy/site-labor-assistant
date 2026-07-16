const CACHE='labor-v30';const ASSETS=['./','./index.html','./project.html','./search.html','./company.html','./encrypted-data.json','./project-encrypted-data.json','./company-encrypted-data.json','./widget-summary.json','./project-widget.js','./photos/project-leader-bg.png'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{
 const u=new URL(e.request.url);
 if(u.pathname.endsWith('/project.html')||u.pathname.endsWith('/project-encrypted-data.json')){
  e.respondWith(fetch(e.request,{cache:'no-store'}).then(r=>{const c=r.clone();caches.open(CACHE).then(x=>x.put(e.request,c));return r}).catch(()=>caches.match(e.request)));return;
 }
 e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)));
});
