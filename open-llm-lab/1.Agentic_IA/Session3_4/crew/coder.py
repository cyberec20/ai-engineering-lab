"""
Pipeline cuantitativo del Coder para la sesi\u00f3n 3.4.

Responsabilidades:
- Descargar OHLCV con yfinance (ventana por defecto 2 a\u00f1os, modo largo 5 a\u00f1os).
- Split cronol\u00f3gico 70/30 (train/test).
- Ajustar modelos ARIMA/SARIMAX (auto_arima), GARCH y Prophet con fallbacks.
- Calcular m\u00e9tricas simples (RMSE/MAE en test; AIC/BIC cuando aplique).
- Generar gr\u00e1ficas PNG en charts/<ticker>/ y devolver rutas + resumen.

El c\u00f3digo es defensivo: si un modelo falla o hay pocos datos, anota un warning
y sigue con los dem\u00e1s modelos para no romper el flujo.
"""

from __future__ import annotations

import os
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.metrics import mean_absolute_error, mean_squared_error

# Modelos; se importan aqu\u00ed para fallar r\u00e1pido si faltan dependencias.
try:
    import pmdarima as pm
except Exception:
    pm = None

try:
    from statsmodels.tsa.statespace.sarimax import SARIMAX
except Exception:
    SARIMAX = None

try:
    from arch import arch_model
except Exception:
    arch_model = None

try:
    from prophet import Prophet
except Exception:
    Prophet = None

import matplotlib

matplotlib.use("Agg")  # backend no interactivo
import matplotlib.pyplot as plt
import seaborn as sns


@dataclass
class ModelResult:
    name: str
    summary: str
    metrics: Dict[str, float] = field(default_factory=dict)
    image_paths: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class CoderResult:
    ticker: str
    models: List[ModelResult]
    warnings: List[str]


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _split_train_test(series: pd.Series, train_ratio: float = 0.7) -> Tuple[pd.Series, pd.Series]:
    n = len(series)
    split_idx = max(1, int(n * train_ratio))
    train = series.iloc[:split_idx]
    test = series.iloc[split_idx:]
    return train, test


def _rmse(y_true, y_pred) -> float:
    return float(math.sqrt(mean_squared_error(y_true, y_pred)))


def _mae(y_true, y_pred) -> float:
    return float(mean_absolute_error(y_true, y_pred))


def _download_ohlcv(ticker: str, lookback_days: int, interval: str = "1d") -> pd.DataFrame:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)
    df = yf.download(ticker, start=start.date(), end=end.date(), interval=interval, progress=False)
    if df is None or df.empty:
        raise RuntimeError(f"Sin datos OHLCV para {ticker}")
    df = df.dropna()
    return df


def _plot_price_forecast(ticker: str, df: pd.DataFrame, forecast: pd.Series, split_idx: int, out_dir: str) -> str:
    _ensure_dir(out_dir)
    plt.figure(figsize=(10, 5))
    sns.lineplot(x=df.index, y=df["Close"], label="Hist\u00f3rico", color="steelblue")
    plt.axvline(df.index[split_idx - 1], color="gray", linestyle="--", linewidth=1, label="Split train/test")
    if forecast is not None and not forecast.empty:
        sns.lineplot(x=forecast.index, y=forecast.values, label="Forecast", color="darkorange")
    plt.title(f"{ticker} - Precio y forecast")
    plt.xlabel("Fecha")
    plt.ylabel("Close")
    plt.legend()
    path = os.path.join(out_dir, f"{ticker}_price_forecast.png")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    return path


def _plot_garch_vol(ticker: str, df: pd.Series, cond_vol: pd.Series, out_dir: str) -> str:
    _ensure_dir(out_dir)
    plt.figure(figsize=(10, 4))
    sns.lineplot(x=df.index, y=cond_vol, label="Volatilidad condicional", color="firebrick")
    plt.title(f"{ticker} - GARCH volatilidad condicional")
    plt.xlabel("Fecha")
    plt.ylabel("Volatilidad")
    plt.legend()
    path = os.path.join(out_dir, f"{ticker}_garch_vol.png")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    return path


