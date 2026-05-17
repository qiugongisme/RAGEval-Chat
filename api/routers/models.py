import json
import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config import config

router = APIRouter()

MODELS_FILE = os.path.join(config.DATA_DIR, "models.json")


def _read_models() -> list:
    with open(MODELS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_models(models: list):
    with open(MODELS_FILE, "w", encoding="utf-8") as f:
        json.dump(models, f, ensure_ascii=False, indent=2)


class ModelCreate(BaseModel):
    name: str = Field(..., description="模型显示名称")
    provider: str = Field(..., description="模型提供商，如 deepseek, qwen")
    api_key: str = Field(default="", description="API 密钥")
    model_name: str = Field(..., description="API 调用的模型标识")
    temperature: float = Field(default=0.7, ge=0, le=2, description="温度参数")
    max_tokens: int = Field(default=2048, ge=1, description="最大 Token 数")


class ModelUpdate(BaseModel):
    name: Optional[str] = Field(None, description="模型显示名称")
    provider: Optional[str] = Field(None, description="模型提供商")
    api_key: Optional[str] = Field(None, description="API 密钥")
    model_name: Optional[str] = Field(None, description="API 调用的模型标识")
    temperature: Optional[float] = Field(None, ge=0, le=2, description="温度参数")
    max_tokens: Optional[int] = Field(None, ge=1, description="最大 Token 数")


class ModelResponse(BaseModel):
    id: str
    name: str
    provider: str
    api_key: str
    model_name: str
    temperature: float
    max_tokens: int


@router.get("", response_model=List[ModelResponse])
async def list_models():
    """获取所有模型配置列表"""
    return _read_models()


@router.post("", response_model=ModelResponse, status_code=201)
async def create_model(model: ModelCreate):
    """新增模型配置"""
    models = _read_models()

    new_model = model.model_dump()
    new_model["id"] = f"model_{uuid.uuid4().hex[:8]}"
    models.append(new_model)
    _write_models(models)
    return new_model


@router.put("/{model_id}", response_model=ModelResponse)
async def update_model(model_id: str, model: ModelUpdate):
    """更新模型配置"""
    models = _read_models()
    for m in models:
        if m["id"] == model_id:
            update_data = model.model_dump(exclude_unset=True)
            m.update(update_data)
            _write_models(models)
            return m
    raise HTTPException(status_code=404, detail=f"模型 {model_id} 不存在")


@router.delete("/{model_id}", status_code=204)
async def delete_model(model_id: str):
    """删除模型配置"""
    models = _read_models()
    filtered = [m for m in models if m["id"] != model_id]
    if len(filtered) == len(models):
        raise HTTPException(status_code=404, detail=f"模型 {model_id} 不存在")
    _write_models(filtered)
