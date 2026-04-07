from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
# 新增：JWT相关导入
import jwt
from datetime import datetime, timedelta
import bcrypt
import os

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
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")

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
    hashed_password = Column(String(255))


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

REFRESH_TOKEN_EXPIRE_DAYS = 7

def create_refresh_token(username: str):
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"sub": username, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
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
def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")

    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")

        if not username:
            raise HTTPException(status_code=401, detail="Token无效")

        return username

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token非法")

# ===================== 接口 =====================
@app.post("/api/register")
def register(user: UserCreate, db=Depends(get_db)):
    existing = db.query(User).filter(User.username == user.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")
    hashed = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt())

    new_user = User(username=user.username, hashed_password=hashed.decode())
    db.add(new_user)
    db.commit()

    return {"msg": "注册成功"}

@app.post("/api/login")
def login(user: UserCreate, db=Depends(get_db)):
    u = db.query(User).filter(User.username == user.username).first()

    if not u or not bcrypt.checkpw(user.hashed_password.encode(), u.hashed_password.encode()):
        raise HTTPException(status_code=401, detail="账号或密码错误")

    access_token = create_access_token(username=u.username)
    refresh_token = create_refresh_token(username=u.username)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token
    }


@app.get("/api/todo/list")
def list_todos(
    username: str = Depends(get_current_user),
    db=Depends(get_db)
):
    todos = db.query(Todo).filter(Todo.username == username).all()

    return [
        {"id": t.id, "content": t.content, "done": t.done}
        for t in todos
    ]

@app.post("/api/todo/add")
def add_todo(
    todo: TodoCreate,
    username: str = Depends(get_current_user),
    db=Depends(get_db)
):
    new_todo = Todo(content=todo.content, username=username)
    db.add(new_todo)
    db.commit()

    return {"msg": "添加成功"}

@app.put("/api/todo/update/{id}")
def update_status(
    id: int,
    username: str = Depends(get_current_user),
    db=Depends(get_db)
):
    todo = db.query(Todo).filter(
        Todo.id == id,
        Todo.username == username
    ).first()

    if not todo:
        raise HTTPException(status_code=404, detail="Todo不存在")

    todo.done = not todo.done
    db.commit()

    return {"msg": "更新成功"}

@app.delete("/api/todo/delete/{id}")
def delete_todo(
    id: int,
    username: str = Depends(get_current_user),
    db=Depends(get_db)
):
    todo = db.query(Todo).filter(
        Todo.id == id,
        Todo.username == username
    ).first()

    if not todo:
        raise HTTPException(status_code=404, detail="Todo不存在")

    db.delete(todo)
    db.commit()

    return {"msg": "删除成功"}

@app.post("/api/refresh")
def refresh_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少refresh token")

    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")

        new_access_token = create_access_token(username=username)

        return {
            "access_token": new_access_token
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="refresh token过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="非法token")