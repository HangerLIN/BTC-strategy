#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import sys
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict

# 添加本地vnpy路径
sys.path.append(os.path.abspath("."))  # 优先使用当前目录下的vnpy

# 导入vnpy组件
from vnpy_ctabacktester.engine import BacktestingEngine
from vnpy.trader.constant import Interval
try:
    from vnpy.trader.setting import SETTINGS
except ImportError:
    # 对于vnpy 4.x版本，设置可能已移动位置
    from vnpy.trader.utility import SETTINGS

# 配置使用 MySQL 数据库
SETTINGS["database.driver"] = "mysql"  # 使用 MySQL 作为数据库
SETTINGS["database.name"] = "mysql"    # 必须和driver一致
SETTINGS["database.database"] = "vnpy"  # 数据库名称
SETTINGS["database.host"] = "localhost"  # 数据库主机
SETTINGS["database.port"] = 3306  # 数据库端口
SETTINGS["database.user"] = "root"  # 数据库用户名
SETTINGS["database.password"] = ""  # 数据库密码

# 配置代理 (如果需要)
os.environ["http_proxy"] = "http://127.0.0.1:7897"
os.environ["https_proxy"] = "http://127.0.0.1:7897"

def create_minute_strategy():
    """基于原有1小时策略创建分钟K线版本"""
    # 创建分钟K线策略文件
    try:
        with open("btc_triple_signal_strategy_1h.py", "r") as f:
            strategy_code = f.read()
        
        # 修改策略代码，将其调整为分钟K线版本
        minute_strategy_code = strategy_code.replace(
            "BtcTripleSignalStrategy1h", "BtcTripleSignalStrategyMin"
        ).replace(
            "BTC 三重信号策略 (1小时版)", "BTC 三重信号策略 (分钟版)"
        ).replace(
            "使用1小时K线", "使用分钟K线"
        )
        
        # 写入新文件
        with open("btc_triple_signal_strategy_min.py", "w") as f:
            f.write(minute_strategy_code)
        
        print("✅ 已创建分钟K线策略文件: btc_triple_signal_strategy_min.py")
        return True
    except Exception as e:
        print(f"❌ 创建分钟K线策略文件失败: {e}")
        return False

# 确保分钟K线策略文件存在，先创建再导入
if not os.path.exists("btc_triple_signal_strategy_min.py"):
    create_minute_strategy()

# 现在导入策略类
try:
    from btc_triple_signal_strategy_min import BtcTripleSignalStrategyMin
except ImportError:
    print("❌ 无法导入分钟K线策略，请确保btc_triple_signal_strategy_1h.py文件存在")
    print("尝试直接使用小时K线策略...")
    from btc_triple_signal_strategy_1h import BtcTripleSignalStrategy1h as BtcTripleSignalStrategyMin

