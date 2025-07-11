# 比特币实盘交易指南

这个文档介绍如何使用`binance_live_trader.py`脚本进行比特币的实盘交易操作。

## 准备工作

1. **创建币安账户**
   - 如果没有币安账户，请先在[币安官网](https://www.binance.com)注册

2. **创建API密钥**
   - 登录币安账户
   - 进入"API管理"页面
   - 创建API密钥（请保存好API密钥和密钥）
   - 设置适当的API权限（至少需要"读取"和"现货交易"权限）

3. **配置密钥**
   - 编辑`config.json`文件
   - 填入你的API密钥和密钥
   - 设置`test_mode`为`true`可以使用测试网络（推荐先测试）

## 使用方法

### 1. 基本命令

```bash
/usr/local/bin/python3.10 binance_live_trader.py
```

### 2. 交易参数说明

脚本中的交易参数来源于回测优化结果：

- `rsi_buy_level`: 40 - RSI买入阈值
- `rsi_sell_level`: 80 - RSI卖出阈值
- `stop_loss_pct`: 0.03 - 止损百分比
- `signal_num`: 2 - 信号数量阈值
- `fast_window`: 5 - 快速均线窗口
- `slow_window`: 30 - 慢速均线窗口

### 3. 交易功能

脚本支持以下交易功能：

- 市价买入BTC (`buy_market`)
- 市价卖出BTC (`sell_market`)
- 限价买入BTC (`buy_limit`)
- 限价卖出BTC (`sell_limit`)
- 取消订单 (`cancel_order`)
- 查询账户余额 (`get_account_balance`)
- 获取当前持仓 (`get_position`)

## 安全建议

1. **从测试开始**：
   - 首次使用时，请将`test_mode`设置为`true`，使用币安测试网络
   - 测试网络无需真实资金，可以安全测试所有功能

2. **小额测试**：
   - 切换到实盘网络后，先使用小额资金测试
   - 调整`trade_amount_usdt`和`trade_percent_btc`参数控制交易量

3. **密钥安全**：
   - 不要分享API密钥
   - 不要将密钥提交到公共代码仓库
   - 定期更换API密钥

## 错误排查

如果遇到问题，请检查：

1. API密钥是否正确
2. API密钥是否有足够权限
3. 账户是否有足够余额
4. 交易量是否符合交易所最低要求

详细的错误日志保存在`binance_trading.log`文件中。

## 注意事项

- 市场波动可能导致滑点，实际成交价格可能与预期不同
- 频繁交易会产生手续费，请考虑交易成本
- 不同市场环境下策略表现可能有所不同
- 请遵守当地法律法规

## 延伸阅读

- [币安API文档](https://binance-docs.github.io/apidocs/)
- [python-binance库文档](https://python-binance.readthedocs.io/) 