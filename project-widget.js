// Variables used by Scriptable.
// These must be at the very top of the file. Do not edit.
// icon-color: deep-blue; icon-glyph: magnifying-glass;
/** 东方枢纽人员快搜挂件 V2.0 - 轻量高速版 */
const SITE_URL = 'https://xiadasy.github.io/site-labor-assistant/search.html?v=33';
const DATA_URL = 'https://xiadasy.github.io/site-labor-assistant/project-widget-summary.json?v=33';
const FALLBACK = {
  records: 2619,
  active: 1266,
  managed: 56,
  managedActive: 38,
  withCert: 2384,
  units: 24,
  updatedAt: '缓存'
};

function text(stack, value, size, color, bold) {
  const t = stack.addText(String(value));
  t.font = bold ? Font.boldSystemFont(size) : Font.systemFont(size);
  t.textColor = new Color(color);
  t.lineLimit = 1;
  t.minimumScaleFactor = 0.65;
  return t;
}

async function getData() {
  const fm = FileManager.local();
  const path = fm.joinPath(fm.documentsDirectory(), 'dongfang-project-widget-summary.json');
  try {
    const req = new Request(DATA_URL + '?t=' + Date.now());
    req.timeoutInterval = 6;
    const value = await req.loadJSON();
    if (value && value.records) {
      fm.writeString(path, JSON.stringify(value));
      return value;
    }
  } catch (e) {}
  if (fm.fileExists(path)) {
    try { return JSON.parse(fm.readString(path)); } catch (e) {}
  }
  return FALLBACK;
}

function makeWidget(data, family) {
  const w = new ListWidget();
  w.url = SITE_URL;
  w.setPadding(14, 15, 13, 15);
  w.backgroundGradient = (() => {
    const g = new LinearGradient();
    g.locations = [0, 1];
    g.colors = [new Color('17342F'), new Color('235248')];
    return g;
  })();

  const head = w.addStack();
  text(head, '人员快搜', 13, 'D7E7E0', true);
  head.addSpacer();
  text(head, '点按搜索 ›', 10, '9FBFB5', false);

  if (family === 'small') {
    w.addSpacer(10);
    text(w, Number(data.records || 0).toLocaleString('zh-CN'), 30, 'FFFFFF', true);
    text(w, '总人数 · ' + Number(data.active || 0).toLocaleString('zh-CN') + ' 在场', 10, 'B7CEC6', false);
    w.addSpacer(8);
    text(w, '我管 ' + Number(data.managed || 0), 16, 'F0B27A', true);
    text(w, '在场 ' + Number(data.managedActive || 0) + ' · 证书 ' + Number(data.withCert || 0), 10, 'B7CEC6', false);
    w.addSpacer();
    text(w, String(data.updatedAt || ''), 9, '8EAAA1', false);
  } else {
    w.addSpacer(10);
    const row = w.addStack();
    const a = row.addStack(); a.layoutVertically();
    text(a, Number(data.records || 0).toLocaleString('zh-CN'), 28, 'FFFFFF', true);
    text(a, '总人数', 10, 'B7CEC6', false);
    row.addSpacer();
    const b = row.addStack(); b.layoutVertically();
    text(b, Number(data.active || 0).toLocaleString('zh-CN'), 24, 'FFFFFF', true);
    text(b, '已进场', 10, 'B7CEC6', false);
    row.addSpacer();
    const c = row.addStack(); c.layoutVertically();
    text(c, Number(data.managed || 0).toLocaleString('zh-CN'), 24, 'F0B27A', true);
    text(c, '我管班组', 10, 'B7CEC6', false);

    w.addSpacer(12);
    const line = w.addStack();
    line.size = new Size(0, 1);
    line.backgroundColor = new Color('FFFFFF', 0.12);
    w.addSpacer(10);

    text(w, '桌面一键搜索姓名 / 身份证 / 手机 / 班组', 12, 'E7F2ED', true);
    w.addSpacer(4);
    text(w, '在场 ' + Number(data.managedActive || 0) + ' · 证书 ' + Number(data.withCert || 0) + ' · 单位 ' + Number(data.units || 0), 10, 'B7CEC6', false);
    w.addSpacer();
    const foot = w.addStack();
    text(foot, String(data.updatedAt || ''), 9, '8EAAA1', false);
    foot.addSpacer();
    text(foot, '打开快搜 ›', 10, 'F0B27A', true);
  }

  w.refreshAfterDate = new Date(Date.now() + 15 * 60 * 1000);
  return w;
}

function makeError(msg) {
  const w = new ListWidget();
  w.url = SITE_URL;
  w.backgroundColor = new Color('17342F');
  w.setPadding(14, 15, 13, 15);
  text(w, '人员快搜', 13, 'D7E7E0', true);
  w.addSpacer(10);
  text(w, '暂用缓存数据', 16, 'FFFFFF', true);
  w.addSpacer(6);
  text(w, String(msg || '点按打开搜索页'), 10, 'B7CEC6', false);
  return w;
}

try {
  const data = await getData();
  const family = config.widgetFamily || 'medium';
  const widget = makeWidget(data, family);
  if (config.runsInWidget) Script.setWidget(widget);
  else if (family === 'small') await widget.presentSmall();
  else if (family === 'large') await widget.presentLarge();
  else await widget.presentMedium();
} catch (error) {
  const widget = makeError(error);
  if (config.runsInWidget) Script.setWidget(widget);
  else await widget.presentMedium();
}
Script.complete();