def run_backtest_leverage_minutes():
    """使用4倍杠杆和分钟K线运行回测"""
    # ================== 1. 定义时间段和基础参数 ==================
    print("📊 配置回测参数...")
    
    # 时间段定义
    start = datetime.datetime(2024, 5, 1)  # 回测开始时间
    end = datetime.datetime(2025, 6, 30)   # 回测结束时间
    
    # 基础参数
    symbol = "btcusdt"  # 使用小写的btcusdt，对应数据库中的格式
    exchange = "SMART"  # 交易所标识符，使用vnpy支持的SMART值
    vt_symbol = f"{symbol}.{exchange}"  # 完整的交易对标识符
    interval = Interval.MINUTE  # 使用分钟K线
    leverage = 4.0  # 使用4倍杠杆
    initial_capital = 100000  # 初始资金10万美金
    
    print(f"📈 回测标的: {symbol}")
    print(f"⏰ K线周期: 分钟K线")
    print(f"💰 初始资金: ${initial_capital:,}")
    print(f"📅 回测时间: {start} 至 {end}")
    print(f"🔄 杠杆倍数: {leverage}倍")
    
    # 最优参数 (来自优化结果，可能需要针对分钟K线重新优化)
    best_params = {
        "rsi_buy_level": 40,
        "rsi_sell_level": 80,
        "stop_loss_pct": 0.03,
        "signal_num": 2,
        "fast_window": 5,
        "slow_window": 30
    }
    
    print("\n🏆 使用参数:")
    for name, value in best_params.items():
        print(f"   - {name}: {value}")

    # ================== 2. 初始化回测引擎 ==================
    engine = BacktestingEngine()
    
    # 设置回测参数
    engine.set_parameters(
        vt_symbol=vt_symbol,
        interval=interval,
        start=start,
        end=end,
        rate=0.0004,  # 杠杆交易手续费率：0.04% (通常杠杆交易手续费更高)
        slippage=0.5,  # 滑点：0.5 USD
        size=1,        # 合约大小：1
        pricetick=0.01, # 价格跳动：0.01 USD
        capital=initial_capital
    )
    
    # 添加策略
    engine.add_strategy(BtcTripleSignalStrategyMin, best_params)

    # ================== 3. 运行回测 ==================
    print("\n⚙️ 开始回测...")
    engine.load_data()
    engine.run_backtesting()
    
    # ================== 4. 计算结果并应用杠杆因子 ==================
    print("\n🧮 计算结果并应用杠杆倍数...")
    engine.calculate_result()
    
    # 应用杠杆因子到每个交易的盈亏
    for trade in engine.trades:
        try:
            if hasattr(trade, "pnl") and isinstance(trade.pnl, (int, float)):
                trade.pnl *= leverage
            elif hasattr(trade, "pnl") and isinstance(trade.pnl, str):
                # 尝试转换为浮点数
                try:
                    pnl_value = float(trade.pnl)
                    trade.pnl = pnl_value * leverage
                except ValueError:
                    print(f"警告: 无法转换交易盈亏 '{trade.pnl}' 为数值")
        except Exception as e:
            print(f"处理交易盈亏时出错: {e}")
    
    # 应用杠杆因子到日度盈亏
    for date, daily_result in engine.daily_results.items():
        try:
            if hasattr(daily_result, 'net_pnl'):
                if isinstance(daily_result.net_pnl, (int, float)):
                    daily_result.net_pnl *= leverage
            
            if hasattr(daily_result, 'end_balance'):
                # 调整结束余额，考虑初始资金和杠杆盈亏
                if isinstance(daily_result.end_balance, (int, float)):
                    leverage_profit = daily_result.end_balance - engine.capital
                    daily_result.end_balance = engine.capital + leverage_profit * leverage
        except Exception as e:
            print(f"处理日度结果时出错: {e}")
    
    # 重新计算统计指标，但不显示结果(我们将在下面手动显示)
    statistics = engine.calculate_statistics(output=False)
    
    # ================== 5. 显示结果统计 ==================
    print("\n" + "=" * 40)
    print(f"📊 回测结果统计 (杠杆倍数: {leverage}倍)")
    print("=" * 40)
    
    # 按顺序显示重要指标
    important_stats = [
        ("start_date", "开始日期"),
        ("end_date", "结束日期"),
        ("total_days", "总交易日"),
        ("profit_days", "盈利天数"),
        ("loss_days", "亏损天数"),
        ("capital", "初始资金"),
        ("end_balance", "结束资金"),
        ("total_return", "总收益率"),
        ("annual_return", "年化收益率"),
        ("max_drawdown", "最大回撤"),
        ("max_ddpercent", "最大回撤比例"),
        ("total_trade_count", "总交易次数"),
        ("daily_trade_count", "日均交易次数"),
        ("sharpe_ratio", "夏普比率"),
        ("return_drawdown_ratio", "收益回撤比")
    ]
    
    for key, name in important_stats:
        value = statistics.get(key, "N/A")
        # 格式化百分比
        if "return" in key or "percent" in key:
            if isinstance(value, (int, float)):
                value = f"{value * 100:.2f}%"
        # 格式化浮点数
        elif isinstance(value, float):
            value = f"{value:.4f}"
            
        print(f"{name:.<20} {value}")
        
    # ================== 6. 展示详细交易记录 ==================
    try:
        trades = engine.get_all_trades()
        if trades:
            print("\n" + "=" * 40)
            print(f"📝 交易记录 (显示前10笔):")
            print("=" * 40)
            print(f"{'序号':<5}{'时间':<20}{'方向':<6}{'价格':<10}{'数量':<8}{'盈亏':<10}")
            print("-" * 60)
            
            for i, trade in enumerate(trades[:10]):
                direction = "多" if str(trade.direction) == "Direction.LONG" else "空"
                try:
                    profit = f"{float(trade.pnl):.2f}" if hasattr(trade, "pnl") else "N/A"
                    price = f"{float(trade.price):.2f}"
                    volume = f"{float(trade.volume):.2f}"
                    datetime_str = trade.datetime.strftime('%Y-%m-%d %H:%M') if hasattr(trade.datetime, 'strftime') else str(trade.datetime)
                except:
                    profit = "N/A"
                    price = str(trade.price)
                    volume = str(trade.volume)
                    datetime_str = str(trade.datetime)
                    
                print(f"{i+1:<5}{datetime_str:<20}{direction:<6}{price:<10}{volume:<8}{profit:<10}")
            
            print(f"\n共{len(trades)}笔交易")
    except Exception as e:
        print(f"\n获取交易记录时出错: {e}")
        import traceback
        traceback.print_exc()
        
    # 显示图表
    print("\n📈 显示资金曲线图...")
    engine.show_chart()
    
    return engine, statistics

