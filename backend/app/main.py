import uuid
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .ai import ai_engine
from .backtest import iterate_parameters, run_backtest
from .config import APP_VERSION, DEFAULT_MARKET_MODE, FRONTEND_DIST_DIR
from .database import database_ready, get_setting, init_db, set_setting
from .exchange import exchange_manager
from .logging_service import export_csv, log_system, safe_payload
from .market_data import fetch_live_market, fetch_onchain_summary
from .optimizer import auto_optimize_strategy
from .replay import run_replay
from .risk import get_risk_rules, risk_guard, save_risk_rules
from .schemas import AITaskRequest, BacktestRequest, ParameterIterationRequest, ReplayRequest, RiskRulesPayload, SecretPayload, TradingStartRequest, TradingTestOrderRequest
from .secrets import has_secret, save_secret
from .strategy_loader import list_strategies
from .trading import trading_engine


app = FastAPI(title="AI量化自动交易平台", version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if FRONTEND_DIST_DIR.exists():
    assets_dir = FRONTEND_DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.on_event("startup")
async def startup() -> None:
    init_db()
    log_system("INFO", "AI量化平台后端启动", {"version": APP_VERSION})


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "version": APP_VERSION, "database": database_ready()}


@app.get("/api/status")
async def status() -> dict[str, Any]:
    okx_status = exchange_manager.status()
    if okx_status.get("configured") and not okx_status.get("auth_ok") and not okx_status.get("last_error"):
        await exchange_manager.account()
        okx_status = exchange_manager.status()
    ai_status = ai_engine.status()
    if ai_status.get("configured") and ai_status.get("valid") is None and not ai_status.get("last_error"):
        ai_status = await ai_engine.validate_connection()
    return {
        "okx": okx_status,
        "ai": ai_status,
        "trading": trading_engine.status(),
        "risk": risk_guard.risk_status(),
    }


@app.get("/api/settings")
async def settings() -> dict[str, Any]:
    return {
        "proxy": get_setting("proxy", {"type": "http", "host": "127.0.0.1", "port": 7897}),
        "market_mode": get_setting("market_mode", DEFAULT_MARKET_MODE),
        "secrets": {
            "okx_api_key": has_secret("okx_api_key"),
            "okx_secret_key": has_secret("okx_secret_key"),
            "okx_password": has_secret("okx_password"),
            "deepseek_api_key": has_secret("deepseek_api_key"),
        },
        "okx": exchange_manager.status(),
        "ai": ai_engine.status(),
    }


@app.get("/api/strategies")
async def strategies() -> list[dict[str, Any]]:
    return list_strategies()


@app.post("/api/settings/secrets")
async def save_settings(payload: SecretPayload) -> dict[str, Any]:
    deepseek_changed = False
    if payload.okx_api_key and payload.okx_api_key.strip():
        save_secret("okx_api_key", payload.okx_api_key)
    if payload.okx_secret_key and payload.okx_secret_key.strip():
        save_secret("okx_secret_key", payload.okx_secret_key)
    if payload.okx_password and payload.okx_password.strip():
        save_secret("okx_password", payload.okx_password)
    if payload.deepseek_api_key and payload.deepseek_api_key.strip():
        save_secret("deepseek_api_key", payload.deepseek_api_key)
        deepseek_changed = True
    if deepseek_changed:
        ai_engine.reset_validation()
    set_setting("proxy", {"type": payload.proxy_type, "host": payload.proxy_host, "port": payload.proxy_port})
    set_setting("market_mode", payload.market_mode)
    log_system("INFO", "系统设置已保存", safe_payload(payload.model_dump()))
    return {"ok": True, "message": "配置已加密保存"}


@app.get("/api/risk")
async def risk_get() -> dict[str, Any]:
    return {"rules": get_risk_rules(), "status": risk_guard.risk_status()}


@app.post("/api/risk")
async def risk_save(payload: RiskRulesPayload) -> dict[str, Any]:
    rules = save_risk_rules(payload.model_dump())
    return {"ok": True, "message": "风险规则已保存", "rules": rules}


@app.post("/api/exchange/test")
async def exchange_test() -> dict[str, Any]:
    return await exchange_manager.test_connection()


@app.get("/api/exchange/diagnose")
async def exchange_diagnose() -> dict[str, Any]:
    return await exchange_manager.diagnose()


@app.get("/api/exchange/account")
async def exchange_account() -> dict[str, Any]:
    return await exchange_manager.account()


@app.get("/api/ai/diagnose")
async def ai_diagnose() -> dict[str, Any]:
    return await ai_engine.validate_connection()


@app.get("/api/exchange/positions")
async def exchange_positions() -> list[dict[str, Any]]:
    return await exchange_manager.positions()


@app.get("/api/exchange/orders")
async def exchange_orders() -> list[dict[str, Any]]:
    return await exchange_manager.orders()


@app.get("/api/market/live")
async def market_live() -> dict[str, Any]:
    return fetch_live_market()


