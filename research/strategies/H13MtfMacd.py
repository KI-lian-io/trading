"""H13: Bitcoin multi-timeframe MACD trend (Quantpedia 2025, "D1H1 + Stop" version).

Entry: 1h MACD(12, 26, 9) crosses above its signal while the last closed daily
MACD(12, 26, 9) is above its signal. Exit: first 1h candle that closes below its
open. Long-only, no other stop. Rules are fixed by the article; do not tune.
"""

import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import IStrategy, informative
from technical import qtpylib


class H13MtfMacd(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False
    minimal_roi = {"0": 100}
    stoploss = -0.99
    use_exit_signal = True
    process_only_new_candles = True
    # 1d MACD(26) + signal(9) needs ~35 daily candles; give EMAs room to settle
    startup_candle_count = 24 * 120

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe["macd"] = macd["macd"]
        dataframe["macdsignal"] = macd["macdsignal"]
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe["macd"] = macd["macd"]
        dataframe["macdsignal"] = macd["macdsignal"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            qtpylib.crossed_above(dataframe["macd"], dataframe["macdsignal"])
            & (dataframe["macd_1d"] > dataframe["macdsignal_1d"])
            & (dataframe["volume"] > 0),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["close"] < dataframe["open"], "exit_long"] = 1
        return dataframe