def _fit_arima(ticker: str, series: pd.Series, train_ratio: float, forecast_horizon: int, out_dir: str) -> ModelResult:
    res = ModelResult(name="ARIMA", summary="", metrics={}, warnings=[])
    if pm is None:
        res.warnings.append("pmdarima no disponible")
        return res

    if isinstance(series, pd.DataFrame):
        if series.shape[1] > 0:
            series = series.iloc[:, 0]
        series = series.squeeze()

    train, test = _split_train_test(series, train_ratio=train_ratio)
    if len(train) < 20 or len(test) < 5:
        res.warnings.append("Datos insuficientes para ARIMA")
        return res

    try:
        model = pm.auto_arima(train, seasonal=False, error_action="ignore", suppress_warnings=True, stepwise=True)
        fitted = model.fit(train)
        preds_test = fitted.predict(n_periods=len(test))
        res.metrics["rmse_test"] = _rmse(test, preds_test)
        res.metrics["mae_test"] = _mae(test, preds_test)
        res.metrics["aic"] = float(fitted.aic())
        res.metrics["bic"] = float(fitted.bic())
        # Forecast futuro
        preds_future = fitted.predict(n_periods=forecast_horizon)
        forecast_index = pd.date_range(start=series.index[-1], periods=forecast_horizon + 1, freq="D")[1:]
        forecast_series = pd.Series(preds_future, index=forecast_index)
        split_idx = len(train)
        img = _plot_price_forecast(ticker, series.to_frame(name="Close"), forecast_series, split_idx, out_dir)
        res.image_paths.append(img)
        res.summary = (
            f"ARIMA ({model.order}) ajustado; RMSE test={res.metrics['rmse_test']:.3f}, "
            f"MAE test={res.metrics['mae_test']:.3f}"
        )
    except Exception as exc:
        res.warnings.append(f"ARIMA fall\u00f3: {exc}")
    return res


def _fit_prophet(ticker: str, series: pd.Series, train_ratio: float, forecast_horizon: int, out_dir: str) -> ModelResult:
    res = ModelResult(name="Prophet", summary="", metrics={}, warnings=[])
    if Prophet is None:
        res.warnings.append("prophet no disponible")
        return res

    if isinstance(series, pd.DataFrame):
        if series.shape[1] > 0:
            series = series.iloc[:, 0]
        series = series.squeeze()

    df = series.reset_index()
    df.columns = ["ds", "y"]
    split_idx = int(len(df) * train_ratio)
    if split_idx < 20 or len(df) - split_idx < 5:
        res.warnings.append("Datos insuficientes para Prophet")
        return res

    train = df.iloc[:split_idx]
    test = df.iloc[split_idx:]

    try:
        m = Prophet(interval_width=0.8, daily_seasonality=False, weekly_seasonality=True, yearly_seasonality=True)
        m.fit(train)
        future = m.make_future_dataframe(periods=len(test) + forecast_horizon, freq="D")
        forecast = m.predict(future)
        # m\u00e9tricas en test
        yhat_test = forecast.iloc[split_idx:split_idx + len(test)]["yhat"].values
        res.metrics["rmse_test"] = _rmse(test["y"].values, yhat_test)
        res.metrics["mae_test"] = _mae(test["y"].values, yhat_test)
        # forecast futuro
        forecast_future = forecast.tail(forecast_horizon)[["ds", "yhat"]]
        forecast_series = pd.Series(forecast_future["yhat"].values, index=pd.to_datetime(forecast_future["ds"]))
        img = _plot_price_forecast(ticker, series.to_frame(name="Close"), forecast_series, split_idx, out_dir)
        res.image_paths.append(img)
        res.summary = (
            f"Prophet con estacionalidad semanal/anual; RMSE test={res.metrics['rmse_test']:.3f}, "
            f"MAE test={res.metrics['mae_test']:.3f}"
        )
    except Exception as exc:
        res.warnings.append(f"Prophet fall\u00f3: {exc}")
    return res


