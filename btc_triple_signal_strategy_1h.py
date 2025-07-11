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


class BtcTripleSignalStrategy1h(CtaTemplate):
    """
    BTC 三重信号策略 (1小时版)
    基于多个技术指标的比特币交易策略，使用1小时K线
    """
    
    author = "HangerLin"
    
    # 优化目标，这是vnpy 4.x版本优化引擎需要的属性
    target_name = "sharpe_ratio"  # 使用夏普率作为优化目标
    
    # 策略参数
    fast_window = 10       # 快速均线窗口
    slow_window = 20       # 慢速均线窗口
    signal_num = 2         # 信号数量阈值（三个信号中至少满足几个）- 提高到2，确保多指标共振
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
    stop_loss_pct = 0.05   # 初始止损百分比 (5%)
    trailing_stop_pct = 0.03  # 移动止损回撤百分比 (3%)
    trailing_stop_activation_pct = 0.01  # 移动止损激活利润百分比 (1%)
    slippage_tolerance_pct = 0.001  # 滑点容忍百分比 (0.1%)
    
    # 【新增】ATR 止损参数
    atr_length = 14          # ATR 计算周期
    atr_multiplier = 2.5     # ATR 止损倍数（可优化）
    
    # 【新增】ADX 趋势过滤参数
    adx_length = 14          # ADX 计算周期
    adx_threshold = 20       # ADX 趋势强度阈值（低于此值不开仓）
    
    # 【新增】成交量过滤参数
    volume_window = 20       # 计算平均成交量的周期
    volume_multiplier = 1.2  # 成交量必须是平均值的多少倍
    
    # 策略变量
    fast_ma0 = 0.0        # 当前快速均线值
    fast_ma1 = 0.0        # 上一个快速均线值
    slow_ma0 = 0.0        # 当前慢速均线值
    slow_ma1 = 0.0        # 上一个慢速均线值
    
    ma_trend = 0          # 均线趋势：1为上升，-1为下降，0为横盘
    signal_count = 0      # 信号计数
    intra_trade_high = 0  # 持仓期间的最高价
    intra_trade_low = 0   # 持仓期间的最低价
    trailing_stop_price = 0.0  # 移动止损价格
    atr_value = 0.0       # 【新增】ATR 值变量
    adx_value = 0.0       # 【新增】ADX 值变量
    
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
        "stop_loss_pct",
        "trailing_stop_pct",
        "trailing_stop_activation_pct",
        "slippage_tolerance_pct",
        "atr_length",      # 【新增】ATR周期参数
        "atr_multiplier",   # 【新增】ATR倍数参数
        "adx_length",      # 【新增】ADX周期参数
        "adx_threshold",    # 【新增】ADX阈值参数
        "volume_window",    # 【新增】成交量窗口参数
        "volume_multiplier" # 【新增】成交量倍数参数
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
        "stoch_cross_over",
        "trailing_stop_price",
        "atr_value",        # 【新增】ATR值变量
        "adx_value"         # 【新增】ADX值变量
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
        self.bg = BarGenerator(self.on_bar, interval=Interval.HOUR)
        
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
        
        # 滑点控制变量
        self.last_tick = None     # 最新的Tick数据
        
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
        self.write_log(f"初始止损百分比：{self.stop_loss_pct * 100}%")
        self.write_log(f"移动止损回撤百分比：{self.trailing_stop_pct * 100}%")
        self.write_log(f"移动止损激活阈值：{self.trailing_stop_activation_pct * 100}%")
        self.write_log(f"滑点容忍百分比：{self.slippage_tolerance_pct * 100}%")
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
            self.write_log(f"当前移动止损价：{self.trailing_stop_price:.2f}")
            
            # 计算止盈止损价格
            if self.pos > 0:  # 多头仓位
                initial_stop_loss_price = self.entry_price * (1 - self.stop_loss_pct)
                self.write_log(f"多头初始止损价格：{initial_stop_loss_price:.2f}")
                self.write_log(f"多头移动止损价格：{self.trailing_stop_price:.2f}")
                self.write_log(f"RSI止盈阈值：{self.rsi_sell_level}")
                
                # 计算移动止损激活条件
                activation_price = self.entry_price * (1 + self.trailing_stop_activation_pct)
                self.write_log(f"移动止损激活价格：{activation_price:.2f}")
                if self.last_price > activation_price:
                    self.write_log(f"移动止损已激活")
                else:
                    self.write_log(f"移动止损未激活，当前价格需要上涨至{activation_price:.2f}")
                
            else:  # 空头仓位
                initial_stop_loss_price = self.entry_price * (1 + self.stop_loss_pct)
                self.write_log(f"空头初始止损价格：{initial_stop_loss_price:.2f}")
                self.write_log(f"空头移动止损价格：{self.trailing_stop_price:.2f}")
                self.write_log(f"RSI止盈阈值：{self.rsi_buy_level}")
                
                # 计算移动止损激活条件
                activation_price = self.entry_price * (1 - self.trailing_stop_activation_pct)
                self.write_log(f"移动止损激活价格：{activation_price:.2f}")
                if self.last_price < activation_price:
                    self.write_log(f"移动止损已激活")
                else:
                    self.write_log(f"移动止损未激活，当前价格需要下跌至{activation_price:.2f}")
            
            # 计算浮动盈亏（需要当前价格，这里用最后已知价格估算）
            if hasattr(self, 'last_price') and self.last_price > 0 and self.entry_price > 0:
                if self.pos > 0:  # 多头仓位
                    unrealized_pnl = (self.last_price - self.entry_price) * abs(self.pos)
                    pnl_pct = (self.last_price - self.entry_price) / self.entry_price * 100
                else:  # 空头仓位
                    unrealized_pnl = (self.entry_price - self.last_price) * abs(self.pos)
                    pnl_pct = (self.entry_price - self.last_price) / self.entry_price * 100
                
                self.write_log(f"浮动盈亏：{unrealized_pnl:.4f} ({pnl_pct:.2f}%)")
                
                # 距离止损的风险评估
                if self.pos > 0:
                    risk_distance = ((self.last_price - self.trailing_stop_price) / self.last_price) * 100
                    self.write_log(f"距止损距离：{risk_distance:.2f}%")
                else:
                    risk_distance = ((self.trailing_stop_price - self.last_price) / self.last_price) * 100
                    self.write_log(f"距止损距离：{risk_distance:.2f}%")
        
        # 策略参数总结
        self.write_log("-" * 30)
        self.write_log("策略参数总结：")
        self.write_log(f"固定手数：{self.fixed_size}")
        self.write_log(f"初始止损百分比：{self.stop_loss_pct * 100}%")
        self.write_log(f"移动止损回撤百分比：{self.trailing_stop_pct * 100}%")
        self.write_log(f"移动止损激活阈值：{self.trailing_stop_activation_pct * 100}%")
        self.write_log(f"滑点容忍百分比：{self.slippage_tolerance_pct * 100}%")
        self.write_log(f"RSI参数：{self.rsi_length}/{self.rsi_buy_level}/{self.rsi_sell_level}")
        self.write_log(f"MACD参数：{self.macd_fast_period}/{self.macd_slow_period}/{self.macd_signal_period}")
        self.write_log(f"KDJ参数：{self.k_period}/{self.d_period}/{self.slowing_period}")
        self.write_log(f"均线参数：{self.fast_window}/{self.slow_window}")
        
        self.write_log("="*50)
        self.write_log("策略已停止，感谢使用BTC三重信号策略")
        self.write_log("="*50)
        
        # 触发UI更新
        self.put_event()
        
    def on_tick(self, tick: TickData):
        """
        Tick数据更新回调
        """
        # 保存最新的Tick数据用于滑点控制
        self.last_tick = tick
        
        # 更新K线
        self.bg.update_tick(tick)
        
    def on_bar(self, bar: BarData):
        """
        K线数据更新回调 - 1小时K线直接处理
        """
        # 每个新K线开始时取消所有挂单
        self.cancel_all()
        
        self.bar_count += 1
        self.last_price = bar.close_price
        
        # 更新最高价/最低价
        if self.pos > 0:
            self.intra_trade_high = max(self.intra_trade_high, bar.high_price)
        elif self.pos < 0:
            self.intra_trade_low = min(self.intra_trade_low, bar.low_price)
            
        # 更新技术指标
        am = self.am
        am.update_bar(bar)
        
        # 每隔100个bar输出一次调试信息
        if self.bar_count % 100 == 0:
            self.write_log(f"处理第{self.bar_count}个K线，价格={bar.close_price:.2f}")
            self.write_log(f"数组管理器初始化状态: {'已初始化' if am.inited else '未初始化'}")
        
        # 只有当数组管理器初始化后才计算指标和生成信号
        if am.inited:
            # 计算技术指标
            self.calculate_indicators()
            
            # 如果数组管理器已初始化，每隔100个bar输出一次指标值
            if self.bar_count % 100 == 0:
                self.write_log(f"技术指标值: RSI={self.rsi_value:.2f}, MACD={self.macd_value:.4f}, KDJ=({self.k_value:.2f},{self.d_value:.2f})")
                self.write_log(f"均线值: 快线={self.fast_ma0:.2f}, 慢线={self.slow_ma0:.2f}, 趋势={self.ma_trend}")
            
            # 生成交易信号
            self.generate_signals(bar)
        else:
            # 数据预热中
            if self.bar_count % 10 == 0:
                self.write_log(f"数据预热中，当前数据量: {len(am.close_array)}")
        
        # 触发UI更新
        self.put_event()
        
    def calculate_indicators(self):
        """
        计算技术指标
        """
        # 如果数组管理器未初始化，则直接返回
        am = self.am
        if not am.inited:
            return
            
        # 计算均线
        self.fast_ma1 = self.fast_ma0
        self.slow_ma1 = self.slow_ma0
        self.fast_ma0 = am.sma(self.fast_window, array=False)
        self.slow_ma0 = am.sma(self.slow_window, array=False)
        
        # 计算均线趋势
        if self.fast_ma0 > self.slow_ma0:
            self.ma_trend = 1  # 上升趋势
        elif self.fast_ma0 < self.slow_ma0:
            self.ma_trend = -1  # 下降趋势
        else:
            self.ma_trend = 0  # 横盘整理
        
        # 计算RSI
        self.rsi_value = am.rsi(self.rsi_length, array=False)
        
        # 计算MACD
        macd, signal, hist = am.macd(
            self.macd_fast_period, 
            self.macd_slow_period, 
            self.macd_signal_period, 
            array=False
        )
        self.macd_value = hist  # 使用MACD柱状图作为信号
        
        # 计算KDJ
        self.last_k = self.k_value
        self.last_d = self.d_value
        self.k_value, self.d_value = am.stoch(
            self.k_period,       # fastk_period
            self.slowing_period, # slowk_period
            0,                   # slowk_matype
            self.d_period,       # slowd_period
            0,                   # slowd_matype
            array=False
        )
        
        # 判断KDJ金叉
        if self.last_k < self.last_d and self.k_value > self.d_value:
            self.stoch_cross_over = True
        # 判断KDJ死叉
        elif self.last_k > self.last_d and self.k_value < self.d_value:
            self.stoch_cross_over = False
            
        # 【新增】计算ATR
        self.atr_value = am.atr(self.atr_length, array=False)
        
        # 【新增】计算ADX
        self.adx_value = am.adx(self.adx_length, array=False)

    def manage_long_position(self, bar: BarData):
        """
        管理多头持仓
        """
        # 【修改】使用ATR计算动态止损价
        atr_stop_price = bar.close_price - self.atr_value * self.atr_multiplier
        
        # 检查是否达到移动止损激活阈值
        if bar.close_price > self.entry_price * (1 + self.trailing_stop_activation_pct):
            # 【修改】根据持仓期间最高价和ATR计算新的止损价
            new_stop_price = self.intra_trade_high - self.atr_value * self.atr_multiplier
            
            # 只有当新的止损价更优（更高）时才更新止损价
            if new_stop_price > self.trailing_stop_price:
                old_stop = self.trailing_stop_price
                self.trailing_stop_price = new_stop_price
                self.write_log(f"更新多头移动ATR止损价：{old_stop:.2f} -> {self.trailing_stop_price:.2f} (最高价：{self.intra_trade_high:.2f}, ATR：{self.atr_value:.2f})")
        
        # 止损：价格跌破止损线
        if bar.close_price <= self.trailing_stop_price:
            self.controlled_sell(abs(self.pos))
            self.write_log(f"多头止损/移动止损：价格={bar.close_price:.2f}, 止损价={self.trailing_stop_price:.2f}, ATR={self.atr_value:.2f}")
            return True
            
        # 止盈（RSI超买区域）
        elif self.rsi_value >= self.rsi_sell_level:
            self.controlled_sell(abs(self.pos))
            self.write_log(f"多头止盈：价格={bar.close_price:.2f}, RSI={self.rsi_value:.2f}")
            return True
            
        # 信号反转（有足够的空头信号）
        elif (self.signal_count >= self.signal_num and 
              self.ma_trend == -1):
            self.controlled_sell(abs(self.pos))
            self.write_log(f"多头反转平仓：价格={bar.close_price:.2f}, 信号数={self.signal_count}")
            return True
            
        return False  # 未平仓
        
    def manage_short_position(self, bar: BarData):
        """
        管理空头持仓
        """
        # 【修改】使用ATR计算动态止损价
        atr_stop_price = bar.close_price + self.atr_value * self.atr_multiplier
        
        # 检查是否达到移动止损激活阈值
        if bar.close_price < self.entry_price * (1 - self.trailing_stop_activation_pct):
            # 【修改】根据持仓期间最低价和ATR计算新的止损价
            new_stop_price = self.intra_trade_low + self.atr_value * self.atr_multiplier
            
            # 只有当新的止损价更优（更低）时才更新止损价
            if self.trailing_stop_price == 0 or new_stop_price < self.trailing_stop_price:
                old_stop = self.trailing_stop_price
                self.trailing_stop_price = new_stop_price
                self.write_log(f"更新空头移动ATR止损价：{old_stop:.2f} -> {self.trailing_stop_price:.2f} (最低价：{self.intra_trade_low:.2f}, ATR：{self.atr_value:.2f})")
        
        # 止损：价格涨破止损线
        if bar.close_price >= self.trailing_stop_price:
            self.controlled_cover(abs(self.pos))
            self.write_log(f"空头止损/移动止损：价格={bar.close_price:.2f}, 止损价={self.trailing_stop_price:.2f}, ATR={self.atr_value:.2f}")
            return True
            
        # 止盈（RSI超卖区域）
        elif self.rsi_value <= self.rsi_buy_level:
            self.controlled_cover(abs(self.pos))
            self.write_log(f"空头止盈：价格={bar.close_price:.2f}, RSI={self.rsi_value:.2f}")
            return True
            
        # 信号反转（有足够的多头信号）
        elif (self.signal_count >= self.signal_num and 
              self.ma_trend == 1):
            self.controlled_cover(abs(self.pos))
            self.write_log(f"空头反转平仓：价格={bar.close_price:.2f}, 信号数={self.signal_count}")
            return True
            
        return False  # 未平仓
    
    def generate_signals(self, bar: BarData):
        """
        生成交易信号 - 采用分层过滤逻辑
        """
        # 如果数组管理器未初始化，则直接返回
        if not self.am.inited:
            return

        # --- 持仓管理优先 ---
        # 如果有持仓，首先执行持仓管理逻辑，并在此之后结束函数，不再考虑开仓
        if self.pos > 0:
            self.manage_long_position(bar)
            return  # 管理完持仓后直接返回
        elif self.pos < 0:
            self.manage_short_position(bar)
            return  # 管理完持仓后直接返回
            
        # --- 以下是开仓逻辑，只有在 self.pos == 0 时才会执行 ---

        # 【第1层：市场状态过滤器】 - 最高优先级
        if self.adx_value < self.adx_threshold:
            # self.write_log(f"第1层过滤: ADX({self.adx_value:.2f}) < 阈值({self.adx_threshold})，市场无趋势，暂停交易。")
            return  # 提前退出，不进行后续判断

        # 【第2层：交易方向过滤器】 - 中等优先级
        # (此处的均线趋势 ma_trend 在 calculate_indicators 中已计算好)
        ma_signal = self.ma_trend
        if ma_signal == 0:
            # self.write_log("第2层过滤: 均线趋势不明，暂停交易。")
            return # 均线方向不明，不交易

        # --- 如果能通过前两层过滤，说明市场既有趋势，方向也明确，值得寻找交易机会 ---
        self.write_log(f"通过前两层过滤: ADX={self.adx_value:.2f}, 均线趋势={ma_signal}。准备寻找入场点...")

        # 【第3层：入场时机触发器】 - 最低优先级
        
        # a. 计算入场信号 (RSI/MACD/KDJ)
        rsi_signal = 1 if self.rsi_value <= self.rsi_buy_level else (-1 if self.rsi_value >= self.rsi_sell_level else 0)
        macd_signal = 1 if self.macd_value > 0 else (-1 if self.macd_value < 0 else 0)
        # 简化KDJ信号逻辑：金叉为买入，死叉为卖出
        kdj_signal = 1 if self.stoch_cross_over else (-1 if (not self.stoch_cross_over and self.k_value > 80 and self.d_value > 80) else 0)
        
        long_signals = (rsi_signal == 1) + (macd_signal == 1) + (kdj_signal == 1)
        short_signals = (rsi_signal == -1) + (macd_signal == -1) + (kdj_signal == -1)
        
        # b. 成交量确认
        volume_ma = self.am.volume_array[-self.volume_window:].mean()
        volume_check_passed = bar.volume > (volume_ma * self.volume_multiplier)
        if not volume_check_passed:
            # self.write_log(f"第3层过滤: 成交量确认失败，暂停交易。")
            return

        # --- 最终决策 ---
        # 结合方向(第2层)和时机(第3层)进行开仓
        
        # 寻找多头机会
        if ma_signal == 1:
            if long_signals >= self.signal_num:
                self.write_log(f"最终决策: 多头开仓。信号数({long_signals}) >= 阈值({self.signal_num})")
                self.write_log(f"成交量确认通过: 当前 {bar.volume:.2f} > 均值*倍数 {volume_ma * self.volume_multiplier:.2f}")
                self.write_log(f"信号详情：RSI={self.rsi_value:.2f}({rsi_signal}), MACD={self.macd_value:.4f}({macd_signal}), KDJ金叉={self.stoch_cross_over}({kdj_signal})")
                self.controlled_buy(self.fixed_size)
                self.entry_price = bar.close_price
                self.intra_trade_high = bar.high_price
            # else:
                # self.write_log("等待多头入场信号...")

        # 寻找空头机会
        elif ma_signal == -1:
            if short_signals >= self.signal_num:
                self.write_log(f"最终决策: 空头开仓。信号数({short_signals}) >= 阈值({self.signal_num})")
                self.write_log(f"成交量确认通过: 当前 {bar.volume:.2f} > 均值*倍数 {volume_ma * self.volume_multiplier:.2f}")
                self.write_log(f"信号详情：RSI={self.rsi_value:.2f}({rsi_signal}), MACD={self.macd_value:.4f}({macd_signal}), KDJ死叉={not self.stoch_cross_over}({kdj_signal})")
                self.controlled_short(self.fixed_size)
                self.entry_price = bar.close_price
                self.intra_trade_low = bar.low_price
            # else:
                # self.write_log("等待空头入场信号...")
                
    def on_order(self, order: OrderData):
        """
        委托回报更新
        """
        # 打印委托信息
        if order.status == Status.SUBMITTING:
            self.write_log(f"提交委托：{order.direction.value} {order.offset.value} {order.volume}@{order.price}")
        elif order.status == Status.ALLTRADED:
            self.write_log(f"委托全部成交：{order.direction.value} {order.offset.value} {order.volume}@{order.price}")
        elif order.status in [Status.CANCELLED, Status.REJECTED]:
            self.write_log(f"委托已取消/拒绝：{order.direction.value} {order.offset.value} {order.volume}@{order.price}")
            
        # 触发UI更新
        self.put_event()
        
    def on_trade(self, trade: TradeData):
        """
        成交回报更新
        """
        # 打印成交信息
        self.write_log(f"成交：{trade.direction.value} {trade.offset.value} {trade.volume}@{trade.price}")
        
        # 更新持仓成本和止损价格
        if trade.offset.value == "开":  # 开仓
            # 设置入场价格
            self.entry_price = trade.price
            
            if trade.direction == Direction.LONG:  # 多头开仓
                self.intra_trade_high = trade.price
                # 【修改】使用ATR设置初始止损价格
                stop_price = trade.price - self.atr_value * self.atr_multiplier
                self.trailing_stop_price = stop_price
                self.write_log(f"设置多头初始ATR止损价：{self.trailing_stop_price:.2f} (ATR={self.atr_value:.2f})")
            else:  # 空头开仓
                self.intra_trade_low = trade.price
                # 【修改】使用ATR设置初始止损价格
                stop_price = trade.price + self.atr_value * self.atr_multiplier
                self.trailing_stop_price = stop_price
                self.write_log(f"设置空头初始ATR止损价：{self.trailing_stop_price:.2f} (ATR={self.atr_value:.2f})")
        else:  # 平仓
            # 重置相关变量
            self.entry_price = 0.0
            self.intra_trade_high = 0
            self.intra_trade_low = 0
            self.trailing_stop_price = 0.0
                
        # 触发UI更新
        self.put_event()
        
    def on_stop_order(self, stop_order: StopOrder):
        """
        停止单回报更新
        """
        # 触发UI更新
        self.put_event() 

    def controlled_buy(self, volume):
        """
        带滑点控制的买入开仓
        """
        if not self.last_tick:
            self.write_log("当前无可用Tick数据，使用市价单买入")
            self.buy(self.last_price, volume)
            return
            
        # 使用卖一价加上允许的滑点作为限价单价格
        limit_price = self.last_tick.ask_price_1 * (1 + self.slippage_tolerance_pct)
        self.buy(limit_price, volume)
        self.write_log(f"限价买入: 数量={volume}, 价格={limit_price:.2f} (卖一价={self.last_tick.ask_price_1:.2f}, 滑点={self.slippage_tolerance_pct*100}%)")
    
    def controlled_sell(self, volume):
        """
        带滑点控制的卖出平仓
        """
        if not self.last_tick:
            self.write_log("当前无可用Tick数据，使用市价单卖出")
            self.sell(self.last_price, volume)
            return
            
        # 使用买一价减去允许的滑点作为限价单价格
        limit_price = self.last_tick.bid_price_1 * (1 - self.slippage_tolerance_pct)
        self.sell(limit_price, volume)
        self.write_log(f"限价卖出: 数量={volume}, 价格={limit_price:.2f} (买一价={self.last_tick.bid_price_1:.2f}, 滑点={self.slippage_tolerance_pct*100}%)")
    
    def controlled_short(self, volume):
        """
        带滑点控制的卖出开仓
        """
        if not self.last_tick:
            self.write_log("当前无可用Tick数据，使用市价单做空")
            self.short(self.last_price, volume)
            return
            
        # 使用买一价减去允许的滑点作为限价单价格
        limit_price = self.last_tick.bid_price_1 * (1 - self.slippage_tolerance_pct)
        self.short(limit_price, volume)
        self.write_log(f"限价做空: 数量={volume}, 价格={limit_price:.2f} (买一价={self.last_tick.bid_price_1:.2f}, 滑点={self.slippage_tolerance_pct*100}%)")
    
    def controlled_cover(self, volume):
        """
        带滑点控制的买入平仓
        """
        if not self.last_tick:
            self.write_log("当前无可用Tick数据，使用市价单平空")
            self.cover(self.last_price, volume)
            return
            
        # 使用卖一价加上允许的滑点作为限价单价格
        limit_price = self.last_tick.ask_price_1 * (1 + self.slippage_tolerance_pct)
        self.cover(limit_price, volume)
        self.write_log(f"限价平空: 数量={volume}, 价格={limit_price:.2f} (卖一价={self.last_tick.ask_price_1:.2f}, 滑点={self.slippage_tolerance_pct*100}%)") 