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

# ============================
# 1. 先开 CORS（必须最先）
# ============================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================
# 2. 安全配置
# ============================
SECRET_KEY = "my-super-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ============================
# 3. 数据库（线上自动适配）
# ============================
DB_URL = os.getenv("DATABASE_URL")

if DB_URL:
    if DB_URL.startswith("mysql://"):
        DB_URL = DB_URL.replace("mysql://", "mysql+pymysql://")
else:
    DB_URL = "mysql+pymysql://root:123456@localhost:3306/todo_db"

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ============================
# 4. 模型
# ============================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True)
    hashed_password = Column(String(255))

class Todo(Base):
    __tablename__ = "todos"
    id = Column(Integer, primary_key=True)
    title = Column(String(100))
    completed = Column(Boolean, default=False)
    username = Column(String(50))

try:
    Base.metadata.create_all(bind=engine)
except:
    pass

# ============================
# 5. 工具
# ============================
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

class UserCreate(BaseModel):
    username: str
    password: str

class TodoCreate(BaseModel):
    title: str

def hash_pw(pw): return pwd_context.hash(pw)
def verify_pw(pw, hashed): return pwd_context.verify(pw, hashed)

def create_token(data: dict):
    exp = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    data.update({"exp": exp})
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

# ============================
# 6. 接口
# ============================
@app.post("/register")
def register(user: UserCreate, db=Depends(get_db)):
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(400, "用户名已存在")
    new_user = User(username=user.username, hashed_password=hash_pw(user.password))
    db.add(new_user)
    db.commit()
    return {"msg": "注册成功"}

@app.post("/login")
def login(user: UserCreate, db=Depends(get_db)):
    u = db.query(User).filter(User.username == user.username).first()
    if not u or not verify_pw(user.password, u.hashed_password):
        raise HTTPException(401, "账号或密码错误")
    return {"access_token": create_token({"sub": u.username})}

@app.get("/todo/list")
def list_todos(token: str, db=Depends(get_db)):
    try:
        user = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["sub"]
    except:
        raise HTTPException(401)
    return db.query(Todo).filter(Todo.username == user).all()

@app.post("/todo/add")
def add(todo: TodoCreate, token: str, db=Depends(get_db)):
    try: user = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["sub"]
    except: raise HTTPException(401)
    db.add(Todo(title=todo.title, username=user))
    db.commit()
    return {"msg": "ok"}

@app.post("/todo/toggle/{id}")
def toggle(id: int, token: str, db=Depends(get_db)):
    try: user = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["sub"]
    except: raise HTTPException(401)
    t = db.query(Todo).filter(Todo.id==id, Todo.username==user).first()
    if t: t.completed = not t.completed; db.commit()
    return {"msg":"ok"}

@app.delete("/todo/delete/{id}")
def delete(id: int, token: str, db=Depends(get_db)):
    try: user = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["sub"]
    except: raise HTTPException(401)
    t = db.query(Todo).filter(Todo.id==id, Todo.username==user).first()
    if t: db.delete(t); db.commit()
    return {"msg":"ok"}