def analyze_leverage_impact():
    """分析不同杠杆倍数的影响"""
    print("\n" + "=" * 30)
    print("📊 杠杆影响分析:")
    print("=" * 30)
    
    # 测试不同杠杆倍数
    leverage_options = [1.0, 2.0, 3.0, 4.0, 5.0]
    results = {}
    
    # 基础参数
    symbol = "btcusdt"
    exchange = "SMART"
    vt_symbol = f"{symbol}.{exchange}"
    interval = Interval.MINUTE
    initial_capital = 100000
    start = datetime.datetime(2024, 5, 1)
    end = datetime.datetime(2025, 6, 30)
    
    best_params = {
        "rsi_buy_level": 40,
        "rsi_sell_level": 80,
        "stop_loss_pct": 0.03,
        "signal_num": 2,
        "fast_window": 5,
        "slow_window": 30
    }
    
    # 先运行一次基准回测，然后仅应用不同杠杆倍数
    print("\n运行基准回测...")
    engine = BacktestingEngine()
    engine.set_parameters(
        vt_symbol=vt_symbol,
        interval=interval,
        start=start,
        end=end,
        rate=0.0004,
        slippage=0.5,
        size=1,
        pricetick=0.01,
        capital=initial_capital
    )
    
    engine.add_strategy(BtcTripleSignalStrategyMin, best_params)
    engine.load_data()
    engine.run_backtesting()
    engine.calculate_result()
    base_stats = engine.calculate_statistics(output=False)
    
    # 保存基准结果 (杠杆倍数=1)
    results[1.0] = {
        "total_return": base_stats.get("total_return", 0) * 100,
        "annual_return": base_stats.get("annual_return", 0) * 100,
        "max_drawdown": base_stats.get("max_ddpercent", 0) * 100,
        "sharpe_ratio": base_stats.get("sharpe_ratio", 0)
    }
    
    # 对每种杠杆倍数计算结果
    for leverage in leverage_options[1:]:  # 跳过1倍杠杆(已经计算)
        print(f"\n计算 {leverage}倍 杠杆结果...")
        
        # 应用杠杆因子到每个交易的盈亏
        for trade in engine.trades:
            try:
                if hasattr(trade, "pnl"):
                    if isinstance(trade.pnl, (int, float)):
                        trade.pnl = (trade.pnl / results[1.0]["total_return"] * 100) * leverage
                    elif isinstance(trade.pnl, str):
                        try:
                            pnl_value = float(trade.pnl)
                            trade.pnl = (pnl_value / results[1.0]["total_return"] * 100) * leverage
                        except ValueError:
                            print(f"警告: 无法转换交易盈亏 '{trade.pnl}' 为数值")
            except Exception as e:
                print(f"处理交易盈亏时出错: {e}")
        
        # 应用杠杆因子到日度盈亏
        for date, daily_result in engine.daily_results.items():
            try:
                if hasattr(daily_result, 'net_pnl'):
                    if isinstance(daily_result.net_pnl, (int, float)):
                        daily_result.net_pnl *= leverage
                
                if hasattr(daily_result, 'end_balance'):
                    # 调整结束余额，考虑初始资金和杠杆盈亏
                    if isinstance(daily_result.end_balance, (int, float)):
                        leverage_profit = daily_result.end_balance - engine.capital
                        daily_result.end_balance = engine.capital + leverage_profit * leverage
            except Exception as e:
                print(f"处理日度结果时出错: {e}")
                
        # 深度复制基础统计数据
        leveraged_stats = base_stats.copy()
        
        # 应用杠杆因子
        if "total_return" in leveraged_stats:
            leveraged_stats["total_return"] *= leverage
        if "annual_return" in leveraged_stats:
            leveraged_stats["annual_return"] *= leverage
        if "max_ddpercent" in leveraged_stats:
            leveraged_stats["max_ddpercent"] *= leverage
        
        # 保存结果
        results[leverage] = {
            "total_return": leveraged_stats.get("total_return", 0) * 100,
            "annual_return": leveraged_stats.get("annual_return", 0) * 100,
            "max_drawdown": leveraged_stats.get("max_ddpercent", 0) * 100,
            "sharpe_ratio": leveraged_stats.get("sharpe_ratio", 0)
        }
    
    # 创建比较表格
    print("\n杠杆倍数对比结果:")
    print(f"{'杠杆倍数':<10}{'总收益率':<15}{'年化收益率':<15}{'最大回撤':<15}{'夏普比率':<15}")
    print("-" * 70)
    
    for leverage, stats in results.items():
        print(f"{leverage:<10.1f}x{stats['total_return']:<15.2f}%{stats['annual_return']:<15.2f}%{stats['max_drawdown']:<15.2f}%{stats['sharpe_ratio']:<15.4f}")
    
    # 绘制比较图
    plt.figure(figsize=(12, 10))
    
    # 1. 总收益率对比
    plt.subplot(2, 2, 1)
    plt.bar([str(l) + "x" for l in results.keys()], [r["total_return"] for r in results.values()], color='blue')
    plt.title('总收益率对比')
    plt.ylabel('收益率 (%)')
    plt.xlabel('杠杆倍数')
    
    # 2. 年化收益率对比
    plt.subplot(2, 2, 2)
    plt.bar([str(l) + "x" for l in results.keys()], [r["annual_return"] for r in results.values()], color='green')
    plt.title('年化收益率对比')
    plt.ylabel('收益率 (%)')
    plt.xlabel('杠杆倍数')
    
    # 3. 最大回撤对比
    plt.subplot(2, 2, 3)
    plt.bar([str(l) + "x" for l in results.keys()], [r["max_drawdown"] for r in results.values()], color='red')
    plt.title('最大回撤对比')
    plt.ylabel('回撤比例 (%)')
    plt.xlabel('杠杆倍数')
    
    # 4. 夏普比率对比
    plt.subplot(2, 2, 4)
    plt.bar([str(l) + "x" for l in results.keys()], [r["sharpe_ratio"] for r in results.values()], color='purple')
    plt.title('夏普比率对比')
    plt.ylabel('夏普比率')
    plt.xlabel('杠杆倍数')
    
    plt.tight_layout()
    plt.savefig('leverage_comparison.png')
    plt.show()
    
    return results

