#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import sys
import os
import argparse

# 添加vnpy路径
sys.path.append(os.path.abspath("../../../"))

# 导入vnpy组件
from vnpy_ctabacktester.engine import BacktestingEngine, OptimizationSetting
from vnpy.trader.constant import Interval
from vnpy.trader.setting import SETTINGS

# 导入自定义策略
from btc_triple_signal_strategy_1h import BtcTripleSignalStrategy1h
from vnpy.trader.object import Exchange

# 配置使用 MySQL 数据库
SETTINGS["database.driver"] = "mysql"  # 使用 MySQL 作为数据库
SETTINGS["database.name"] = "mysql"    # 必须和driver一致
SETTINGS["database.database"] = "vnpy"  # 数据库名称
SETTINGS["database.host"] = "localhost"  # 数据库主机
SETTINGS["database.port"] = 3306  # 数据库端口
SETTINGS["database.user"] = "root"  # 数据库用户名
SETTINGS["database.password"] = ""  # 数据库密码

def run_optimization(target_name="sharpe_ratio"):
    """
    执行参数优化
    
    参数:
        target_name (str): 优化目标名称，可选值：
            - "sharpe_ratio": 夏普率 (默认)
            - "total_return": 总收益率
            - "calmar_ratio": 卡尔马比率
    """
    # ================== 1. 定义时间段和基础参数 ==================
    print("📊 配置优化参数...")
    
    # 时间段定义
    start = datetime.datetime(2023, 1, 1)  # 回测开始时间
    end = datetime.datetime(2024, 5, 1)    # 回测结束时间
    
    # 基础参数
    symbol = "btcusdt"  # 使用小写的btcusdt，对应数据库中的格式
    exchange = "SMART"  # 交易所标识符，使用vnpy支持的SMART值
    vt_symbol = f"{symbol}.{exchange}"  # 完整的交易对标识符
    interval = Interval.HOUR  # 使用1小时K线
    initial_capital = 100000  # 初始资金10万美金
    
    print(f"📈 回测标的: {symbol}")
    print(f"⏰ K线周期: 1h")
    print(f"💰 初始资金: ${initial_capital:,}")
    print(f"📅 回测时间: {start} 至 {end}")
    
    # ================== 2. 初始化回测引擎 ==================
    engine = BacktestingEngine()
    
    # 设置回测参数
    engine.set_parameters(
        vt_symbol=vt_symbol,
        interval=interval,
        start=start,
        end=end,
        rate=0.0003,  # 手续费率：0.03%
        slippage=0.5,  # 滑点：0.5 USD
        size=1,        # 合约大小：1
        pricetick=0.01, # 价格跳动：0.01 USD
        capital=initial_capital
    )
    
    # ================== 3. 设置优化参数 ==================
    print("\n🔧 设置优化参数...")
    
    # 创建优化设置
    setting = OptimizationSetting()
    
    # 设置优化参数范围（使用遗传算法时参数需要离散化）
    setting.add_parameter("rsi_buy_level", 20, 40, 5)           # RSI买入阈值：20-40
    setting.add_parameter("rsi_sell_level", 60, 80, 5)          # RSI卖出阈值：60-80
    setting.add_parameter("stop_loss_pct", 0.02, 0.08, 0.01)    # 初始止损百分比：2%-8%
    setting.add_parameter("trailing_stop_pct", 0.01, 0.05, 0.01) # 移动止损回撤百分比：1%-5%
    setting.add_parameter("trailing_stop_activation_pct", 0.005, 0.02, 0.005) # 移动止损激活阈值：0.5%-2%
    setting.add_parameter("slippage_tolerance_pct", 0.0005, 0.003, 0.0005)   # 滑点容忍百分比：0.05%-0.3%
    setting.add_parameter("signal_num", 2, 3, 1)                # 信号数：2-3（提高最小值，确保多指标共振）
    setting.add_parameter("fast_window", 5, 20, 5)              # 快速均线窗口：5-20
    setting.add_parameter("slow_window", 20, 50, 5)             # 慢速均线窗口：20-50
    # 【新增】ATR参数优化
    setting.add_parameter("atr_length", 10, 20, 2)              # ATR计算周期：10-20
    setting.add_parameter("atr_multiplier", 1.5, 3.5, 0.5)      # ATR倍数：1.5-3.5
    # 【新增】ADX参数优化
    setting.add_parameter("adx_length", 10, 20, 2)              # ADX计算周期：10-20
    setting.add_parameter("adx_threshold", 15, 30, 5)           # ADX阈值：15-30
    # 【新增】成交量参数优化
    setting.add_parameter("volume_window", 10, 30, 5)           # 成交量窗口：10-30
    setting.add_parameter("volume_multiplier", 1.0, 2.0, 0.2)   # 成交量倍数：1.0-2.0
    
    # 设置优化目标
    target_description = {
        "sharpe_ratio": "夏普率 (风险调整后收益)",
        "total_return": "总收益率 (最大化绝对收益)",
        "calmar_ratio": "卡尔马比率 (年化收益/最大回撤)"
    }
    
    setting.set_target(target_name)
    
    # 显示优化参数
    print("\n优化参数范围:")
    for name in setting.params:
        values = setting.params[name]
        print(f"   - {name}: {min(values)} → {max(values)}")
    
    print(f"\n🧬 优化算法: 遗传算法")
    print(f"   - 种群大小: 自动设置")
    print(f"   - 最大代数: 自动设置")
    print(f"\n🎯 优化目标: 最大化{target_description.get(target_name, target_name)}")
    print(f"💻 使用线程数: 4")
    
    # ================== 4. 运行优化 ==================
    print("\n⚙️ 开始优化...")
    engine.add_strategy(BtcTripleSignalStrategy1h, {})
    
    # 使用VnPy内置的遗传算法优化
    result = engine.run_ga_optimization(
        setting,
        output=True,
        max_workers=4
    )
    
    # ================== 5. 输出优化结果 ==================
    if not result:
        print("❌ 优化失败，未找到结果")
        return
        
    # 输出最优参数组合
    print("\n" + "=" * 50)
    print(f"🏆 最优参数组合 (基于{target_description.get(target_name, target_name)}):")
    print("=" * 50)
    
    best_setting = result[0][0]
    best_metric_value = result[0][1]
    
    for name, value in best_setting.items():
        print(f"{name}: {value}")
    
    print("\n" + "=" * 50)
    print(f"📊 最优回测结果 (基于{target_description.get(target_name, target_name)}):")
    print("=" * 50)
    
    # 处理best_metric_value，可能是单一值或字典
    if hasattr(best_metric_value, 'items'):
        # 如果是字典，遍历所有键值对
        for key, value in best_metric_value.items():
            print(f"{key}: {value}")
    else:
        # 如果是单一值，直接打印
        print(f"{target_name}: {best_metric_value}")
    
    # ================== 6. 使用最优参数回测 ==================
    print("\n" + "=" * 50)
    print("🔄 使用最优参数执行完整回测...")
    print("=" * 50)
    
    # 创建新的回测引擎
    best_engine = BacktestingEngine()
    
    # 设置回测参数
    best_engine.set_parameters(
        vt_symbol=vt_symbol,
        interval=interval,
        start=start,
        end=end,
        rate=0.0003,  # 手续费率：0.03%
        slippage=0.5,  # 滑点：0.5 USD
        size=1,        # 合约大小：1
        pricetick=0.01, # 价格跳动：0.01 USD
        capital=initial_capital
    )
    
    # 添加策略
    best_engine.add_strategy(BtcTripleSignalStrategy1h, best_setting)
    
    # 运行回测
    best_engine.load_data()
    best_engine.run_backtesting()
    
    # 计算结果
    best_engine.calculate_result()
    statistics = best_engine.calculate_statistics()
    
    # 输出统计结果
    print("\n" + "=" * 50)
    print(f"📊 最优参数回测结果统计 (基于{target_description.get(target_name, target_name)}):")
    print("=" * 50)
    
    for key, value in statistics.items():
        print(f"{key}: {value}")
        
    # 显示图表
    best_engine.show_chart()
    
    # 保存最优参数到文件
    file_name = f"best_params_{target_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(file_name, "w") as f:
        f.write(f"优化目标: {target_description.get(target_name, target_name)}\n")
        f.write(f"优化时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("最优参数组合:\n")
        for name, value in best_setting.items():
            # 对百分比参数进行特殊处理
            if name.endswith('_pct'):
                f.write(f"{name}: {value:.4f} ({value*100:.2f}%)\n")
            else:
                f.write(f"{name}: {value}\n")
        
        # 添加参数分类描述
        f.write("\n参数分类说明:\n")
        f.write("- 风险管理参数:\n")
        f.write("  * stop_loss_pct: 初始止损百分比\n")
        f.write("  * trailing_stop_pct: 移动止损回撤百分比\n")
        f.write("  * trailing_stop_activation_pct: 移动止损激活阈值\n")
        f.write("  * slippage_tolerance_pct: 滑点容忍百分比\n")
        f.write("- 技术指标参数:\n")
        f.write("  * rsi_buy_level/rsi_sell_level: RSI买入/卖出阈值\n")
        f.write("  * signal_num: 所需信号数量\n")
        f.write("  * fast_window/slow_window: 快速/慢速均线窗口\n")
        
        f.write("\n最优回测结果统计:\n")
        for key, value in statistics.items():
            f.write(f"{key}: {value}\n")
    
    print(f"\n💾 最优参数已保存到文件: {file_name}")
    
    return result, best_setting, statistics


def run_all_optimizations():
    """运行所有三种优化目标的优化，使用遗传算法"""
    targets = [
        "sharpe_ratio",   # 夏普率
        "total_return",   # 总收益率
        "calmar_ratio"    # 卡尔马比率
    ]
    
    results = {}
    
    for target in targets:
        print("\n" + "=" * 60)
        print(f"🚀 开始遗传算法优化目标: {target}")
        print("=" * 60)
        
        try:
            result, best_setting, statistics = run_optimization(target)
            results[target] = {
                "best_setting": best_setting,
                "statistics": statistics
            }
        except Exception as e:
            print(f"❌ 优化 {target} 失败: {str(e)}")
            results[target] = {
                "best_setting": None,
                "statistics": None
            }
    
    # 比较三种优化目标的结果
    print("\n" + "=" * 60)
    print("📊 三种优化目标结果比较")
    print("=" * 60)
    
    print(f"{'优化目标':<15} {'总收益率':<15} {'夏普率':<15} {'卡尔马比率':<15} {'最大回撤':<15}")
    print("-" * 75)
    
    for target, data in results.items():
        stats = data["statistics"]
        if stats:
            try:
                print(f"{target:<15} {stats.get('total_return', 'N/A'):<15.2%} {stats.get('sharpe_ratio', 'N/A'):<15.2f} {stats.get('calmar_ratio', 'N/A'):<15.2f} {stats.get('max_drawdown', 'N/A'):<15.2%}")
            except (TypeError, ValueError):
                print(f"{target:<15} {'N/A':<15} {'N/A':<15} {'N/A':<15} {'N/A':<15}")
        else:
            print(f"{target:<15} {'N/A':<15} {'N/A':<15} {'N/A':<15} {'N/A':<15}")
    
    return results


def run_direct_backtest():
    """直接使用推荐参数运行回测，不进行优化"""
    # ================== 1. 定义时间段和基础参数 ==================
    print("\n" + "=" * 60)
    print("🚀 使用推荐参数直接运行回测...")
    print("=" * 60)
    
    # 时间段定义 - 可以调整为更短的时间段以便快速测试
    start = datetime.datetime(2024, 1, 1)  # 回测开始时间
    end = datetime.datetime(2024, 5, 1)    # 回测结束时间
    
    # 基础参数
    symbol = "btcusdt"  # 使用小写的btcusdt，对应数据库中的格式
    exchange = "SMART"  # 交易所，使用SMART
    vt_symbol = f"{symbol}.{exchange}"  # 完整的交易对标识符
    interval = Interval.HOUR  # 使用1小时K线
    initial_capital = 100000  # 初始资金10万美金
    
    print(f"📈 回测标的: {symbol}")
    print(f"⏰ K线周期: 1h")
    print(f"💰 初始资金: ${initial_capital:,}")
    print(f"📅 回测时间: {start} 至 {end}")
    
    # ================== 2. 优化后的最佳参数 ==================
    # 使用之前优化得到的最佳参数
    recommended_setting = {
        "rsi_buy_level": 40,                 # RSI买入阈值
        "rsi_sell_level": 80,                # RSI卖出阈值
        "stop_loss_pct": 0.05,               # 初始止损百分比(5%)
        "trailing_stop_pct": 0.03,           # 移动止损回撤百分比(3%)
        "trailing_stop_activation_pct": 0.01, # 移动止损激活阈值(1%)
        "slippage_tolerance_pct": 0.001,     # 滑点容忍百分比(0.1%)
        "signal_num": 2,                     # 所需信号数量
        "fast_window": 20,                   # 快速均线窗口
        "slow_window": 50,                   # 慢速均线窗口
        "atr_length": 14,                    # 【新增】ATR计算周期
        "atr_multiplier": 2.5,               # 【新增】ATR倍数
        "adx_length": 14,                    # 【新增】ADX计算周期
        "adx_threshold": 20,                 # 【新增】ADX趋势强度阈值
        "volume_window": 20,                 # 【新增】成交量窗口
        "volume_multiplier": 1.2,            # 【新增】成交量倍数
    }
    
    print("\n📝 使用的参数组合:")
    for name, value in recommended_setting.items():
        if name.endswith('_pct'):
            print(f"  - {name}: {value:.4f} ({value*100:.2f}%)")
        else:
            print(f"  - {name}: {value}")
    
    # ================== 3. 初始化回测引擎 ==================
    engine = BacktestingEngine()
    
    # 设置回测参数
    engine.set_parameters(
        vt_symbol=vt_symbol,
        interval=interval,
        start=start,
        end=end,
        rate=0.0003,  # 手续费率：0.03%
        slippage=0.5,  # 引擎内置滑点(这个在策略内部已通过限价单方式控制)
        size=1,        # 合约大小：1
        pricetick=0.01, # 价格跳动：0.01 USD
        capital=initial_capital
    )
    
    # 添加策略
    engine.add_strategy(BtcTripleSignalStrategy1h, recommended_setting)
    
    # ================== 4. 运行回测 ==================
    print("\n⚙️ 开始回测...")
    
    # 加载数据
    engine.load_data()
    
    # 运行回测
    engine.run_backtesting()
    
    # 计算结果
    engine.calculate_result()
    statistics = engine.calculate_statistics()
    
    # 输出统计结果
    print("\n" + "=" * 50)
    print(f"📊 回测结果统计:")
    print("=" * 50)
    
    for key, value in statistics.items():
        print(f"{key}: {value}")
        
    # 显示图表
    engine.show_chart()
    
    # 保存回测结果到文件
    file_name = f"direct_backtest_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(file_name, "w") as f:
        f.write(f"回测时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"回测周期: {start.strftime('%Y-%m-%d')} 至 {end.strftime('%Y-%m-%d')}\n\n")
        f.write("使用参数组合:\n")
        for name, value in recommended_setting.items():
            if name.endswith('_pct'):
                f.write(f"{name}: {value:.4f} ({value*100:.2f}%)\n")
            else:
                f.write(f"{name}: {value}\n")
        
        # 添加参数分类描述
        f.write("\n参数说明:\n")
        f.write("- 风险管理参数:\n")
        f.write("  * stop_loss_pct: 初始止损百分比\n")
        f.write("  * trailing_stop_pct: 移动止损回撤百分比\n")
        f.write("  * trailing_stop_activation_pct: 移动止损激活阈值\n")
        f.write("  * slippage_tolerance_pct: 滑点容忍百分比\n")
        f.write("- 技术指标参数:\n")
        f.write("  * rsi_buy_level/rsi_sell_level: RSI买入/卖出阈值\n")
        f.write("  * signal_num: 所需信号数量\n")
        f.write("  * fast_window/slow_window: 快速/慢速均线窗口\n")
        
        f.write("\n回测结果统计:\n")
        for key, value in statistics.items():
            f.write(f"{key}: {value}\n")
    
    print(f"\n💾 回测结果已保存到文件: {file_name}")
    
    return statistics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="比特币交易策略参数优化和回测 (使用遗传算法)")
    parser.add_argument(
        "--target", 
        type=str, 
        default="direct", 
        choices=["direct", "all", "sharpe_ratio", "total_return", "calmar_ratio"],
        help="操作模式: direct(直接回测), sharpe_ratio(夏普率遗传算法优化), total_return(总收益率遗传算法优化), calmar_ratio(卡尔马比率遗传算法优化), all(全部优化)"
    )
    
    args = parser.parse_args()
    
    if args.target == "direct":
        run_direct_backtest()
    elif args.target == "all":
        run_all_optimizations()
    else:
        run_optimization(args.target) 