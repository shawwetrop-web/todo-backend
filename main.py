from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer

# ------------------------------
# 数据库 ORM 部分
# ------------------------------
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session


import os
DB_URL = os.getenv("DATABASE_URL")

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ------------------------------
# 表结构定义
# ------------------------------
class DBUser(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    hashed_password = Column(String(255))

class DBTodo(Base):
    __tablename__ = "todos"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(String(255))
    done = Column(Boolean, default=False)
    # 👇 新增：绑定用户名
    username = Column(String(50))

# 自动建表

Base.metadata.create_all(bind=engine)

# 数据库依赖
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ------------------------------
# 安全与登录
# ------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "my-super-secret-key"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ------------------------------
# 请求体模型
# ------------------------------
class TodoCreate(BaseModel):
    content: str

class UserCreate(BaseModel):
    username: str
    password: str

# ------------------------------
# 登录校验
# ------------------------------
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效凭证，请重新登录",
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return username
    except JWTError:
        raise credentials_exception

# ------------------------------
# 待办接口
# ------------------------------
@app.get("/todo/list")
def get_todo_list(
    username: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 👇 只查询当前用户的待办！
    todos = db.query(DBTodo).filter(DBTodo.username == username).all()
    return todos

@app.post("/api/todo/add")
def add_todo(
    todo: TodoCreate,
    username: str = Depends(get_current_user),  # 当前登录用户
    db: Session = Depends(get_db)
):
    # 👇 把 username 一起存进去
    new_todo = DBTodo(
        content=todo.content,
        done=False,
        username=username  # 关键
    )
    db.add(new_todo)
    db.commit()
    db.refresh(new_todo)
    return {"msg": "添加成功", "data": new_todo}
@app.delete("/api/todo/delete/{todo_id}")
def delete_todo(
    todo_id: int,
    username: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 修复：正确的多条件过滤
    todo = db.query(DBTodo).filter(
        DBTodo.id == todo_id,
        DBTodo.username == username
    ).first()

    if not todo:
        raise HTTPException(status_code=404, detail="待办不存在或无权操作")

    db.delete(todo)
    db.commit()
    return {"msg": "删除成功"}

@app.put("/api/todo/update/{todo_id}")
def update_todo(
    todo_id: int,
    username: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 修复：正确的多条件过滤
    todo = db.query(DBTodo).filter(
        DBTodo.id == todo_id,
        DBTodo.username == username
    ).first()

    if not todo:
        raise HTTPException(status_code=404, detail="待办不存在或无权操作")

    todo.done = not todo.done
    db.commit()
    return {"msg": "状态更新成功"}

# ------------------------------
# 注册 & 登录
# ------------------------------
@app.post("/register")
def register(
        user: UserCreate,
        db: Session = Depends(get_db)
):


    # 查询用户是否存在
    db_user = db.query(DBUser).filter(DBUser.username == user.username).first()


    if db_user:
        raise HTTPException(status_code=400, detail="用户名已存在")

    # ====================== 修复密码长度（关键！）
    password = user.password[:72]  # 自动截断到72位

    # 加密密码
    hashed_pw = pwd_context.hash(password)

    # 创建用户
    new_user = DBUser(username=user.username, hashed_password=hashed_pw)
    db.add(new_user)
    db.commit()

    return {"msg": "注册成功"}


@app.post("/login")
def login(
    user: UserCreate,
    db: Session = Depends(get_db)
):
    db_user = db.query(DBUser).filter(DBUser.username == user.username).first()
    if not db_user:
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    if not pwd_context.verify(user.password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    token = jwt.encode({"sub": user.username}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}