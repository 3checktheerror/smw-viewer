#!/usr/bin/env python3
"""
信号收益率计算器
从MongoDB获取告警信号数据，生成用于计算收益率的静态HTML界面
"""

import json
import sys
import os
from datetime import datetime
from typing import List, Dict, Any

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.utils.mongo_client import MongoDBClient
from backend.app.core.config import settings


class SignalCalculator:
    """信号收益率计算器"""
    
    def __init__(self):
        self.mongo_client = MongoDBClient()
        self.db_name = "graph"
        self.collection_name = "debot_signal"
    
    def get_signal_data(self) -> List[Dict[str, Any]]:
        """
        获取2025-05-09之后的所有信号数据
        """
        try:
            # 转换日期为时间戳
            
            # 查询条件
            filter_dict = {
                "store_time": {"$gte": '2025-05-09'}
            }
            
            # 获取数据
            signals = self.mongo_client.find_many(
                collection_name=self.collection_name,
                filter_dict=filter_dict,
                db_name=self.db_name
            )
            
            print(f"获取到 {len(signals)} 条信号数据")
            return signals
            
        except Exception as e:
            print(f"获取信号数据失败: {e}")
            return []
    
    def generate_html(self, signals: List[Dict[str, Any]]) -> str:
        """
        生成包含信号数据和计算逻辑的静态HTML页面
        """
        # 将信号数据转换为JSON字符串，嵌入到HTML中
        signals_json = json.dumps(signals, default=str, ensure_ascii=False)
        
        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>信号收益率计算器</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}

        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 300;
        }}

        .header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}

        .main-content {{
            padding: 40px;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}

        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
        }}

        .stat-number {{
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 5px;
        }}

        .stat-label {{
            font-size: 0.9em;
            opacity: 0.9;
        }}

        .calculator-section {{
            background: #f8f9fa;
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 30px;
        }}

        .section-title {{
            font-size: 1.5em;
            color: #333;
            margin-bottom: 25px;
            text-align: center;
            font-weight: 500;
        }}

        .form-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 25px;
            margin-bottom: 30px;
        }}

        .form-group {{
            display: flex;
            flex-direction: column;
        }}

        .form-label {{
            font-weight: 500;
            color: #333;
            margin-bottom: 8px;
            font-size: 0.95em;
        }}

        .form-input {{
            padding: 12px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 1em;
            transition: all 0.3s ease;
            background: white;
        }}

        .form-input:focus {{
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }}

        .calculate-btn {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 40px;
            border: none;
            border-radius: 10px;
            font-size: 1.1em;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s ease;
            margin: 20px auto;
            display: block;
            min-width: 200px;
        }}

        .calculate-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }}

        .results-section {{
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            color: white;
            border-radius: 15px;
            padding: 30px;
            margin-top: 20px;
            display: none;
        }}

        .results-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }}

        .result-item {{
            text-align: center;
            padding: 20px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            backdrop-filter: blur(10px);
        }}

        .result-value {{
            font-size: 2em;
            font-weight: bold;
            margin-bottom: 5px;
        }}

        .result-label {{
            font-size: 0.9em;
            opacity: 0.9;
        }}

        .error-message {{
            background: #ff6b6b;
            color: white;
            padding: 15px;
            border-radius: 10px;
            margin: 20px 0;
            text-align: center;
            display: none;
        }}

        .input-hint {{
            font-size: 0.8em;
            color: #666;
            margin-top: 5px;
        }}

        @media (max-width: 768px) {{
            .form-grid {{
                grid-template-columns: 1fr;
            }}
            
            .stats-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
            
            .header h1 {{
                font-size: 2em;
            }}
            
            .main-content {{
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>信号收益率计算器</h1>
            <p>基于历史告警信号数据计算投资收益率</p>
        </div>
        
        <div class="main-content">
            <!-- 数据统计 -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number" id="totalSignals">0</div>
                    <div class="stat-label">总信号数量</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="avgIncrease">0%</div>
                    <div class="stat-label">平均最大涨幅</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="maxIncrease">0%</div>
                    <div class="stat-label">最大涨幅</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="positiveSignals">0%</div>
                    <div class="stat-label">盈利信号比例</div>
                </div>
            </div>

            <!-- 计算器 -->
            <div class="calculator-section">
                <h2 class="section-title">收益率计算器</h2>
                
                <div class="form-grid">
                    <div class="form-group">
                        <label class="form-label" for="profitRatio">止盈比例 (%)</label>
                        <input type="number" id="profitRatio" class="form-input" 
                               placeholder="例如: 50" min="1" max="1000" step="0.1">
                        <div class="input-hint">涨到此比例时卖出获利</div>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label" for="lossRatio">止损比例 (%)</label>
                        <input type="number" id="lossRatio" class="form-input" 
                               placeholder="例如: 20" min="1" max="100" step="0.1">
                        <div class="input-hint">跌到此比例时卖出止损</div>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label" for="investAmount">投资金额</label>
                        <input type="number" id="investAmount" class="form-input" 
                               placeholder="例如: 1000" min="1" step="0.01">
                        <div class="input-hint">单次投资金额（USDT）</div>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label" for="currency">投资币种</label>
                        <select id="currency" class="form-input">
                            <option value="USDT">USDT</option>
                            <option value="SOL">SOL</option>
                        </select>
                        <div class="input-hint">选择投资使用的币种</div>
                    </div>
                </div>
                
                <button class="calculate-btn" onclick="calculateProfit()">
                    计算收益率
                </button>
                
                <div class="error-message" id="errorMessage"></div>
            </div>

            <!-- 结果展示 -->
            <div class="results-section" id="resultsSection">
                <h2 class="section-title">计算结果</h2>
                <div class="results-grid">
                    <div class="result-item">
                        <div class="result-value" id="totalProfit">$0</div>
                        <div class="result-label">总利润</div>
                    </div>
                    <div class="result-item">
                        <div class="result-value" id="profitRate">0%</div>
                        <div class="result-label">利润率</div>
                    </div>
                    <div class="result-item">
                        <div class="result-value" id="successRate">0%</div>
                        <div class="result-label">成功率</div>
                    </div>
                    <div class="result-item">
                        <div class="result-value" id="avgProfitPerSignal">$0</div>
                        <div class="result-label">平均每信号收益</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // 嵌入的信号数据
        const signalData = {signals_json};
        
        // SOL/USDT 汇率（简化处理，实际应该从API获取）
        const SOL_TO_USDT = 20; // 假设1 SOL = 20 USDT
        
        // 初始化页面
        document.addEventListener('DOMContentLoaded', function() {{
            updateStatistics();
        }});
        
        function updateStatistics() {{
            const totalSignals = signalData.length;
            
            if (totalSignals === 0) {{
                document.getElementById('totalSignals').textContent = '0';
                document.getElementById('avgIncrease').textContent = '0%';
                document.getElementById('maxIncrease').textContent = '0%';
                document.getElementById('positiveSignals').textContent = '0%';
                return;
            }}
            
            // 计算统计数据
            const increases = signalData.map(signal => signal.max_increase || 0);
            const avgIncrease = increases.reduce((sum, val) => sum + val, 0) / increases.length;
            const maxIncrease = Math.max(...increases);
            const positiveCount = increases.filter(val => val > 0).length;
            const positiveRate = (positiveCount / totalSignals) * 100;
            
            // 更新显示
            document.getElementById('totalSignals').textContent = totalSignals.toLocaleString();
            document.getElementById('avgIncrease').textContent = (avgIncrease * 100).toFixed(1) + '%';
            document.getElementById('maxIncrease').textContent = (maxIncrease * 100).toFixed(1) + '%';
            document.getElementById('positiveSignals').textContent = positiveRate.toFixed(1) + '%';
        }}
        
        function calculateProfit() {{
            // 获取输入值
            const profitRatio = parseFloat(document.getElementById('profitRatio').value);
            const lossRatio = parseFloat(document.getElementById('lossRatio').value);
            const investAmount = parseFloat(document.getElementById('investAmount').value);
            const currency = document.getElementById('currency').value;
            
            // 验证输入
            if (!profitRatio || !lossRatio || !investAmount) {{
                showError('请填写所有必填字段！');
                return;
            }}
            
            if (profitRatio <= 0 || lossRatio <= 0 || investAmount <= 0) {{
                showError('所有数值必须大于0！');
                return;
            }}
            
            if (lossRatio >= 100) {{
                showError('止损比例不能大于等于100%！');
                return;
            }}
            
            hideError();
            
            // 转换投资金额为USDT
            const investAmountUSDT = currency === 'SOL' ? investAmount * SOL_TO_USDT : investAmount;
            
            // 计算每个信号的收益
            let totalProfit = 0;
            let successfulTrades = 0;
            
            signalData.forEach(signal => {{
                const maxIncrease = signal.max_increase || 0;
                const maxIncreasePercent = maxIncrease * 100;
                
                let profit = 0;
                
                if (maxIncreasePercent >= profitRatio) {{
                    // 达到止盈目标
                    profit = investAmountUSDT * (profitRatio / 100);
                    successfulTrades++;
                }} else if (maxIncreasePercent < 0 && Math.abs(maxIncreasePercent) >= lossRatio) {{
                    // 触发止损
                    profit = -investAmountUSDT * (lossRatio / 100);
                }} else {{
                    // 按实际涨跌幅计算
                    profit = investAmountUSDT * (maxIncreasePercent / 100);
                    if (profit > 0) successfulTrades++;
                }}
                
                totalProfit += profit;
            }});
            
            // 计算指标
            const totalInvestment = investAmountUSDT * signalData.length;
            const profitRate = (totalProfit / totalInvestment) * 100;
            const successRate = (successfulTrades / signalData.length) * 100;
            const avgProfitPerSignal = totalProfit / signalData.length;
            
            // 显示结果
            document.getElementById('totalProfit').textContent = 
                (currency === 'SOL' ? 
                    (totalProfit / SOL_TO_USDT).toFixed(2) + ' SOL' : 
                    '$' + totalProfit.toFixed(2));
            document.getElementById('profitRate').textContent = profitRate.toFixed(2) + '%';
            document.getElementById('successRate').textContent = successRate.toFixed(1) + '%';
            document.getElementById('avgProfitPerSignal').textContent = 
                (currency === 'SOL' ? 
                    (avgProfitPerSignal / SOL_TO_USDT).toFixed(2) + ' SOL' : 
                    '$' + avgProfitPerSignal.toFixed(2));
            
            // 显示结果区域
            document.getElementById('resultsSection').style.display = 'block';
            
            // 滚动到结果区域
            document.getElementById('resultsSection').scrollIntoView({{ 
                behavior: 'smooth' 
            }});
        }}
        
        function showError(message) {{
            const errorElement = document.getElementById('errorMessage');
            errorElement.textContent = message;
            errorElement.style.display = 'block';
        }}
        
        function hideError() {{
            document.getElementById('errorMessage').style.display = 'none';
        }}
        
        // 输入框回车事件
        document.addEventListener('keypress', function(e) {{
            if (e.key === 'Enter') {{
                calculateProfit();
            }}
        }});
    </script>
</body>
</html>
        """
        
        return html_content
    
    def save_html(self, html_content: str, filename: str = "signal_calculator.html"):
        """
        保存HTML文件
        """
        try:
            filepath = os.path.join(os.path.dirname(__file__), filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"HTML文件已保存到: {filepath}")
            return filepath
        except Exception as e:
            print(f"保存HTML文件失败: {e}")
            return None
    
    def run(self):
        """
        运行计算器：获取数据并生成HTML
        """
        print("正在获取信号数据...")
        signals = self.get_signal_data()
        
        print("正在生成HTML界面...")
        html_content = self.generate_html(signals)
        
        print("正在保存HTML文件...")
        filepath = self.save_html(html_content)
        
        if filepath:
            print(f"\\n信号收益率计算器已生成完成！")
            print(f"文件路径: {filepath}")
            print(f"请在浏览器中打开该文件查看界面")
        else:
            print("生成失败！")


def main():
    """主函数"""
    calculator = SignalCalculator()
    calculator.run()


if __name__ == "__main__":
    main()
