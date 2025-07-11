#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VNPy格式的币安数据下载脚本
====================================
直接通过币安REST API获取BTC历史数据并保存到vnpy标准数据库结构
兼容vnpy回测引擎

作者: HangerLin
创建时间: 2025-07
"""

import datetime
import time
import sys
import os
import traceback
import mysql.connector
from mysql.connector import Error
import requests
from typing import List, Dict, Any, Optional

# 币安API基本配置
BASE_URL = "https://api.binance.com"
API_KEY = ""
API_SECRET = ""

# 代理设置
proxies = {
    "http": "http://127.0.0.1:7897",
    "https": "http://127.0.0.1:7897"
}

# 请求头
headers = {
    "X-MBX-APIKEY": API_KEY
}

def create_database_and_table():
    """
    创建与vnpy兼容的数据库和表
    """
    try:
        # 连接到MySQL服务器
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password=""
        )
        
        if connection.is_connected():
            cursor = connection.cursor()
            
            # 创建数据库（如果不存在）- 注意：使用vnpy名称
            cursor.execute("CREATE DATABASE IF NOT EXISTS vnpy")
            print("✅ 数据库vnpy创建成功或已存在")
            
            # 切换到vnpy数据库
            cursor.execute("USE vnpy")
            
            # 创建表（如果不存在）- 使用vnpy标准的dbbardata表结构
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dbbardata (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    symbol VARCHAR(255) NOT NULL,
                    exchange VARCHAR(255) NOT NULL,
                    datetime DATETIME NOT NULL,
                    `interval` VARCHAR(255) NOT NULL,
                    volume DOUBLE NOT NULL,
                    open_price DOUBLE NOT NULL,
                    high_price DOUBLE NOT NULL,
                    low_price DOUBLE NOT NULL,
                    close_price DOUBLE NOT NULL,
                    open_interest DOUBLE NOT NULL DEFAULT 0,
                    turnover DOUBLE NOT NULL DEFAULT 0,
                    gateway_name VARCHAR(255) NOT NULL DEFAULT 'BINANCE',
                    INDEX idx_symbol_exchange_interval_datetime (symbol, exchange, `interval`, datetime)
                )
            """)
            connection.commit()
            print("✅ 表dbbardata创建成功或已存在")
            
            cursor.close()
            connection.close()
            return True
            
    except Error as e:
        print(f"❌ 数据库操作失败: {e}")
        return False

