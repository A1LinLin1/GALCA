import os
import shutil
from typing import List
from fastapi import FastAPI, Depends, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from . import models
from .database import engine, get_db

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="GALCA Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

import json
import uuid
from src.main_graph import app as graph_app

def process_documents_background(file_paths: List[str], db: Session):
    print(f"🚀 [后台任务] 开始处理 {len(file_paths)} 个文件: {file_paths}")
    try:
        inputs = {"file_paths": file_paths}
        config = {"recursion_limit": 50}
        job_id = str(uuid.uuid4())
        
        final_state = graph_app.invoke(inputs, config)
        
        if final_state:
            # 存入提取记录
            records = final_state.get("extracted_records", [])
            for r in records:
                # 智能增强：兼容各种可能的非标准表头
                eq_type = r.get('设备类型') or r.get('equipment_type') or r.get('用途/电压等级') or r.get('类型') or '未知设备'
                model_type = r.get('规格型号') or r.get('equipment_model') or r.get('规格/型号') or r.get('型号') or '-'
                cost_cat = r.get('工单类型(成本大类)') or r.get('cost_category') or '运行成本'
                cost_sub = r.get('具体维修内容(成本子项)') or r.get('cost_subcategory') or r.get('用途') or '-'
                
                # 兼容复杂的金额文本提取（比如 "¥198.05/米" 或者 "1.5–16 mm²：¥2.33–¥24.49/米"）
                raw_amt = r.get('发生金额(万元)') or r.get('成本(万元)') or r.get('amount') or r.get('报价（含税）') or 0.0
                amt = 0.0
                if isinstance(raw_amt, str):
                    import re
                    # 尝试用正则提取第一个符合的数字序列
                    matches = re.findall(r"[\d]+[.]?[\d]*", raw_amt)
                    if matches:
                        amt = float(matches[0])
                else:
                    try:
                        amt = float(raw_amt)
                    except:
                        amt = 0.0
                        
                # 金额量级标准化(万元换算)
                if amt > 1000 and (not r.get('发生金额(万元)')):
                    amt = amt / 10000.0

                record = models.EquipmentCostRecord(
                    job_id=job_id,
                    equipment_type=str(eq_type),
                    equipment_model=str(model_type),
                    cost_category=str(cost_cat),
                    cost_subcategory=str(cost_sub),
                    amount=amt,
                    date=str(r.get('日期') or r.get('date') or '2025-01-01'),
                    source_document=file_paths[0].split('/')[-1] if file_paths else "API"
                )
                db.add(record)
                
            # 存入预测结果
            forecasts = final_state.get("forecast_results", {})
            for eq, data in forecasts.items():
                existing = db.query(models.ForecastResult).filter(models.ForecastResult.equipment_type == eq).first()
                preds = data.get("predictions", [])
                algo = data.get("algorithm", "PolynomialRegression")
                if existing:
                    existing.forecast_json = json.dumps(preds)
                    existing.algo_used = algo
                else:
                    new_forecast = models.ForecastResult(
                        equipment_type=eq,
                        algo_used=algo,
                        equation="y = f(x)",
                        forecast_json=json.dumps(preds)
                    )
                    db.add(new_forecast)
                    
            db.commit()
            print("✅ [后台任务] 智能体提取完成并成功写入数据库！")
    except Exception as e:
        print(f"❌ [后台任务] 处理异常: {e}")

@app.post("/api/v1/upload")
async def upload_documents(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(None),
    files: List[UploadFile] = File([]),
    db: Session = Depends(get_db)
):
    saved_paths = []
    file_list = []
    if file:
        file_list.append(file)
    if files:
        file_list.extend(files)
        
    for f in file_list:
        file_path = os.path.join(UPLOAD_DIR, f.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(f.file, buffer)
        saved_paths.append(file_path)
    background_tasks.add_task(process_documents_background, saved_paths, db)
    return {"status": "success", "message": f"成功接收 {len(file_list)} 个文件。"}

@app.get("/api/v1/records")
def get_historical_records(db: Session = Depends(get_db)):
    return db.query(models.EquipmentCostRecord).limit(100).all()

@app.get("/api/v1/forecast/{equipment_type}")
def get_equipment_forecast(equipment_type: str, db: Session = Depends(get_db)):
    forecast = db.query(models.ForecastResult).filter(models.ForecastResult.equipment_type == equipment_type).first()
    if forecast:
        return {"equipment": equipment_type, "data": forecast}
    return {"error": "未找到"}

# 将前端 Vue 编译后的 dist 目录挂载到根路径
app.mount("/", StaticFiles(directory="backend/static", html=True), name="static")
