import os
import pandas as pd
import datetime
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

from src.loader import UniversalLoader
from src.extractor import InformationExtractor
from src.forecaster import LCCForecaster  # 导入我们新写的 LCC 预测引擎

load_dotenv()

# 1. 定义多设备状态结构
class GraphState(TypedDict):
    file_paths: List[str]
    extracted_records: List[dict]
    forecast_results: dict  # 存储多种设备的预测结果: {eq_type: {"predictions": [], "algo": "", "plot": ""}}
    final_output: str

# 2. 定义节点逻辑
def extraction_node(state: GraphState):
    """提取节点：读取所有 LCC 工单与合同"""
    all_data = []
    extractor = InformationExtractor()
    
    for path in state["file_paths"]:
        print(f"📄 正在摄取文件: {path}")
        if path.endswith(('.xlsx', '.csv')):
            loader = UniversalLoader(path)
            df = loader.load_as_dataframe()
            all_data.extend(df.to_dict(orient='records'))
        elif path.endswith('.docx') or path.endswith('.txt'):
            loader = UniversalLoader(path)
            text_doc = loader.load_as_text()
            # 简化的合同文本提取
            contract = extractor.extract_from_text(text_doc.page_content)
            all_data.append(contract.model_dump())
            
    return {"extracted_records": all_data}


def analytics_node(state: GraphState):
    """分析节点：动态感知用户上传的设备类型，并进行筛选拟合"""
    raw_records = state["extracted_records"]
    cleaned_data = []
    
    # 1. 异构数据对齐
    for r in raw_records:
        import re
        
        # 兼容性增强提取逻辑
        eq_type = r.get('设备类型') or r.get('equipment_type') or r.get('用途/电压等级') or r.get('类型')
        raw_amt = r.get('成本(万元)') or r.get('amount') or r.get('发生金额(万元)') or r.get('报价（含税）')
        date = r.get('日期') or r.get('date') or '2025-01-01'
        
        if eq_type and raw_amt is not None:
            amt = 0.0
            if isinstance(raw_amt, str):
                matches = re.findall(r"[\d]+[.]?[\d]*", raw_amt)
                if matches:
                    amt = float(matches[0])
            else:
                try:
                    amt = float(raw_amt)
                except:
                    amt = 0.0
                    
            if amt > 1000:
                amt = amt / 10000.0
                
            cleaned_data.append({
                '设备类型': eq_type,
                '日期': date,
                '成本(万元)': amt
            })

    df = pd.DataFrame(cleaned_data)
    forecast_results = {}
    forecaster = LCCForecaster()
    
    # 2. 动态感知与白名单过滤
    # 我们扩展白名单，加入用户刚才上传的非标设备 (低压配电 / 建筑)
    allowed_equipments = ["高压熔断器", "隔离开关", "交流避雷器", "电缆终端", "低压配电 0.6/1kV", "低压配线（建筑）", "电缆"]
    
    if not df.empty and '设备类型' in df.columns:
        # 动态提取用户本次上传的文件中实际包含了哪些设备
        uploaded_equipments = df['设备类型'].dropna().unique()
        
        # 取交集：既在白名单内，又是用户实际上传的
        target_equipments = [eq for eq in uploaded_equipments if eq in allowed_equipments]
        
        print(f"🧠 系统检测到本次上传的有效设备为: {target_equipments}")
        
        for eq in target_equipments:
            trend_df = forecaster.preprocess_data(df, eq_type=eq, target_col='成本(万元)')
            
            if trend_df is not None and len(trend_df) >= 3:
                predictions, algo = forecaster.fit_and_predict(trend_df, eq_type=eq)
                plot_path = forecaster.save_plot(trend_df, predictions, eq, algo)
                
                forecast_results[eq] = {
                    "predictions": predictions,
                    "algorithm": algo,
                    "plot_path": plot_path,
                    "data_count": len(trend_df)
                }
                
    return {"forecast_results": forecast_results}

def report_node(state: GraphState):
    """报告节点：根据实际分析的设备动态生成报告"""
    forecasts = state.get("forecast_results", {})
    
    # 获取本次真正成功分析了的设备列表
    analyzed_eqs = list(forecasts.keys())
    
    md = f"# ⚡ 电网核心装备 LCC 专项评估报告\n\n"
    md += f"**生成时间：** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    if not analyzed_eqs:
        md += "## ⚠️ 数据不足或设备不符\n本次上传的文件中，未能提取到目标设备（高压熔断器、隔离开关、交流避雷器、电缆终端）的有效数据，或单一设备的数据周期少于3个，无法进行数学拟合预测。\n"
    else:
        # 报告标题动态显示用户上传的设备
        md += f"**本次分析对象：** {', '.join(analyzed_eqs)}\n\n---\n\n"
        md += f"## 1. 成本趋势预测与专家诊断\n\n"
        
        for eq, data in forecasts.items():
            md += f"### 🔹 {eq} (基于 {data['data_count']} 个聚合数据点)\n"
            md += f"- **匹配算法**: `{data['algorithm']}`\n"
            md += f"- **未来 4 季度成本预测 (万元)**: "
            formatted_preds = [f"{v:.2f}" for v in data['predictions']]
            md += f"{', '.join(formatted_preds)}\n\n"
            
            if data['plot_path']:
                md += f"![{eq}预测图表]({os.path.basename(data['plot_path'])})\n\n"
                
    md += f"---\n*报告由 GALCA 多智能体系统自动生成。*\n"
    
    report_path = "data/电网装备LCC综合评估报告.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)
        
    return {"final_output": f"✅ 分析完成！报告已生成至: {report_path}"}

# 3. 构建工作流
workflow = StateGraph(GraphState)
workflow.add_node("extract", extraction_node)
workflow.add_node("analyze", analytics_node)
workflow.add_node("report", report_node)

workflow.set_entry_point("extract")
workflow.add_edge("extract", "analyze")
workflow.add_edge("analyze", "report")
workflow.add_edge("report", END)

app = workflow.compile()

if __name__ == "__main__":
    # 指定我们刚才用脚本生成的真实业务数据
    test_excel = "data/LCC工单记录表_2020_2025.xlsx"
    
    if not os.path.exists(test_excel):
        print(f"❌ 找不到 {test_excel}，请先运行 generate_lcc_dataset.py！")
    else:
        inputs = {"file_paths": [test_excel]}
        config = {"recursion_limit": 50}
        
        for output in app.stream(inputs, config):
            print("--- 节点输出 ---")
            if "report" in output:
                print(output["report"]["final_output"])