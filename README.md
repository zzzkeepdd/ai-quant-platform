# AI量化自动交易平台

本项目是本地运行的 OKX 加密货币 AI 量化平台：DeepSeek 负责行情理解，四个通过五重质检的策略负责信号，风控守卫负责所有下单前硬约束。

## 功能预览

| 策略回测 | AI 参数迭代 |
| --- | --- |
| ![策略回测](docs/screenshots/backtest.png) | ![AI参数迭代](docs/screenshots/ai-optimizer.png) |

| 实盘监控 | 系统设置 |
| --- | --- |
| ![实盘监控](docs/screenshots/live-monitor.png) | ![系统设置](docs/screenshots/settings.png) |

## 快速启动

1. 安装后端依赖：
   ```bash
   cd backend
   pip install -r requirements.txt
   ```
2. 安装前端依赖：
   ```bash
   cd frontend
   npm install
   ```
3. 回到项目根目录双击 `start.bat`，或运行：
   ```bash
   ./start.sh
   ```
4. 打开 `http://127.0.0.1:5173`。

## 数据与策略

- 回测优先读取 `D:\量化平台V2\data\smc_raw` 下的 `BTC_USDT_1h.csv`、`ETH_USDT_1h.csv`、`SOL_USDT_1h.csv`。
- 策略目录只允许以下四个文件参与加载：
  - `BB挤压突破.py`
  - `BOS移动止损增强版.py`
  - `摆动点区间反转.py`
  - `趋势衰竭反转.py`

## 安全说明

- OKX 与 DeepSeek 密钥只通过系统设置页写入本地 SQLite，并使用 Fernet 加密。数据库位于 `backend/data_cache/`，根目录 `data_cache/` 保留给行情缓存与导出文件。
- DeepSeek 默认使用本机实测可返回内容的 `deepseek-chat` 模型。
- 密钥不会写入源码、README、前端缓存或日志。
- 默认自动交易为模拟盘。切换实盘会显示强警告。
- AI 只能建议行情、策略和参数，不能修改风控，也不能绕过订单审核。

## 风控硬规则

- 最大杠杆 3x
- 单日亏损 5% 熔断
- ATR 异常波动熔断
- 最小名义仓位 10 USDT
- 策略切换冷却期 12 小时
- 趋势末端信号无视冷却期，并优先平掉顺势仓位
- 连续 3 次下单失败自动暂停自动交易

## 测试

后端：
```bash
cd backend
pytest
```

前端：
```bash
cd frontend
npm run test
npm run build
```

## 截图

截图位于 `docs/screenshots/`，由本地运行页面生成。界面默认深色主题，左侧导航包含策略回测、实盘监控、AI助手、AI参数迭代、历史重放、风险管理、策略管理、系统设置。
