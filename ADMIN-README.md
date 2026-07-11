# 东方枢纽劳务助手管理模式

## 已实现

- 原查询页面增加“管”入口，不改变原查询网址和查询密码。
- 管理页面继续使用查询密码在浏览器本机解密。
- 人员进场、退场均追加到 `statusHistory[]`，不会覆盖历史事件。
- 重新进场时保留之前的退场记录，最后一条事件决定当前状态。
- 可编辑人员基本资料。
- 可新增、修改、删除个人工资月份，区分应发、实发和发放状态。
- 保存时自动重算单位工资汇总、人员数、在场数和挂件汇总。
- 证书PDF在浏览器本机使用 PBKDF2 + AES-GCM 加密，再上传 `.bin` 密文。
- 云端后端使用 Cloudflare Worker + D1；D1保存加密状态、操作日志和新增证书密文。若以后启用R2，新证书密文可迁移到R2。
- 无云端服务时可以导出加密备份，不会把明文下载到手机。

## 云端部署

需要有效的 Cloudflare API Token，权限至少包括：

- Account / Workers Scripts / Edit
- Account / D1 / Edit
- Account / Workers R2 Storage / Edit

环境变量使用：

- `CF_API_TOKEN`
- `CF_ACCOUNT_ID`
- `LABOR_ADMIN_TOKEN`（至少24字符；只作为 Worker secret，不写入仓库）

部署顺序：

```sh
cd /var/minis/workspace/site-labor-pwa/worker
CLOUDFLARE_API_TOKEN="$CF_API_TOKEN" CLOUDFLARE_ACCOUNT_ID="$CF_ACCOUNT_ID" wrangler d1 create dongfang_labor_admin
# 将返回的 database_id 填入 wrangler.toml
CLOUDFLARE_API_TOKEN="$CF_API_TOKEN" CLOUDFLARE_ACCOUNT_ID="$CF_ACCOUNT_ID" wrangler r2 bucket create dongfang-labor-certs
CLOUDFLARE_API_TOKEN="$CF_API_TOKEN" CLOUDFLARE_ACCOUNT_ID="$CF_ACCOUNT_ID" wrangler d1 execute dongfang_labor_admin --remote --file schema.sql
printf '%s' "$LABOR_ADMIN_TOKEN" | CLOUDFLARE_API_TOKEN="$CF_API_TOKEN" CLOUDFLARE_ACCOUNT_ID="$CF_ACCOUNT_ID" wrangler secret put ADMIN_TOKEN
CLOUDFLARE_API_TOKEN="$CF_API_TOKEN" CLOUDFLARE_ACCOUNT_ID="$CF_ACCOUNT_ID" wrangler deploy
```

部署后把 Worker 地址填入管理页“管理服务地址”。

## 数据关系

人员仍以身份证号作为唯一关联主键。

进退场事件：

```json
{
  "statusHistory": [
    {"type": "entry", "date": "2026-04-02", "note": "首次进场"},
    {"type": "exit", "date": "2026-07-15", "note": "阶段退场"},
    {"type": "entry", "date": "2026-08-01", "note": "重新进场"}
  ]
}
```

兼容字段 `status`、`entryDate`、`exitDate` 会同步更新，旧查询页面仍可读取。
