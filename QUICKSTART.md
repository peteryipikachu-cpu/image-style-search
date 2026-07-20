# 🚀 快速启动指南

## 系统状态
✅ **状态**: 正常运行
✅ **服务地址**: http://localhost:5001
✅ **数据库**: PostgreSQL + pgvector (已配置)
✅ **CLIP模型**: 已加载
✅ **缓存图片**: 15张图片

## 快速启动

### 1. 启动服务（如果未运行）
```bash
cd /Users/pikachu/work/bodeng/yitusoutu
PORT=5001 python3 -m src.app
```

### 2. 访问系统
- **Web界面**: http://localhost:5001/
- **API测试**: http://localhost:5001/api/cases

### 3. 测试功能
```bash
# 测试所有API
python3 /Users/pikachu/work/bodeng/yitusoutu/test_api.py

# 查看所有案例
curl http://localhost:5001/api/cases

# 分析单个案例
curl http://localhost:5001/api/analyze/case_001 | python3 -m json.tool
```

## 功能说明

### 📊 分析Badcase
- 自动分析5个badcase案例
- 计算原图、参考图、结果图之间的相似度
- 评估风格匹配度

### 🔍 推荐参考图
- 根据结果图和目标风格推荐最佳参考图
- 考虑内容相似度和风格匹配度

### 🎨 相似度分析
- 原图 vs 参考图
- 原图 vs 结果图
- 参考图 vs 结果图
- 风格 vs 参考图
- 风格 vs 结果图

## 查看分析结果

### Web界面
1. 打开浏览器访问: http://localhost:5001/
2. 点击"开始分析"按钮
3. 查看所有案例卡片
4. 点击案例查看详细分析

### API调用
```python
import requests

# 获取所有分析结果
results = requests.get('http://localhost:5001/api/analyze').json()

# 获取单个案例分析
case = requests.get('http://localhost:5001/api/analyze/case_001').json()

# 查看推荐参考图
print(case['suggested_references'])
```

## 项目结构
```
/Users/pikachu/work/bodeng/yitusoutu/
├── src/
│   ├── app.py              # Flask应用
│   ├── style_matcher.py    # 风格匹配算法
│   ├── feature_extractor.py # CLIP特征提取
│   └── database.py         # 数据库操作
├── static/
│   └── index.html         # Web界面
├── scripts/
│   └── init_db.py         # 数据库初始化
└── test_api.py            # API测试脚本
```

## 下一步
- ✅ 系统已正常运行
- ✅ Web界面可访问
- ✅ API功能正常
- 🎯 可以开始使用系统分析badcase数据

## 遇到问题？

### 检查服务状态
```bash
lsof -i :5001
```

### 重启服务
```bash
lsof -ti:5001 | xargs kill -9
cd /Users/pikachu/work/bodeng/yitusoutu
PORT=5001 python3 -m src.app
```

### 运行测试
```bash
python3 /Users/pikachu/work/bodeng/yitusoutu/test_api.py
```
