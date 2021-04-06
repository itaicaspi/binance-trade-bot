#!python3

import os

import matplotlib.pyplot as plt
import numpy as np
import plyer

from binance_trade_bot.binance_api_manager import BinanceAPIManager
from binance_trade_bot.config import Config
from binance_trade_bot.database import Database
from binance_trade_bot.logger import Logger


def plot_trends(manager, axs):
    klines = manager.binance_client.get_historical_klines(symbol="WINUSDT", interval="15m",
                                                          start_str="2 day ago UTC", end_str="NOW")
    klines = np.array([[int(o[0]), float(o[2])] for o in klines])
    axs[0].plot(*klines.T, 'y')
    orders = manager.binance_client.get_all_orders(symbol="WINUSDT")
    # orders = [[o['time'], float(o['cummulativeQuoteQty'])] for o in orders]
    sells = [o['time'] for o in orders if o['side'] == "SELL"]
    sells_y = np.interp(sells, *np.array(klines).T)
    buys = [o['time'] for o in orders if o['side'] == "BUY"]
    buys_y = np.interp(buys, *np.array(klines).T)
    # axs[0].plot(buys, buys_y, '+r')
    # axs[0].plot(sells, sells_y, '+g')

    start_patch = 0
    end_patch = 0
    for i in range(len(orders)):
        if orders[i]['time'] < klines[0][0]:
            continue
        if orders[i]['side'] == "BUY":
            start_patch = i

        if orders[i]['side'] == "SELL":
            end_patch = i

            kline_start = np.argmax(klines.T[0] > orders[start_patch]['time'])
            kline_end = np.argmax(klines.T[0] > orders[end_patch]['time'])

            if kline_start == kline_end:
                kline_x = [orders[start_patch]['time'], orders[end_patch]['time']]
                kline_y = np.interp(kline_x, *np.array(klines).T)
                color = 'g' if kline_y[1] > kline_y[0] else 'r'
                axs[0].plot(kline_x, kline_y, color)
            else:
                color = 'g' if klines[kline_start:kline_end].T[1, 0] < klines[kline_start:kline_end].T[1, -1] else 'r'
                axs[0].plot(*klines[kline_start:kline_end].T, color)
        # if buys[0] < sells[0]:
        #     x = [buys[i], sells[i]]
        #     y = [buys_y[i], sells_y[i]]
        # else:
        #     x = [buys[i], sells[i+1]]
        #     y = [buys_y[i], sells_y[i+1]]
        # color = 'r' if y[1] < y[0] else 'g'
        # axs[0].plot(x, y, color)
        

def notify(text):
    os.system("osascript -e 'display notification \"{}\"\'".format(text))


def draw_coin(manager, symbol, axis, height=1e8, bar_width=0.0000003):
    order_book = manager.binance_client.get_order_book(symbol=symbol)
    bids_x, bids_y = np.array(order_book['bids']).astype(float).T
    asks_x, asks_y = np.array(order_book['asks']).astype(float).T
    axis.bar(bids_x, bids_y, bar_width, color='r')
    axis.bar(asks_x, asks_y, bar_width, color='g')
    axis.set_title(symbol)
    axis.set_ylim([0, height])
    return order_book


class SymbolData:
    def __init__(self):
        self.last_buy = None
        self.last_buy_price = None
        self.last_notify = None


def main():
    logger = Logger()
    logger.info("Starting")
    print(plyer.utils.platform)
    config = Config()
    db = Database(logger, config)
    manager = BinanceAPIManager(config, db, logger)

    coins = {
        "WINUSDT": {
            "height": 1e8,
            "bar_width": 0.0000003
        },
        "BTTUSDT": {
            "height": 2e7,
            "bar_width": 0.000001
        }
    }

    symbols_data = {symbol: SymbolData() for symbol in coins}


    index = 0
    fig, axes = plt.subplots(len(coins))
    if not isinstance(axes, np.ndarray):
        axes = [axes]

    while True:
        # plot_trends(manager, axs)

        for i, symbol in enumerate(coins):
            symbol_data = symbols_data[symbol]
            if index % 5 == 0:
                orders = manager.binance_client.get_all_orders(symbol=symbol)
                if orders[-1]['side'] == "BUY":
                    if symbol_data.last_buy is not None and symbol_data.last_buy['orderId'] != orders[-1]['orderId']:
                        notify("you have a new buy order")
                    symbol_data.last_buy = orders[-1]
                    symbol_data.last_buy_price = float(symbol_data.last_buy['origQuoteOrderQty'])

            order_book = draw_coin(manager, symbol, axes[i], coins[symbol]["height"], coins[symbol]["bar_width"])
        
            # notify me on barriers
            last_ask = order_book['asks'][0][0]
            if float(order_book['asks'][0][1]) > coins[symbol]["height"] / 5 and symbol_data.last_notify != last_ask:
                notify(f"{symbol} - ASK BARRIER! {last_ask}")
                symbol_data.last_notify = last_ask

            last_bid = order_book['bids'][0][0]
            if float(order_book['bids'][0][1]) > coins[symbol]["height"] / 5 and symbol_data.last_notify != last_bid:
                notify(f"{symbol} - BID BARRIER! {last_bid}")
                symbol_data.last_notify = last_bid

            # print price changes from last buy
            if symbol_data.last_buy:
                sell_value = float(order_book['bids'][0][0])
                sell_price = sell_value * float(symbol_data.last_buy['origQty'])
                fee = sell_price * 0.001
                sell_price -= fee
                change_dollar = (sell_price - symbol_data.last_buy_price)
                change_percentage = 100*change_dollar/symbol_data.last_buy_price
                last_buy_value = symbol_data.last_buy_price/float(symbol_data.last_buy['origQty'])
                print(f'buy: {round(symbol_data.last_buy_price, 2)} sell: {round(sell_price, 2)} change: {round(change_percentage, 2)}% '
                      f' {round(change_dollar, 2)}$ (buy value: {round(last_buy_value, 6)} sell value: {round(sell_value, 6)})')

        #
        if index < 1:
            plt.pause(1)
        else:
            if fig.canvas.figure.stale:
                fig.canvas.draw_idle()
            fig.canvas.start_event_loop(1)

        for i in range(len(coins)):
            axes[i].clear()

        index += 1


if __name__ == '__main__':
    main()