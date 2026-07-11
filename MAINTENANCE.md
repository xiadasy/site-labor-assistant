# 东方枢纽劳务助手维护说明

> 用途：新窗口更新东方枢纽劳务助手资料时，必须先读本文件。目标是在现有站点结构上增量更新人员、工资、证书和挂件汇总，不重建网站、不改变网址、不改变查询密码。

## 1. 固定资产

- GitHub 仓库：`https://github.com/xiadasy/site-labor-assistant`
- GitHub Pages：`https://xiadasy.github.io/site-labor-assistant/`
- 本地工程：`/var/minis/workspace/site-labor-pwa/`
- 公开文件：
  - `index.html`：单页 PWA 查询页。
  - `encrypted-data.json`：加密后的人员、工资、证书元数据。
  - `cert-files/*.bin`：逐份加密后的证书原件。
  - `widget-summary.json`：Scriptable 轻量挂件读取的无隐私汇总。
  - `widget.js`：Scriptable 轻量挂件代码。
  - `manifest.webmanifest`、`sw.js`、`app-icon.png`：PWA 固定文件。
- 查询密码：只从环境变量 `LABOR_QUERY_PASSWORD` 读取，禁止改密码、禁止输出密码、禁止写入仓库。
- 发布凭据：使用当前 Git 配置或 `GITHUB_TOKEN`；禁止打印 token。

## 2. 核心原则

1. 不重建网站，不改变仓库、Pages 网址、PWA 名称、查询密码和基本交互。
2. 更新数据必须在现有 schema 上增量合并。
3. 人员主键优先用身份证号；姓名只作显示和弱匹配辅助。
4. 新花名册更新人员基础信息、进退场和状态，但不得删除历史工资。
5. 工资必须保留历史月份，并区分：
   - `expectedAmount` / `expectedTotal`：应发。
   - `paidAmount` / `paidTotal`：实发。
   - `status`：`已发放`、`待发放`、`发放失败`、`部分成功` 等。
6. 证书原件不得明文发布；必须使用查询密码派生密钥逐份 AES-GCM 加密为 `.bin` 后再上传。
7. `widget-summary.json` 只能包含汇总数字，禁止姓名、身份证、手机号、银行卡、证书编号等隐私明文。
8. 公开仓库扫描必须无隐私明文：姓名、身份证、手机号、银行卡、PDF 明文都不得出现在公开文件中。

## 3. 推荐执行流程

### 3.1 准备工程

```sh
cd /var/minis/workspace
[ -d site-labor-pwa/.git ] || git clone https://github.com/xiadasy/site-labor-assistant.git site-labor-pwa
cd site-labor-pwa
git pull --ff-only
[ -n "$LABOR_QUERY_PASSWORD" ] && echo 'LABOR_QUERY_PASSWORD:set' || echo 'LABOR_QUERY_PASSWORD:not_set'
```

只能检查变量是否存在，不得 echo 变量值。

### 3.2 读取现有密文

使用 `LABOR_QUERY_PASSWORD` 对 `encrypted-data.json` 解密，得到当前人员主数据。临时明文只能保存在本地工作文件（建议 `.private-current-data.json`），不得提交。

加密参数沿用：

- PBKDF2-HMAC-SHA256
- iterations：`210000`
- AES-GCM 256
- `salt`、`iv`、`ciphertext` 使用 base64

`encrypted-data.json` 字段保持：

```json
{
  "version": 1,
  "algorithm": "AES-GCM-256",
  "kdf": "PBKDF2-SHA256",
  "iterations": 210000,
  "salt": "...",
  "iv": "...",
  "ciphertext": "..."
}
```

注意：现有前端只依赖 `salt`、`iv`、`iterations`、`ciphertext`，但保留其他字段便于审计。

### 3.3 资料识别

优先从以下目录找用户本次提供资料：

- `/var/minis/attachments/`
- `/var/minis/workspace/`
- `/var/minis/mounts/*/`
- 用户明确指定路径

只处理本次新增或用户指定文件，不要用旧演示数据覆盖线上数据。

资料类型：

- 花名册：XLS/XLSX/CSV。
- 工资：ZIP、XLS/XLSX、银行批量文件、工资发放记录、委托书。
- 证书：PDF、图片、ZIP。
- 说明文件：DOCX、PDF、文本。

### 3.4 人员合并

人员匹配顺序：

1. 身份证号完全一致。
2. 身份证缺失时：单位 + 姓名 + 手机/银行卡/合同编号弱匹配，并在日志中标注。
3. 不确定时不得强行合并。

更新字段：

- `name`
- `idCard`
- `phone`
- `bankCard`
- `bankName`
- `trade`
- `dailyWage`
- `entryDate`
- `exitDate`
- `status`
- `medicalDate`
- `certificates[]`
- `payrollHistory[]`

保留已有历史工资和证书，除非新资料明确更正。

### 3.5 工资合并

每个人 `payrollHistory[]` 按月份唯一。新月份追加，已有月份按身份证更新。

个人工资建议结构：

```json
{
  "month": "2026-06",
  "expectedAmount": 9900,
  "paidAmount": 0,
  "amount": 9900,
  "status": "发放失败",
  "remark": "银行退回或资料说明"
}
```

