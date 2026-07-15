const CACHE='dongfang-labor-v22';
const ASSETS=['./','./index.html','./admin.html','./company.html','./company-admin.html','./project.html','./manifest.webmanifest','./app-icon.png'];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS))));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key))))));
self.addEventListener('fetch',event=>{
  if(new URL(event.request.url).pathname.endsWith('encrypted-data.json')||new URL(event.request.url).pathname.endsWith('project-encrypted-data.json')){
    event.respondWith(fetch(event.request,{cache:'no-store'}).catch(()=>caches.match(event.request)));
    return;
  }
  event.respondWith(caches.match(event.request).then(hit=>hit||fetch(event.request).then(response=>{const copy=response.clone();caches.open(CACHE).then(cache=>cache.put(event.request,copy));return response})));
});
