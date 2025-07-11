#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import math
import sys
import os

# 添加当前目录到路径
sys.path.append(os.path.abspath("."))

# 修改导入路径，适配 vnpy 4.x 版本
from vnpy_ctastrategy import (
    CtaTemplate,
    StopOrder,
)
from vnpy.trader.object import (
    TickData,
    BarData,
    TradeData,
    OrderData,
)
from vnpy.trader.utility import BarGenerator, ArrayManager
from vnpy.trader.constant import Interval, Direction, Status
from vnpy.trader.object import ContractData


class BtcTripleSignalStrategyMin(CtaTemplate):
    """
    BTC 三重信号策略 (分钟版)
    基于多个技术指标的比特币交易策略，使用分钟K线
    """
    
    author = "HangerLin"
    
    # 优化目标，这是vnpy 4.x版本优化引擎需要的属性
    target_name = "sharpe_ratio"  # 使用夏普率作为优化目标
    
    # 策略参数
    fast_window = 10       # 快速均线窗口
    slow_window = 20       # 慢速均线窗口
    signal_num = 1         # 信号数量阈值（三个信号中至少满足几个）
    fixed_size = 0.01      # 固定交易手数 (BTC)
    
    # RSI 参数
    rsi_length = 14        # RSI 计算周期
    rsi_buy_level = 30     # RSI 超卖买入阈值
    rsi_sell_level = 70    # RSI 超买卖出阈值
    
    # MACD 参数
    macd_fast_period = 12  # MACD 快线周期
    macd_slow_period = 26  # MACD 慢线周期
    macd_signal_period = 9 # MACD 信号线周期
    
    # KDJ 参数
    k_period = 14          # KDJ K值计算周期
    d_period = 3           # KDJ D值平滑周期
    slowing_period = 3     # KDJ 减缓周期
    
    # 风险管理参数
    stop_loss_pct = 0.05   # 止损百分比 (5%)
    
    # 策略变量
    fast_ma0 = 0.0        # 当前快速均线值
    fast_ma1 = 0.0        # 上一个快速均线值
    slow_ma0 = 0.0        # 当前慢速均线值
    slow_ma1 = 0.0        # 上一个慢速均线值
    
    ma_trend = 0          # 均线趋势：1为上升，-1为下降，0为横盘
    signal_count = 0      # 信号计数
    intra_trade_high = 0  # 持仓期间的最高价
    intra_trade_low = 0   # 持仓期间的最低价
    
    # 技术指标参数
    parameters = [
        "fast_window", 
        "slow_window", 
        "signal_num", 
        "fixed_size",
        "rsi_length",
        "rsi_buy_level",
        "rsi_sell_level",
        "macd_fast_period",
        "macd_slow_period", 
        "macd_signal_period",
        "k_period",
        "d_period",
        "slowing_period",
        "stop_loss_pct"
    ]
    
    # 状态变量
    variables = [
        "fast_ma0",
        "fast_ma1", 
        "slow_ma0",
        "slow_ma1",
        "ma_trend",
        "signal_count",
        "intra_trade_high",
        "intra_trade_low",
        "rsi_value",
        "macd_value",
        "k_value",
        "d_value",
        "last_k",
        "last_d",
        "entry_price",
        "bar_count",
        "last_price",
        "stoch_cross_over"
    ]
    
    @classmethod
    def generate_settings(cls):
        """
        生成策略优化参数设置
        这是vnpy 4.x版本优化引擎需要的方法
        """
        settings = []
        
        # 生成RSI买入阈值参数组合
        for rsi_buy_level in range(20, 45, 5):  # 20, 25, 30, 35, 40
            # 生成止损百分比参数组合
            for stop_loss_pct in [0.03, 0.04, 0.05, 0.06, 0.07, 0.08]:
                setting = {
                    "rsi_buy_level": rsi_buy_level,
                    "stop_loss_pct": stop_loss_pct
                }
                settings.append(setting)
                
        return settings

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """
        策略初始化
        """
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        
        # 创建K线生成器（直接使用1小时K线）
        self.bg = BarGenerator(self.on_bar, interval=Interval.MINUTE)
        
        # 创建数组管理器
        self.am = ArrayManager(200)
        
        # 初始化策略状态
        self.pos = 0
        
        # 参数会通过父类自动初始化，无需重复赋值
        
        # 初始化技术指标计算结果变量
        self.rsi_value = 0.0      # 最新RSI值
        self.macd_value = 0.0     # 最新MACD值
        self.k_value = 0.0        # 最新K值
        self.d_value = 0.0        # 最新D值
        self.last_k = 0.0         # 上一个Bar的K值
        self.last_d = 0.0         # 上一个Bar的D值
        
        # 初始化交易状态变量
        self.entry_price = 0.0    # 开仓成交价
        self.bar_count = 0        # 已处理的K线数量
        self.last_price = 0.0     # 最新价格（用于计算浮动盈亏）
        self.stoch_cross_over = False  # KDJ金叉状态
        
    def on_init(self):
        """
        策略初始化回调
        """
        self.write_log("策略初始化")
        
        # 计算安全的指标预热期，确保有足够的数据进行技术指标计算
        # 至少需要 MACD 慢线周期 + 信号线周期 的长度
        init_days = 5  # 假设每天有24小时数据，加载5天的数据即可满足MACD计算需求
        
        # 加载足够的历史数据进行指标预热
        self.load_bar(init_days)
        
        self.write_log(f"策略初始化完成，预热期：{init_days}天，数组管理器大小：200")
        
    def on_start(self):
        """
        策略启动回调
        """
        self.write_log("策略启动")
        self.write_log(f"合约代码：{self.vt_symbol}")
        self.write_log(f"策略名称：{self.strategy_name}")
        self.write_log(f"固定手数：{self.fixed_size}")
        self.write_log(f"止损百分比：{self.stop_loss_pct * 100}%")
        self.write_log(f"RSI参数：周期={self.rsi_length}, 买入={self.rsi_buy_level}, 卖出={self.rsi_sell_level}")
        self.write_log(f"MACD参数：快线={self.macd_fast_period}, 慢线={self.macd_slow_period}, 信号线={self.macd_signal_period}")
        self.write_log(f"KDJ参数：K周期={self.k_period}, D周期={self.d_period}, 减缓周期={self.slowing_period}")
        self.write_log(f"均线参数：快线={self.fast_window}, 慢线={self.slow_window}")
        self.write_log("策略启动完成，开始监控市场信号...")
        
        # 调试信息
        self.write_log(f"数组管理器初始化状态: {'已初始化' if self.am.inited else '未初始化'}")
        self.write_log(f"数组管理器当前数据量: {len(self.am.close_array)}")
        
        # 触发UI更新
        self.put_event()
        
    def on_stop(self):
        """
        策略停止回调
        """
        self.write_log("="*50)
        self.write_log("策略停止 - 运行统计报告")
        self.write_log("="*50)
        
        # 基础信息
        self.write_log(f"合约代码：{self.vt_symbol}")
        self.write_log(f"策略名称：{self.strategy_name}")
        
        # 当前状态
        self.write_log(f"当前仓位：{self.pos}")
        self.write_log(f"开仓价格：{self.entry_price}")
        self.write_log(f"信号计数：{self.signal_count}")
        self.write_log(f"K线计数：{self.bar_count}")
        
        # 技术指标当前值
        self.write_log(f"当前RSI值：{self.rsi_value:.2f}")
        self.write_log(f"当前MACD值：{self.macd_value:.4f}")
        self.write_log(f"当前K值：{self.k_value:.2f}")
        self.write_log(f"当前D值：{self.d_value:.2f}")
        self.write_log(f"KDJ金叉状态：{'是' if self.stoch_cross_over else '否'}")
        
        # 均线状态
        self.write_log(f"快速均线：{self.fast_ma0:.2f}")
        self.write_log(f"慢速均线：{self.slow_ma0:.2f}")
        if self.ma_trend == 1:
            trend_str = "上升趋势"
        elif self.ma_trend == -1:
            trend_str = "下降趋势"
        else:
            trend_str = "横盘整理"
        self.write_log(f"市场趋势：{trend_str}")
        
        # 持仓期间统计（如果有持仓）
        if self.pos != 0:
            self.write_log(f"持仓期间最高价：{self.intra_trade_high:.2f}")
            self.write_log(f"持仓期间最低价：{self.intra_trade_low:.2f}")
            
            # 计算止盈止损价格
            if self.pos > 0:  # 多头仓位
                stop_loss_price = self.entry_price * (1 - self.stop_loss_pct)
                self.write_log(f"多头止损价格：{stop_loss_price:.2f}")
                self.write_log(f"RSI止盈阈值：{self.rsi_sell_level}")
            else:  # 空头仓位
                stop_loss_price = self.entry_price * (1 + self.stop_loss_pct)
                self.write_log(f"空头止损价格：{stop_loss_price:.2f}")
                self.write_log(f"RSI止盈阈值：{self.rsi_buy_level}")

    def on_tick(self, tick: TickData):
        """
        Tick数据回调
        """
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        K线数据回调
        """
        # 更新K线计数
        self.bar_count += 1
        
        # 更新最新价格
        self.last_price = bar.close_price
        
        # 更新Array Manager
        am = self.am
        am.update_bar(bar)
        
        # 如果K线数据不足，等待更多数据
        if not am.inited:
            self.put_event()  # 更新UI显示
            return
            
        # 计算技术指标
        self.calculate_indicators()
        
        # 生成交易信号
        self.generate_signals(bar)
        
        # 更新图形界面
        self.put_event()

    def calculate_indicators(self):
        """
        计算技术指标
        """
        am = self.am
        
        # 计算均线
        try:
            # 确保有足够的数据
            if len(am.close_array) > max(self.fast_window, self.slow_window):
                fast_ma = am.sma(self.fast_window, array=True)
                slow_ma = am.sma(self.slow_window, array=True)
                
                # 保存上一次的均线值
                self.fast_ma1 = self.fast_ma0
                self.slow_ma1 = self.slow_ma0
                
                # 更新当前均线值
                if len(fast_ma) > 0 and len(slow_ma) > 0:
                    self.fast_ma0 = fast_ma[-1]
                    self.slow_ma0 = slow_ma[-1]
                    
                    # 确定趋势方向
                    if self.fast_ma0 > self.slow_ma0:
                        self.ma_trend = 1  # 上升趋势
                    elif self.fast_ma0 < self.slow_ma0:
                        self.ma_trend = -1  # 下降趋势
                    else:
                        self.ma_trend = 0  # 横盘整理
        except Exception as e:
            self.write_log(f"计算均线异常: {e}")
            
        # 计算RSI
        try:
            if len(am.close_array) > self.rsi_length:
                rsi = am.rsi(self.rsi_length)
                if rsi is not None:
                    self.rsi_value = rsi
        except Exception as e:
            self.write_log(f"计算RSI异常: {e}")
            
        # 计算MACD
        try:
            if len(am.close_array) > self.macd_slow_period + self.macd_signal_period:
                macd, signal, hist = am.macd(
                    self.macd_fast_period,
                    self.macd_slow_period,
                    self.macd_signal_period,
                    array=True
                )
                if len(hist) > 0:
                    self.macd_value = hist[-1]
        except Exception as e:
            self.write_log(f"计算MACD异常: {e}")
            
        # 计算KDJ
        try:
            if len(am.high_array) > self.k_period and len(am.low_array) > self.k_period:
                k, d = am.stoch(
                    self.k_period, 
                    self.d_period, 
                    self.slowing_period
                )
                # 保存上一个K和D值
                self.last_k = self.k_value
                self.last_d = self.d_value
                
                # 更新当前K和D值
                self.k_value = k
                self.d_value = d
                
                # 判断KDJ金叉和死叉
                if self.last_k is not None and self.last_d is not None:
                    # 金叉：K线从下方突破D线
                    if self.last_k < self.last_d and k > d:
                        self.stoch_cross_over = True
                    # 死叉：K线从上方跌破D线
                    elif self.last_k > self.last_d and k < d:
                        self.stoch_cross_over = False
        except Exception as e:
            self.write_log(f"计算KDJ异常: {e}")

    def generate_signals(self, bar: BarData):
        """
        生成交易信号
        """
        # 初始化信号计数
        self.signal_count = 0
        
        # === 1. RSI信号 ===
        rsi_signal = 0
        if self.rsi_value <= self.rsi_buy_level:
            rsi_signal = 1  # 买入信号
        elif self.rsi_value >= self.rsi_sell_level:
            rsi_signal = -1  # 卖出信号
        
        if rsi_signal != 0:
            self.signal_count += 1
            
        # === 2. MACD信号 ===
        macd_signal = 0
        if self.macd_value > 0:
            macd_signal = 1  # 买入信号
        elif self.macd_value < 0:
            macd_signal = -1  # 卖出信号
            
        if macd_signal != 0:
            self.signal_count += 1
            
        # === 3. KDJ信号 ===
        kdj_signal = 0
        if self.stoch_cross_over:
            kdj_signal = 1  # 买入信号
        elif not self.stoch_cross_over and self.k_value > 80:
            kdj_signal = -1  # 卖出信号
            
        if kdj_signal != 0:
            self.signal_count += 1
            
        # === 综合信号判断 ===
        # 无仓位时，需要开仓条件：
        if self.pos == 0:
            # 多头开仓条件：至少有signal_num个买入信号，且均线趋势向上
            if (rsi_signal + kdj_signal + macd_signal) >= self.signal_num:
                self.buy(bar.close_price, self.fixed_size)
                self.entry_price = bar.close_price
                self.intra_trade_high = bar.close_price
                self.intra_trade_low = bar.close_price
                
                self.write_log(f"开多仓: 价格={bar.close_price:.2f}, 数量={self.fixed_size}")
                self.write_log(f"信号: RSI={self.rsi_value:.2f}, MACD={self.macd_value:.4f}, K={self.k_value:.2f}, D={self.d_value:.2f}")
                
            # 空头开仓条件：至少有signal_num个卖出信号，且均线趋势向下
            elif (rsi_signal + kdj_signal + macd_signal) <= -self.signal_num:
                self.short(bar.close_price, self.fixed_size)
                self.entry_price = bar.close_price
                self.intra_trade_high = bar.close_price
                self.intra_trade_low = bar.close_price
                
                self.write_log(f"开空仓: 价格={bar.close_price:.2f}, 数量={self.fixed_size}")
                self.write_log(f"信号: RSI={self.rsi_value:.2f}, MACD={self.macd_value:.4f}, K={self.k_value:.2f}, D={self.d_value:.2f}")
                
        # 持有多头仓位
        elif self.pos > 0:
            # 更新最高价
            self.intra_trade_high = max(self.intra_trade_high, bar.high_price)
            self.intra_trade_low = min(self.intra_trade_low, bar.low_price)
            
            # 止损条件：当前价格跌破止损线
            stop_loss_price = self.entry_price * (1 - self.stop_loss_pct)
            if bar.close_price <= stop_loss_price:
                self.sell(bar.close_price, abs(self.pos))
                self.write_log(f"多头止损: 开仓价={self.entry_price:.2f}, 止损价={bar.close_price:.2f}, 止损比例={self.stop_loss_pct*100:.2f}%")
                
            # 止盈条件：RSI达到超买区域
            elif self.rsi_value >= self.rsi_sell_level:
                self.sell(bar.close_price, abs(self.pos))
                self.write_log(f"多头止盈: 开仓价={self.entry_price:.2f}, 止盈价={bar.close_price:.2f}, RSI={self.rsi_value:.2f}")
                
            # 其他离场信号：三个技术指标都是卖出信号
            elif (rsi_signal + kdj_signal + macd_signal) <= -self.signal_num:
                self.sell(bar.close_price, abs(self.pos))
                self.write_log(f"多头离场: 价格={bar.close_price:.2f}, 技术指标转为卖出信号")
                
        # 持有空头仓位
        elif self.pos < 0:
            # 更新最高价和最低价
            self.intra_trade_high = max(self.intra_trade_high, bar.high_price)
            self.intra_trade_low = min(self.intra_trade_low, bar.low_price)
            
            # 止损条件：当前价格突破止损线
            stop_loss_price = self.entry_price * (1 + self.stop_loss_pct)
            if bar.close_price >= stop_loss_price:
                self.cover(bar.close_price, abs(self.pos))
                self.write_log(f"空头止损: 开仓价={self.entry_price:.2f}, 止损价={bar.close_price:.2f}, 止损比例={self.stop_loss_pct*100:.2f}%")
                
            # 止盈条件：RSI达到超卖区域
            elif self.rsi_value <= self.rsi_buy_level:
                self.cover(bar.close_price, abs(self.pos))
                self.write_log(f"空头止盈: 开仓价={self.entry_price:.2f}, 止盈价={bar.close_price:.2f}, RSI={self.rsi_value:.2f}")
                
            # 其他离场信号：三个技术指标都是买入信号
            elif (rsi_signal + kdj_signal + macd_signal) >= self.signal_num:
                self.cover(bar.close_price, abs(self.pos))
                self.write_log(f"空头离场: 价格={bar.close_price:.2f}, 技术指标转为买入信号")

    def on_order(self, order: OrderData):
        """
        订单状态更新
        """
        pass

    def on_trade(self, trade: TradeData):
        """
        成交回报
        """
        # 更新持仓，虽然底层已经会更新，这里再次显式更新是为了确保准确性
        if trade.direction == Direction.LONG:
            self.pos += trade.volume
        else:
            self.pos -= trade.volume
            
        # 记录开仓价格
        if abs(self.pos) == trade.volume:
            self.entry_price = trade.price
            
        self.write_log(f"成交回报: 方向={'多' if trade.direction == Direction.LONG else '空'}, 价格={trade.price:.2f}, 数量={trade.volume}, 当前持仓={self.pos}")
        
        # 更新UI
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        停止单状态更新
        """
        pass 