def save_klines_to_db(symbol, interval, klines):
    """
    将K线数据保存到数据库的dbbardata表中
    """
    if not klines:
        print("❌ 没有数据需要保存")
        return False
        
    try:
        # 连接到MySQL数据库
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="vnpy"
        )
        
        if connection.is_connected():
            cursor = connection.cursor()
            
            # 准备插入语句 - 适配vnpy的dbbardata表结构
            insert_query = """
                INSERT INTO dbbardata 
                (symbol, exchange, datetime, `interval`, volume, open_price, high_price, 
                low_price, close_price, open_interest, turnover, gateway_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            # 准备批量插入的数据
            records = []
            for kline in klines:
                open_time = datetime.datetime.fromtimestamp(kline[0] / 1000)
                
                record = (
                    symbol.lower(),            # 小写符号，如btcusdt
                    "SMART",                  # 使用vnpy支持的SMART交易所
                    open_time,                # 开盘时间
                    interval,                 # 时间周期
                    float(kline[5]),          # volume
                    float(kline[1]),          # open_price
                    float(kline[2]),          # high_price
                    float(kline[3]),          # low_price
                    float(kline[4]),          # close_price
                    0.0,                      # open_interest (默认为0)
                    float(kline[7]),          # turnover (交易额)
                    "BINANCE"                 # gateway_name
                )
                records.append(record)
            
            # 批量插入数据
            cursor.executemany(insert_query, records)
            connection.commit()
            
            print(f"✅ 成功保存 {len(records)} 条K线数据到数据库")
            
            cursor.close()
            connection.close()
            return True
            
    except Error as e:
        print(f"❌ 数据库保存失败: {e}")
        traceback.print_exc()
        return False

def check_existing_data(symbol, interval):
    """
    检查数据库中是否已存在指定的数据
    """
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="vnpy"
        )
        
        if connection.is_connected():
            cursor = connection.cursor()
            
            # 查询数据库中已有的数据范围 - 适用于dbbardata表
            query = """
                SELECT MIN(datetime), MAX(datetime), COUNT(*)
                FROM dbbardata
                WHERE symbol = %s AND exchange = %s AND `interval` = %s
            """
            
            cursor.execute(query, (symbol.lower(), "SMART", interval))
            result = cursor.fetchone()
            
            if result and result[2] > 0:
                min_date = result[0]
                max_date = result[1]
                count = result[2]
                
                print(f"✅ 数据库中已有 {count} 条数据")
                print(f"📅 数据范围: {min_date.strftime('%Y-%m-%d %H:%M:%S')} 至 {max_date.strftime('%Y-%m-%d %H:%M:%S')}")
                
                cursor.close()
                connection.close()
                return min_date, max_date, count
            
            cursor.close()
            connection.close()
            
    except Error as e:
        print(f"❌ 检查数据失败: {e}")
    
    return None, None, 0

def get_klines(symbol, interval, start_time=None, end_time=None, limit=1000):
    """
    从币安API获取K线数据
    
    参数:
        symbol: 交易对，如 'BTCUSDT'
        interval: K线间隔，如 '1h'
        start_time: 开始时间戳（毫秒）
        end_time: 结束时间戳（毫秒）
        limit: 每次请求的K线数量，最大1000
        
    返回:
        K线数据列表
    """
    params = {
        'symbol': symbol,
        'interval': interval,
        'limit': limit
    }
    
    if start_time:
        params['startTime'] = start_time
    if end_time:
        params['endTime'] = end_time
    
    try:
        response = requests.get(f"{BASE_URL}/api/v3/klines", params=params, headers=headers, proxies=proxies, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ 获取K线数据失败: {response.status_code} {response.text}")
            return []
    except Exception as e:
        print(f"❌ 请求出错: {e}")
        return []

def download_historical_data(symbol, interval, start_date, end_date):
    """
    下载指定时间范围内的历史数据
    
    参数:
        symbol: 交易对，如 'BTCUSDT'
        interval: K线间隔，如 '1h'
        start_date: 开始日期（datetime对象）
        end_date: 结束日期（datetime对象）
    """
    # 转换为时间戳（毫秒）
    start_ts = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)
    now_ts = int(time.time() * 1000)
    
    # 确保结束时间不超过当前时间
    if end_ts > now_ts:
        end_ts = now_ts
    
    print(f"📈 下载标的: {symbol}")
    print(f"⏰ K线周期: {interval}")
    print(f"📅 时间范围: {start_date.strftime('%Y-%m-%d %H:%M:%S')} 至 {end_date.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 分批下载数据（币安API每次最多返回1000条记录）
    current_start_ts = start_ts
    total_records = 0
    batch_count = 0
    
    while current_start_ts < end_ts:
        batch_count += 1
        print(f"⚙️ 下载第 {batch_count} 批数据...")
        
        # 获取当前批次的数据
        klines = get_klines(symbol, interval, current_start_ts, end_ts, 1000)
        
        if not klines:
            print("❌ 未获取到数据，可能已达到API限制，等待60秒后重试...")
            time.sleep(60)  # 遇到问题时等待更长时间
            # 重试一次
            klines = get_klines(symbol, interval, current_start_ts, end_ts, 1000)
            if not klines:
                print("❌ 重试失败，跳过")
                break
        
        # 保存到数据库
        save_klines_to_db(symbol, interval, klines)
        
        total_records += len(klines)
        
        # 更新起始时间为最后一条记录的收盘时间 + 1毫秒
        current_start_ts = klines[-1][6] + 1
        
        # 添加延时以避免API请求限制
        time.sleep(1)
    
    print(f"✅ 总共下载并保存了 {total_records} 条K线数据")

def main():
    """
    主函数
    """
    try:
        print("=" * 60)
        print("币安BTC历史数据下载工具 - VNPY兼容版")
        print("=" * 60)
        
        # 创建数据库和表
        if not create_database_and_table():
            print("❌ 数据库初始化失败，下载终止")
            return
        
        # 数据参数 - 与回测脚本保持一致
        symbol = "BTCUSDT"  # 币安API需要大写
        vnpy_symbol = "btcusdt"  # vnpy使用小写
        interval = "1h"     # 1小时K线，币安API使用的格式
        vnpy_interval = "1h"  # vnpy中的间隔格式
        
        # 检查现有数据
        min_date, max_date, count = check_existing_data(vnpy_symbol, vnpy_interval)
        
        # 定义下载时间范围 - 与回测脚本保持一致
        now = datetime.datetime.now()
        end_date = datetime.datetime(2024, 5, 1)  # 回测脚本中的结束时间
        
        # 如果结束时间在未来，设为当前时间
        if end_date > now:
            end_date = now
            
        start_date = datetime.datetime(2023, 1, 1)  # 回测脚本中的开始时间
        
        # 如果已有数据，只下载缺失的部分
        if count > 0:
            # 检查是否需要下载历史数据（早于现有数据的部分）
            if min_date and min_date > start_date:
                print(f"📥 下载早期数据: {start_date.strftime('%Y-%m-%d')} 至 {min_date.strftime('%Y-%m-%d')}...")
                download_historical_data(symbol, interval, start_date, min_date)
            
            # 检查是否需要下载最新数据（晚于现有数据的部分）
            if max_date and max_date < end_date:
                print(f"📥 下载最新数据: {max_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}...")
                download_historical_data(symbol, interval, max_date, end_date)
                
            if min_date <= start_date and max_date >= end_date:
                print("✅ 数据库中已有所需的完整数据，无需下载")
        else:
            # 如果没有数据，分段下载完整历史
            # 将长时间段分成多个较短的时间段，以避免API限制
            segments = []
            
            # 每次下载3个月数据
            current_date = start_date
            while current_date < end_date:
                next_date = current_date + datetime.timedelta(days=90)
                if next_date > end_date:
                    next_date = end_date
                segments.append((current_date, next_date))
                current_date = next_date
            
            print(f"📥 下载完整历史数据，分为{len(segments)}个时间段...")
            
            for i, (seg_start, seg_end) in enumerate(segments):
                print(f"📥 下载第{i+1}/{len(segments)}段: {seg_start.strftime('%Y-%m-%d')} 至 {seg_end.strftime('%Y-%m-%d')}...")
                download_historical_data(symbol, interval, seg_start, seg_end)
        
        print("✅ 数据下载完成")
        
        # 最后检查数据
        final_min_date, final_max_date, final_count = check_existing_data(vnpy_symbol, vnpy_interval)
        print(f"📊 最终数据统计:")
        print(f"   - 总记录数: {final_count}")
        if final_min_date and final_max_date:
            print(f"   - 数据范围: {final_min_date.strftime('%Y-%m-%d %H:%M:%S')} 至 {final_max_date.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 检查是否覆盖了回测所需的时间范围
        if final_min_date and final_max_date and final_min_date <= start_date and final_max_date >= end_date:
            print("✅ 数据已覆盖回测所需的完整时间范围")
        else:
            print("⚠️ 数据可能未完全覆盖回测所需的时间范围，请检查")
            
    except Exception as e:
        print(f"❌ 程序执行出错: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main() 