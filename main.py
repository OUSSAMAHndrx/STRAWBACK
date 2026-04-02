import backtrader as bt
import os
import pandas as pd
import numpy as np
from datetime import timedelta

# ==========================================
# 1. STRATEGY: XAUUSD SMC + ADVANCED TRACKING
# ==========================================
class GoldSMCQuant(bt.Strategy):
    params = (
        ('lookback', 30),
        ('atr_period', 14),
        ('risk_pct', 0.01),
        ('rr_target', 2.5),
    )

    def __init__(self):
        self.h1_high = bt.indicators.Highest(self.data0.high, period=self.p.lookback)
        self.h1_low = bt.indicators.Lowest(self.data0.low, period=self.p.lookback)
        self.atr = bt.indicators.ATR(self.data1, period=self.p.atr_period)
        
        # Streak tracking
        self.cur_win_streak = self.cur_loss_streak = 0
        self.max_win_streak = self.max_loss_streak = 0
        
        # Advanced Trade Log
        self.trade_log = []
        self.current_setup = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        
        # Streak Logic
        if trade.pnlcomm > 0:
            self.cur_win_streak += 1
            self.cur_loss_streak = 0
            self.max_win_streak = max(self.max_win_streak, self.cur_win_streak)
        else:
            self.cur_loss_streak += 1
            self.cur_win_streak = 0
            self.max_loss_streak = max(self.max_loss_streak, self.cur_loss_streak)
            
        # Log Trade for Advanced Stats
        open_time = self.data.num2date(trade.dtopen)
        close_time = self.data.num2date(trade.dtclose)
        
        self.trade_log.append({
            'pnl': trade.pnlcomm,
            'duration_bars': trade.barlen,
            'day_of_week': open_time.strftime('%A'),
            'hour_of_day': open_time.hour,
            'type': 'Long' if trade.size > 0 else 'Short'
        })

    def next(self):
        if self.position: return 

        price = self.data1.close[0]
        sl_dist = max(self.atr[0] * 2, 0.5) 
        risk_amt = self.broker.get_value() * self.p.risk_pct
        size = risk_amt / sl_dist

        # LONG
        if self.data0.close[0] > self.h1_high[-1]:
            if self.data1.low[0] < self.h1_high[-1] and self.data1.close[0] > self.h1_high[-1]:
                sl = price - sl_dist
                tp = price + (sl_dist * self.p.rr_target)
                self.buy_bracket(size=size, stopprice=sl, limitprice=tp)

        # SHORT
        elif self.data0.close[0] < self.h1_low[-1]:
            if self.data1.high[0] > self.h1_low[-1] and self.data1.close[0] < self.h1_low[-1]:
                sl = price + sl_dist
                tp = price - (sl_dist * self.p.rr_target)
                self.sell_bracket(size=size, stopprice=sl, limitprice=tp)

