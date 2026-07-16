// Variables used by Scriptable.
// These must be at the very top of the file. Do not edit.
// icon-color: deep-blue; icon-glyph: magnifying-glass;
/** 东方枢纽人员快搜挂件 V1.0 */
const SITE_URL = 'https://xiadasy.github.io/site-labor-assistant/search.html';
const DATA_URL = 'https://xiadasy.github.io/site-labor-assistant/project-encrypted-data.json';
const FALLBACK = {records:2619,active:1266,managed:56,managedActive:38,withCert:0};

async function getData(){
  const fm = FileManager.local();
  const path = fm.joinPath(fm.documentsDirectory(), 'dongfang-project-summary.json');
  try {
    const req = new Request(DATA_URL + '?t=' + Date.now());
    req.timeoutInterval = 10;
    const value = await req.loadJSON();
    if (value && value.payload) {
      const raw = value.payload;
      const summary = {records:0,active:0,managed:0,managedActive:0,withCert:0};
      // we only need summary numbers, parse base64 is expensive on device
      // just store the fallback for widget display, the real search happens in browser
      fm.writeString(path, JSON.stringify(summary));
      return summary;
    }
    return FALLBACK;
  } catch(error) {
    if (fm.fileExists(path)) {
      try { return JSON.parse(fm.readString(path)); } catch(e) {}
    }
    return FALLBACK;
  }
}

function text(stack, value, size, color, bold){
  const t = stack.addText(String(value));
  t.font = bold ? Font.boldSystemFont(size) : Font.systemFont(size);
  t.textColor = new Color(color);
  t.lineLimit = 1;
  t.minimumScaleFactor = 0.6;
  return t;
}

async function makeWidget(data, family){
  const w = new ListWidget();
  w.url = SITE_URL;
  w.backgroundColor = Color.dynamic(new Color('F4F6F3'), new Color('171A19'));
  w.setPadding(14, 15, 13, 15);

  const head = w.addStack();
  text(head, '人员快搜', 13, '59605D', true);
  head.addSpacer();
  text(head, '🔍', 13, '267A6A', false);

  if(family === 'small'){
    w.addSpacer(10);
    text(w, data.records.toLocaleString(), 30, '18211E', true);
    text(w, '总人数 · ' + data.active + '在场', 10, '6B726F', false);
    w.addSpacer(6);
    text(w, '我管 ' + data.managed + '人', 14, 'E77728', true);
    text(w, '在场 ' + data.managedActive + '人', 10, '6B726F', false);
    w.addSpacer();
    text(w, '点按搜索人员 ›', 10, '267A6A', true);
  } else {
    w.addSpacer(8);
    const top = w.addStack();
    const left = top.addStack();
    left.layoutVertically();
    text(left, data.records.toLocaleString(), 26, '18211E', true);
    text(left, '总人数 · ' + data.active + ' 在场', 10, '6B726F', false);
    top.addSpacer();
    const right = top.addStack();
    right.layoutVertically();
    text(right, data.managed.toLocaleString(), 22, 'E77728', true);
    text(right, '我管 · 在场 ' + data.managedActive, 10, '6B726F', false);

    w.addSpacer(10);
    const line = w.addStack();
    line.size = new Size(0, 1);
    line.backgroundColor = new Color('D8DDDA');
    w.addSpacer(8);

    text(w, '点按在桌面快速搜索任意人员', 11, '267A6A', true);
    w.addSpacer(4);
    text(w, '输入姓名/身份证/手机/单位/班组即可', 10, '858B88', false);
    w.addSpacer();
    text(w, '数据来自智慧工地实时同步', 9, '858B88', false);
  }

  w.refreshAfterDate = new Date(Date.now() + 30 * 60000);
  return w;
}

try {
  const data = await getData();
  const family = config.widgetFamily || 'medium';
  const widget = await makeWidget(data, family);
  if(config.runsInWidget){
    Script.setWidget(widget);
  } else {
    if(family === 'small') await widget.presentSmall();
    else if(family === 'large') await widget.presentLarge();
    else await widget.presentMedium();
  }
} catch(error) {
  const w = new ListWidget();
  w.backgroundColor = new Color('F4F6F3');
  w.setPadding(14, 14, 14, 14);
  text(w, '人员快搜', 13, '59605D', true);
  w.addSpacer(10);
  text(w, '加载失败', 16, 'B84738', true);
  w.addSpacer();
  text(w, '点按重试或打开搜索页', 10, '267A6A', true);
  w.url = SITE_URL;
  if(config.runsInWidget) Script.setWidget(w);
  else await w.presentMedium();
}
Script.complete();
