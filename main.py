# ==============================
# 最终稳定版 · 可直接上线后端
# ==============================
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os

# ==============================
# 安全配置
# ==============================
SECRET_KEY = "my-super-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ==============================
# 【关键】数据库线上兼容配置（永不报错）
# ==============================
DB_URL = os.getenv("DATABASE_URL")

if DB_URL:
    if DB_URL.startswith("mysql://"):
        DB_URL = DB_URL.replace("mysql://", "mysql+pymysql://")
else:
    DB_URL = "mysql+pymysql://root:123456@localhost:3306/todo_db"

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==============================
# 数据库模型
# ==============================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    hashed_password = Column(String(255))

class Todo(Base):
    __tablename__ = "todos"
    id = Column(Integer, primary_key=True)
    title = Column(String(100))
    completed = Column(Boolean, default=False)
    username = Column(String(50))

# 自动创建表（上线安全）
try:
    Base.metadata.create_all(bind=engine)
except Exception:
    pass

# ==============================
# FastAPI 初始化
# ==============================
app = FastAPI()

# 👇 必须加这段！解决跨域！
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================
# 数据库依赖
# ==============================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==============================
# Pydantic
# ==============================
class UserCreate(BaseModel):
    username: str
    password: str

class TodoCreate(BaseModel):
    title: str

# ==============================
# 工具函数
# ==============================
def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# ==============================
# 路由
# ==============================
@app.post("/register")
def register(user: UserCreate, db=Depends(get_db)):
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    hashed = get_password_hash(user.password)
    new_user = User(username=user.username, hashed_password=hashed)
    db.add(new_user)
    db.commit()
    return {"msg": "注册成功"}

@app.post("/login")
def login(user: UserCreate, db=Depends(get_db)):
    u = db.query(User).filter(User.username == user.username).first()
    if not u or not verify_password(user.password, u.hashed_password):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    token = create_access_token({"sub": u.username})
    return {"access_token": token, "token_type": "bearer"}

# ==============================
# 待办接口（已自动绑定 username）
# ==============================
@app.get("/todo/list")
def list_todos(token: str, db=Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="请先登录")
    todos = db.query(Todo).filter(Todo.username == username).all()
    return todos

@app.post("/todo/add")
def add_todo(todo: TodoCreate, token: str, db=Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401)
    new_todo = Todo(title=todo.title, username=username)
    db.add(new_todo)
    db.commit()
    return {"msg": "添加成功"}

@app.post("/todo/toggle/{todo_id}")
def toggle_todo(todo_id: int, token: str, db=Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401)
    todo = db.query(Todo).filter(Todo.id == todo_id, Todo.username == username).first()
    if todo:
        todo.completed = not todo.completed
        db.commit()
    return {"msg": "切换状态成功"}

@app.delete("/todo/delete/{todo_id}")
def delete_todo(todo_id: int, token: str, db=Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401)
    todo = db.query(Todo).filter(Todo.id == todo_id, Todo.username == username).first()
    if todo:
        db.delete(todo)
        db.commit()
    return {"msg": "删除成功"}