单位工资汇总 `unit.payrollHistory[]`：

```json
{
  "month": "2026-06",
  "total": 246830,
  "expectedTotal": 246830,
  "paidTotal": 0,
  "peopleCount": 19,
  "status": "待发放"
}
```

规则：

- `total` 为兼容旧代码，可等于 `expectedTotal`。
- `paidTotal` 是实发总额，不得把待发或失败金额计入。
- 有人发放失败时，单位状态通常为 `部分成功`，并准确扣减 `paidTotal`。
- 未提供某单位某月份工资时，显示暂无资料，不猜数。
- `availableMonths` 按新到旧排序。

### 3.6 证书合并与加密

证书元数据进入人员 `certificates[]`，原件走 `cert-files/*.bin`。

证书对象建议结构：

```json
{
  "type": "建设施工高处作业证",
  "operation": "高处作业",
  "number": "...",
  "issuer": "...",
  "issueDate": "YYYY-MM-DD",
  "validUntil": "YYYY-MM-DD",
  "file": "cert-files/xxxx.bin",
  "fileName": "原文件名.pdf"
}
```

加密要求：

- 每份证书原件单独加密。
- 明文 PDF/图片不得留在仓库。
- `.bin` 文件名建议用原文件 hash 或证书 hash 生成，避免泄露姓名。
- 加密后抽查解密，确认前几个字节是 `%PDF` 或对应图片 magic。

### 3.7 重新生成密文和挂件汇总

更新主数据后：

1. 重新加密写入 `encrypted-data.json`。
2. 生成 `widget-summary.json`，只保留汇总：
   - `records`
   - `active`
   - `focusOver55`
   - `certificateCount`
   - `certifiedPeople`
   - `units[].records`
   - `units[].active`
   - `units[].certificateCount`
   - `units[].payrollHistory[]` 的 `month/expectedTotal/paidTotal/peopleCount/status`
3. 不改 `widget.js`，除非汇总结构变化。

### 3.8 发布

```sh
cd /var/minis/workspace/site-labor-pwa
git status --short
git add index.html encrypted-data.json widget-summary.json widget.js manifest.webmanifest sw.js app-icon.png cert-files MAINTENANCE.md
git commit -m "更新东方枢纽劳务助手资料"
git push origin main
```

若只变数据和汇总，不要拆成几十次提交，避免 GitHub Pages 排队。

## 4. 验证清单

### 4.1 本地回读

- 用 `LABOR_QUERY_PASSWORD` 解密 `encrypted-data.json` 成功。
- 统计人员总数、在场人数、证书数量、月份工资汇总。
- 检查每个工资月份：个人合计与单位 `expectedTotal/paidTotal` 一致。
- 检查身份证重复、姓名弱匹配冲突。
- 检查证书 `file` 对应 `.bin` 均存在。

### 4.2 线上回读

等待 Pages 构建后，从以下地址取回：

- `https://xiadasy.github.io/site-labor-assistant/encrypted-data.json?t=时间戳`
- `https://xiadasy.github.io/site-labor-assistant/widget-summary.json?t=时间戳`
- 抽查 `cert-files/*.bin`

使用本机 `LABOR_QUERY_PASSWORD` 解密线上密文，验证 schema、人数、工资、证书数量与本地一致。

### 4.3 隐私扫描

公开仓库和线上公开文本必须扫描：

- 18位身份证：`[1-9][0-9]{16}[0-9Xx]`
- 手机号：`1[3-9][0-9]{9}`
- 银行卡长号：`[0-9]{16,19}`
- 常见姓名明文（从解密数据取姓名列表后扫公开文件）
- PDF magic：公开仓库内不得有未加密 `.pdf` 证书原件

允许：

- `widget-summary.json` 中的单位名、项目名、汇总数字。
- `index.html`、`widget.js` 的固定文案。
- `cert-files/*.bin` 随机密文中偶然出现短数字片段，但不得出现完整证件/手机号/姓名。

## 5. 当前已知口径

- 项目：东方枢纽上海东站机电安装装修装修地下工程项目。
- 单位：共强、铭富。
- 当前站点已支持：人员查询、隐私眼睛、工资历史、证书资料、加密 PDF 原件、年龄动态计算、体检周期、轻量 Scriptable 汇总挂件。
- 重点年龄规则：年龄 `>55` 周岁为重点关注，体检有效期 6 个月；其余 12 个月。
- 隐私眼睛关闭时：姓名中间星号、个人日薪/进退场/工资、证书编号/机构/日期等均遮蔽，PDF 按钮禁用。

## 6. 禁止事项

- 禁止输出、提交或写入查询密码。
- 禁止把解密明文数据提交到 Git。
- 禁止把原始证书 PDF/图片放进公开仓库。
- 禁止用姓名替代身份证作唯一主键。
- 禁止删除历史工资。
- 禁止把应发当实发。
- 禁止用旧挂件 JSON 或旧本地 data.json 覆盖线上新版。
- 禁止为了“看起来更新了”而伪造人数、金额、证书。