@app.get("/api/onchain/summary")
async def onchain_summary() -> dict[str, Any]:
    return fetch_onchain_summary()


@app.post("/api/backtest/run")
async def backtest(payload: BacktestRequest) -> dict[str, Any]:
    return run_backtest(
        payload.strategy_file,
        payload.symbol,
        payload.limit,
        payload.params,
        payload.start_date,
        payload.end_date,
        timeframe=payload.timeframe,
        initial_capital=payload.initial_capital,
        preset=payload.preset,
    )


@app.post("/api/backtest/iterate")
async def backtest_iterate(payload: ParameterIterationRequest) -> dict[str, Any]:
    return iterate_parameters(
        payload.strategy_file,
        payload.symbol,
        payload.timeframe,
        payload.limit,
        payload.initial_capital,
        payload.param_grid,
        payload.start_date,
        payload.end_date,
    )


@app.post("/api/ai/auto-optimize")
async def ai_auto_optimize(payload: AITaskRequest) -> dict[str, Any]:
    return auto_optimize_strategy(
        payload.symbol,
        payload.timeframe,
        payload.initial_capital,
        get_setting("market_mode", DEFAULT_MARKET_MODE),
    )


@app.post("/api/ai/{task_type}")
async def ai_task(task_type: str, payload: AITaskRequest) -> dict[str, Any]:
    task_id = str(uuid.uuid4())
    # REST入口返回task_id，前端通过/ws/ai/{task_id}消费流。
    ai_engine.tasks[task_id] = []
    payload_data = payload.model_dump()
    try:
        account = await exchange_manager.account()
        positions = await exchange_manager.positions()
        payload_data["okx_account"] = {
            "source": account.get("source"),
            "equity": account.get("equity"),
            "total_eq_usd": account.get("total_eq_usd"),
            "funding_assets": account.get("funding_assets", []),
        }
        payload_data["okx_positions_count"] = len(positions)
    except Exception as exc:
        payload_data["okx_account_error"] = str(exc)[:120]
    if task_type in {"auto-select", "auto-optimize", "optimize"}:
        payload_data["auto_optimization"] = auto_optimize_strategy(
            payload.symbol,
            payload.timeframe,
            payload.initial_capital,
            get_setting("market_mode", DEFAULT_MARKET_MODE),
        )
    ai_engine.pending[task_id] = (task_type, payload_data)
    return {"ok": True, "task_id": task_id, "ws": f"/ws/ai/{task_id}", "task_type": task_type, "payload": payload_data}


@app.post("/api/trading/start")
async def trading_start(payload: TradingStartRequest) -> dict[str, Any]:
    return await trading_engine.start(payload.mode, payload.position_mode, payload.confirm)


@app.post("/api/trading/pause")
async def trading_pause() -> dict[str, Any]:
    return await trading_engine.pause()


@app.post("/api/trading/stop")
async def trading_stop() -> dict[str, Any]:
    return await trading_engine.stop()


@app.post("/api/trading/test-order")
async def trading_test_order(payload: TradingTestOrderRequest) -> dict[str, Any]:
    return await trading_engine.place_demo_test_order(
        payload.confirm,
        inst_id=payload.inst_id,
        side=payload.side,
        size=payload.size,
        td_mode=payload.td_mode,
    )


@app.post("/api/replay/run")
async def replay(payload: ReplayRequest) -> dict[str, Any]:
    return run_replay(
        payload.symbol,
        payload.strategy_file,
        payload.candles,
        payload.start_date,
        payload.end_date,
        initial_capital=payload.initial_capital,
        timeframe=payload.timeframe,
    )


@app.get("/api/logs/export")
async def logs_export(type: str = "trade") -> Response:
    csv_text = export_csv(type)
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={type}_logs.csv"},
    )


@app.websocket("/ws/status")
async def ws_status(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        await websocket.send_json(await status())
    except WebSocketDisconnect:
        return


@app.websocket("/ws/market")
async def ws_market(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({"symbol": "BTC/USDT:USDT", "timeframe": "1h", "message": "市场WebSocket已连接"})


@app.websocket("/ws/logs")
async def ws_logs(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({"message": "日志WebSocket已连接"})


@app.websocket("/ws/ai/{task_id}")
async def ws_ai(websocket: WebSocket, task_id: str) -> None:
    await websocket.accept()
    task_type, payload = ai_engine.pending.pop(task_id, ("analyze", {"market_summary": "前端请求流式AI分析", "task_id": task_id}))
    async for chunk in ai_engine.stream(task_id, task_type, payload):
        await websocket.send_json({"delta": chunk})
    await websocket.send_json({"done": True})


@app.get("/", include_in_schema=False)
async def frontend_index() -> FileResponse:
    return FileResponse(FRONTEND_DIST_DIR / "index.html")


@app.get("/{full_path:path}", include_in_schema=False)
async def frontend_app(full_path: str) -> FileResponse:
    index = FRONTEND_DIST_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return FileResponse(FRONTEND_DIST_DIR / full_path)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
