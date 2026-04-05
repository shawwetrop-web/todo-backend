from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

app = FastAPI()

# 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===================== 在这里填写你的 Railway MySQL 信息 =====================
MYSQL_HOST = "这里填 Host"
MYSQL_PORT = "这里填 Port"
MYSQL_USER = "这里填 User"
MYSQL_PASSWORD = "这里填 Password"
MYSQL_DATABASE = "这里填 Database"
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

# token 验证
def get_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")
    return authorization.replace("Bearer ", "")

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

@app.post("/login")
def login(user: UserCreate, db=next(get_db())):
    u = db.query(User).filter(User.username == user.username, User.password == user.password).first()
    if not u:
        raise HTTPException(401, "账号或密码错误")
    return {"access_token": u.username, "token_type": "bearer"}

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