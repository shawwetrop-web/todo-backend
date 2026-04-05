from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 内存数据库
users = []
todos = []

# 模型
class UserCreate(BaseModel):
    username: str
    password: str

class TodoCreate(BaseModel):
    content: str  # 改成前端传的 content，适配前端

# 从请求头获取 token
def get_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")
    if authorization.startswith("Bearer "):
        return authorization[7:]
    return authorization

# 接口
@app.post("/register")
def register(user: UserCreate):
    for u in users:
        if u["username"] == user.username:
            raise HTTPException(400, "用户名已存在")
    users.append({"username": user.username, "password": user.password})
    return {"msg": "注册成功"}

@app.post("/login")
def login(user: UserCreate):
    for u in users:
        if u["username"] == user.username and u["password"] == user.password:
            return {"access_token": user.username, "token_type": "bearer"}
    raise HTTPException(401, "账号或密码错误")

# ===================== 完全适配前端 =====================
@app.get("/todo/list")
def list_todos(authorization: str = Header(None)):
    username = get_token(authorization)
    user_todos = [t for t in todos if t["username"] == username]
    # 返回前端需要的字段：id, content, done
    return [{"id": t["id"], "content": t["content"], "done": t["done"]} for t in user_todos]

@app.post("/api/todo/add")  # 前端地址：/api/todo/add
def add_todo(todo: TodoCreate, authorization: str = Header(None)):
    username = get_token(authorization)
    todos.append({
        "id": len(todos)+1,
        "content": todo.content,
        "done": False,
        "username": username
    })
    return {"msg": "添加成功"}

@app.put("/api/todo/update/{id}")  # 前端地址：/api/todo/update/{id}
def update_status(id: int, authorization: str = Header(None)):
    username = get_token(authorization)
    for t in todos:
        if t["id"] == id and t["username"] == username:
            t["done"] = not t["done"]
    return {"msg": "状态更新成功"}

@app.delete("/api/todo/delete/{id}")  # 前端地址：/api/todo/delete/{id}
def delete_todo(id: int, authorization: str = Header(None)):
    username = get_token(authorization)
    global todos
    todos = [t for t in todos if not (t["id"] == id and t["username"] == username)]
    return {"msg": "删除成功"}