# ==========================================
# 2. BACKTEST ENGINE & STATS PROCESSING
# ==========================================
def run_gold_backtest():
    cerebro = bt.Cerebro()
    initial_cash = 10000.0
    
    csv_args = dict(dtformat='%Y-%m-%d %H:%M:%S', datetime=0, open=1, high=2, low=3, close=4, volume=5, openinterest=-1, headers=True)

    for tf in ['1H', '15m']:
        if not os.path.exists(f'XAUUSD_{tf}.csv'): 
            print(f"[!] File XAUUSD_{tf}.csv missing!")
            return
        data = bt.feeds.GenericCSVData(dataname=f'XAUUSD_{tf}.csv', **csv_args)
        cerebro.adddata(data)

    cerebro.addstrategy(GoldSMCQuant)
    
    # Analyzers
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="tr")
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="dd")
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.0)
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="timereturn") # For equity volatility & Sortino

    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=0.0005, margin=0.01, leverage=100.0)
    cerebro.broker.set_slippage_fixed(0.30, slip_open=True, slip_limit=False, slip_match=True, slip_out=True)

    results = cerebro.run()
    strat = results[0]
    
    # --- DATA EXTRACTION ---
    t = strat.analyzers.tr.get_analysis()
    d = strat.analyzers.dd.get_analysis()
    s = strat.analyzers.sharpe.get_analysis().get('sharperatio', 0)
    daily_returns = pd.Series(strat.analyzers.timereturn.get_analysis())
    
    total = t.total.total if 'total' in t.total else 0
    if total > 0:
        won = t.won.total if 'won' in t else 0
        lost = t.lost.total if 'lost' in t else 0
        pnl_total = cerebro.broker.getvalue() - initial_cash
        return_pct = (pnl_total / initial_cash) * 100
        
        gross_profit = t.won.pnl.total if 'won' in t else 0
        gross_loss = abs(t.lost.pnl.total) if 'lost' in t else 1
        prof_factor = gross_profit / gross_loss
        
        avg_win = t.won.pnl.average if won > 0 else 0
        avg_loss = abs(t.lost.pnl.average) if lost > 0 else 1
        
        max_dd = d.max.drawdown
        dd_duration = d.max.len # Max consecutive bars in drawdown
        
        # Advanced Ratios
        calmar = (return_pct / max_dd) if max_dd > 0 else 0
        
        # Sortino Ratio calculation
        # $Sortino = \frac{R_p - r_f}{\sigma_d}$
        downside_returns = daily_returns[daily_returns < 0]
        down_stdev = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 1
        annualized_return = daily_returns.mean() * 252
        sortino = annualized_return / down_stdev if down_stdev > 0 else 0
        
        eq_volatility = daily_returns.std() * np.sqrt(252) * 100 # Annualized equity volatility

        # Trade Log Processing
        tl = pd.DataFrame(strat.trade_log)
        avg_bars = tl['duration_bars'].mean()
        avg_duration_hrs = (avg_bars * 15) / 60
        
        best_day = tl.groupby('day_of_week')['pnl'].sum().idxmax()
        worst_day = tl.groupby('day_of_week')['pnl'].sum().idxmin()
        best_hour = tl.groupby('hour_of_day')['pnl'].sum().idxmax()
        
        print("\n" + "║" + "═"*55 + "║")
        print(f"║ {'QUANTITATIVE PERFORMANCE REPORT':^53} ║")
        print("║" + "═"*55 + "║")
        print(f"║ {'Net Profit:':<30} | ${pnl_total:<20.2f} ║")
        print(f"║ {'Return %:':<30} | {return_pct:<19.2f}% ║")
        print(f"║ {'Win Rate %:':<30} | {(won/total)*100:<19.2f}% ║")
        print(f"║ {'Profit Factor:':<30} | {prof_factor:<20.2f} ║")
        print(f"║ {'Max Drawdown %:':<30} | {max_dd:<19.2f}% ║")
        print(f"║ {'Max Drawdown Duration:':<30} | {dd_duration:<16} Bars ║")
        print("╟" + "─"*55 + "╢")
        print(f"║ {'Risk/Reward Ratio:':<30} | 1:{avg_win/avg_loss if avg_loss else 0:<18.2f} ║")
        print(f"║ {'Return / Drawdown (Calmar):':<30} | {calmar:<20.2f} ║")
        print(f"║ {'Sharpe Ratio:':<30} | {s if s else 0:<20.2f} ║")
        print(f"║ {'Sortino Ratio:':<30} | {sortino:<20.2f} ║")
        print(f"║ {'Expectancy / Trade:':<30} | ${pnl_total/total:<19.2f} ║")
        print("╟" + "─"*55 + "╢")
        print(f"║ {'Total Trades:':<30} | {total:<20} ║")
        print(f"║ {'Average Win:':<30} | ${avg_win:<19.2f} ║")
        print(f"║ {'Average Loss:':<30} | ${avg_loss:<19.2f} ║")
        print(f"║ {'Best Trade:':<30} | ${tl['pnl'].max():<19.2f} ║")
        print(f"║ {'Worst Trade:':<30} | ${tl['pnl'].min():<19.2f} ║")
        print(f"║ {'Avg Trade Duration:':<30} | {avg_duration_hrs:<15.1f} Hours ║")
        print(f"║ {'Consecutive Wins/Losses:':<30} | {strat.max_win_streak} W / {strat.max_loss_streak} L{'':<10} ║")
        print("╟" + "─"*55 + "╢")
        print(f"║ {'Best Day of Week:':<30} | {best_day:<20} ║")
        print(f"║ {'Worst Day of Week:':<30} | {worst_day:<20} ║")
        print(f"║ {'Most Profitable Hour (UTC):':<30} | {best_hour:<17}:00 ║")
        print(f"║ {'Equity Curve Volatility:':<30} | {eq_volatility:<19.2f}% ║")
        print("╚" + "═"*55 + "╝")
    else:
        print("\n[!] Zero trades detected.")

if __name__ == '__main__':
    run_gold_backtest()