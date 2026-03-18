import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

class LCCForecaster:
    """基于全寿命周期成本 (LCC) 的智能预测引擎"""
    
    def __init__(self):
        self.linear_model = LinearRegression()
        self.poly_model = LinearRegression()
        self.poly_features = PolynomialFeatures(degree=2)
        
    def preprocess_data(self, df: pd.DataFrame, eq_type: str, target_col: str = '成本(万元)'):
        """数据预处理：筛选特定设备，并按季度汇总金额"""
        # 1. 筛选特定设备
        eq_df = df[df['设备类型'] == eq_type].copy()
        if eq_df.empty:
            return None
            
        # 2. 确保日期格式正确
        eq_df['日期'] = pd.to_datetime(eq_df['日期'])
        
        # 3. 按季度汇总成本 (降噪，寻找宏观趋势)
        eq_df['季度'] = eq_df['日期'].dt.to_period('Q')
        trend_df = eq_df.groupby('季度')[target_col].sum().reset_index()
        
        return trend_df

    def fit_and_predict(self, trend_df: pd.DataFrame, eq_type: str, periods_to_forecast: int = 4):
        """动态路由：根据设备物理特性选择拟合算法"""
        if trend_df is None or len(trend_df) < 3:
            return [], "数据不足"
            
        X = np.arange(len(trend_df)).reshape(-1, 1)
        y = trend_df['成本(万元)'].values
        
        future_X = np.arange(len(trend_df), len(trend_df) + periods_to_forecast).reshape(-1, 1)
        
        # --- 核心专家逻辑：动态选择算法 ---
        if eq_type in ["电缆终端", "隔离开关"]:
            # 老化设备：使用多项式拟合捕捉加速上升的维护成本
            X_poly = self.poly_features.fit_transform(X)
            self.poly_model.fit(X_poly, y)
            
            future_X_poly = self.poly_features.transform(future_X)
            predictions = self.poly_model.predict(future_X_poly)
            algorithm_used = "二次多项式回归 (老化加速特征)"
            
        else:
            # 耗材设备 (熔断器/避雷器)：使用线性拟合
            self.linear_model.fit(X, y)
            predictions = self.linear_model.predict(future_X)
            algorithm_used = "线性回归 (随机损耗特征)"
            
        # 确保预测成本不为负数
        predictions = np.maximum(predictions, 0)
        
        return predictions.tolist(), algorithm_used

    def save_plot(self, trend_df, predictions, eq_type, algorithm_used, save_dir="data"):
        """为每种设备单独生成带有专家说明的拟合图表"""
        plt.rcParams['font.sans-serif'] = ['SimHei'] 
        plt.rcParams['axes.unicode_minus'] = False
        
        plt.figure(figsize=(10, 6))
        
        # 绘制历史数据
        plt.plot(trend_df.index, trend_df['成本(万元)'], 'o-', label=f'历史实际成本', color='#1f77b4')
        
        # 绘制预测数据
        future_x = np.arange(len(trend_df), len(trend_df) + len(predictions))
        plt.plot(future_x, predictions, 'o--', label=f'未来预测趋势', color='#d62728')
        
        plt.title(f"{eq_type} LCC成本趋势预测\n(使用算法: {algorithm_used})", fontsize=14)
        plt.xlabel("时间周期 (季度)", fontsize=12)
        plt.ylabel("汇总成本 (万元)", fontsize=12)
        plt.legend(fontsize=12)
        plt.grid(True, linestyle='--', alpha=0.6)
        
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, f"forecast_{eq_type}.png")
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        return save_path