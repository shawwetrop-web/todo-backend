from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
# 新增：JWT相关导入
import jwt
from datetime import datetime, timedelta

app = FastAPI()

# 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===================== JWT 配置（核心新增） =====================
# 密钥：请替换为随机字符串（生产环境务必保密）
SECRET_KEY = "afasfzcv"
# 加密算法
ALGORITHM = "HS256"
# Token过期时间：30分钟（可改60、1440=24小时）
ACCESS_TOKEN_EXPIRE_MINUTES = 30
# ===============================================================

# ===================== 在这里填写你的 Railway MySQL 信息 =====================
MYSQL_HOST = "mysql.railway.internal"
MYSQL_PORT = "3306"
MYSQL_USER = "root"
MYSQL_PASSWORD = "cumWjIIMTeMlIcqFqYJXPxLxVdOhJiwm"
MYSQL_DATABASE = "railway"
# ===========================================================================

# MySQL 连接
DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 用户表
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    password = Column(String(100))

# 待办表
class Todo(Base):
    __tablename__ = "todos"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(String(255))
    done = Column(Boolean, default=False)
    username = Column(String(50))

# 创建表（第一次运行自动建表）
Base.metadata.create_all(bind=engine)

# 模型
class UserCreate(BaseModel):
    username: str
    password: str

class TodoCreate(BaseModel):
    content: str

# 获取数据库连接
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ===================== 新增：生成JWT临时Token函数 =====================
def create_access_token(username: str):
    # 过期时间
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # 生成JWT
    to_encode = {"sub": username, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# ===================== 改写：Token验证（校验JWT合法性+过期） =====================
def get_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录，请先登录")
    try:
        # 提取Token
        token = authorization.replace("Bearer ", "")
        # 解析并验证JWT
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Token无效")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token非法，拒绝访问")

# ===================== 接口 =====================
@app.post("/register")
def register(user: UserCreate, db=next(get_db())):
    existing = db.query(User).filter(User.username == user.username).first()
    if existing:
        raise HTTPException(400, "用户名已存在")
    new_user = User(username=user.username, password=user.password)
    db.add(new_user)
    db.commit()
    return {"msg": "注册成功"}

# ===================== 改写：登录返回JWT Token =====================
@app.post("/login")
def login(user: UserCreate, db=next(get_db())):
    u = db.query(User).filter(User.username == user.username, User.password == user.password).first()
    if not u:
        raise HTTPException(401, "账号或密码错误")
    # 生成临时JWT Token
    access_token = create_access_token(username=u.username)
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/todo/list")
def list_todos(authorization: str = Header(None), db=next(get_db())):
    username = get_token(authorization)
    todos = db.query(Todo).filter(Todo.username == username).all()
    return [{"id": t.id, "content": t.content, "done": t.done} for t in todos]

@app.post("/api/todo/add")
def add_todo(todo: TodoCreate, authorization: str = Header(None), db=next(get_db())):
    username = get_token(authorization)
    new_todo = Todo(content=todo.content, username=username)
    db.add(new_todo)
    db.commit()
    return {"msg": "添加成功"}

@app.put("/api/todo/update/{id}")
def update_status(id: int, authorization: str = Header(None), db=next(get_db())):
    username = get_token(authorization)
    todo = db.query(Todo).filter(Todo.id == id, Todo.username == username).first()
    if todo:
        todo.done = not todo.done
        db.commit()
    return {"msg": "状态更新成功"}

@app.delete("/api/todo/delete/{id}")
def delete_todo(id: int, authorization: str = Header(None), db=next(get_db())):
    username = get_token(authorization)
    todo = db.query(Todo).filter(Todo.id == id, Todo.username == username).first()
    if todo:
        db.delete(todo)
        db.commit()
    return {"msg": "删除成功"}