def check_minute_data_availability():
    """检查分钟K线数据是否可用"""
    import mysql.connector
    from mysql.connector import Error

    try:
        # 连接到MySQL数据库
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="vnpy"
        )
        
        if conn.is_connected():
            cursor = conn.cursor()
            
            # 查询分钟级别的数据
            query = """
                SELECT COUNT(*) as count, 
                       MIN(datetime) as earliest, 
                       MAX(datetime) as latest,
                       `interval`
                FROM dbbardata 
                WHERE symbol = 'btcusdt' AND `interval` = '1m'
                GROUP BY `interval`
            """
            
            cursor.execute(query)
            result = cursor.fetchone()
            
            if result:
                count, earliest, latest, interval = result
                print(f"✅ 找到 {count} 条 {interval} 级别的BTC数据")
                print(f"   日期范围: {earliest} 至 {latest}")
                return True
            else:
                print("❌ 没有找到分钟级别的BTC数据")
                
                # 查询有哪些间隔的数据可用
                query = """
                    SELECT `interval`, COUNT(*) as count 
                    FROM dbbardata 
                    WHERE symbol = 'btcusdt'
                    GROUP BY `interval`
                """
                cursor.execute(query)
                available_intervals = cursor.fetchall()
                
                print("\n可用的数据间隔:")
                for interval, count in available_intervals:
                    print(f"   - {interval}: {count} 条记录")
                
                return False
    
    except Error as e:
        print(f"数据库错误: {e}")
        return False
    
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def download_minute_data():
    """下载分钟级别的历史数据"""
    print("\n准备下载分钟级别的历史数据...")
    
    # 如果vnpy_data_downloader.py存在，使用它下载数据
    if os.path.exists("vnpy_data_downloader.py"):
        print("使用现有的下载器下载分钟K线数据...")
        try:
            # 修改下载器以支持分钟K线
            with open("vnpy_data_downloader.py", "r") as f:
                code = f.read()
                
            # 临时创建分钟K线下载器
            with open("download_minute_data.py", "w") as f:
                # 修改interval为分钟
                modified_code = code.replace('interval = "1h"', 'interval = "1m"')
                # 修改下载时间范围
                modified_code = modified_code.replace(
                    'start_date = datetime.datetime(2023, 1, 1)',
                    'start_date = datetime.datetime(2024, 5, 1)'
                )
                modified_code = modified_code.replace(
                    'end_date = datetime.datetime(2024, 5, 1)',
                    'end_date = datetime.datetime(2025, 6, 30)'
                )
                f.write(modified_code)
                
            # 执行下载
            print("开始下载分钟K线数据，这可能需要较长时间...")
            os.system(f"{sys.executable} download_minute_data.py")
            
            # 检查下载结果
            has_data = check_minute_data_availability()
            if has_data:
                print("✅ 分钟K线数据下载成功")
            else:
                print("❌ 分钟K线数据下载失败或不完整")
            
            # 删除临时文件
            os.remove("download_minute_data.py")
            
        except Exception as e:
            print(f"下载数据时出错: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("❌ 找不到数据下载器 vnpy_data_downloader.py")
        print("请先创建数据下载器或手动下载分钟级别的数据")

def main():
    """主函数"""
    print("=" * 50)
    print("BTC杠杆交易策略回测系统 (分钟K线版)")
    print("=" * 50)
    
    # 检查分钟K线数据是否可用
    has_minute_data = check_minute_data_availability()
    
    if not has_minute_data:
        print("\n需要先下载分钟K线数据")
        choice = input("是否现在下载分钟K线数据? (y/n): ")
        if choice.lower() == 'y':
            download_minute_data()
        else:
            print("退出程序")
            return
    
    print("\n请选择操作:")
    print("1. 执行4倍杠杆回测 (2024.5-2025.6)")
    print("2. 分析不同杠杆倍数的影响")
    print("3. 退出")
    
    choice = input("\n请输入选项 (1/2/3): ")
    
    if choice == '1':
        run_backtest_leverage_minutes()
    elif choice == '2':
        analyze_leverage_impact()
    else:
        print("退出程序")


if __name__ == "__main__":
    main() 