def _fit_garch(ticker: str, series: pd.Series, train_ratio: float, out_dir: str) -> ModelResult:
    res = ModelResult(name="GARCH", summary="", metrics={}, warnings=[])
    if arch_model is None:
        res.warnings.append("arch (GARCH) no disponible")
        return res

    if isinstance(series, pd.DataFrame):
        if series.shape[1] > 0:
            series = series.iloc[:, 0]
        series = series.squeeze()

    # retornos log
    returns = np.log(series / series.shift(1)).dropna()
    train, test = _split_train_test(returns, train_ratio=train_ratio)
    if len(train) < 30 or len(test) < 10:
        res.warnings.append("Datos insuficientes para GARCH")
        return res

    try:
        model = arch_model(train * 100, vol="Garch", p=1, q=1, dist="normal")
        fitted = model.fit(disp="off")
        res.metrics["aic"] = float(fitted.aic)
        res.metrics["bic"] = float(fitted.bic)
        # forecast volatilidad condicional
        forecast = fitted.forecast(horizon=len(test))
        cond_var = forecast.variance.iloc[-1]
        cond_vol = np.sqrt(cond_var)
        # Alinear índices evitando mismatches: usa el tramo final común
        min_len = min(len(cond_vol), len(returns))
        cond_vol = cond_vol.iloc[-min_len:]
        ret_tail = returns.iloc[-min_len:]
        cond_vol.index = ret_tail.index
        img = _plot_garch_vol(ticker, ret_tail, cond_vol, out_dir)
        res.image_paths.append(img)
        res.summary = f"GARCH(1,1) ajustado; AIC={res.metrics['aic']:.2f}, BIC={res.metrics['bic']:.2f}"
    except Exception as exc:
        res.warnings.append(f"GARCH fall\u00f3: {exc}")
    return res


def run_coder_for_ticker(
    ticker: str,
    charts_root: str,
    lookback_days: int = 730,
    forecast_horizon: int = 75,
    train_ratio: float = 0.7,
) -> CoderResult:
    """
    Ejecuta el pipeline cuant para un ticker.
    """
    ticker = ticker.upper().strip()
    out_dir = os.path.join(charts_root, ticker)
    warnings: List[str] = []
    models: List[ModelResult] = []

    try:
        df = _download_ohlcv(ticker, lookback_days=lookback_days, interval="1d")
    except Exception as exc:
        return CoderResult(
            ticker=ticker,
            models=[],
            warnings=[f"Descarga yfinance fall\u00f3: {exc}"],
        )

    close = df["Close"].astype(float)
    if close.empty:
        return CoderResult(
            ticker=ticker,
            models=[],
            warnings=["Serie Close vac\u00eda tras limpieza"],
        )

    # ARIMA
    models.append(_fit_arima(ticker, close, train_ratio=train_ratio, forecast_horizon=forecast_horizon, out_dir=out_dir))

    # Prophet
    models.append(_fit_prophet(ticker, close, train_ratio=train_ratio, forecast_horizon=forecast_horizon, out_dir=out_dir))

    # GARCH
    models.append(_fit_garch(ticker, close, train_ratio=train_ratio, out_dir=out_dir))

    # Acumular warnings generales (modelo sin salida v\u00e1lida)
    valid_models = [m for m in models if m.summary]
    if not valid_models:
        warnings.append("Ning\u00fan modelo produjo salida v\u00e1lida; revisar datos o dependencias.")

    return CoderResult(
        ticker=ticker,
        models=models,
        warnings=warnings,
    )


def run_coder(
    tickers: List[str],
    charts_root: str,
    lookback_mode: str = "default",
    forecast_horizon: int = 75,
    train_ratio: float = 0.7,
) -> Dict[str, CoderResult]:
    """
    Ejecuta el Coder sobre una lista de tickers.

    lookback_mode:
      - "default": 2 a\u00f1os (~730 d\u00edas)
      - "largo": 5 a\u00f1os (~1825 d\u00edas)
    """
    lookback_days = 730 if lookback_mode != "largo" else 1825
    _ensure_dir(charts_root)
    out: Dict[str, CoderResult] = {}
    for t in tickers:
        out[t] = run_coder_for_ticker(
            ticker=t,
            charts_root=charts_root,
            lookback_days=lookback_days,
            forecast_horizon=forecast_horizon,
            train_ratio=train_ratio,
        )
    return out
