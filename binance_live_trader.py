#!/usr/bin/env python3.10
# -*- coding: utf-8 -*-
"""
BTC实盘交易脚本
===================
基于三重信号策略的实盘交易实现，通过币安API进行实际下单操作

作者: HangerLin
创建时间: 2025-07
"""

import sys
import time
import json
import logging
import datetime
from decimal import Decimal, ROUND_DOWN
from typing import Dict, List, Optional, Tuple

from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException, BinanceOrderException

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("binance_trading.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class BinanceLiveTrader:
    """比特币实盘交易类"""
    
    def __init__(self, api_key: str, api_secret: str, test_mode: bool = True):
        """
        初始化交易类
        
        参数:
            api_key: 币安API密钥
            api_secret: 币安API密钥
            test_mode: 是否使用测试模式 (True=测试网络, False=实盘网络)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.test_mode = test_mode
        
        # 初始化客户端
        if test_mode:
            self.client = Client(api_key, api_secret, testnet=True)
            logger.info("使用测试网络模式")
        else:
            self.client = Client(api_key, api_secret)
            logger.info("使用实盘网络模式")
        
        # 交易参数
        self.symbol = "BTCUSDT"  # 交易对
        self.order_precision = 5  # BTC数量精度 (5位小数)
        self.price_precision = 2  # 价格精度 (2位小数)
        
        # 策略参数 (来自回测优化结果)
        self.rsi_buy_level = 40
        self.rsi_sell_level = 80
        self.stop_loss_pct = 0.03
        self.signal_num = 2
        self.fast_window = 5
        self.slow_window = 30
        
        # 交易状态
        self.position = 0.0  # 当前持仓量
        self.entry_price = 0.0  # 入场价格
        
        # 检查系统状态
        self._check_system_status()
        
    def _check_system_status(self):
        """检查系统状态"""
        try:
            status = self.client.get_system_status()
            logger.info(f"币安系统状态: {status}")
            
            # 获取交易规则
            exchange_info = self.client.get_exchange_info()
            symbol_info = next((s for s in exchange_info['symbols'] if s['symbol'] == self.symbol), None)
            
            if not symbol_info:
                logger.error(f"找不到交易对信息: {self.symbol}")
                sys.exit(1)
                
            logger.info(f"交易对信息: {self.symbol}")
            logger.info(f"状态: {symbol_info['status']}")
            
            # 提取交易规则
            for filter_item in symbol_info['filters']:
                if filter_item['filterType'] == 'LOT_SIZE':
                    self.min_qty = float(filter_item['minQty'])
                    self.max_qty = float(filter_item['maxQty'])
                    self.step_size = float(filter_item['stepSize'])
                    logger.info(f"交易量限制 - 最小: {self.min_qty}, 最大: {self.max_qty}, 步长: {self.step_size}")
                    
                elif filter_item['filterType'] == 'PRICE_FILTER':
                    self.min_price = float(filter_item['minPrice'])
                    self.max_price = float(filter_item['maxPrice'])
                    self.tick_size = float(filter_item['tickSize'])
                    logger.info(f"价格限制 - 最小: {self.min_price}, 最大: {self.max_price}, 步长: {self.tick_size}")
            
        except Exception as e:
            logger.error(f"检查系统状态时出错: {str(e)}")
            sys.exit(1)
    
    def get_account_balance(self) -> dict:
        """获取账户余额"""
        try:
            account = self.client.get_account()
            balances = {}
            
            for asset in account['balances']:
                free = float(asset['free'])
                locked = float(asset['locked'])
                if free > 0 or locked > 0:
                    balances[asset['asset']] = {
                        'free': free,
                        'locked': locked,
                        'total': free + locked
                    }
            
            return balances
            
        except Exception as e:
            logger.error(f"获取账户余额失败: {str(e)}")
            return {}
    
    def get_current_price(self) -> float:
        """获取当前BTC价格"""
        try:
            ticker = self.client.get_symbol_ticker(symbol=self.symbol)
            price = float(ticker['price'])
            logger.info(f"当前{self.symbol}价格: {price}")
            return price
        except Exception as e:
            logger.error(f"获取价格失败: {str(e)}")
            return 0
    
    def round_quantity(self, quantity: float) -> float:
        """根据交易对规则调整BTC数量精度"""
        step_size_str = str(self.step_size).rstrip('0').rstrip('.') if '.' in str(self.step_size) else str(self.step_size)
        precision = len(step_size_str.split('.')[-1]) if '.' in step_size_str else 0
        
        # 使用Decimal确保精确舍入
        return float(Decimal(str(quantity)).quantize(Decimal('0.' + '0' * precision), rounding=ROUND_DOWN))
    
    def round_price(self, price: float) -> float:
        """根据交易对规则调整价格精度"""
        tick_size_str = str(self.tick_size).rstrip('0').rstrip('.') if '.' in str(self.tick_size) else str(self.tick_size)
        precision = len(tick_size_str.split('.')[-1]) if '.' in tick_size_str else 0
        
        # 使用Decimal确保精确舍入
        return float(Decimal(str(price)).quantize(Decimal('0.' + '0' * precision), rounding=ROUND_DOWN))
    
    def buy_market(self, quantity: float) -> Optional[dict]:
        """
        市价买入BTC
        
        参数:
            quantity: BTC数量
        返回:
            订单信息或None(如果失败)
        """
        try:
            # 调整数量精度
            quantity = self.round_quantity(quantity)
            if quantity < self.min_qty:
                logger.error(f"买入数量 {quantity} 小于最小交易量 {self.min_qty}")
                return None
                
            logger.info(f"准备市价买入 {quantity} BTC")
            
            # 创建市价买单
            order = self.client.create_order(
                symbol=self.symbol,
                side=SIDE_BUY,
                type=ORDER_TYPE_MARKET,
                quantity=quantity
            )
            
            logger.info(f"买单已提交: {order}")
            
            # 更新持仓信息
            self.position += quantity
            self.entry_price = float(order['fills'][0]['price']) if 'fills' in order and order['fills'] else self.get_current_price()
            
            logger.info(f"买入成功 - 数量: {quantity}, 价格: {self.entry_price}")
            return order
            
        except BinanceAPIException as e:
            logger.error(f"币安API错误: {e.status_code} - {e.message}")
            return None
        except BinanceOrderException as e:
            logger.error(f"订单错误: {e.message}")
            return None
        except Exception as e:
            logger.error(f"买入过程中发生未知错误: {str(e)}")
            return None
    
    def sell_market(self, quantity: float) -> Optional[dict]:
        """
        市价卖出BTC
        
        参数:
            quantity: BTC数量
        返回:
            订单信息或None(如果失败)
        """
        try:
            # 调整数量精度
            quantity = self.round_quantity(quantity)
            if quantity < self.min_qty:
                logger.error(f"卖出数量 {quantity} 小于最小交易量 {self.min_qty}")
                return None
                
            logger.info(f"准备市价卖出 {quantity} BTC")
            
            # 创建市价卖单
            order = self.client.create_order(
                symbol=self.symbol,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=quantity
            )
            
            logger.info(f"卖单已提交: {order}")
            
            # 更新持仓信息
            self.position -= quantity
            if self.position <= 0:
                self.position = 0
                self.entry_price = 0
            
            logger.info(f"卖出成功 - 数量: {quantity}")
            return order
            
        except BinanceAPIException as e:
            logger.error(f"币安API错误: {e.status_code} - {e.message}")
            return None
        except BinanceOrderException as e:
            logger.error(f"订单错误: {e.message}")
            return None
        except Exception as e:
            logger.error(f"卖出过程中发生未知错误: {str(e)}")
            return None
    
    def buy_limit(self, quantity: float, price: float) -> Optional[dict]:
        """
        限价买入BTC
        
        参数:
            quantity: BTC数量
            price: 限价
        返回:
            订单信息或None(如果失败)
        """
        try:
            # 调整数量和价格精度
            quantity = self.round_quantity(quantity)
            price = self.round_price(price)
            
            if quantity < self.min_qty:
                logger.error(f"买入数量 {quantity} 小于最小交易量 {self.min_qty}")
                return None
                
            logger.info(f"准备限价买入 {quantity} BTC, 价格: {price}")
            
            # 创建限价买单
            order = self.client.create_order(
                symbol=self.symbol,
                side=SIDE_BUY,
                type=ORDER_TYPE_LIMIT,
                timeInForce=TIME_IN_FORCE_GTC,
                quantity=quantity,
                price=str(price)
            )
            
            logger.info(f"限价买单已提交: {order}")
            return order
            
        except BinanceAPIException as e:
            logger.error(f"币安API错误: {e.status_code} - {e.message}")
            return None
        except BinanceOrderException as e:
            logger.error(f"订单错误: {e.message}")
            return None
        except Exception as e:
            logger.error(f"限价买入过程中发生未知错误: {str(e)}")
            return None
    
    def sell_limit(self, quantity: float, price: float) -> Optional[dict]:
        """
        限价卖出BTC
        
        参数:
            quantity: BTC数量
            price: 限价
        返回:
            订单信息或None(如果失败)
        """
        try:
            # 调整数量和价格精度
            quantity = self.round_quantity(quantity)
            price = self.round_price(price)
            
            if quantity < self.min_qty:
                logger.error(f"卖出数量 {quantity} 小于最小交易量 {self.min_qty}")
                return None
                
            logger.info(f"准备限价卖出 {quantity} BTC, 价格: {price}")
            
            # 创建限价卖单
            order = self.client.create_order(
                symbol=self.symbol,
                side=SIDE_SELL,
                type=ORDER_TYPE_LIMIT,
                timeInForce=TIME_IN_FORCE_GTC,
                quantity=quantity,
                price=str(price)
            )
            
            logger.info(f"限价卖单已提交: {order}")
            return order
            
        except BinanceAPIException as e:
            logger.error(f"币安API错误: {e.status_code} - {e.message}")
            return None
        except BinanceOrderException as e:
            logger.error(f"订单错误: {e.message}")
            return None
        except Exception as e:
            logger.error(f"限价卖出过程中发生未知错误: {str(e)}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """
        取消订单
        
        参数:
            order_id: 订单ID
        返回:
            是否取消成功
        """
        try:
            result = self.client.cancel_order(
                symbol=self.symbol,
                orderId=order_id
            )
            logger.info(f"已取消订单: {result}")
            return True
        except Exception as e:
            logger.error(f"取消订单失败: {str(e)}")
            return False
    
    def get_open_orders(self) -> List[dict]:
        """
        获取当前未完成的订单
        
        返回:
            订单列表
        """
        try:
            orders = self.client.get_open_orders(symbol=self.symbol)
            logger.info(f"当前未完成订单数量: {len(orders)}")
            return orders
        except Exception as e:
            logger.error(f"获取未完成订单失败: {str(e)}")
            return []
    
    def get_position(self) -> float:
        """
        获取当前BTC持仓量
        
        返回:
            BTC持仓量
        """
        try:
            balances = self.get_account_balance()
            if 'BTC' in balances:
                self.position = balances['BTC']['free'] + balances['BTC']['locked']
                logger.info(f"当前BTC持仓: {self.position}")
            else:
                self.position = 0
                logger.info("当前无BTC持仓")
            return self.position
        except Exception as e:
            logger.error(f"获取持仓量失败: {str(e)}")
            return 0
    
    def calculate_buy_amount(self, usdt_amount: float, current_price: float) -> float:
        """
        根据USDT金额计算可以购买的BTC数量
        
        参数:
            usdt_amount: USDT金额
            current_price: BTC当前价格
        返回:
            可购买的BTC数量
        """
        if current_price <= 0:
            return 0
            
        # 计算原始数量
        raw_quantity = usdt_amount / current_price
        
        # 考虑手续费 (假设0.1%手续费)
        quantity_after_fee = raw_quantity * 0.999
        
        # 根据交易规则调整精度
        final_quantity = self.round_quantity(quantity_after_fee)
        
        logger.info(f"USDT: {usdt_amount}, 价格: {current_price}, 可购买BTC: {final_quantity}")
        return final_quantity
    
    def get_order_status(self, order_id: str) -> Optional[dict]:
        """
        获取订单状态
        
        参数:
            order_id: 订单ID
        返回:
            订单信息或None(如果失败)
        """
        try:
            order = self.client.get_order(
                symbol=self.symbol,
                orderId=order_id
            )
            logger.info(f"订单状态: {order}")
            return order
        except Exception as e:
            logger.error(f"获取订单状态失败: {str(e)}")
            return None


def demo_trading():
    """
    实盘交易演示函数
    """
    # 您的API密钥和密码
    api_key = "YOUR_API_KEY_HERE"  # 请替换为您的API密钥
    api_secret = "YOUR_API_SECRET_HERE"  # 请替换为您的API密钥
    
    # 初始化交易类 (使用测试网络)
    trader = BinanceLiveTrader(api_key, api_secret, test_mode=True)
    
    # 获取账户余额
    balances = trader.get_account_balance()
    print("\n==== 账户余额 ====")
    for asset, balance in balances.items():
        print(f"{asset}: {balance['free']} (可用) + {balance['locked']} (锁定) = {balance['total']} (总计)")
    
    # 获取当前BTC价格
    btc_price = trader.get_current_price()
    
    # 演示: 如果想使用一定数量的USDT买入BTC
    if 'USDT' in balances:
        usdt_available = balances['USDT']['free']
        print(f"\n可用USDT: {usdt_available}")
        
        # 使用一部分USDT (例如25%)买入BTC
        usdt_to_use = usdt_available * 0.25
        btc_amount = trader.calculate_buy_amount(usdt_to_use, btc_price)
        
        if btc_amount > 0:
            print(f"\n==== 买入演示 ====")
            print(f"准备使用 {usdt_to_use} USDT 买入 {btc_amount} BTC")
            
            # 确认是否执行买入操作
            confirm = input("是否执行买入操作? (y/n): ")
            if confirm.lower() == 'y':
                order = trader.buy_market(btc_amount)
                if order:
                    print(f"买入订单已执行: {order['orderId']}")
            else:
                print("取消买入操作")
    
    # 获取当前BTC持仓
    btc_position = trader.get_position()
    
    # 演示: 如果有BTC持仓，卖出一部分
    if btc_position > 0:
        print(f"\n==== 卖出演示 ====")
        print(f"当前BTC持仓: {btc_position}")
        
        # 卖出部分BTC (例如25%)
        btc_to_sell = trader.round_quantity(btc_position * 0.25)
        
        if btc_to_sell >= trader.min_qty:
            print(f"准备卖出 {btc_to_sell} BTC")
            
            # 确认是否执行卖出操作
            confirm = input("是否执行卖出操作? (y/n): ")
            if confirm.lower() == 'y':
                order = trader.sell_market(btc_to_sell)
                if order:
                    print(f"卖出订单已执行: {order['orderId']}")
            else:
                print("取消卖出操作")
        else:
            print(f"卖出数量 {btc_to_sell} 小于最小交易量 {trader.min_qty}")
    
    # 演示: 查询未完成订单
    open_orders = trader.get_open_orders()
    if open_orders:
        print("\n==== 未完成订单 ====")
        for order in open_orders:
            print(f"订单ID: {order['orderId']}, 类型: {order['type']}, 方向: {order['side']}, 价格: {order['price']}, 数量: {order['origQty']}")
            
            # 确认是否取消订单
            confirm = input(f"是否取消订单 {order['orderId']}? (y/n): ")
            if confirm.lower() == 'y':
                if trader.cancel_order(order['orderId']):
                    print(f"订单 {order['orderId']} 已取消")
            else:
                print(f"保留订单 {order['orderId']}")


def main():
    """主函数"""
    print("\n===== 比特币实盘交易系统 =====")
    print("1. 执行交易演示")
    print("2. 退出程序")
    
    choice = input("\n请选择操作: ")
    
    if choice == '1':
        demo_trading()
    else:
        print("退出程序")


if __name__ == "__main__":
    main() 