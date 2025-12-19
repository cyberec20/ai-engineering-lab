import os
import sys
import pandas as pd
import numpy as np
import datetime as dt

# Asegurar que Session3_4 esté en el path para importar crew.*
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from crew import coder


class FakeArimaModel:
    def __init__(self, series):
        self._last = series.iloc[-1]
        self.order = (1, 0, 0)

    def fit(self, series):
        return self

    def predict(self, n_periods):
        return np.array([self._last] * n_periods)

    def aic(self):
        return 100.0

    def bic(self):
        return 110.0


class FakeProphet:
    def __init__(self, *args, **kwargs):
        pass

    def fit(self, df):
        self.df = df
        return self

    def make_future_dataframe(self, periods, freq="D"):
        last = self.df["ds"].iloc[-1]
        future_dates = pd.date_range(start=last, periods=periods + 1, freq=freq)[1:]
        future = pd.DataFrame({"ds": future_dates})
        return pd.concat([self.df[["ds"]], future], ignore_index=True)

    def predict(self, df):
        # yhat = último valor conocido
        last = float(self.df["y"].iloc[-1])
        return pd.DataFrame({"ds": df["ds"], "yhat": [last] * len(df)})


class FakeArchFit:
    def __init__(self, returns):
        self.returns = returns
        self.aic = 50.0
        self.bic = 55.0

    def forecast(self, horizon):
        # Varianza constante
        idx = range(horizon)
        var = pd.DataFrame([0.01] * horizon, index=idx)
        return type("Forecast", (), {"variance": var})


class FakeArchModel:
    def __init__(self, returns, **kwargs):
        self.returns = returns

    def fit(self, disp="off"):
        return FakeArchFit(self.returns)


def _mock_download(ticker: str, lookback_days: int, interval: str = "1d") -> pd.DataFrame:
    dates = pd.date_range(end=dt.date.today(), periods=150, freq="D")
    close = np.linspace(100, 110, num=len(dates))
    return pd.DataFrame({"Close": close}, index=dates)


def test_run_coder_for_ticker_with_mocks(tmp_path, monkeypatch):
    # Mocks para evitar dependencias pesadas y redes
    monkeypatch.setattr(coder, "_download_ohlcv", _mock_download)
    monkeypatch.setattr(coder, "pm", type("PM", (), {"auto_arima": lambda series, **kw: FakeArimaModel(series)}))
    monkeypatch.setattr(coder, "Prophet", FakeProphet)
    monkeypatch.setattr(coder, "arch_model", FakeArchModel)

    result = coder.run_coder_for_ticker(
        ticker="AAPL",
        charts_root=str(tmp_path),
        lookback_days=60,
        forecast_horizon=10,
        train_ratio=0.7,
    )

    assert result.warnings == []
    assert result.ticker == "AAPL"
    assert result.models, "Debe contener modelos"
    # Cada modelo debe tener summary o warnings específicos
    for m in result.models:
        assert m.summary or m.warnings is not None


def test_create_pdf_report(tmp_path):
    # Verifica que create_pdf_report genera un archivo PDF sin errores con texto simple.
    from crew.pdf_report import create_pdf_report

    out_dir = tmp_path / "reports"
    out_dir.mkdir()
    pdf_path = create_pdf_report(
        tickers=["TEST"],
        final_text="Informe de prueba\nLinea 2\nBullet: item",
        images_by_ticker={"TEST": []},
        output_dir=str(out_dir),
    )
    assert os.path.exists(pdf_path)
